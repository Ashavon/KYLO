import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_CHROMA_PATH = Path(__file__).parent.parent.parent / "data" / "chroma"
_COLLECTION_NAME = "kylo_documents"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        _client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        return _collection
    except Exception as e:
        log.error("ChromaDB init error: %s", e)
        return None


def upsert(file_id: str, text: str, embedding: list[float], metadata: dict) -> bool:
    col = _get_collection()
    if col is None:
        return False
    try:
        col.upsert(
            ids=[file_id],
            embeddings=[embedding],
            documents=[text[:2000]],
            metadatas=[metadata],
        )
        return True
    except Exception as e:
        log.error("ChromaDB upsert error: %s", e)
        return False


def query(embedding: list[float], n_results: int = 5) -> list[dict]:
    col = _get_collection()
    if col is None:
        return []
    try:
        results = col.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for i in range(len(results["ids"][0])):
            out.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "similarity": 1.0 - results["distances"][0][i],
            })
        return out
    except Exception as e:
        log.error("ChromaDB query error: %s", e)
        return []


def delete(file_id: str) -> bool:
    col = _get_collection()
    if col is None:
        return False
    try:
        col.delete(ids=[file_id])
        return True
    except Exception as e:
        log.error("ChromaDB delete error: %s", e)
        return False


def find_similar(embedding: list[float], threshold: float = 0.92, exclude_id: Optional[str] = None) -> list[dict]:
    results = query(embedding, n_results=10)
    similar = []
    for r in results:
        if exclude_id and r["id"] == exclude_id:
            continue
        if r["similarity"] >= threshold:
            similar.append(r)
    return similar
