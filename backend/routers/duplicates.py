import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.db.database import get_connection, row_to_dict

log = logging.getLogger(__name__)
router = APIRouter(prefix="/duplicates", tags=["duplicates"])

_CONFIG: dict = {}


def set_config(cfg: dict):
    global _CONFIG
    _CONFIG = cfg


@router.get("/bin")
def list_bin():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT db.*, f.current_name, f.subject, f.summary, f.file_type, f.ai_confidence
        FROM duplicates_bin db
        LEFT JOIN files f ON db.file_id = f.id
        ORDER BY db.date_binned DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"bin": rows}


@router.post("/bin/{bin_id}/restore")
def restore_from_bin(bin_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM duplicates_bin WHERE id = ?", (bin_id,))
    bin_row = c.fetchone()
    if not bin_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Bin entry not found")

    bin_data = dict(bin_row)
    bin_path = Path(bin_data["bin_path"])
    original_path = Path(bin_data["original_path"])

    if not bin_path.exists():
        conn.close()
        raise HTTPException(status_code=404, detail="File not found in bin")

    original_path.parent.mkdir(parents=True, exist_ok=True)
    dest = original_path
    counter = 1
    while dest.exists():
        dest = original_path.parent / f"{original_path.stem}_{counter}{original_path.suffix}"
        counter += 1

    from backend.routers.undo import append_operation
    append_operation({
        "op": "restore",
        "original_path": str(bin_path),
        "new_path": str(dest),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reversible": True,
    })

    shutil.move(str(bin_path), str(dest))

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE files SET status = 'new', current_path = ?, date_modified = ? WHERE id = ?",
        (str(dest), now, bin_data["file_id"]),
    )
    conn.execute("DELETE FROM duplicates_bin WHERE id = ?", (bin_id,))
    conn.commit()
    conn.close()

    return {"status": "restored", "path": str(dest)}


@router.delete("/bin/{bin_id}")
def permanent_delete(bin_id: int, confirmed: bool = False):
    """Permanently delete a file from the bin. Requires confirmed=true."""
    if not confirmed:
        raise HTTPException(
            status_code=400,
            detail="Permanent delete requires confirmed=true. This cannot be undone."
        )

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM duplicates_bin WHERE id = ?", (bin_id,))
    bin_row = c.fetchone()
    if not bin_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Bin entry not found")

    bin_data = dict(bin_row)
    bin_path = Path(bin_data["bin_path"])
    if bin_path.exists():
        bin_path.unlink()

    conn.execute("DELETE FROM duplicates_bin WHERE id = ?", (bin_id,))
    conn.execute("DELETE FROM files WHERE id = ?", (bin_data["file_id"],))
    conn.commit()
    conn.close()

    return {"status": "permanently_deleted"}


@router.post("/merge")
def merge_files(payload: dict):
    """
    Merge two files: creates a merged .md file, soft-deletes both originals.
    payload: {file_id_a, file_id_b}
    """
    id_a = payload.get("file_id_a")
    id_b = payload.get("file_id_b")
    if not id_a or not id_b:
        raise HTTPException(status_code=400, detail="file_id_a and file_id_b required")

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id IN (?, ?)", (id_a, id_b))
    rows = {r["id"]: row_to_dict(r) for r in c.fetchall()}

    if id_a not in rows or id_b not in rows:
        conn.close()
        raise HTTPException(status_code=404, detail="One or both files not found")

    file_a = rows[id_a]
    file_b = rows[id_b]

    path_a = Path(file_a["current_path"])
    path_b = Path(file_b["current_path"])

    text_a = _read_text(path_a)
    text_b = _read_text(path_b)
    diff_text = _unified_diff(text_a, text_b, file_a["current_name"], file_b["current_name"])

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    merged_name = f"{Path(file_a['current_name']).stem}_MERGED.md"
    library = Path(_CONFIG.get("library_path", "./data/library"))
    merged_path = library / merged_name

    merged_content = (
        f"# MERGED: {file_a['current_name']}\n"
        f"> Merged by KYLO on {now_str}\n"
        f"> Sources: {file_a['current_name']} + {file_b['current_name']}\n\n"
        f"## Version A — {file_a['current_name']}\n{text_a}\n\n---\n\n"
        f"## Version B — {file_b['current_name']}\n{text_b}\n\n---\n\n"
        f"## Delta (Changes from A to B)\n{diff_text}\n"
    )

    with open(str(merged_path), "w", encoding="utf-8") as f:
        f.write(merged_content)

    # Soft-delete both originals
    for fid in (id_a, id_b):
        _soft_delete_to_bin(conn, fid)

    conn.close()
    return {"status": "merged", "merged_path": str(merged_path)}


def _read_text(path: Path) -> str:
    try:
        with open(str(path), "r", encoding="utf-8", errors="replace") as f:
            return f.read(8000)
    except Exception:
        return f"[Binary or unreadable file: {path.name}]"


def _unified_diff(text_a: str, text_b: str, name_a: str, name_b: str) -> str:
    import difflib
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    diff = difflib.unified_diff(lines_a, lines_b, fromfile=name_a, tofile=name_b)
    return "".join(diff) or "(no textual differences found)"


def _soft_delete_to_bin(conn, file_id: int):
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    if not row:
        return

    file_data = row_to_dict(row)
    src = Path(file_data["current_path"])
    bin_dir = Path(_CONFIG.get("duplicates_bin_path", "./data/duplicates_bin"))
    bin_dir.mkdir(parents=True, exist_ok=True)
    dest = bin_dir / src.name
    counter = 1
    while dest.exists():
        dest = bin_dir / f"{src.stem}_{counter}{src.suffix}"
        counter += 1

    if src.exists():
        shutil.move(str(src), str(dest))

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE files SET status = 'binned', current_path = ?, date_modified = ? WHERE id = ?",
        (str(dest), now, file_id),
    )
    conn.execute(
        "INSERT INTO duplicates_bin (file_id, original_path, bin_path, date_binned) VALUES (?, ?, ?, ?)",
        (file_id, file_data["current_path"], str(dest), now),
    )
    conn.commit()
