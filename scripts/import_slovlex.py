"""Import pinned Slov-Lex print snapshots offline.

Snapshots 20250801 and 20260601 remain Act 36/2005. Snapshot 20250101 is the
closed wording of constitutional act 460/1992. Its PDF is pinned, not archived.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

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


class ConstitutionSnapshot(NamedTuple):
    version_id: str
    title: str
    law_number: int
    law_year: int
    authority: str
    source_url: str
    acquired_at: str
    published_on: str
    effective_from: str
    effective_until: str
    sha256: str
    pdf_url: str
    pdf_sha256: str


CONSTITUTION = {
    "20250101": ConstitutionSnapshot(
        version_id="sk-zz-1992-460-20250101",
        title="Ústava Slovenskej republiky",
        law_number=460,
        law_year=1992,
        authority="Slovenská národná rada",
        source_url="https://static.slov-lex.sk/static/SK/ZZ/1992/460/20250101.print.html",
        acquired_at="2026-11-19T09:00:06+00:00",
        published_on="1992-10-01",
        effective_from="2025-01-01",
        effective_until="2025-11-01",
        sha256="f58fc284e6aea0c3905d1b8f8d92e424fa9584a58b5b830565255b7414999fa1",
        pdf_url="https://static.slov-lex.sk/pdf/SK/ZZ/1992/460/ZZ_1992_460_20250101.pdf",
        pdf_sha256="010bca4e5da12a25029384b62c29b422de17e7da87fb1dc33b2ce7dfef36dad0",
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


NODE = re.compile(
    r"ustavnyclanok-(?P<article>[0-9]+[a-z]?)"
    r"(?:\.odsek-(?P<paragraph>[0-9]+[a-z]?))?"
    r"(?:\.pismeno-(?P<letter>[a-z]+))?"
    r"(?:\.bod-(?P<point>[0-9]+))?"
    r"\.(?P<part>text2|text|oznacenie)\Z"
)
PREAMBLE_ID = "predpis.text"


class ConstitutionText(HTMLParser):
    """Index the preamble and article text. Append text2. Skip headings."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.active = None
        self.parts = []
        self.nodes = {}

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            self.depth += 1
            node = dict(attrs).get("id") or ""
            if node == PREAMBLE_ID or NODE.fullmatch(node):
                if self.active is not None or node in self.nodes:
                    raise ValueError(f"Nejednoznačný identifikátor v Slov-Lexe: {node}")
                self.active = (node, self.depth)
                self.parts = []
            elif self.active is None and node.startswith("ustavnyclanok-"):
                tail = node.rsplit(".", 1)[-1]
                if tail in {"text", "text2", "oznacenie"}:
                    raise ValueError(f"Neznáma štruktúra Slov-Lexu: {node}")
        if self.active and tag in VisibleSourceText.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.active and tag in VisibleSourceText.blocks:
            self.parts.append("\n")
        if tag == "div":
            if self.active and self.active[1] == self.depth:
                self.nodes[self.active[0]] = normalized("".join(self.parts))
                self.active = None
            self.depth -= 1

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def _label(self, node_id: str) -> str:
        if node_id not in self.nodes:
            raise ValueError(f"Chýba označenie: {node_id}")
        return self.nodes[node_id]

    def _passage(self, match: re.Match, source_id: str, text: str) -> dict:
        article = match["article"]
        heading = self._label(f"ustavnyclanok-{article}.oznacenie")
        if heading != f"Čl. {article}":
            raise ValueError(f"Označenie článku {article} je {heading!r}.")
        paragraph = None
        if match["paragraph"]:
            label = self._label(f"ustavnyclanok-{article}.odsek-{match['paragraph']}.oznacenie")
            if label:
                if label != f"({match['paragraph']})":
                    raise ValueError(f"Neplatné označenie odseku: {source_id}")
                paragraph = match["paragraph"]
        base = f"ustavnyclanok-{article}"
        if match["paragraph"]:
            base += f".odsek-{match['paragraph']}"
        letter = None
        if match["letter"]:
            label = self._label(f"{base}.pismeno-{match['letter']}.oznacenie")
            if label != f"{match['letter']})":
                raise ValueError(f"Neplatné označenie písmena: {source_id}")
            letter = match["letter"]
        if match["point"]:
            label = self._label(f"{base}.bod-{match['point']}.oznacenie")
            if label != f"{match['point']}.":
                raise ValueError(f"Neplatné označenie bodu: {source_id}")
        return {
            "source_id": source_id,
            "section": f"cl-{article}",
            "paragraph": paragraph,
            "letter": letter,
            "norm_status": None,
            "text": text,
        }

    def passages(self) -> list[dict]:
        if self.active is not None or not self.nodes:
            raise ValueError("Chýba úplná štruktúra ústavy v exporte Slov-Lexu.")
        passages = []
        used_text2 = set()
        for node, text in self.nodes.items():
            if node == PREAMBLE_ID:
                if not text:
                    raise ValueError("Prázdna preambula v exporte Slov-Lexu.")
                passages.append(
                    {
                        "source_id": PREAMBLE_ID,
                        "section": None,
                        "paragraph": None,
                        "letter": None,
                        "norm_status": None,
                        "text": text,
                    }
                )
                continue
            match = NODE.fullmatch(node)
            if match is None or match["part"] != "text":
                continue
            if not text:
                raise ValueError(f"Prázdny text: {node}")
            source_id = node.removesuffix(".text")
            extra_id = f"{source_id}.text2"
            if extra_id in self.nodes:
                extra = self.nodes[extra_id]
                if not extra:
                    raise ValueError(f"Prázdne text2: {extra_id}")
                text = normalized(f"{text} {extra}")
                used_text2.add(extra_id)
            passages.append(self._passage(match, source_id, text))
        missed = [
            node
            for node in self.nodes
            if node.endswith(".text2") and NODE.fullmatch(node) and node not in used_text2
        ]
        if missed:
            raise ValueError(f"text2 bez textu: {missed[0]}")
        if not passages:
            raise ValueError("V exporte Slov-Lexu sa nenašli ustanovenia ústavy.")
        return passages


