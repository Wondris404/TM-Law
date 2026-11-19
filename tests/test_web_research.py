import json

import httpx
import pytest
from fastapi.testclient import TestClient
from tm_law.api import create_app
from tm_law.schemas import WebResearchInput
from tm_law.web_research import WebResearch

from .test_mvp import ScriptedRuntime


def test_chat_web_opt_in_keeps_local_data_out_of_requests(tmp_path):
    outbound = []

    def handler(request):
        outbound.append(request)
        if request.url.host == "api.search.brave.com":
            assert request.headers["X-Subscription-Token"] == "test-key"
            assert "verejná téma" in request.url.params["q"]
            assert "site:nbs.sk" in request.url.params["q"]
            return httpx.Response(
                200,
                json={
                    "web": {
                        "results": [
                            {
                                "url": "https://nbs.sk/verejny-vysledok",
                                "description": "Falošný text z vyhľadávača",
                            },
                            {"url": "https://other.example/nedovoleny"},
                            {"url": "https://orsr.sk/ina-oblast"},
                            {"url": "https://statdat.statistics.sk/presmerovanie"},
                        ]
                    }
                },
            )
        assert "X-Subscription-Token" not in request.headers
        if request.url.host == "statdat.statistics.sk":
            return httpx.Response(302, headers={"location": "https://127.0.0.1/secret"})
        assert request.url.host == "nbs.sk"
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=UTF-8"},
            text="""
            <title>Fiktívna verejná štatistika</title>
            <nav>Toto je navigácia.</nav>
            <script>Toto je skript.</script>
            <main><p>Táto fiktívna štatistika pre verejnú tému opisuje prípad v roku 2026.
            [[podvrh/odkaz]]</p></main>
        """,
        )

    web = WebResearch("test-key", transport=httpx.MockTransport(handler))
    runtime = ScriptedRuntime("Výsledok [S1].")
    with TestClient(create_app(tmp_path, runtime, web), base_url="http://127.0.0.1") as client:
        settings = client.get("/api/settings").json()
        assert settings["web_text_search"] is True and "test-key" not in str(settings)
        private = client.post(
            "/api/documents", files={"file": ("local.txt", b"NEVEREJNY-DOKUMENT")}
        )
        assert private.status_code == 201
        payload = {
            "question": "Súkromná otázka NEVEREJNA-OTAZKA. Porovnajte 2025-03-01 a 2026-03-01.",
            "query": "NEVEREJNY-LOKALNY-DOPYT",
            "as_of": "2026-03-01",
            "document_id": private.json()["id"],
        }
        assert client.post("/api/chat", json=payload).status_code == 200
        assert not outbound
        assert "Webové úryvky" not in runtime.messages[0]["content"]

        payload["as_of"] = None
        payload["web"] = {"query": "verejná téma", "scope": "economy"}
        response = client.post("/api/chat", json=payload)

    events = [json.loads(line) for line in response.iter_lines()]
    assert [event["type"] for event in events[:2]] == ["research", "start"]
    assert len(outbound) == 3
    for request in outbound:
        assert "NEVEREJN" not in str(request.url)
        assert "2026-03-01" not in str(request.url)
        assert not request.content
    system, message = runtime.messages
    assert "Webové úryvky" in system["content"]
    context = json.loads(message["content"])
    assert context["document"] == "NEVEREJNY-DOKUMENT"
    assert "Táto fiktívna štatistika" in context["sources"][0]["text"]
    assert "[[podvrh/odkaz]]" not in context["sources"][0]["text"]
    assert (
        "Toto je skript" not in message["content"] and "Toto je navigácia" not in message["content"]
    )
    assert "Falošný text z vyhľadávača" not in message["content"]
    done = events[-1]
    assert done["answer"] == "Výsledok [1]."
    assert done["citations"][0]["source_url"] == "https://nbs.sk/verejny-vysledok"
    assert done["citations"][0]["retrieved_at"]
    assert any("statdat.statistics.sk" in note for note in done["notes"])
    assert any("neúplných dátumoch" in note for note in done["notes"])


