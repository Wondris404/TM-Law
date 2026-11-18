import hashlib
import json
import re
import sqlite3
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
PRAGMA user_version=1;
COMMIT;
"""
PRIVATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS document (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL, sha256 TEXT NOT NULL
);
"""
LAW_PATTERN = re.compile(r"(?<!\w)(\d{1,8})\s*/\s*(\d{4})(?!\w)")
SECTION_PATTERN = re.compile(r"§\s*(\d+[a-z]?)", re.IGNORECASE)
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
            elif version != 1:
                raise RuntimeError(f"Unsupported database schema version {version}")
        with closing(self.connect(self.private)) as conn:
            conn.executescript(PRIVATE_SCHEMA)

    def import_version(self, version: LegalVersion) -> tuple[str, bool]:
        data = version.model_dump(mode="json", exclude={"passages"})
        digest = hashlib.sha256(
            json.dumps(version.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        with closing(self.connect(self.legal)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT content_sha256 FROM legal_version WHERE version_id=?", (version.version_id,)
            ).fetchone()
            if current:
                if current[0] != digest:
                    raise ValueError("Toto ID znenia už označuje iný obsah.")
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
                    "INSERT INTO passage(version_id, source_id, section, paragraph, letter, text) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (version.version_id, p.source_id, p.section, p.paragraph, p.letter, p.text),
                )
                conn.execute(
                    "INSERT INTO passage_fts(rowid, title, text) VALUES (?, ?, ?)",
                    (cursor.lastrowid, version.title, p.text),
                )
        return digest, True

    def search(
        self,
        query: str,
        *,
        kind=None,
        as_of: date | None = None,
        limit=10,
        include_fictional=True,
    ) -> list[dict]:
        law = LAW_PATTERN.search(query)
        section = SECTION_PATTERN.search(query)
        remaining = SECTION_PATTERN.sub(" ", LAW_PATTERN.sub(" ", query))
        words = [
            word
            for word in dict.fromkeys(re.findall(r"[^\W_]+", remaining.casefold()))
            if word not in STOP_WORDS and len(word) > 1
        ][:20]
        if not (law or section or words or kind or as_of):
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
            params.append(section[1].lower())
        if kind:
            filters.append("v.kind=?")
            params.append(kind)
        if not include_fictional:
            filters.append("json_extract(v.metadata, '$.fictional')=0")
        if as_of:
            day = as_of.isoformat()
            filters.append(
                "((v.effective_from<=? AND (v.effective_until>? OR v.open_ended=1)) OR "
                "(v.kind='rozhodnutie' AND v.decision_date<=?))"
            )
            params.extend((day, day, day))
        where = " AND ".join(filters) or "1"
        with closing(self.connect(self.legal)) as conn:
            rows = conn.execute(
                f"SELECT p.*, v.metadata, v.content_sha256 FROM passage p "
                f"JOIN legal_version v USING(version_id) {join} "
                f"WHERE {where} ORDER BY {order} LIMIT ?",
                [*params, limit],
            ).fetchall()
        if not rows and words and (law or section):
            citations = " ".join(part[0] for part in (law, section) if part)
            return self.search(
                citations, kind=kind, as_of=as_of, limit=limit, include_fictional=include_fictional
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
                        "content_sha256",
                    )
                },
                "citation_id": f"{row['version_id']}/{row['source_id']}",
            }
            for row in rows
        ]

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
            return conn.execute("DELETE FROM document WHERE id=?", (document_id,)).rowcount == 1
