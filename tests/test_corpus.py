import hashlib
import json
import sqlite3
from datetime import date

import pytest
from fastapi.testclient import TestClient
from tm_law.api import create_app
from tm_law.corpus import corpus_warnings, coverage, draft_sections, load_package, original_text
from tm_law.runtime import MockRuntime
from tm_law.schemas import LegalVersion
from tm_law.store import SCHEMA, SCHEMA_VERSION, Store

TEXT = "Čl. 1\n(1) Ilustračné pravidlo pre test.\n(2) Ďalší odsek.\n"


def write_package(tmp_path, raw=TEXT.encode()):
    path = tmp_path / "test.json"
    (tmp_path / "original.txt").write_bytes(raw)
    package = {
        "schema_version": 1,
        "original_file": "original.txt",
        "version": {
            "version_id": "synthetic-package",
            "title": "Fiktívne pravidlo",
            "kind": "predpis",
            "authority": "Test",
            "law_number": 9999,
            "law_year": 2099,
            "acquired_on": "2026-11-18",
            "acquired_at": "2026-11-18T12:34:56+01:00",
            "effective_from": "2024-01-01",
            "effective_until": "2025-01-01",
            "effective_basis": "Ilustračný interval pre test.",
            "provenance": "Umelý testovací súbor.",
            "reuse_terms": "MIT",
            "fictional": True,
            "original_sha256": hashlib.sha256(raw).hexdigest(),
            "passages": draft_sections(TEXT),
        },
    }
    path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
    return path, package


def test_article_heading_accepts_full_word():
    drafted = draft_sections("Článok 1\n(1) Prvé pravidlo.\n")
    assert drafted == [
        {
            "source_id": "s-cl-1-o-1",
            "section": "cl-1",
            "paragraph": "1",
            "text": "Prvé pravidlo.",
        }
    ]
    assert draft_sections("Čl. 1\n(1) Prvé pravidlo.\n") == drafted


def test_archive_package_date_filter_and_coverage(tmp_path):
    path, package = write_package(tmp_path)
    package["version"]["passages"][0]["norm_status"] = "transitional"
    path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
    version, original = load_package(path)
    store = Store(tmp_path / "data")
    store.initialize()
    digest, created = store.import_version(version, original)
    assert created
    assert store.import_version(version, original) == (digest, False)
    hits = store.search("9999/2099 Čl. 1 ods. 1", as_of=date(2024, 12, 31))
    assert [hit["text"] for hit in hits] == ["Ilustračné pravidlo pre test."]
    assert hits[0]["norm_status"] == "transitional"
    with TestClient(
        create_app(store.directory, MockRuntime()), base_url="http://127.0.0.1"
    ) as client:
        result = client.post(
            "/api/chat",
            json={
                "question": "Aké pravidlo sa tu použije?",
                "query": "9999/2099 Čl. 1 ods. 1",
                "as_of": "2024-12-31",
            },
        )
    final = json.loads(result.text.splitlines()[-1])
    assert final["type"] == "done"
    assert any("prechodné ustanovenie" in note for note in final["notes"])
    assert not store.search("9999/2099 Čl. 1", as_of=date(2025, 1, 1))
    assert store.get_legal_original(version.original_sha256) == TEXT.encode()
    summary = coverage(store)
    assert summary["nonfictional_documents"] == 0
    assert summary["version_counts"] == {"archive_verified": 0, "metadata_only": 0, "fictional": 1}
    assert {row["law_number"] for row in summary["missing_priority_acts"]} == {40, 300, 301, 160}
    assert summary["overlapping_versions"] == []
    with sqlite3.connect(store.legal) as conn:
        assert conn.execute("SELECT count(*) FROM legal_original").fetchone()[0] == 1


