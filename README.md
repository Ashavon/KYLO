# KYLO — Know Your Local Objects

A local-first personal file intelligence system. 100% local. Zero external API calls.

## Quick Start

**Windows:** Double-click `start.bat`  
**macOS/Linux:** `bash start.sh`

Then open http://localhost:8765

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) (for AI features)
- Tesseract OCR (optional, for scanned PDFs)

### Install Ollama models (once):
```
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

### Install Tesseract (Windows):
Download from https://github.com/UB-Mannheim/tesseract/wiki

## Usage

1. Drop files into `data/inbox/` OR drag them into the UI
2. KYLO extracts content, classifies it with AI, and proposes a name
3. Review and approve the proposed name and tags
4. File moves to `data/library/` with a `.kylo.json` sidecar

## Naming Convention

```
[Subject]_[What]_[Where]_[Who]_[When].ext
```

Example: `[Tax]_[Tax-Return]_[Canada]_[Self]_[2025].pdf`

## Configuration

Edit `config.json` to change paths, Ollama models, and thresholds.

## External Drive Portability

KYLO is designed to live on an external drive. All paths in `config.json` are relative.
The launcher auto-detects the drive root via the `_DRIVE_HOME` marker file.
