import hashlib
import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import date
from pathlib import Path

from .schemas import LegalVersion

SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS legal_version (
    version_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    law_number INTEGER,
    law_year INTEGER,
    effective_from TEXT,
    effective_until TEXT,
    open_ended INTEGER NOT NULL,
    decision_date TEXT,
    content_sha256 TEXT NOT NULL,
    metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS passage (
    id INTEGER PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES legal_version(version_id),
    source_id TEXT NOT NULL,
    section TEXT,
    paragraph TEXT,
    letter TEXT,
    text TEXT NOT NULL,
    UNIQUE(version_id, source_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts USING fts5(
    title, text, tokenize='unicode61 remove_diacritics 2'
);
COMMIT;
"""
PRIVATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS document (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL, sha256 TEXT NOT NULL
);
"""
LAW_PATTERN = re.compile(r"(?<!\w)(\d{1,8})\s*/\s*(\d{4})(?!\w)")
SCHEMA_VERSION = 2
SECTION_PATTERN = re.compile(
    r"§\s*(?P<section>\d+[a-z]?)|\b(?:čl|cl)\.\s*(?P<article>\d+[a-z]?|[ivxlcdm]+)", re.IGNORECASE
)
PARAGRAPH_PATTERN = re.compile(r"\b(?:ods|odsek)\.?\s*(\d+[a-z]?)", re.IGNORECASE)
LETTER_PATTERN = re.compile(r"\b(?:písm|pism|písmeno|pismeno)\.?\s*([a-z])(?=\)|\b)", re.IGNORECASE)
LEGAL_WORDS = {
    "obcianskeho": "obciansky",
    "trestneho": "trestny",
    "obchodneho": "obchodny",
    "zakonnika": "zakonnik",
    "poriadku": "poriadok",
    "kupnej": "kupna",
    "zmluvy": "zmluva",
    "rozsudku": "rozsudok",
}
VERSION_FIELDS_ADDED = (
    "acquired_at",
    "valid_from",
    "valid_until",
    "effective_basis",
    "decision_type",
    "publication_status",
    "cited_legislation",
)
STOP_WORDS = frozenset(
    "a aj ak ako aké aký alebo boli bol byť by čo do je k kde kedy ktorý ktorá "
    "má môže na od o podľa po pre pri sa si sú tak to v vo z za zo znenie zákon".split()
)


class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        self.legal = directory / "legal.sqlite3"
        self.private = directory / "documents.sqlite3"

    @staticmethod
    def connect(path: Path):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with closing(self.connect(self.legal)) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                conn.executescript(SCHEMA)
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version in {0, 1}:
                    conn.execute("ALTER TABLE passage ADD COLUMN norm_status TEXT")
                    conn.execute(
                        "CREATE TABLE legal_original ("
                        "sha256 TEXT PRIMARY KEY, suffix TEXT NOT NULL, payload BLOB NOT NULL)"
                    )
                    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                elif version != SCHEMA_VERSION:
                    raise RuntimeError(f"Unsupported database schema version {version}")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS legal_version_original ("
                    "version_id TEXT PRIMARY KEY REFERENCES legal_version(version_id), "
                    "sha256 TEXT NOT NULL REFERENCES legal_original(sha256))"
                )
        with closing(self.connect(self.private)) as conn:
            conn.executescript(PRIVATE_SCHEMA)

    def import_version(
        self,
        version: LegalVersion,
        original: tuple[str, bytes] | None = None,
    ) -> tuple[str, bool]:
        # Omitting new null fields preserves v1 content hashes and repeat-import behaviour.
        payload = version.model_dump(mode="json")
        for field in VERSION_FIELDS_ADDED:
            if payload[field] is None:
                del payload[field]
        for passage in payload["passages"]:
            if passage["norm_status"] is None:
                del passage["norm_status"]
        data = {key: value for key, value in payload.items() if key != "passages"}
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if original and hashlib.sha256(original[1]).hexdigest() != version.original_sha256:
            raise ValueError("Originál nemá deklarovaný SHA-256.")
        with closing(self.connect(self.legal)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            if original:
                conn.execute(
                    "INSERT OR IGNORE INTO legal_original VALUES (?, ?, ?)",
                    (version.original_sha256, *original),
                )
            current = conn.execute(
                "SELECT content_sha256 FROM legal_version WHERE version_id=?", (version.version_id,)
            ).fetchone()
            if current:
                if current[0] != digest:
                    raise ValueError("Toto ID znenia už označuje iný obsah.")
                if original:
                    self.link_original(conn, version)
                return digest, False
            conn.execute(
                "INSERT INTO legal_version VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    version.version_id,
                    version.title,
                    version.kind,
                    version.law_number,
                    version.law_year,
                    data["effective_from"],
                    data["effective_until"],
                    version.open_ended,
                    data["decision_date"],
                    digest,
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            for p in version.passages:
                cursor = conn.execute(
                    "INSERT INTO passage(version_id, source_id, section, paragraph, letter, text, norm_status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        version.version_id,
                        p.source_id,
                        p.section,
                        p.paragraph,
                        p.letter,
                        p.text,
                        p.norm_status,
                    ),
                )
                conn.execute(
                    "INSERT INTO passage_fts(rowid, title, text) VALUES (?, ?, ?)",
                    (cursor.lastrowid, version.title, p.text),
                )
            if original:
                self.link_original(conn, version)
        return digest, True

    @staticmethod
    def link_original(conn, version: LegalVersion):
        conn.execute(
            "INSERT OR IGNORE INTO legal_version_original VALUES (?, ?)",
            (version.version_id, version.original_sha256),
        )

    def search(
        self,
        query: str,
        *,
        kind=None,
        case_number: str | None = None,
        as_of: date | None = None,
        limit=10,
        include_fictional=True,
    ) -> list[dict]:
        law = LAW_PATTERN.search(query)
        section = SECTION_PATTERN.search(query)
        paragraph = PARAGRAPH_PATTERN.search(query) if section else None
        letter = LETTER_PATTERN.search(query) if section else None
        remaining = SECTION_PATTERN.sub(" ", LAW_PATTERN.sub(" ", query))
        if section:
            remaining = LETTER_PATTERN.sub(" ", PARAGRAPH_PATTERN.sub(" ", remaining))
        words = [
            word
            for word in dict.fromkeys(re.findall(r"[^\W_]+", remaining.casefold()))
            if word not in STOP_WORDS and len(word) > 1
        ][:20]
        for word in tuple(words):
            folded = "".join(
                c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c)
            )
            alias = LEGAL_WORDS.get(folded)
            if alias and alias not in words:
                words.append(alias)
        if not (law or section or words or kind or case_number or as_of):
            return []
        filters, params = [], []
        join = ""
        order = "v.title, v.effective_from DESC, p.id"
        if words:
            join = "JOIN passage_fts ON passage_fts.rowid=p.id"
            filters.append("passage_fts MATCH ?")
            params.append(" OR ".join(f'"{word}"' for word in words))
            order = "bm25(passage_fts, 2.0, 1.0), " + order
        if law:
            filters.append("v.law_number=? AND v.law_year=?")
            params.extend(map(int, law.groups()))
        if section:
            filters.append("lower(p.section)=?")
            params.append((section["section"] or f"cl-{section['article']}").lower())
        if paragraph:
            filters.append("lower(p.paragraph)=?")
            params.append(paragraph[1].lower())
        if letter:
            filters.append("lower(p.letter)=?")
            params.append(letter[1].lower())
        if kind:
            filters.append("v.kind=?")
            params.append(kind)
        if case_number:
            filters.append(
                "v.kind='rozhodnutie' AND replace(json_extract(v.metadata, '$.case_number'), ' ', '') "
                "= replace(?, ' ', '') COLLATE NOCASE"
            )
            params.append(case_number.strip())
        if not include_fictional:
            filters.append("json_extract(v.metadata, '$.fictional')=0")
        if as_of:
            day = as_of.isoformat()
            filters.append(
                "((v.kind!='rozhodnutie' AND v.effective_from<=? AND (v.effective_until>? OR v.open_ended=1)) OR "
                "(v.kind='rozhodnutie' AND v.decision_date<=?))"
            )
            params.extend((day, day, day))
        where = " AND ".join(filters) or "1"
        with closing(self.connect(self.legal)) as conn:
            rows = conn.execute(
                f"SELECT p.*, v.metadata, v.content_sha256, "
                "EXISTS(SELECT 1 FROM legal_version_original o WHERE o.version_id=v.version_id) "
                "AS original_archived FROM passage p "
                f"JOIN legal_version v USING(version_id) {join} "
                f"WHERE {where} ORDER BY {order} LIMIT ?",
                [*params, limit],
            ).fetchall()
        if not rows and words and (law or section):
            citations = " ".join(part[0] for part in (law, section, paragraph, letter) if part)
            return self.search(
                citations,
                kind=kind,
                case_number=case_number,
                as_of=as_of,
                limit=limit,
                include_fictional=include_fictional,
            )
        return [
            {
                **json.loads(row["metadata"]),
                **{
                    key: row[key]
                    for key in (
                        "source_id",
                        "section",
                        "paragraph",
                        "letter",
                        "text",
                        "norm_status",
                        "content_sha256",
                    )
                },
                "citation_id": f"{row['version_id']}/{row['source_id']}",
                "original_archived": bool(row["original_archived"]),
            }
            for row in rows
        ]

    def get_legal_original(self, sha256: str) -> bytes | None:
        with closing(self.connect(self.legal)) as conn:
            row = conn.execute(
                "SELECT payload FROM legal_original WHERE sha256=?", (sha256,)
            ).fetchone()
        if row is None:
            return None
        if hashlib.sha256(row[0]).hexdigest() != sha256:
            raise ValueError("Uložený originál neprešiel kontrolou integrity.")
        return row[0]

    def save_document(self, document_id: str, name: str, text: str, digest: str):
        with closing(self.connect(self.private)) as conn, conn:
            conn.execute(
                "INSERT INTO document VALUES (?, ?, ?, ?)", (document_id, name, text, digest)
            )

    def list_documents(self):
        with closing(self.connect(self.private)) as conn:
            return [
                dict(row)
                for row in conn.execute("SELECT id, name FROM document ORDER BY rowid DESC")
            ]

    def get_document(self, document_id: str):
        with closing(self.connect(self.private)) as conn:
            row = conn.execute("SELECT * FROM document WHERE id=?", (document_id,)).fetchone()
        return dict(row) if row else None

    def delete_document(self, document_id: str):
        with closing(self.connect(self.private)) as conn, conn:
            conn.execute("PRAGMA secure_delete=ON")
            return conn.execute("DELETE FROM document WHERE id=?", (document_id,)).rowcount == 1