def test_priority_gaps_and_overlapping_intervals(tmp_path):
    store = Store(tmp_path / "data")
    store.initialize()

    def wording(version_id, number, year, start, end, fictional=False):
        return LegalVersion.model_validate(
            {
                "version_id": version_id,
                "title": "Skúšobné znenie",
                "kind": "predpis",
                "law_number": number,
                "law_year": year,
                "authority": "Test",
                "source_url": None if fictional else "https://example.invalid/act",
                "acquired_on": "2026-01-01",
                "effective_from": start,
                "effective_until": end,
                "effective_basis": "Skúšobný interval bez právneho textu.",
                "provenance": "Umelé metadáta, nie text predpisu.",
                "reuse_terms": "Test.",
                "fictional": fictional,
                "passages": [{"source_id": "p1", "section": "1", "text": "Umelý úsek."}],
            }
        )

    store.import_version(wording("civil-a", 40, 1964, "2020-01-01", "2022-01-01"))
    store.import_version(wording("civil-b", 40, 1964, "2021-06-01", "2023-01-01"))
    store.import_version(wording("family-fake", 36, 2005, "2020-01-01", "2021-01-01", True))
    report = coverage(store)
    assert all(item["law_number"] != 40 for item in report["missing_priority_acts"])
    assert {300, 301, 160} <= {item["law_number"] for item in report["missing_priority_acts"]}
    assert report["overlapping_versions"] == [
        {"law_number": 40, "law_year": 1964, "versions": ["civil-a", "civil-b"]}
    ]
    assert report["coverage_ends"] == [
        {"law_number": 40, "law_year": 1964, "coverage_until_exclusive": "2023-01-01"}
    ]
    empty = corpus_warnings([])
    assert len(empty["missing_priority_acts"]) == 4
    assert empty["overlapping_versions"] == []


def test_evidence_check_rejects_fake_passages_and_wrong_source_hash(tmp_path):
    path, package = write_package(tmp_path)
    (tmp_path / "original.txt").write_text("Altered.", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        load_package(path)
    (tmp_path / "original.txt").write_bytes(TEXT.encode("utf-8"))
    package["version"]["passages"][0]["text"] = "Text, ktorý v origináli nie je."
    path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="nenašiel v origináli"):
        load_package(path)
    html = b"<p>Visible</p><script>internal</script><p>containing &amp; text</p>"
    assert original_text(html, ".html").strip().split() == ["Visible", "containing", "&", "text"]


def test_legacy_schema_upgrade_preserves_content_hash(tmp_path):
    _, package = write_package(tmp_path)
    model = LegalVersion.model_validate(package["version"])
    old_data = model.model_dump(mode="json")
    for key in (
        "acquired_at",
        "effective_basis",
        "valid_from",
        "valid_until",
        "decision_type",
        "publication_status",
        "cited_legislation",
    ):
        del old_data[key]
    for p in old_data["passages"]:
        del p["norm_status"]
    digest = hashlib.sha256(
        json.dumps(old_data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    passages = old_data.pop("passages")
    store = Store(tmp_path)
    with sqlite3.connect(store.legal) as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA user_version=1")
        conn.execute(
            "INSERT INTO legal_version VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                model.version_id,
                model.title,
                model.kind,
                model.law_number,
                model.law_year,
                old_data["effective_from"],
                old_data["effective_until"],
                0,
                None,
                digest,
                json.dumps(old_data),
            ),
        )
        for passage in passages:
            conn.execute(
                "INSERT INTO passage(version_id, source_id, section, paragraph, text) VALUES (?,?,?,?,?)",
                (
                    model.version_id,
                    passage["source_id"],
                    passage["section"],
                    passage["paragraph"],
                    passage["text"],
                ),
            )
    store.initialize()
    assert store.import_version(
        LegalVersion.model_validate({**old_data, "passages": passages})
    ) == (
        digest,
        False,
    )
    assert len(store.search("9999/2099 Čl. 1")) == 2
    with sqlite3.connect(store.legal) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_case_number_and_decision_date(tmp_path):
    path, package = write_package(tmp_path)
    package["version"].update(
        kind="rozhodnutie",
        law_year=None,
        law_number=None,
        case_number="3 Test 1/2024",
        decision_type="Fiktívny rozsudok",
        decision_date="2024-10-01",
        publication_status="anonymized",
        cited_legislation=["Fiktívne pravidlo"],
    )
    path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
    version, original = load_package(path)
    store = Store(tmp_path / "data")
    store.initialize()
    store.import_version(version, original)
    assert not store.search("", case_number="3 Test 1/2024", as_of=date(2024, 9, 30))
    hits = store.search("", case_number="3 test1/2024", as_of=date(2024, 10, 1))
    assert len(hits) == 2 and hits[0]["original_archived"]
    assert hits[0]["publication_status"] == "anonymized"
