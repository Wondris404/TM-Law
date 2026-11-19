import hashlib
from datetime import date

import pytest

from scripts.import_slovlex import (
    ADMINISTRATIVE_PROCEDURE,
    ConstitutionText,
    FamilyActText,
    prepare_version,
)


def test_extract_only_article_one_preserving_printed_numbering():
    parser = FamilyActText()
    parser.feed(
        """
        <div id="paragraf-7.odsek-1.text">Index</div>
        <div id="predpis.clanok-1">
            <div id="paragraf-7.odsek-1.oznacenie">(1)</div>
            <div id="paragraf-7.odsek-1.text">Skúšobná <em>citácia</em> zákona.</div>
            <div id="paragraf-7.odsek-1.pismeno-a.text">Odlišná pasáž.</div>
            <div id="paragraf-119b.odsek-1.oznacenie"></div>
            <div id="paragraf-119b.odsek-1.text">Prechodný režim.</div>
        </div>
        <div id="predpis.clanok-2">
            <div id="paragraf-7.odsek-1.text">Novela cudzieho predpisu.</div>
        </div>
        """
    )
    parser.close()

    first, letter, transitional = parser.passages()
    assert first["text"] == "Skúšobná citácia zákona."
    assert first["section"] == "7"
    assert first["paragraph"] == letter["paragraph"] == "1"
    assert letter["letter"] == "a"
    assert transitional["norm_status"] == "transitional"
    assert transitional["paragraph"] is None


def test_unpinned_export_is_rejected_before_html_parsing():
    with pytest.raises(ValueError, match="očakávaný SHA-256"):
        prepare_version(b"\xffnot the official snapshot", "20260601")


def test_constitution_fixture_appends_quote_and_skips_headings():
    parser = ConstitutionText()
    parser.feed(
        """
        <div id="predpis.hlava-prva.oznacenie">PRVÁ HLAVA</div>
        <div id="predpis.text">PREAMBULA Skúšobný úvod.</div>
        <div id="ustavnyclanok-1.oznacenie">Čl. 1</div>
        <div id="ustavnyclanok-1.odsek-1.oznacenie">(1)</div>
        <div id="ustavnyclanok-1.odsek-1.text">Skúšobný odsek.</div>
        <div id="ustavnyclanok-81a.oznacenie">Čl. 81a</div>
        <div id="ustavnyclanok-81a.text">Úvod bez odseku.</div>
        <div id="ustavnyclanok-81a.pismeno-a.oznacenie">a)</div>
        <div id="ustavnyclanok-81a.pismeno-a.text">Písmeno a.</div>
        <div id="ustavnyclanok-75.oznacenie">Čl. 75</div>
        <div id="ustavnyclanok-75.odsek-1.oznacenie">(1)</div>
        <div id="ustavnyclanok-75.odsek-1.text">Sľub znie:</div>
        <div id="ustavnyclanok-75.odsek-1.text2">
            <div id="ustavnyclanok-75.odsek-1.text2.citat.odsek-1.text">„Skúšobný sľub.“</div>
        </div>
        <div id="ustavnyclanok-112.oznacenie">Čl. 112</div>
        <div id="ustavnyclanok-112.odsek-1.oznacenie"></div>
        <div id="ustavnyclanok-112.odsek-1.text">Nečíslovaný úvod.</div>
        <div id="ustavnyclanok-155.oznacenie">Čl. 155</div>
        <div id="ustavnyclanok-155.bod-1.oznacenie">1.</div>
        <div id="ustavnyclanok-155.bod-1.text">Skúšobný bod.</div>
        """
    )
    parser.close()
    passages = parser.passages()
    by_id = {item["source_id"]: item for item in passages}

    assert [item["source_id"] for item in passages] == [
        "predpis.text",
        "ustavnyclanok-1.odsek-1",
        "ustavnyclanok-81a",
        "ustavnyclanok-81a.pismeno-a",
        "ustavnyclanok-75.odsek-1",
        "ustavnyclanok-112.odsek-1",
        "ustavnyclanok-155.bod-1",
    ]
    assert by_id["predpis.text"]["section"] is None
    assert by_id["predpis.text"]["text"] == "PREAMBULA Skúšobný úvod."
    assert by_id["ustavnyclanok-1.odsek-1"]["section"] == "cl-1"
    assert by_id["ustavnyclanok-1.odsek-1"]["paragraph"] == "1"
    assert by_id["ustavnyclanok-81a.pismeno-a"]["letter"] == "a"
    assert by_id["ustavnyclanok-81a.pismeno-a"]["paragraph"] is None
    assert by_id["ustavnyclanok-75.odsek-1"]["text"] == "Sľub znie: „Skúšobný sľub.“"
    assert by_id["ustavnyclanok-112.odsek-1"]["paragraph"] is None
    assert by_id["ustavnyclanok-155.bod-1"]["paragraph"] is None
    assert by_id["ustavnyclanok-155.bod-1"]["letter"] is None
    assert all(item["norm_status"] is None for item in passages)
    assert "predpis.hlava-prva.oznacenie" not in by_id
    assert all("text2" not in item["source_id"] for item in passages)


def test_constitution_parser_rejects_unknown_article_node():
    parser = ConstitutionText()
    with pytest.raises(ValueError, match="Neznáma štruktúra"):
        parser.feed('<div id="ustavnyclanok-1.odsek-1.veta-1.text">Text.</div>')


def test_unpinned_constitution_export_is_rejected_before_html_parsing():
    with pytest.raises(ValueError, match="očakávaný SHA-256"):
        prepare_version(b"<div id='predpis.text'>Nie je to export.</div>", "20250101")


def test_standalone_print_export_preserves_open_interval_and_points(monkeypatch):
    raw = b"""
        <div id="paragraf-82.odsek-1.text">Navigation noise.</div>
        <div id="predpis">
          <div id="paragraf-82.odsek-1.oznacenie">(1)</div>
          <div id="paragraf-82.odsek-1.text">Synthetic transitional text.</div>
          <div id="paragraf-83.bod-1.text">Synthetic numbered point.</div>
        </div>
    """
    key = "20180901"
    pinned = ADMINISTRATIVE_PROCEDURE[key]
    monkeypatch.setitem(
        ADMINISTRATIVE_PROCEDURE, key, pinned._replace(sha256=hashlib.sha256(raw).hexdigest())
    )
    result = prepare_version(raw, key)
    assert result.open_ended and result.effective_until is None
    assert result.effective_from == date(2018, 9, 1)
    paragraph, point = result.passages
    assert paragraph.text == "Synthetic transitional text." and paragraph.paragraph == "1"
    assert paragraph.norm_status == "transitional"
    assert point.source_id == "paragraf-83.bod-1" and point.norm_status is None
