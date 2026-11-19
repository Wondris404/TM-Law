"""Validate local source packages. This module never downloads legal material."""

import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from .extract import MAX_UPLOAD
from .schemas import LegalVersion, StrictModel
from .store import Store

MAX_MANIFEST = 5 * 1024 * 1024
SOURCE_EXTENSIONS = {".txt", ".html", ".htm", ".xml", ".pdf"}
SECTION_HEADER = re.compile(
    r"^\s*(?:§\s*(\d+[a-z]?)|(?:článok|clanok|čl|cl)\.?\s*(\d+[a-z]?|[ivxlcdm]+))\s*$",
    re.IGNORECASE | re.MULTILINE,
)
PARAGRAPH_HEADER = re.compile(r"^\s*\((\d+[a-z]?)\)\s*", re.IGNORECASE | re.MULTILINE)


class SourcePackage(StrictModel):
    schema_version: Literal[1]
    original_file: Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._ -]{0,199}$")]
    version: LegalVersion


class VisibleSourceText(HTMLParser):
    blocks = frozenset(
        {"br", "p", "div", "li", "tr", "td", "section", "article", "h1", "h2", "h3", "h4"}
    )
    excluded = frozenset({"head", "script", "style", "template"})

    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = None

    def handle_starttag(self, tag, attrs):
        if self.hidden is None:
            if tag in self.excluded:
                self.hidden = tag
            elif tag in self.blocks:
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == self.hidden:
            self.hidden = None
        elif self.hidden is None and tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.hidden is None:
            self.parts.append(data)


def read_limited(path: Path, limit: int) -> bytes:
    with path.open("rb") as handle:
        content = handle.read(limit + 1)
    if not 0 < len(content) <= limit:
        raise ValueError(f"Neplatná veľkosť súboru. Limit {limit} bajtov.")
    return content


def original_text(raw: bytes, suffix: str) -> str:
    if suffix not in SOURCE_EXTENSIONS:
        raise ValueError("Podporované originály: UTF-8 TXT, HTML, XML a textové PDF.")
    if suffix == ".pdf":
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("extract.py")), suffix],
            input=raw,
            capture_output=True,
            timeout=15,
        )
        if result.returncode:
            raise ValueError(
                "Nepodarilo sa získať text z PDF. Vyberte originál s textovou vrstvou."
            )
        return result.stdout.decode("utf-8")
    # Neutral text extraction only. HTML/XML is never rendered, evaluated or resolved.
    text = raw.decode("utf-8-sig")
    if "\0" in text:
        raise ValueError("Originál musí byť UTF-8 text bez nulových znakov.")
    if suffix == ".txt":
        return text
    parser = VisibleSourceText()
    parser.feed(text)
    parser.close()
    return "".join(parser.parts)


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def load_package(path: Path) -> tuple[LegalVersion, tuple[str, bytes]]:
    package = SourcePackage.model_validate_json(read_limited(path, MAX_MANIFEST))
    source_file = (path.resolve().parent / package.original_file).resolve()
    if source_file.parent != path.resolve().parent:
        raise ValueError("Originál musí ležať vedľa manifestu.")
    version = package.version
    if version.acquired_at is None:
        raise ValueError("Balík vyžaduje presný acquired_at s posunom UTC.")
    if version.source_url and (
        version.source_url.scheme != "https"
        or version.source_url.username
        or version.source_url.password
    ):
        raise ValueError("Použite verejnú HTTPS URL bez prihlasovacích údajov.")
    if version.effective_from and not version.effective_basis:
        raise ValueError("Doplňte pôvod overených dátumov účinnosti.")
    if version.kind == "rozhodnutie" and not all(
        (
            version.case_number,
            version.decision_date,
            version.decision_type,
            version.publication_status,
        )
    ):
        raise ValueError("Rozhodnutie vyžaduje spisovú značku, dátum, typ a stav publikovania.")
    raw = read_limited(source_file, MAX_UPLOAD)
    suffix = source_file.suffix.lower()
    validate_original(version, suffix, raw)
    return version, (suffix, raw)


def validate_original(version: LegalVersion, suffix: str, raw: bytes) -> None:
    if hashlib.sha256(raw).hexdigest() != version.original_sha256:
        raise ValueError("SHA-256 originálu sa nezhoduje s manifestom.")
    visible = normalized(original_text(raw, suffix))
    for passage in version.passages:
        if normalized(passage.text) not in visible:
            raise ValueError(f"Úsek {passage.source_id} sa nenašiel v origináli.")


def draft_sections(text: str) -> list[dict]:
    """Propose boundaries for numbered, line-oriented originals. Verify before import."""
    matches = list(SECTION_HEADER.finditer(text))
    passages = []
    for index, heading in enumerate(matches):
        section = heading[1] or f"cl-{heading[2].lower()}"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[heading.end() : end]
        paragraphs = list(PARAGRAPH_HEADER.finditer(block))
        if not paragraphs and block.strip():
            passages.append(
                {"source_id": f"s-{section}", "section": section, "text": block.strip()}
            )
        for offset, paragraph in enumerate(paragraphs):
            end = paragraphs[offset + 1].start() if offset + 1 < len(paragraphs) else len(block)
            if block[paragraph.end() : end].strip():
                passages.append(
                    {
                        "source_id": f"s-{section}-o-{paragraph[1]}",
                        "section": section,
                        "paragraph": paragraph[1],
                        "text": block[paragraph.end() : end].strip(),
                    }
                )
    return passages


