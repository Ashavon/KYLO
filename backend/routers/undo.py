import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

log = logging.getLogger(__name__)
router = APIRouter(prefix="/undo", tags=["undo"])

_UNDO_LOG = Path(__file__).parent.parent.parent / "logs" / "kylo_undo.json"
_SESSION_ID: str = ""
_CURRENT_SESSION: dict = {}


def _init_session():
    global _SESSION_ID, _CURRENT_SESSION
    _SESSION_ID = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _CURRENT_SESSION = {
        "id": _SESSION_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operations": [],
        "status": "open",
    }


def append_operation(op: dict):
    """Append an operation to the current session in the undo log."""
    if not _SESSION_ID:
        _init_session()
    _CURRENT_SESSION["operations"].append(op)
    _flush_log()


def _flush_log():
    _UNDO_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_data = _load_log()
    # Update or insert current session
    sessions = log_data.get("sessions", [])
    for i, s in enumerate(sessions):
        if s["id"] == _SESSION_ID:
            sessions[i] = _CURRENT_SESSION
            break
    else:
        sessions.append(_CURRENT_SESSION)
    log_data["sessions"] = sessions[-200:]  # Keep last 200 sessions
    with open(str(_UNDO_LOG), "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)


def _load_log() -> dict:
    if _UNDO_LOG.exists():
        try:
            with open(str(_UNDO_LOG), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sessions": []}


@router.get("")
def get_undo_log(limit: int = 20):
    log_data = _load_log()
    sessions = log_data.get("sessions", [])
    recent = sessions[-limit:][::-1]  # Most recent first
    return {"sessions": recent, "total": len(sessions)}


@router.post("/session/{session_id}/revert")
def revert_session(session_id: str):
    log_data = _load_log()
    sessions = log_data.get("sessions", [])
    session = next((s for s in sessions if s["id"] == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    ops = list(reversed(session.get("operations", [])))
    results = []
    for op in ops:
        if not op.get("reversible"):
            results.append({"op": op, "status": "skipped_not_reversible"})
            continue
        try:
            _revert_operation(op)
            results.append({"op": op, "status": "reverted"})
        except Exception as e:
            results.append({"op": op, "status": "failed", "error": str(e)})

    # Mark session as reverted
    for s in sessions:
        if s["id"] == session_id:
            s["status"] = "reverted"
    log_data["sessions"] = sessions
    with open(str(_UNDO_LOG), "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

    return {"status": "reverted", "results": results}


@router.post("/operation/revert")
def revert_single_operation(payload: dict):
    op = payload.get("operation")
    if not op:
        raise HTTPException(status_code=400, detail="operation required")
    if not op.get("reversible"):
        raise HTTPException(status_code=400, detail="Operation is not reversible")
    try:
        _revert_operation(op)
        return {"status": "reverted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _revert_operation(op: dict):
    op_type = op.get("op")
    original = op.get("original_path")
    new = op.get("new_path")

    if op_type in ("rename", "move", "bin"):
        # Move new_path back to original_path
        src = Path(new)
        dest = Path(original)
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            # Update DB
            _update_db_path(str(new), str(dest))
        else:
            raise FileNotFoundError(f"File not found at reverted path: {src}")

    elif op_type == "restore":
        # Move back to bin
        src = Path(new)
        dest = Path(original)
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            _update_db_path(str(new), str(dest))


def _update_db_path(old_path: str, new_path: str):
    from backend.db.database import get_connection
    conn = get_connection()
    conn.execute(
        "UPDATE files SET current_path = ?, current_name = ?, date_modified = ? WHERE current_path = ?",
        (new_path, Path(new_path).name, datetime.now(timezone.utc).isoformat(), old_path),
    )
    conn.commit()
    conn.close()


# Initialize session on import
_init_session()
