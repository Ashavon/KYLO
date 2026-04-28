import logging
from fastapi import APIRouter, HTTPException
from backend.services.ollama import embed, answer_query, is_available as ollama_available
from backend.services.embedder import query as chroma_query
from backend.db.database import get_connection, row_to_dict

log = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])

_CONFIG: dict = {}


def set_config(cfg: dict):
    global _CONFIG
    _CONFIG = cfg


@router.post("")
def natural_language_query(payload: dict):
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question required")

    top_k = payload.get("top_k", 5)

    if not ollama_available():
        return {
            "answer": "AI features are not available because Ollama is not running. "
                      "Please install Ollama and pull the required models. See README.md.",
            "citations": [],
            "chunks_used": 0,
        }

    embed_model = _CONFIG.get("ollama_embed_model", "nomic-embed-text")
    query_embedding = embed(question, embed_model)

    if not query_embedding:
        return {
            "answer": "Could not generate embedding for your question. "
                      "Is the nomic-embed-text model pulled in Ollama?",
            "citations": [],
            "chunks_used": 0,
        }

    # Search ChromaDB
    results = chroma_query(query_embedding, n_results=top_k)

    if not results:
        return {
            "answer": "No relevant documents found in your knowledge base. "
                      "Try ingesting some files first.",
            "citations": [],
            "chunks_used": 0,
        }

    # Build context chunks
    chunks = []
    for r in results:
        meta = r.get("metadata", {})
        chunks.append({
            "filename": meta.get("filename", r["id"]),
            "text": r.get("text", ""),
            "similarity": r.get("similarity", 0.0),
            "path": meta.get("path", ""),
        })

    # Get file IDs for citation enrichment
    conn = get_connection()
    enriched_citations = []
    for chunk in chunks:
        c = conn.cursor()
        c.execute("SELECT id, current_name, subject FROM files WHERE current_name = ?", (chunk["filename"],))
        row = c.fetchone()
        if row:
            enriched_citations.append({
                "file_id": row["id"],
                "filename": row["current_name"],
                "subject": row["subject"],
                "similarity": chunk["similarity"],
            })
        else:
            enriched_citations.append({
                "file_id": None,
                "filename": chunk["filename"],
                "subject": None,
                "similarity": chunk["similarity"],
            })
    conn.close()

    text_model = _CONFIG.get("ollama_text_model", "gemma3:4b")
    result = answer_query(question, chunks, text_model)

    return {
        "answer": result.get("answer", ""),
        "citations": enriched_citations,
        "chunks_used": len(chunks),
    }
