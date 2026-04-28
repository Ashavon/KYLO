import json
import logging
from fastapi import APIRouter, HTTPException
from backend.db.database import get_connection

log = logging.getLogger(__name__)
router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
def list_tags():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name, color, count FROM tags ORDER BY count DESC")
    tags = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"tags": tags}


@router.post("/{file_id}")
def add_tag(file_id: int, payload: dict):
    tag_name = payload.get("tag", "").strip().lower()
    source = payload.get("source", "user")
    if not tag_name:
        raise HTTPException(status_code=400, detail="tag required")

    conn = get_connection()
    c = conn.cursor()

    # Upsert tag
    c.execute("INSERT OR IGNORE INTO tags (name, count) VALUES (?, 0)", (tag_name,))
    c.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
    tag_row = c.fetchone()
    tag_id = tag_row["id"]

    # Link to file
    c.execute(
        "INSERT OR IGNORE INTO file_tags (file_id, tag_id, source) VALUES (?, ?, ?)",
        (file_id, tag_id, source),
    )

    # Update tags JSON array on the file record
    c.execute("SELECT tags FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")

    current_tags = json.loads(row["tags"] or "[]")
    if tag_name not in current_tags:
        current_tags.append(tag_name)
        conn.execute("UPDATE files SET tags = ? WHERE id = ?", (json.dumps(current_tags), file_id))

    conn.execute("UPDATE tags SET count = count + 1 WHERE name = ?", (tag_name,))
    conn.commit()
    conn.close()
    return {"status": "added", "tag": tag_name}


@router.delete("/{file_id}/{tag_name}")
def remove_tag(file_id: int, tag_name: str):
    tag_name = tag_name.lower()
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
    tag_row = c.fetchone()
    if not tag_row:
        conn.close()
        return {"status": "not_found"}

    conn.execute(
        "DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?",
        (file_id, tag_row["id"]),
    )

    c.execute("SELECT tags FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    if row:
        current_tags = json.loads(row["tags"] or "[]")
        current_tags = [t for t in current_tags if t != tag_name]
        conn.execute("UPDATE files SET tags = ? WHERE id = ?", (json.dumps(current_tags), file_id))

    conn.execute("UPDATE tags SET count = MAX(0, count - 1) WHERE name = ?", (tag_name,))
    conn.commit()
    conn.close()
    return {"status": "removed", "tag": tag_name}
