# KYLO — Installation Guide

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.10+ | https://python.org — check "Add to PATH" during install |
| Ollama | https://ollama.com — for AI features |
| Tesseract OCR (optional) | For scanned PDF support |

---

## Quick Start (Windows)

1. **Clone or download** this repository to your drive:
   ```
   git clone <repo-url> D:\KYLO
   ```
   Or extract the ZIP to `D:\KYLO`.

2. **Create the `_DRIVE_HOME` marker** at the root of the drive you want to use:
   ```
   echo. > D:\_DRIVE_HOME
   ```
   This tells KYLO where the drive root is (so it works even if the drive letter changes).

3. **Double-click `start.bat`**

   On first run it will:
   - Create a shared Python virtual environment at `D:\_env\`
   - Install all Python dependencies (~2–3 minutes)
   - Open KYLO in your browser at http://localhost:8765

4. **Pull the Ollama AI models** (first time only, ~3 GB):
   ```
   ollama pull gemma3:4b
   ollama pull nomic-embed-text
   ```

That's it. Every subsequent launch is just `start.bat`.

---

## Quick Start (macOS / Linux)

```bash
git clone <repo-url> ~/KYLO
echo "" > ~/_DRIVE_HOME      # or wherever you want the drive root
cd ~/KYLO
chmod +x start.sh
./start.sh
```

---

## Installing Tesseract OCR (optional)

Tesseract enables text extraction from scanned PDFs and images.

**Windows:**
Download the installer from:
https://github.com/UB-Mannheim/tesseract/wiki

After installing, add Tesseract to your PATH (the installer can do this automatically).

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt install tesseract-ocr
```

---

## External Drive Setup

KYLO is designed to live on an external drive alongside a PKM Wiki:

```
/ExternalDrive/
├── _DRIVE_HOME          ← create this empty marker file once
├── _env/                ← shared Python venv (auto-created on first run)
├── KYLO/                ← this project
│   ├── start.bat
│   ├── start.sh
│   └── ...
└── PKM_WIKI/            ← optional companion wiki
```

All paths in `config.json` are relative, so KYLO works regardless of which drive letter Windows assigns on a new machine.

---

## Configuration

Edit `config.json` in the project root (or use the Settings page in the UI):

| Key | Default | Description |
|---|---|---|
| `ollama_text_model` | `gemma3:4b` | Model for classification and querying |
| `ollama_embed_model` | `nomic-embed-text` | Model for semantic search embeddings |
| `pkm_wiki_path` | `../PKM_WIKI` | Path to your PKM wiki vault |
| `auto_approve_naming` | `false` | Skip the approval step on ingest |
| `semantic_dedup_threshold` | `0.92` | Cosine similarity cutoff for near-duplicate detection |
| `port` | `8765` | Port the web UI listens on |

---

## Troubleshooting

**"Ollama not connected" banner in UI**
Ollama isn't running. Start it, then reload the page. AI features (naming, querying) are disabled without it; browsing, OCR, and undo still work.

**Port already in use**
`start.bat` kills any existing process on port 8765 automatically. If it persists, run:
```
netstat -ano | findstr :8765
taskkill /PID <PID> /F
```

**Venv creation fails (Windows)**
If `D:\_env` can't be created, try running `start.bat` as Administrator once. The venv is created once and reused forever.

**Scanned PDFs show no text**
Install Tesseract (see above). If already installed, ensure it's on your PATH:
```
tesseract --version
```

**ChromaDB / embedding errors**
Ensure the `nomic-embed-text` model is pulled:
```
ollama pull nomic-embed-text
```

---

## Stopping KYLO

Press `Ctrl+C` in the terminal window, or close the terminal.