# Priority statutes named by the product plan. Titles are labels only; the corpus
# never invents their wording. A missing row means the act is not imported.
PRIORITY_ACTS = (
    (40, 1964, "Občiansky zákonník"),
    (300, 2005, "Trestný zákon"),
    (301, 2005, "Trestný poriadok"),
    (160, 2015, "Civilný sporový poriadok"),
    (161, 2015, "Civilný mimosporový poriadok"),
    (513, 1991, "Obchodný zákonník"),
    (311, 2001, "Zákonník práce"),
    (162, 2015, "Správny súdny poriadok"),
)


def _intervals_overlap(left: dict, right: dict) -> bool:
    start = max(left["effective_from"], right["effective_from"])
    ends = [
        value
        for value, open_ended in (
            (left.get("effective_until"), left.get("open_ended")),
            (right.get("effective_until"), right.get("open_ended")),
        )
        if value and not open_ended
    ]
    return start < min(ends) if ends else True


def corpus_warnings(versions: list[dict]) -> dict:
    """Report absent priority acts and overlapping non-fictional wordings."""
    authentic = [
        row
        for row in versions
        if row.get("origin") != "fictional"
        and row.get("kind") == "predpis"
        and row.get("law_number")
        and row.get("law_year")
    ]
    present = {(row["law_year"], row["law_number"]) for row in authentic}
    missing = [
        {"law_number": number, "law_year": year, "label": label}
        for number, year, label in PRIORITY_ACTS
        if (year, number) not in present
    ]
    overlaps = []
    by_act: dict[tuple, list[dict]] = {}
    for row in authentic:
        if row.get("effective_from"):
            by_act.setdefault((row["law_year"], row["law_number"]), []).append(row)
    for rows in by_act.values():
        ordered = sorted(rows, key=lambda row: (row["effective_from"], row["version_id"]))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if _intervals_overlap(left, right):
                    overlaps.append(
                        {
                            "law_number": left["law_number"],
                            "law_year": left["law_year"],
                            "versions": [left["version_id"], right["version_id"]],
                        }
                    )
    endings = []
    for (year, number), rows in sorted(by_act.items()):
        if any(row.get("open_ended") for row in rows):
            continue
        ends = [row["effective_until"] for row in rows if row.get("effective_until")]
        if not ends:
            continue
        last = max(ends)
        if not any(row["effective_from"] >= last for row in rows):
            endings.append(
                {
                    "law_number": number,
                    "law_year": year,
                    "coverage_until_exclusive": last,
                }
            )
    return {
        "missing_priority_acts": missing,
        "overlapping_versions": overlaps,
        "coverage_ends": endings,
    }


def coverage(store: Store) -> dict:
    with closing(store.connect(store.legal)) as conn:
        rows = conn.execute(
            """SELECT v.metadata, o.sha256 AS archived, count(p.id) AS passages
               FROM legal_version v JOIN passage p USING(version_id)
               LEFT JOIN legal_version_original o USING(version_id)
               GROUP BY v.version_id ORDER BY v.kind, v.law_year, v.law_number, v.version_id"""
        ).fetchall()
    result = []
    documents = set()
    status = Counter()
    for row in rows:
        md = json.loads(row["metadata"])
        if md["law_number"] is not None:
            identity = (md["kind"], md["law_year"], md["law_number"])
        elif md["case_number"]:
            identity = (md["kind"], md["authority"], md["case_number"], md["decision_date"])
        else:
            identity = (md["kind"], md["source_url"] or md["version_id"])
        origin = (
            "fictional"
            if md["fictional"]
            else "archive_verified"
            if row["archived"]
            else "metadata_only"
        )
        documents.add((origin == "fictional", identity))
        status[origin] += 1
        result.append(
            {
                **{
                    key: md.get(key)
                    for key in (
                        "version_id",
                        "kind",
                        "title",
                        "source_url",
                        "effective_from",
                        "effective_until",
                        "open_ended",
                        "original_sha256",
                    )
                },
                "origin": origin,
                "law_number": md.get("law_number"),
                "law_year": md.get("law_year"),
                "passages": row["passages"],
            }
        )
    summary = {
        "nonfictional_documents": sum(not fictional for fictional, _ in documents),
        "fictional_documents": sum(fictional for fictional, _ in documents),
        "version_counts": {
            key: status[key] for key in ("archive_verified", "metadata_only", "fictional")
        },
        "versions": result,
    }
    summary.update(corpus_warnings(summary["versions"]))
    summary["repeated_passage_texts"] = repeated_passage_texts(store)
    summary["decision_count"] = sum(row.get("kind") == "rozhodnutie" for row in summary["versions"])
    return summary


def repeated_passage_texts(store: Store) -> list[dict]:
    """Same wording stored under more than one source id inside one version."""
    with closing(store.connect(store.legal)) as conn:
        rows = conn.execute(
            """SELECT version_id, group_concat(source_id) AS source_ids, count(*) AS copies
               FROM passage GROUP BY version_id, text HAVING count(*) > 1
               ORDER BY version_id"""
        ).fetchall()
    return [
        {"version_id": row["version_id"], "source_ids": row["source_ids"], "copies": row["copies"]}
        for row in rows
    ]
