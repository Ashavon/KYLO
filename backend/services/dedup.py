import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def text_hash(text: str) -> str:
    """Hash normalized text content (for same-content, different-format detection)."""
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def phash_image(path: Path) -> Optional[str]:
    try:
        import imagehash
        from PIL import Image
        img = Image.open(str(path))
        return str(imagehash.phash(img))
    except Exception as e:
        log.warning("pHash failed for %s: %s", path, e)
        return None


def phash_distance(hash_a: str, hash_b: str) -> int:
    try:
        import imagehash
        return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
    except Exception:
        return 999


def check_duplicates(
    path: Path,
    text: str,
    embedding: list[float],
    db_conn,
    embed_threshold: float = 0.92,
    phash_threshold: int = 10,
) -> list[dict]:
    """
    Run all four levels of duplicate detection.
    Returns list of {file_id, filename, level, score, description}
    """
    found = []
    c = db_conn.cursor()

    # Level 1: MD5 exact match
    file_md5 = md5_file(path)
    c.execute("SELECT id, current_name, current_path FROM files WHERE md5_hash = ?", (file_md5,))
    for row in c.fetchall():
        found.append({
            "file_id": row["id"],
            "filename": row["current_name"],
            "path": row["current_path"],
            "level": 1,
            "level_name": "Exact duplicate (MD5)",
            "score": 1.0,
            "description": "Byte-identical files",
        })

    if found:
        return found  # No need to check further for exact matches

    # Level 2: Normalized text hash
    if text:
        t_hash = text_hash(text)
        c.execute("SELECT id, current_name, current_path FROM files WHERE text_hash = ?", (t_hash,))
        for row in c.fetchall():
            found.append({
                "file_id": row["id"],
                "filename": row["current_name"],
                "path": row["current_path"],
                "level": 2,
                "level_name": "Content duplicate (text hash)",
                "score": 1.0,
                "description": "Same content, possibly different format",
            })

    # Level 3: Semantic similarity via ChromaDB
    if embedding:
        from backend.services.embedder import find_similar
        similar = find_similar(embedding, threshold=embed_threshold)
        for s in similar:
            meta = s.get("metadata", {})
            found.append({
                "file_id": s["id"],
                "filename": meta.get("filename", s["id"]),
                "path": meta.get("path", ""),
                "level": 3,
                "level_name": "Near-duplicate (semantic)",
                "score": round(s["similarity"], 3),
                "description": f"Cosine similarity: {s['similarity']:.1%}",
            })

    # Level 4: Visual perceptual hash (images only)
    suffix = path.suffix.lower()
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    if suffix in image_exts:
        new_phash = phash_image(path)
        if new_phash:
            c.execute("SELECT id, current_name, current_path, text_hash FROM files WHERE file_type LIKE 'image%'")
            for row in c.fetchall():
                stored_phash = row["text_hash"]  # We repurpose text_hash for images
                if stored_phash:
                    dist = phash_distance(new_phash, stored_phash)
                    if dist <= phash_threshold:
                        score = max(0.0, 1.0 - dist / 64.0)
                        found.append({
                            "file_id": row["id"],
                            "filename": row["current_name"],
                            "path": row["current_path"],
                            "level": 4,
                            "level_name": "Visual duplicate (pHash)",
                            "score": round(score, 3),
                            "description": f"Perceptual hash distance: {dist}",
                        })

    return found
