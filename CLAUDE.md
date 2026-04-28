# CLAUDE.md — KYLO Project Guide

## What KYLO Is

KYLO (Know Your Local Objects) is a local-first personal file intelligence system. It combines:
- **OCR** via Tesseract for scanned documents
- **AI classification** via Ollama (gemma3:4b) for auto-naming and tagging
- **Semantic search** via ChromaDB + nomic-embed-text embeddings
- **Duplicate detection** at 4 levels (MD5, text hash, semantic similarity, perceptual hash)
- **Natural language querying** (RAG over local documents)

All processing is 100% local. No file content ever leaves the machine.

## Architecture

```
backend/
  main.py          — FastAPI app, mounts routers, serves frontend
  routers/
    ingest.py      — Full pipeline: extract → AI classify → dedup check → approve → commit
    files.py       — File listing, search, rename, star, note, bin, wiki
    duplicates.py  — Bin management, restore, permanent delete, merge
    query.py       — RAG: embed query → ChromaDB search → Ollama answer
    tags.py        — Tag CRUD linked to files
    undo.py        — Session-based undo log, per-session revert
  services/
    extractor.py   — Content extraction for all supported file types
    ocr.py         — Tesseract wrapper (ocr_image_file, ocr_pdf_page)
    ollama.py      — Ollama API client (generate, embed, classify_file, answer_query)
    namer.py       — KYLO naming convention: build_name(), parse_name(), is_kylo_name()
    embedder.py    — ChromaDB wrapper (upsert, query, delete, find_similar)
    dedup.py       — md5_file, text_hash, phash_image, check_duplicates
    indexer.py     — SQLite index_file(), update_status(), update_wiki_status()
    pkm.py         — Copy file to PKM wiki raw/ and append to ingest_queue.md
  db/
    database.py    — SQLite init_db(), get_connection(), row_to_dict()
    kylo.db        — Auto-created SQLite database
  models/
    schemas.py     — Pydantic models for API responses
frontend/
  index.html       — App shell (Bootstrap 5 + Google Fonts)
  css/             — main.css, layout.css, cards.css, duplicates.css, query.css
  js/              — api.js, app.js, explorer.js, preview.js, rename.js,
                     duplicates.js, query.js, tags.js, undo.js
```

## Running the Backend

```bash
# From project root (with venv active):
python backend/main.py
# → serves at http://localhost:8765
```

Or use the launchers: `start.bat` (Windows) / `start.sh` (macOS/Linux).

## Adding a New File Type Parser

1. Open `backend/services/extractor.py`
2. Add the extension to the appropriate set at the top
3. Write a `_extract_<type>()` function following the existing pattern
4. Call it in the `extract()` dispatch function

## Adding a New Ollama Model

1. Edit `config.json` — change `ollama_text_model`, `ollama_vision_model`, or `ollama_embed_model`
2. Or edit via the Settings page in the UI
3. No code changes needed — the model name is passed through `backend/services/ollama.py`

## Undo Log Replay

The undo log is at `logs/kylo_undo.json`. Structure:
```json
{"sessions": [{"id": "...", "operations": [...], "status": "open|committed|reverted"}]}
```

Via API: `POST /undo/session/{session_id}/revert`  
Via UI: ↩️ button in header → "Revert all" for a session.

## Database Schema

Defined in `backend/db/database.py` → `init_db()`.

Key tables:
- `files` — all indexed files with metadata, AI results, hashes
- `duplicates_bin` — soft-deleted files with original and bin paths
- `tags` + `file_tags` — tag dictionary and file↔tag links
- `related_files` — manual or AI-detected file relationships

## Common Maintenance Tasks

**Re-index a file:** DELETE the row from `files` by `current_path`, then POST to `/ingest/process/{filename}` (move the file back to inbox first).

**Clear ChromaDB:** delete `data/chroma/` directory and restart. The next ingest will rebuild it.

**Reset the DB:** delete `backend/db/kylo.db` and restart. `init_db()` recreates the schema.

**Check Ollama models available:**
```bash
curl http://localhost:11434/api/tags
```

**Pull required models:**
```bash
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

## External Drive Portability

All paths in `config.json` are relative to the KYLO project root. The launcher detects the drive root via `_DRIVE_HOME` marker and sets `KYLO_DRIVE_ROOT` env var. `backend/main.py` resolves paths via `resolve_path()`.

## Naming Convention

`[Subject]_[What]_[Where]_[Who]_[When].ext`

- Square brackets are literal characters in the filename
- Segments use Title-Case with hyphens (no spaces)
- Optional segments (Where, Who, When) are omitted when unknown — never write `[None]`
- See `backend/services/namer.py` for `build_name()` and `parse_name()`
