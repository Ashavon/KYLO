import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def index_file(
    conn,
    original_name: str,
    current_name: str,
    current_path: str,
    md5_hash: str,
    text_hash: Optional[str],
    ai_result: dict,
    extraction: dict,
    origin: str = "imported",
    ocr_status: str = "pending",
    chroma_id: Optional[str] = None,
) -> int:
    """
    Insert or replace a file record in SQLite. Returns the row id.
    """
    now = datetime.now(timezone.utc).isoformat()
    tags = json.dumps(ai_result.get("tags", []))
    file_type = _detect_type(current_name)

    c = conn.cursor()
    c.execute("""
        INSERT INTO files (
            original_name, current_name, current_path,
            md5_hash, text_hash,
            subject, what, where_field, who, when_field,
            summary, tags, file_type, file_size,
            page_count, word_count, row_count, dimensions, language,
            origin, ocr_status, ai_confidence, status,
            chroma_id, date_added, date_modified, sidecar_path
        ) VALUES (
            :original_name, :current_name, :current_path,
            :md5_hash, :text_hash,
            :subject, :what, :where_field, :who, :when_field,
            :summary, :tags, :file_type, :file_size,
            :page_count, :word_count, :row_count, :dimensions, :language,
            :origin, :ocr_status, :ai_confidence, :status,
            :chroma_id, :date_added, :date_modified, :sidecar_path
        )
        ON CONFLICT(current_path) DO UPDATE SET
            current_name    = excluded.current_name,
            md5_hash        = excluded.md5_hash,
            text_hash       = excluded.text_hash,
            subject         = excluded.subject,
            what            = excluded.what,
            where_field     = excluded.where_field,
            who             = excluded.who,
            when_field      = excluded.when_field,
            summary         = excluded.summary,
            tags            = excluded.tags,
            ai_confidence   = excluded.ai_confidence,
            date_modified   = excluded.date_modified,
            chroma_id       = excluded.chroma_id
    """, {
        "original_name": original_name,
        "current_name": current_name,
        "current_path": str(current_path),
        "md5_hash": md5_hash,
        "text_hash": text_hash,
        "subject": ai_result.get("subject"),
        "what": ai_result.get("what"),
        "where_field": ai_result.get("where"),
        "who": ai_result.get("who"),
        "when_field": ai_result.get("when"),
        "summary": ai_result.get("summary"),
        "tags": tags,
        "file_type": file_type,
        "file_size": Path(current_path).stat().st_size if Path(current_path).exists() else 0,
        "page_count": extraction.get("page_count"),
        "word_count": extraction.get("word_count"),
        "row_count": extraction.get("row_count"),
        "dimensions": extraction.get("dimensions"),
        "language": extraction.get("language"),
        "origin": origin,
        "ocr_status": ocr_status,
        "ai_confidence": ai_result.get("confidence", 0.0),
        "status": "new",
        "chroma_id": chroma_id,
        "date_added": now,
        "date_modified": now,
        "sidecar_path": str(Path(current_path).with_suffix("")) + ".kylo.json",
    })
    conn.commit()
    return c.lastrowid


def update_status(conn, file_id: int, status: str):
    conn.execute(
        "UPDATE files SET status = ?, date_modified = ? WHERE id = ?",
        (status, datetime.now(timezone.utc).isoformat(), file_id),
    )
    conn.commit()


def update_wiki_status(conn, file_id: int, wiki_status: str):
    conn.execute(
        "UPDATE files SET wiki_status = ? WHERE id = ?",
        (wiki_status, file_id),
    )
    conn.commit()


def _detect_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    type_map = {
        ".pdf": "pdf",
        ".doc": "docx", ".docx": "docx",
        ".xls": "xlsx", ".xlsx": "xlsx",
        ".ppt": "pptx", ".pptx": "pptx",
        ".odt": "odt", ".ods": "ods", ".odp": "odp",
        ".csv": "csv",
        ".md": "md",
        ".txt": "txt", ".rtf": "txt",
        ".jpg": "image", ".jpeg": "image", ".png": "image",
        ".gif": "image", ".webp": "image", ".bmp": "image", ".tiff": "image",
        ".py": "code", ".js": "code", ".ts": "code",
        ".html": "code", ".css": "code", ".json": "code", ".yaml": "code",
    }
    return type_map.get(ext, "other")
