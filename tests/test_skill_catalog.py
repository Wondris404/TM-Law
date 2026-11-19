import httpx
import pytest

from scripts.skill_catalog import ROOT, load_catalog, read_upstream, render_markdown, select


def test_complete_catalog_has_valid_routes_and_matches_generated_library():
    catalog = load_catalog()
    repos = {resource["repo"] for resource in catalog["resources"]}
    assert len(catalog["resources"]) == len(repos) == 30
    assert repos == {
        repo for definition in catalog["intents"].values() for repo in definition["resources"]
    }
    for intent in catalog["intents"]:
        selection = select(catalog, "", intent=intent)
        assert all((ROOT / path).is_file() for path in selection["local_skills"])
    skills = [resource for resource in catalog["resources"] if "upstream" in resource]
    assert len(skills) == 6
    for resource in skills:
        for intent in resource["upstream"]["intents"]:
            match = select(catalog, "", intent=intent, repo=resource["repo"])["primary"]
            assert match["upstream"]["name"] == resource["upstream"]["name"]
    assert (ROOT / "docs/SKILL_LIBRARY.md").read_text(encoding="utf-8") == render_markdown(catalog)


@pytest.mark.parametrize(
    ("task", "intent", "repo", "skill"),
    [
        (
            "Porovnaj tržby a súvahu firmy podľa IČO",
            "company-financials",
            "originalmagneto/RUZ-MCP",
            "ruz-uctovne-zavierky",
        ),
        (
            "Zisti, kto je konateľ firmy podľa IČO",
            "company-register",
            "ShepDogSk/rpo-mcp-server",
            None,
        ),
        (
            "Dohľadaj historické znenie slovenského zákona",
            "slovak-legislation",
            "ESKRiPO/Slov-Lex_MCP",
            None,
        ),
        (
            "Dohľadaj CELEX a transpozíciu smernice",
            "eu-law",
            "cyanheads/eur-lex-mcp-server",
            "eur-lex-guide",
        ),
        (
            "Spracuj tabuľky v PDF a zachovaj poradie čítania",
            "document-layout",
            "docling-project/docling",
            "docling",
        ),
        ("Pridaj textovú vrstvu do slovenského skenu", "pdf-ocr", "ocrmypdf/OCRmyPDF", None),
        (
            "Natrénuj embeddingový model pre hybridné vyhľadávanie",
            "embedding-training",
            "huggingface/sentence-transformers",
            "train-sentence-transformers",
        ),
        (
            "Zaveď reranker na zoradenie pasáží",
            "reranking",
            "huggingface/sentence-transformers",
            None,
        ),
        (
            "Priprav regresný test citácií pre RAG",
            "evaluations",
            "promptfoo/promptfoo",
            "promptfoo-evals",
        ),
        (
            "Vyhľadaj na internete nezávislé zdroje o energetike",
            "web-research",
            "ItzCrazyKns/Vane",
            None,
        ),
    ],
)
def test_selects_relevant_skill_or_repository(task, intent, repo, skill):
    result = select(load_catalog(), task)
    assert result["intent"] == intent
    assert result["primary"]["repo"] == repo
    assert result["primary"].get("upstream", {}).get("name") == skill


def test_unknown_task_and_explicit_intent():
    catalog = load_catalog()
    assert select(catalog, "priprav narodeninovú tortu") == {"intent": None, "status": "no-match"}
    assert select(catalog, "porovnaj ružové kvety")["intent"] is None
    result = select(catalog, "neštruktúrovaný opis", intent="public-contracts")
    assert result["primary"]["repo"] == "zltastopa/zmluvy"
    with pytest.raises(ValueError, match="priradený"):
        select(catalog, "", intent="public-contracts", repo="searxng/searxng")


def test_reads_only_the_pinned_upstream_file():
    result = select(load_catalog(), "", intent="company-financials")["primary"]
    entry = {"repo": result["repo"], **result["upstream"]}
    text = "---\nname: ruz-uctovne-zavierky\n---\n\nFiktívny skúšobný návod.\n"
    expected = f"/{entry['repo']}/{entry['revision']}/{entry['path']}"

    def handle(request):
        assert request.url.host == "raw.githubusercontent.com"
        assert request.url.path == expected and not request.url.query
        return httpx.Response(200, text=text)

    assert read_upstream(entry, transport=httpx.MockTransport(handle)) == text
    with pytest.raises(ValueError, match="pripnutú adresu"):
        read_upstream({**entry, "path": "../SKILL.md"}, transport=httpx.MockTransport(handle))
