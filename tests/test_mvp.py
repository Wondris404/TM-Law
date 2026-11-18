import json
import sqlite3
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from tm_law.api import create_app
from tm_law.rag import validate_citations
from tm_law.runtime import MockRuntime

ROOT = Path(__file__).resolve().parents[1]


def fixture(year):
    return json.loads((ROOT / "data" / f"demo-{year}.json").read_text(encoding="utf-8"))


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path, MockRuntime()), base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").json()["simulated"] is True
        for year in (2022, 2024):
            assert client.post("/api/legal/import", json=fixture(year)).status_code == 201
        yield client


def test_search_filters_history_and_content(client):
    query = {"q": "9999/2099 § 7 evidencia", "kind": "predpis"}
    older = client.get("/api/search", params={**query, "as_of": "2023-12-31"}).json()
    assert older["hits"][0]["citation_id"] == "demo-2022/p7-1"
    assert "dva roky" in older["hits"][0]["text"]
    newer = client.get("/api/search", params={**query, "as_of": "2024-01-01"}).json()
    assert newer["hits"][0]["citation_id"] == "demo-2024/p7-1"
    assert "tri roky" in newer["hits"][0]["text"]
    absent = client.get("/api/search", params={**query, "as_of": "2021-01-01"}).json()
    assert not absent["hits"] and "nenašlo" in absent["note"]
    assert client.get("/api/search", params={**query, "kind": "rozhodnutie"}).json()["hits"] == []
    assert (
        client.get("/api/search", params={"q": '"suciastky" OR *'}).json()["hits"][0]["source_id"]
        == "p7-2"
    )


def test_import_is_atomic_versioned_and_idempotent(client, tmp_path):
    version = fixture(2022)
    same = client.post("/api/legal/import", json=version)
    assert same.status_code == 200 and not same.json()["created"]
    version["passages"][0]["text"] = "Changed"
    assert client.post("/api/legal/import", json=version).status_code == 409
    assert (
        "dva roky"
        in client.get("/api/search", params={"q": "evidencia"}).json()["hits"][-2]["text"]
    )
    version["passages"].append(version["passages"][0])
    assert client.post("/api/legal/import", json=version).status_code == 422
    with sqlite3.connect(tmp_path / "legal.sqlite3") as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT count(*) FROM passage_fts").fetchone()[0] == 3


def test_unknown_effective_end_is_excluded(client):
    data = fixture(2022)
    data.update(version_id="unknown-end", effective_until=None, title="Neznáma platnosť")
    assert client.post("/api/legal/import", json=data).status_code == 201
    hits = client.get("/api/search", params={"q": "9999/2099", "as_of": "2023-01-01"}).json()[
        "hits"
    ]
    assert {hit["version_id"] for hit in hits} == {"demo-2022"}


def test_streamed_answer_and_validated_citations(client):
    response = client.post(
        "/api/chat",
        json={
            "question": "Evidencia k 2022-12-31",
            "query": "9999/2099 § 7",
        },
    )
    events = [json.loads(line) for line in response.iter_lines()]
    assert response.headers["content-type"] == "application/x-ndjson"
    assert events[0]["simulated"] is True
    assert any(event["type"] == "delta" for event in events)
    result = events[-1]
    assert result["type"] == "done"
    assert result["citations"][0]["citation_id"] == "demo-2022/p7-1"
    assert "[1]" in result["answer"]
    cleaned, valid, rejected = validate_citations(
        "Cite [[fake/1]] and [[demo-2022/p7-1]] twice [[demo-2022/p7-1]].", result["citations"]
    )
    assert cleaned == "Cite [neoverený odkaz] and [1] twice [1]."
    assert len(valid) == 1 and rejected == ["fake/1"]
    assert validate_citations("Raw citation [1]", result["citations"])[0] == (
        "Raw citation [neoverený odkaz]"
    )
    result = client.post("/api/chat", json={"question": "Čo platilo v roku 2022?"})
    assert json.loads(result.text)["type"] == "error"


