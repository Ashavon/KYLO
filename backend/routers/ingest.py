import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from backend.db.database import get_connection
from backend.services import extractor, dedup, indexer
from backend.services.namer import build_name, ai_result_to_name
from backend.services.ollama import classify_file, embed, is_available as ollama_available
from backend.services.embedder import upsert as chroma_upsert
from backend.services.pkm import send_to_wiki

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

_CONFIG: dict = {}


def set_config(cfg: dict):
    global _CONFIG
    _CONFIG = cfg


def _inbox_path() -> Path:
    return Path(_CONFIG.get("inbox_path", "./data/inbox"))


def _library_path() -> Path:
    return Path(_CONFIG.get("library_path", "./data/library"))


def _bin_path() -> Path:
    return Path(_CONFIG.get("duplicates_bin_path", "./data/duplicates_bin"))


@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Receive a file upload and drop it into the inbox for processing."""
    inbox = _inbox_path()
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / file.filename
    with open(str(dest), "wb") as f:
        content = await file.read()
        f.write(content)
    background_tasks.add_task(process_inbox_file, dest)
    return {"status": "queued", "filename": file.filename, "path": str(dest)}


@router.post("/process/{filename}")
async def process_file_endpoint(filename: str):
    """Manually trigger processing of a specific inbox file."""
    inbox = _inbox_path()
    path = inbox / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found in inbox")
    result = await _run_pipeline(path)
    return result


@router.get("/inbox")
def list_inbox():
    """List all files currently in the inbox."""
    inbox = _inbox_path()
    if not inbox.exists():
        return {"files": []}
    files = []
    for f in inbox.iterdir():
        if f.is_file() and not f.name.startswith("."):
            files.append({"name": f.name, "size": f.stat().st_size, "path": str(f)})
    return {"files": files}


@router.post("/approve")
async def approve_ingest(payload: dict):
    """
    Approve (possibly edited) AI proposal and commit the file to library.
    payload: {
        inbox_path, approved_name, subject, what, where, who, when,
        summary, tags, skip_duplicate_ids
    }
    """
    inbox_file = Path(payload.get("inbox_path", ""))
    if not inbox_file.exists():
        raise HTTPException(status_code=404, detail="Inbox file not found")

    ai_result = {
        "subject": payload.get("subject"),
        "what": payload.get("what"),
        "where": payload.get("where"),
        "who": payload.get("who"),
        "when": payload.get("when"),
        "summary": payload.get("summary"),
        "tags": payload.get("tags", []),
        "confidence": payload.get("confidence", 0.0),
    }

    approved_name = payload.get("approved_name")
    if not approved_name:
        approved_name = ai_result_to_name(ai_result, inbox_file)

    result = await _commit_to_library(inbox_file, approved_name, ai_result)
    return result


async def process_inbox_file(path: Path) -> dict:
    """Full auto-pipeline (called from background task or watcher)."""
    return await _run_pipeline(path)


async def _run_pipeline(path: Path) -> dict:
    log.info("Processing: %s", path.name)

    # Step 1 — Extract content
    extraction = extractor.extract(path)
    text = extraction.get("text", "")
    image_b64 = extraction.get("image_b64")

    # Step 2 — AI classification
    ai_result = {}
    if ollama_available():
        model = _CONFIG.get("ollama_text_model", "gemma3:4b")
        ai_result = classify_file(text, model, image_b64=image_b64)
    else:
        log.warning("Ollama unavailable — skipping AI classification for %s", path.name)

    proposed_name = ai_result_to_name(ai_result, path) if ai_result else path.name

    # Step 3 — Compute hashes and embedding
    file_md5 = dedup.md5_file(path)
    t_hash = dedup.text_hash(text) if text else None

    embedding = []
    if text and ollama_available():
        embed_model = _CONFIG.get("ollama_embed_model", "nomic-embed-text")
        embedding = embed(text[:2000], embed_model)

    # Step 3b — Duplicate check
    conn = get_connection()
    duplicates_found = dedup.check_duplicates(
        path=path,
        text=text,
        embedding=embedding,
        db_conn=conn,
        embed_threshold=_CONFIG.get("semantic_dedup_threshold", 0.92),
        phash_threshold=_CONFIG.get("image_dedup_phash_threshold", 10),
    )

    # Build response for Step 4 (user approval gate)
    response = {
        "status": "pending_approval",
        "inbox_path": str(path),
        "original_name": path.name,
        "proposed_name": proposed_name,
        "subject": ai_result.get("subject"),
        "what": ai_result.get("what"),
        "where": ai_result.get("where"),
        "who": ai_result.get("who"),
        "when": ai_result.get("when"),
        "summary": ai_result.get("summary", ""),
        "tags": ai_result.get("tags", []),
        "confidence": ai_result.get("confidence", 0.0),
        "duplicates": duplicates_found,
        "extraction": {
            "method": extraction.get("method"),
            "page_count": extraction.get("page_count"),
            "word_count": extraction.get("word_count"),
            "row_count": extraction.get("row_count"),
            "dimensions": extraction.get("dimensions"),
            "language": extraction.get("language"),
        },
    }

    # Auto-approve if configured and no duplicates
    if _CONFIG.get("auto_approve_naming") and not duplicates_found:
        commit_result = await _commit_to_library(
            path, proposed_name, ai_result,
            file_md5=file_md5, t_hash=t_hash, embedding=embedding,
            extraction=extraction,
        )
        response.update(commit_result)
        response["status"] = "committed"

    conn.close()
    return response


async def _commit_to_library(
    inbox_file: Path,
    approved_name: str,
    ai_result: dict,
    file_md5: Optional[str] = None,
    t_hash: Optional[str] = None,
    embedding: Optional[list] = None,
    extraction: Optional[dict] = None,
) -> dict:
    library = _library_path()
    library.mkdir(parents=True, exist_ok=True)

    dest = library / approved_name
    # Handle name collisions
    counter = 1
    stem = dest.stem
    ext = dest.suffix
    while dest.exists():
        dest = library / f"{stem}_{counter}{ext}"
        counter += 1

    # Log to undo BEFORE moving
    _log_undo("move", str(inbox_file), str(dest))

    shutil.move(str(inbox_file), str(dest))

    # Compute hashes if not already done
    if not file_md5:
        file_md5 = dedup.md5_file(dest)
    if not t_hash and extraction:
        t_hash = dedup.text_hash(extraction.get("text", ""))
    if extraction is None:
        extraction = {}

    # Embed and index in ChromaDB
    chroma_id = str(dest.name)
    if embedding is None:
        embedding = []
    if embedding:
        upsert_meta = {
            "filename": dest.name,
            "path": str(dest),
            "subject": ai_result.get("subject", ""),
            "tags": ",".join(ai_result.get("tags", [])),
        }
        chroma_upsert(chroma_id, extraction.get("text", ""), embedding, upsert_meta)

    # Index in SQLite
    conn = get_connection()
    file_id = indexer.index_file(
        conn=conn,
        original_name=inbox_file.name,
        current_name=dest.name,
        current_path=str(dest),
        md5_hash=file_md5,
        text_hash=t_hash,
        ai_result=ai_result,
        extraction=extraction,
        origin="imported",
        ocr_status="complete" if extraction.get("method") == "ocr" else "complete",
        chroma_id=chroma_id,
    )

    # Write sidecar .kylo.json
    sidecar = dest.with_suffix("").parent / (dest.stem + ".kylo.json")
    _write_sidecar(sidecar, file_id, dest.name, ai_result, extraction)

    # PKM wiki integration
    wiki_status = "not_sent"
    if _CONFIG.get("auto_copy_to_pkm") and _CONFIG.get("pkm_wiki_path"):
        success = send_to_wiki(
            file_path=dest,
            subject=ai_result.get("subject"),
            pkm_wiki_path=_CONFIG.get("pkm_wiki_path", ""),
            shared_path=_CONFIG.get("shared_path"),
        )
        wiki_status = "in_wiki" if success else "failed"
        if success:
            indexer.update_wiki_status(conn, file_id, "in_wiki")

    conn.close()

    return {
        "status": "committed",
        "file_id": file_id,
        "committed_path": str(dest),
        "committed_name": dest.name,
        "sidecar_path": str(sidecar),
        "wiki_status": wiki_status,
    }


def _write_sidecar(path: Path, file_id: int, filename: str, ai_result: dict, extraction: dict):
    data = {
        "kylo_version": "1.0",
        "file_id": file_id,
        "filename": filename,
        "classification": ai_result,
        "extraction_method": extraction.get("method"),
        "page_count": extraction.get("page_count"),
        "word_count": extraction.get("word_count"),
        "language": extraction.get("language"),
        "user_note": "",
        "related_files": [],
        "date_indexed": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(str(path), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error("Failed to write sidecar %s: %s", path, e)


def _log_undo(op: str, original_path: str, new_path: str):
    from backend.routers.undo import append_operation
    append_operation({
        "op": op,
        "original_path": original_path,
        "new_path": new_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reversible": True,
    })
