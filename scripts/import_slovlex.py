"""Import the two pinned Slov-Lex print snapshots of Act 36/2005, offline."""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from backend.tm_law.corpus import VisibleSourceText, normalized, read_limited, validate_original
from backend.tm_law.extract import MAX_UPLOAD
from backend.tm_law.schemas import LegalVersion
from backend.tm_law.store import Store

SOURCE = "https://static.slov-lex.sk/static/SK/ZZ/2005/36/"
VERSIONS = {
    "20250801": (
        "2025-08-01",
        "2026-06-01",
        "2026-11-18T20:50:49+00:00",
        "6aef24ba897e41abb0d74ebe816a1b044fc2a2bb707b4d3dd702942af68cb5b3",
    ),
    "20260601": (
        "2026-06-01",
        "2026-09-01",
        "2026-11-18T20:49:57+00:00",
        "dc612336395aa41ee130d152ecebd5a51b9ef819f1ed29acb67e9582d9e8c793",
    ),
}

ARTICLE = "predpis.clanok-1"
BASIC = ARTICLE + ".skupinaElementov-zakladne_zasady."
PASSAGE = re.compile(
    r"(?:(?:paragraf-(?P<section>[0-9]+[a-z]?))|(?:clanok-(?P<article>[0-9]+)))"
    r"(?P<paragraph>\.odsek-[0-9]+[a-z]?(?:~[0-9]+)?)?"
    r"(?:\.pismeno-(?P<letter>[a-z]+))?(?:\.bod-[0-9]+)?"
    r"\.(?P<part>text|oznacenie)"
)
TRANSITIONAL = {"114", "115", "116", "117", "118", "119", "119a", "119b"}


class FamilyActText(HTMLParser):
    """Read the numbered provisions from article I, excluding the navigation index."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.article_depth = None
        self.active = None
        self.parts = []
        self.nodes = {}

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            self.depth += 1
            node = (dict(attrs).get("id") or "").removeprefix(BASIC)
            if node == ARTICLE:
                self.article_depth = self.depth
            if self.article_depth is not None and PASSAGE.fullmatch(node):
                if self.active is not None or node in self.nodes:
                    raise ValueError(f"Nejednoznačný identifikátor v Slov-Lexe: {node}")
                self.active = (node, self.depth)
                self.parts = []
        if self.active and tag in VisibleSourceText.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.active and tag in VisibleSourceText.blocks:
            self.parts.append("\n")
        if tag == "div":
            if self.active and self.active[1] == self.depth:
                self.nodes[self.active[0]] = normalized("".join(self.parts))
                self.active = None
            if self.article_depth == self.depth:
                self.article_depth = None
            self.depth -= 1

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def passages(self) -> list[dict]:
        if self.article_depth is not None or self.active is not None or not self.nodes:
            raise ValueError("Chýba úplná štruktúra čl. I v exporte Slov-Lexu.")
        passages = []
        for node, text in self.nodes.items():
            if not node.endswith(".text") or not text:
                continue
            match = PASSAGE.fullmatch(node)
            section = match["section"] or f"cl-{match['article']}"
            paragraph = None
            if match["paragraph"]:
                prefix = node.split(match["paragraph"], 1)[0]
                label = self.nodes.get(prefix + match["paragraph"] + ".oznacenie")
                if label is None or (label and not re.fullmatch(r"\([0-9]+[a-z]?\)", label)):
                    raise ValueError(f"Neplatné označenie odseku: {node}")
                paragraph = label[1:-1] or None
            passages.append(
                {
                    "source_id": node.removesuffix(".text").replace("~", "-cast-"),
                    "section": section,
                    "paragraph": paragraph,
                    "letter": match["letter"],
                    "norm_status": "transitional" if section in TRANSITIONAL else None,
                    "text": text,
                }
            )
        if not passages:
            raise ValueError("V exporte Slov-Lexu sa nenašli ustanovenia čl. I.")
        return passages


def prepare_version(raw: bytes, snapshot: str) -> LegalVersion:
    start, end, recorded_at, checksum = VERSIONS[snapshot]
    if hashlib.sha256(raw).hexdigest() != checksum:
        raise ValueError(f"Export {snapshot} nemá očakávaný SHA-256 zo zdrojového katalógu.")
    parser = FamilyActText()
    parser.feed(raw.decode("utf-8-sig"))
    parser.close()
    acquired = datetime.fromisoformat(recorded_at)
    version = LegalVersion(
        version_id=f"sk-zz-2005-36-{snapshot}",
        title="Zákon o rodine a o zmene a doplnení niektorých zákonov",
        kind="predpis",
        law_number=36,
        law_year=2005,
        authority="Národná rada Slovenskej republiky",
        source_url=f"{SOURCE}{snapshot}.print.html",
        acquired_on=acquired.date(),
        acquired_at=acquired,
        published_on="2005-02-11",
        effective_from=start,
        effective_until=end,
        effective_basis="Časová verzia v hlavičke znenia Slov-Lex. Koniec je prvý deň mimo účinnosti.",
        provenance="Oficiálny export Slov-Lex, čl. I. HTML je informatívne, záväzné znenie je v PDF.",
        reuse_terms="Text predpisu podľa § 5 písm. b) zákona č. 185/2015 Z. z.",
        original_sha256=checksum,
        passages=parser.passages(),
    )
    validate_original(version, ".html", raw)
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", choices=VERSIONS)
    parser.add_argument("original", type=Path, help="Vopred uložený oficiálny HTML export.")
    parser.add_argument("--data-dir", type=Path, default=Path(".tm-law/slovlex"))
    args = parser.parse_args()
    try:
        raw = read_limited(args.original, MAX_UPLOAD)
        version = prepare_version(raw, args.snapshot)
        store = Store(args.data_dir)
        store.initialize()
        _, created = store.import_version(version, (".html", raw))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "version_id": version.version_id,
                "created": created,
                "passages": len(version.passages),
                "sections": len({passage.section for passage in version.passages}),
                "original_sha256": version.original_sha256,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
