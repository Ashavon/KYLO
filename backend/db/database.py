import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "kylo.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name   TEXT NOT NULL,
            current_name    TEXT NOT NULL,
            current_path    TEXT NOT NULL UNIQUE,
            md5_hash        TEXT,
            text_hash       TEXT,
            subject         TEXT,
            what            TEXT,
            where_field     TEXT,
            who             TEXT,
            when_field      TEXT,
            summary         TEXT,
            tags            TEXT DEFAULT '[]',
            file_type       TEXT,
            file_size       INTEGER,
            page_count      INTEGER,
            word_count      INTEGER,
            row_count       INTEGER,
            dimensions      TEXT,
            language        TEXT,
            origin          TEXT DEFAULT 'imported',
            ocr_status      TEXT DEFAULT 'pending',
            ai_confidence   REAL DEFAULT 0.0,
            status          TEXT DEFAULT 'new',
            starred         INTEGER DEFAULT 0,
            user_note       TEXT,
            wiki_status     TEXT DEFAULT 'not_sent',
            chroma_id       TEXT,
            date_added      TEXT,
            date_modified   TEXT,
            sidecar_path    TEXT,
            related_files   TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS duplicates_bin (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id         INTEGER,
            original_path   TEXT NOT NULL,
            bin_path        TEXT NOT NULL,
            duplicate_of_id INTEGER,
            similarity_score REAL,
            detection_level TEXT,
            date_binned     TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id)
        );

        CREATE TABLE IF NOT EXISTS tags (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL UNIQUE,
            color   TEXT,
            count   INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS file_tags (
            file_id INTEGER NOT NULL,
            tag_id  INTEGER NOT NULL,
            source  TEXT DEFAULT 'user',
            PRIMARY KEY (file_id, tag_id),
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        );

        CREATE TABLE IF NOT EXISTS related_files (
            file_a_id   INTEGER NOT NULL,
            file_b_id   INTEGER NOT NULL,
            relation    TEXT DEFAULT 'related',
            PRIMARY KEY (file_a_id, file_b_id),
            FOREIGN KEY (file_a_id) REFERENCES files(id),
            FOREIGN KEY (file_b_id) REFERENCES files(id)
        );

        CREATE INDEX IF NOT EXISTS idx_files_md5       ON files(md5_hash);
        CREATE INDEX IF NOT EXISTS idx_files_subject   ON files(subject);
        CREATE INDEX IF NOT EXISTS idx_files_status    ON files(status);
        CREATE INDEX IF NOT EXISTS idx_files_date      ON files(date_added);
    """)

    conn.commit()
    conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in ("tags", "related_files"):
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                d[field] = []
    return d
