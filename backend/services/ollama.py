import json
import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_BASE_URL = "http://localhost:11434"
_TIMEOUT = 120.0


def _base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", _BASE_URL)


def is_available() -> bool:
    try:
        r = httpx.get(f"{_base_url()}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def generate(prompt: str, model: str, system: Optional[str] = None) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    try:
        r = httpx.post(
            f"{_base_url()}/api/generate",
            json=payload,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        log.error("Ollama generate error: %s", e)
        return ""


def generate_vision(prompt: str, model: str, image_b64: str, system: Optional[str] = None) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }
    if system:
        payload["system"] = system
    try:
        r = httpx.post(
            f"{_base_url()}/api/generate",
            json=payload,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        log.error("Ollama vision error: %s", e)
        return ""


def embed(text: str, model: str) -> list[float]:
    payload = {"model": model, "prompt": text}
    try:
        r = httpx.post(
            f"{_base_url()}/api/embeddings",
            json=payload,
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json().get("embedding", [])
    except Exception as e:
        log.error("Ollama embed error: %s", e)
        return []


def classify_file(content_preview: str, model: str, image_b64: Optional[str] = None) -> dict:
    """
    Sends file content to Ollama with the KYLO classification prompt.
    Returns parsed JSON dict or empty dict on failure.
    """
    system = (
        "You are KYLO, an expert personal document intelligence system.\n"
        "Analyze the file content provided and return ONLY a valid JSON object with these fields:\n"
        "{\n"
        '  "subject": "Primary topic category (e.g. Tax, Health, Work, Finance, Travel, Legal, Personal)",\n'
        '  "what": "What the document IS (e.g. Tax-Return, Blood-Test, Invoice, Contract, Report)",\n'
        '  "where": "Location or organization context. Use None if unknown.",\n'
        '  "who": "Person or entity name. Use None if unknown.",\n'
        '  "when": "Date in YYYY, YYYY-MM, or YYYY-MM-DD format. Use None if unknown.",\n'
        '  "summary": "One paragraph (max 150 words) describing what this document contains.",\n'
        '  "tags": ["array", "of", "3-7", "relevant", "lowercase", "tags"],\n'
        '  "confidence": 0.0\n'
        "}\n"
        "No markdown, no explanation. Only the JSON object."
    )

    if image_b64:
        raw = generate_vision(
            prompt=f"Analyze this image and classify the document. {content_preview[:500] if content_preview.strip() else 'Describe what you see and extract any text.'}",
            model=model,
            image_b64=image_b64,
            system=system,
        )
    else:
        raw = generate(
            prompt=f"Classify this file:\n\n{content_preview[:4000]}",
            model=model,
            system=system,
        )

    return _parse_json_response(raw)


def answer_query(question: str, context_chunks: list[dict], model: str) -> dict:
    """
    Builds a RAG prompt and returns {answer, citations}.
    context_chunks: list of {filename, text}
    """
    docs_block = "\n\n".join(
        f"[{i+1}] {c['filename']}:\n{c['text']}" for i, c in enumerate(context_chunks)
    )
    prompt = (
        "You are KYLO, a personal knowledge assistant. "
        "Answer the user's question using ONLY the document excerpts provided below. "
        "If the answer isn't in the documents, say so. "
        "Always cite which file(s) your answer comes from.\n\n"
        f"DOCUMENTS:\n{docs_block}\n\n"
        f"USER QUESTION: {question}"
    )
    answer = generate(prompt=prompt, model=model)
    citations = [c["filename"] for c in context_chunks]
    return {"answer": answer, "citations": citations}


def _parse_json_response(raw: str) -> dict:
    if not raw:
        return {}
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except Exception:
                pass
    log.warning("Could not parse Ollama JSON response: %s", raw[:200])
    return {}
