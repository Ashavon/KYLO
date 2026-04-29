import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.db.database import get_connection, row_to_dict

log = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])

_CONFIG: dict = {}


def set_config(cfg: dict):
    global _CONFIG
    _CONFIG = cfg


def _library_path() -> Path:
    return Path(_CONFIG.get("library_path", "./data/library"))


@router.get("")
def list_files(
    subject: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    starred: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    conn = get_connection()
    c = conn.cursor()

    clauses = ["status != 'binned'"]  # never show binned files in library
    params = []
    if subject:
        clauses.append("subject = ?")
        params.append(subject)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if starred is not None:
        clauses.append("starred = ?")
        params.append(1 if starred else 0)
    if search:
        clauses.append("(current_name LIKE ? OR summary LIKE ? OR tags LIKE ?)")
        s = f"%{search}%"
        params += [s, s, s]
    if tag:
        clauses.append("tags LIKE ?")
        params.append(f'%"{tag}"%')

    where = " AND ".join(clauses)
    c.execute(
        f"SELECT * FROM files WHERE {where} ORDER BY date_added DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    rows = [row_to_dict(r) for r in c.fetchall()]

    c.execute(f"SELECT COUNT(*) FROM files WHERE {where}", params)
    total = c.fetchone()[0]
    conn.close()

    return {"files": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/subjects")
def get_subjects():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT subject, COUNT(*) as count FROM files WHERE subject IS NOT NULL AND status != 'binned' GROUP BY subject ORDER BY count DESC")
    subjects = [{"subject": r["subject"], "count": r["count"]} for r in c.fetchall()]
    conn.close()
    return {"subjects": subjects}


@router.get("/{file_id}")
def get_file(file_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    return row_to_dict(row)


@router.get("/{file_id}/preview")
def preview_file(file_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT current_path, file_type FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    path = Path(row["current_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(path))


@router.put("/{file_id}/rename")
def rename_file(file_id: int, payload: dict):
    new_name = payload.get("new_name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="new_name required")

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT current_path, current_name FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")

    old_path = Path(row["current_path"])
    new_path = old_path.parent / new_name

    if new_path.exists() and new_path != old_path:
        conn.close()
        raise HTTPException(status_code=409, detail="A file with that name already exists")

    # Log to undo BEFORE rename
    from backend.routers.undo import append_operation
    append_operation({
        "op": "rename",
        "original_path": str(old_path),
        "new_path": str(new_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reversible": True,
    })

    old_path.rename(new_path)

    # Update sidecar path
    old_sidecar = old_path.with_suffix("").parent / (old_path.stem + ".kylo.json")
    new_sidecar = new_path.with_suffix("").parent / (new_path.stem + ".kylo.json")
    if old_sidecar.exists():
        old_sidecar.rename(new_sidecar)

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE files SET current_name = ?, current_path = ?, sidecar_path = ?, date_modified = ? WHERE id = ?",
        (new_name, str(new_path), str(new_sidecar), now, file_id),
    )
    conn.commit()
    conn.close()

    return {"status": "renamed", "new_name": new_name, "new_path": str(new_path)}


@router.put("/{file_id}/star")
def toggle_star(file_id: int, payload: dict):
    starred = 1 if payload.get("starred") else 0
    conn = get_connection()
    conn.execute("UPDATE files SET starred = ? WHERE id = ?", (starred, file_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "starred": bool(starred)}


@router.put("/{file_id}/note")
def update_note(file_id: int, payload: dict):
    note = payload.get("note", "")
    conn = get_connection()
    conn.execute("UPDATE files SET user_note = ? WHERE id = ?", (note, file_id))
    conn.commit()

    # Also update sidecar
    c = conn.cursor()
    c.execute("SELECT sidecar_path FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    conn.close()
    if row and row["sidecar_path"]:
        sidecar = Path(row["sidecar_path"])
        if sidecar.exists():
            try:
                with open(str(sidecar), "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["user_note"] = note
                with open(str(sidecar), "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass
    return {"status": "ok"}


@router.post("/{file_id}/bin")
def move_to_bin(file_id: int):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")

        file_data = row_to_dict(row)
        if file_data.get("status") == "binned":
            raise HTTPException(status_code=400, detail="File is already in the bin")

        original_path = file_data["current_path"]
        src = Path(original_path)

        bin_dir = Path(_CONFIG.get("duplicates_bin_path", "./data/duplicates_bin")).resolve()
        bin_dir.mkdir(parents=True, exist_ok=True)

        dest = bin_dir / src.name
        counter = 1
        while dest.exists():
            dest = bin_dir / f"{src.stem}_{counter}{src.suffix}"
            counter += 1

        # Log to undo BEFORE moving
        from backend.routers.undo import append_operation
        append_operation({
            "op": "bin",
            "original_path": str(src),
            "new_path": str(dest),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reversible": True,
        })

        # Move the file
        if src.exists():
            shutil.move(str(src), str(dest))
        else:
            log.warning("move_to_bin: source file not found on disk: %s (continuing with DB update)", src)

        # Also move the sidecar if present
        sidecar_src = src.with_suffix("").parent / (src.stem + ".kylo.json")
        if sidecar_src.exists():
            sidecar_dest = dest.parent / (dest.stem + ".kylo.json")
            shutil.move(str(sidecar_src), str(sidecar_dest))

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE files SET status = 'binned', current_path = ?, date_modified = ? WHERE id = ?",
            (str(dest), now, file_id),
        )
        conn.execute(
            """INSERT INTO duplicates_bin (file_id, original_path, bin_path, date_binned)
               VALUES (?, ?, ?, ?)""",
            (file_id, original_path, str(dest), now),
        )
        conn.commit()
        return {"status": "binned", "bin_path": str(dest)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("move_to_bin failed for file_id=%s: %s", file_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not move to bin: {e}")
    finally:
        conn.close()


@router.post("/{file_id}/send_to_wiki")
def send_to_wiki_endpoint(file_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    file_data = row_to_dict(row)
    from backend.services.pkm import send_to_wiki
    success = send_to_wiki(
        file_path=Path(file_data["current_path"]),
        subject=file_data.get("subject"),
        pkm_wiki_path=_CONFIG.get("pkm_wiki_path", ""),
        shared_path=_CONFIG.get("shared_path"),
    )
    if success:
        conn = get_connection()
        from backend.services.indexer import update_wiki_status
        update_wiki_status(conn, file_id, "in_wiki")
        conn.close()
    return {"status": "sent" if success else "failed"}