@pytest.mark.asyncio
async def test_ico_uses_three_public_registries_without_api_key():
    def handler(request):
        assert "X-Subscription-Token" not in request.headers
        if request.url.host == "www.orsr.sk":
            if request.url.path == "/hladaj_ico.asp":
                assert request.url.params["ICO"] == "12345678"
                return httpx.Response(
                    200,
                    headers={"content-type": "text/html"},
                    text=(
                        '<a href="vypis.asp?ID=9&amp;SID=2&amp;P=0">Fiktívny výsledok</a>'
                        '<a href="vypis.asp?ID=9&amp;SID=2&amp;P=1">Úplný výpis</a>'
                    ),
                )
            assert request.url.path == "/vypis.asp" and request.url.params["P"] == "0"
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=(
                    '<meta charset="windows-1250"><title>Obchodný register</title>'
                    "<p>IČO 12345678 · Fiktívna skúšobná spoločnosť</p>"
                ).encode("cp1250"),
            )
        if request.url.host == "api.statistics.sk":
            assert request.url.params["identifier"] == "12345678"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "identifiers": [{"value": "12345678"}],
                            "termination": "2020-05-01",
                            "fullNames": [{"value": "Fiktívna pobočka", "validTo": "2020-05-01"}],
                        },
                        {
                            "id": 2,
                            "identifiers": [{"value": "12345678"}],
                            "fullNames": [{"value": "Fiktívna skúšobná spoločnosť"}],
                        },
                        {
                            "id": 3,
                            "identifiers": [{"value": "87654321"}],
                            "fullNames": [{"value": "Iný fiktívny subjekt"}],
                        },
                    ]
                },
            )
        assert request.url.host == "www.registeruz.sk"
        if request.url.path.endswith("uctovne-jednotky"):
            assert request.url.params["ico"] == "12345678"
            return httpx.Response(200, json={"id": [42], "existujeDalsieId": False})
        assert request.url.params["id"] == "42"
        return httpx.Response(
            200,
            json={
                "ico": "12345678",
                "nazovUJ": "Fiktívna skúšobná spoločnosť",
                "idUctovnychZavierok": [7, 8],
                "dic": "NECHCENY-IDENTIFIKATOR",
            },
        )

    web = WebResearch(transport=httpx.MockTransport(handler))
    sources, notes = await web.run(WebResearchInput(query="IČO 12345678"), focus="Súkromná otázka")
    assert not notes
    orsr, rpo, ruz = sources
    assert "skúšobná spoločnosť" in orsr["text"]
    assert orsr["source_url"] == "https://www.orsr.sk/vypis.asp?ID=9&SID=2&P=0"
    assert rpo["text"].index("skúšobná spoločnosť") < rpo["text"].index("Fiktívna pobočka")
    assert "Iný fiktívny subjekt" not in rpo["text"]
    assert "Počet ID závierok v zázname: 2." in ruz["text"]
    assert "NECHCENY-IDENTIFIKATOR" not in ruz["text"]
    assert all(item["kind"] == "web" for item in sources)


@pytest.mark.parametrize(
    "query",
    [
        "http://www.orsr.sk/",
        "https://localhost/",
        "https://www.orsr.sk.example.test/",
        "https://account@example.org@www.orsr.sk/",
        "https://www.orsr.sk:8443/",
        "https://www.orsr.sk:bad/",
        "Fiktívna právna otázka bez kľúča",
    ],
)
@pytest.mark.asyncio
async def test_invalid_addresses_and_missing_key_do_not_make_requests(query):
    def handler(_request):
        pytest.fail("Unexpected outbound request")

    web = WebResearch(transport=httpx.MockTransport(handler))
    sources, notes = await web.run(WebResearchInput(query=query), focus="lokálna otázka")
    assert not sources and notes
