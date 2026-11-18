from datetime import date

from tm_law.schemas import LegalVersion
from tm_law.store import Store


def version(version_id, number, year, start, end, passages):
    return LegalVersion(
        version_id=version_id,
        title="Fiktívny predpis A" if number == 9999 else "Fiktívny predpis B",
        kind="predpis",
        law_number=number,
        law_year=year,
        authority="Test",
        acquired_on=date(2026, 11, 18),
        effective_from=start,
        effective_until=end,
        provenance="Syntetický regresný záznam.",
        reuse_terms="MIT",
        fictional=True,
        passages=passages,
    )


def test_separated_references_share_date_filter_and_limit(tmp_path):
    store = Store(tmp_path)
    store.initialize()
    records = [
        version(
            "a-early",
            9999,
            2099,
            date(2022, 1, 1),
            date(2024, 1, 1),
            [{"source_id": "p7", "section": "7", "text": "Staršie prekrývajúce znenie."}],
        ),
        version(
            "a-late",
            9999,
            2099,
            date(2023, 1, 1),
            date(2025, 1, 1),
            [
                {"source_id": "p7", "section": "7", "text": "Novšie prekrývajúce znenie."},
                {"source_id": "p3", "section": "3", "text": "Ďalší paragraf toho istého predpisu."},
            ],
        ),
        version(
            "b-old",
            9998,
            2099,
            date(2020, 1, 1),
            date(2023, 1, 1),
            [{"source_id": "p2", "section": "2", "text": "Skorší úsek druhého predpisu."}],
        ),
        version(
            "b-current",
            9998,
            2099,
            date(2023, 1, 1),
            date(2024, 1, 1),
            [{"source_id": "p2", "section": "2", "text": "Účinný úsek druhého predpisu."}],
        ),
    ]
    for record in records:
        store.import_version(record)

    overlap = date(2023, 6, 1)
    limited = store.search(
        "9999/2099 § 7; 9998/2099 § 2",
        as_of=overlap,
        limit=2,
        include_fictional=True,
        kind="predpis",
    )
    assert [hit["citation_id"] for hit in limited] == ["a-late/p7", "b-current/p2"]
    wider = store.search("9999/2099 § 7; 9998/2099 § 2", as_of=overlap, limit=3)
    assert [hit["citation_id"] for hit in wider] == ["a-late/p7", "b-current/p2", "a-early/p7"]
    assert "b-old/p2" not in {hit["citation_id"] for hit in wider}

    earlier = store.search("9999/2099 § 7; 9998/2099 § 2", as_of=date(2022, 6, 1), limit=4)
    assert {hit["citation_id"] for hit in earlier} == {"a-early/p7", "b-old/p2"}

    same_law = store.search("9999/2099 § 7; § 3", as_of=overlap, limit=2)
    assert {hit["section"] for hit in same_law} == {"7", "3"}
    before_added = store.search("9999/2099 § 7; § 3", as_of=date(2022, 6, 1))
    assert {hit["section"] for hit in before_added} == {"7"}

    ordinary = store.search("9999/2099 § 7 a § 3", as_of=overlap)
    assert {hit["section"] for hit in ordinary} == {"7"}
    assert {hit["citation_id"] for hit in ordinary} == {"a-late/p7", "a-early/p7"}
    hidden = store.search("9999/2099 § 7; 9998/2099 § 2", as_of=overlap, include_fictional=False)
    assert hidden == []


def test_article_word_matches_stored_abbreviation(tmp_path):
    store = Store(tmp_path)
    store.initialize()
    store.import_version(
        version(
            "article",
            9999,
            2099,
            date(2024, 1, 1),
            date(2025, 1, 1),
            [
                {"source_id": "a1", "section": "cl-1", "text": "Prvý článok."},
                {"source_id": "a2", "section": "cl-2", "text": "Druhý článok."},
            ],
        )
    )
    day = date(2024, 6, 1)
    for query in ("9999/2099 Čl. 1", "9999/2099 Článok 1", "9999/2099 clanok 1"):
        hits = store.search(query, as_of=day)
        assert [hit["citation_id"] for hit in hits] == ["article/a1"]
    both = store.search("9999/2099 Článok 1; Článok 2", as_of=day, limit=2)
    assert [hit["citation_id"] for hit in both] == ["article/a1", "article/a2"]
