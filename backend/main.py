import json
import logging
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.db.database import init_db
from backend.routers import ingest, files, duplicates, query, tags, undo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(PROJECT_ROOT / "logs" / "kylo_activity.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
DRIVE_ROOT = Path(os.environ.get("KYLO_DRIVE_ROOT", PROJECT_ROOT.parent))


def resolve_path(relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
CONFIG_FILE = PROJECT_ROOT / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(str(CONFIG_FILE), "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {}
    # Resolve all path fields
    for key in ("library_path", "inbox_path", "duplicates_bin_path"):
        if key in cfg:
            cfg[key] = str(resolve_path(cfg[key]))
    return cfg


CONFIG = load_config()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="KYLO", description="Know Your Local Objects — AI File Explorer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Inject config into all routers
# ---------------------------------------------------------------------------
ingest.set_config(CONFIG)
files.set_config(CONFIG)
duplicates.set_config(CONFIG)
query.set_config(CONFIG)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(ingest.router)
app.include_router(files.router)
app.include_router(duplicates.router)
app.include_router(query.router)
app.include_router(tags.router)
app.include_router(undo.router)

# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------
@app.get("/api/config")
def get_config():
    return CONFIG


@app.put("/api/config")
def update_config(payload: dict):
    global CONFIG
    CONFIG.update(payload)
    with open(str(CONFIG_FILE), "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=2)
    ingest.set_config(CONFIG)
    files.set_config(CONFIG)
    duplicates.set_config(CONFIG)
    query.set_config(CONFIG)
    return {"status": "saved"}


# ---------------------------------------------------------------------------
# AI status
# ---------------------------------------------------------------------------
@app.get("/api/status")
def get_status():
    from backend.services.ollama import is_available
    return {
        "ollama_available": is_available(),
        "ai_available": os.environ.get("KYLO_AI_AVAILABLE", "true").lower() != "false",
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# Catch-all for SPA routing
@app.get("/{path:path}")
def spa_fallback(path: str):
    # API routes are handled above; fall through to index for everything else
    static_file = FRONTEND_DIR / path
    if static_file.exists() and static_file.is_file():
        return FileResponse(str(static_file))
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Inbox watcher
# ---------------------------------------------------------------------------
def start_inbox_watcher():
    if not CONFIG.get("inbox_watch_enabled", True):
        return
    inbox = Path(CONFIG.get("inbox_path", "./data/inbox"))
    inbox.mkdir(parents=True, exist_ok=True)
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        import asyncio

        class InboxHandler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix.lower() in (".tmp", ".part", ".crdownload"):
                    return
                log.info("Inbox watcher: new file detected: %s", path.name)
                # We can't run async directly here; just log for now
                # Full async processing is triggered via the /ingest/process endpoint

        observer = Observer()
        observer.schedule(InboxHandler(), str(inbox), recursive=False)
        observer.daemon = True
        observer.start()
        log.info("Inbox watcher started on %s", inbox)
    except Exception as e:
        log.warning("Could not start inbox watcher: %s", e)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    # Ensure data dirs exist
    for key in ("library_path", "inbox_path", "duplicates_bin_path"):
        Path(CONFIG.get(key, f"./data/{key.split('_')[0]}")).mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)

    init_db()
    start_inbox_watcher()
    log.info("KYLO started. UI: http://localhost:%s", CONFIG.get("port", 8765))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(CONFIG.get("port", 8765))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
