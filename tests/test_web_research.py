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


def test_general_research_digs_into_uncovered_topics_and_cites_indexed_sources(tmp_path):
    public_query = "Tepelné čerpadlá v zime; porovnanie prevádzkových nákladov"
    lookups = []
    field_study = "https://laboratory.example.org/field-study"
    independent = "https://university.example.net/costs"
    reply = "https://manufacturer.example.com/winter"
    duplicate = "https://publisher.example.com/syndicated"
    winter = (
        "Fiktívne tepelné čerpadlá v zime pracovali pri testovanej teplote do mínus 12 stupňov."
    )

    def handler(request):
        assert request.url.host == "api.search.brave.com"
        assert request.url.path == "/res/v1/llm/context"
        assert request.headers["X-Subscription-Token"] == "test-key"
        query = request.url.params["q"]
        assert "SUKROMNY" not in query
        assert "site:" not in query
        lookups.append(query)
        if query == public_query:
            results = [
                {"url": field_study, "title": "Fiktívny test", "snippets": [winter]},
                {"url": duplicate, "title": "Kópia", "snippets": [winter]},
                {"url": "https://127.0.0.1/sukromne", "snippets": [winter + " interný obsah."]},
                {"url": "https://router.internal/secret", "snippets": [winter + " interný údaj."]},
            ]
        elif query.startswith("porovnanie"):
            results = [
                {
                    "url": independent,
                    "title": "Fiktívna štúdia nákladov",
                    "snippets": [
                        "Porovnanie prevádzkových nákladov používa rovnaké ceny elektriny a obdobia."
                    ],
                }
            ]
        else:
            results = [
                {
                    "url": reply,
                    "title": "Fiktívny druhý zimný test",
                    "snippets": [
                        "Tepelné čerpadlá v zime mali podľa druhej skúšky odlišný prah odmrazovania."
                    ],
                }
            ]
        return httpx.Response(
            200,
            json={
                "grounding": {"generic": results},
                "sources": {field_study: {"fetched_content_timestamp": 1700000000}},
            },
        )

    runtime = ScriptedRuntime("Testovací záver [S1]. Porovnanie [S2]. Ďalší podklad [S3].")
    research = WebResearch("test-key", httpx.MockTransport(handler))
    with TestClient(create_app(tmp_path, runtime, research), base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/chat",
            json={
                "question": "SUKROMNY pracovný kontext. Porovnaj prevádzkové náklady.",
                "web": {"query": public_query, "scope": "general"},
            },
        )
    assert lookups == [public_query, "porovnanie prevádzkových nákladov", "Tepelné čerpadlá v zime"]
    done = json.loads(response.text.splitlines()[-1])
    assert done["type"] == "done"
    assert [item["source_url"] for item in done["citations"]] == [field_study, independent, reply]
    assert all(item["web_reader"] == "brave_index" for item in done["citations"])
    assert done["citations"][0]["indexed_at"] == "2023-11-14T22:13:20+00:00"
    assert any("dopyty 3" in note for note in done["notes"])


@pytest.mark.asyncio
async def test_general_research_keeps_first_sources_when_followup_is_rate_limited():
    lookups = []
    public_query = "Porovnanie tepelných izolácií"

    def handler(request):
        query = request.url.params["q"]
        lookups.append(query)
        if len(lookups) > 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                "grounding": {
                    "generic": [
                        {
                            "url": "https://publisher.example.org/study",
                            "snippets": [
                                "Fiktívne porovnanie tepelných izolácií používa rovnakú hrúbku a vlhkosť vzorky."
                            ],
                        }
                    ]
                }
            },
        )

    web = WebResearch("test-key", httpx.MockTransport(handler))
    sources, notes = await web.run(
        WebResearchInput(query=public_query, scope="general"), focus=public_query
    )
    assert lookups == [public_query, f"({public_query}) NOT site:publisher.example.org"]
    assert len(sources) == 1 and any("HTTP 429" in note for note in notes)


@pytest.mark.asyncio
async def test_general_link_uses_only_exact_indexed_page():
    target = "https://publisher.example.org/paper"

    def handler(request):
        assert request.url.host == "api.search.brave.com"
        assert request.url.params["q"] == target
        return httpx.Response(
            200,
            json={
                "grounding": {
                    "generic": [
                        {
                            "url": target + "-different",
                            "snippets": [
                                "Tento fiktívny text sa týka iného študijného materiálu od rovnakého vydavateľa."
                            ],
                        },
                        {
                            "url": target,
                            "snippets": [
                                "Tento fiktívny text obsahuje zistenia presného dokumentu zadaného v dopyte."
                            ],
                        },
                    ]
                }
            },
        )

    web = WebResearch("test-key", httpx.MockTransport(handler))
    sources, _ = await web.run(WebResearchInput(query=target, scope="general"), focus="zistenia")
    assert [source["source_url"] for source in sources] == [target]
    sources, notes = await web.run(
        WebResearchInput(query="https://127.0.0.1/secret", scope="general"), focus="zistenia"
    )
    assert not sources and notes