def test_chat_citations_only_show_context_and_exclude_repealed_passages(client):
    version = fixture(2024)
    version["version_id"] = "demo-citation-context"
    text = "Riadok s právne významnou informáciou. " * 40 + "SKUTOČNÝ KONIEC."
    version["passages"][0]["text"] = text
    version["passages"][0]["section"] = "40"
    version["passages"].append(
        version["passages"][0] | {"source_id": "p41", "section": "41", "norm_status": "repealed"}
    )
    assert client.post("/api/legal/import", json=version).status_code == 201

    def chat(section):
        response = client.post(
            "/api/chat",
            json={
                "question": "Ktorý podklad sa zachoval?",
                "query": f"9999/2099 § {section}",
                "as_of": "2024-01-01",
            },
        )
        return json.loads(response.text.splitlines()[-1])

    result = chat(40)
    assert result["citations"][0]["text"] == text[:1300]
    assert result["citations"][0]["context_truncated"] is True
    search = client.get("/api/search", params={"q": "9999/2099 § 40"}).json()
    assert search["hits"][0]["text"] == text

    repealed = chat(41)
    assert repealed["retrieved_ids"]
    assert not repealed["context_ids"] and not repealed["citations"]
    assert repealed["evidence_status"] == "insufficient"
    assert any("Zrušené ustanovenia" in note for note in repealed["notes"])


def test_document_upload_query_deletion_and_isolation(client, tmp_path):
    response = client.post("/api/documents", files={"file": ("../../moje.txt", b"Tajny spis")})
    assert response.status_code == 201 and response.json()["name"] == "moje.txt"
    document_id = response.json()["id"]
    result = client.post("/api/chat", json={"question": "Tajny spis", "document_id": document_id})
    assert "vybraný súkromný dokument" in json.loads(result.text.splitlines()[-1])["answer"]
    assert client.get("/api/search", params={"q": "Tajny spis"}).json()["hits"] == []
    assert not (tmp_path / "moje.txt").exists()
    assert client.delete(f"/api/documents/{document_id}").status_code == 200
    result = client.post("/api/chat", json={"question": "Tajny spis", "document_id": document_id})
    assert result.status_code == 404


def test_pdf_text_layer_and_docx(client):
    pdf = PdfWriter()
    page = pdf.add_blank_page(width=200, height=200)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    ),
                }
            ),
        }
    )
    body = DecodedStreamObject()
    body.set_data(b"BT /F1 12 Tf 10 10 Td (Sample legal document) Tj ET")
    page[NameObject("/Contents")] = body
    stream = BytesIO()
    pdf.write(stream)
    assert (
        client.post("/api/documents", files={"file": ("word.pdf", stream.getvalue())}).status_code
        == 201
    )

    docx = BytesIO()
    with ZipFile(docx, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>Text zmluvy</w:t></w:r></w:p></w:body>
            </w:document>
        """,
        )
    assert (
        client.post("/api/documents", files={"file": ("word.docx", docx.getvalue())}).status_code
        == 201
    )


def test_invalid_upload_guard_and_rebinding(client):
    assert (
        client.post(
            "/api/documents", files={"file": ("broken.pdf", b"%PDF-not-a-file")}
        ).status_code
        == 422
    )
    assert client.post("/api/documents", files={"file": ("bad.exe", b"123")}).status_code == 415
    assert client.post("/api/documents", files={"file": ("bad.txt", b"\xff")}).status_code == 422
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    stream = BytesIO()
    pdf.write(stream)
    result = client.post("/api/documents", files={"file": ("scan.pdf", stream.getvalue())})
    assert result.status_code == 422 and "OCR" in result.json()["detail"]
    assert client.get("/api/documents", headers={"Host": "remote.example"}).status_code == 403
    assert (
        client.post(
            "/api/legal/import",
            json=fixture(2022),
            headers={
                "Origin": "https://remote.example",
            },
        ).status_code
        == 403
    )


def test_historical_overlap_and_insufficient_evidence(client):
    competing = fixture(2024)
    competing.update(version_id="overlap", effective_from="2023-01-01")
    assert client.post("/api/legal/import", json=competing).status_code == 201
    question = {"question": "Evidencia dielne k danému dátumu.", "query": "9999/2099 § 7 evidencia"}
    early = client.post("/api/chat", json={**question, "as_of": "2021-01-01"})
    no_evidence = json.loads(early.text.splitlines()[-1])
    assert no_evidence["evidence_status"] == "insufficient"
    assert no_evidence["retrieved_ids"] == no_evidence["verified_ids"] == []
    response = client.post("/api/chat", json={**question, "as_of": "2023-06-01"})
    result = json.loads(response.text.splitlines()[-1])
    assert result["evidence_status"] == "version_conflict"
    assert set(result["version_conflicts"][0]) == {"demo-2022/p7-1", "overlap/p7-1"}
    assert set(result["context_ids"]) <= set(result["retrieved_ids"])
    assert result["verified_ids"] == [result["citations"][0]["citation_id"]]
