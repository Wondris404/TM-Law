import pytest

from scripts.import_slovlex import FamilyActText, prepare_version


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