def prepare_constitution(raw: bytes, snapshot: str) -> LegalVersion:
    pinned = CONSTITUTION[snapshot]
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != pinned.sha256:
        raise ValueError(f"Export {snapshot} nemá očakávaný SHA-256 zo zdrojového katalógu.")
    parser = ConstitutionText()
    parser.feed(raw.decode("utf-8-sig"))
    parser.close()
    acquired = datetime.fromisoformat(pinned.acquired_at)
    start = datetime.fromisoformat(pinned.effective_from).date()
    end = datetime.fromisoformat(pinned.effective_until).date()
    inclusive_end = end - timedelta(days=1)
    version = LegalVersion(
        version_id=pinned.version_id,
        title=pinned.title,
        kind="predpis",
        law_number=pinned.law_number,
        law_year=pinned.law_year,
        authority=pinned.authority,
        source_url=pinned.source_url,
        acquired_on=acquired.date(),
        acquired_at=acquired,
        published_on=pinned.published_on,
        effective_from=start,
        effective_until=end,
        effective_basis=(
            f"Hlavička HTML a PDF: účinná od {start.strftime('%d.%m.%Y')} "
            f"do {inclusive_end.strftime('%d.%m.%Y')}. "
            "Koniec v SQLite je prvý deň mimo účinnosti."
        ),
        provenance=(
            "Oficiálny export Slov-Lex. Indexuje preambulu a články z HTML. "
            "HTML je informatívne, záväzné znenie je PDF."
        ),
        reuse_terms="Text predpisu podľa § 5 písm. b) zákona č. 185/2015 Z. z.",
        original_sha256=checksum,
        passages=parser.passages(),
    )
    validate_original(version, ".html", raw)
    return version


def prepare_version(raw: bytes, snapshot: str) -> LegalVersion:
    if snapshot in CONSTITUTION:
        return prepare_constitution(raw, snapshot)
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
    parser.add_argument("snapshot", choices=[*VERSIONS, *CONSTITUTION])
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
                "sections": len(
                    {passage.section for passage in version.passages if passage.section}
                ),
                "original_sha256": version.original_sha256,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
