import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def send_to_wiki(
    file_path: Path,
    subject: Optional[str],
    pkm_wiki_path: str,
    shared_path: Optional[str] = None,
) -> bool:
    """
    Copy processed file to {pkm_wiki_path}/raw/{subject}/ and log to ingest queue.
    Returns True on success.
    """
    if not pkm_wiki_path:
        return False

    wiki_root = Path(pkm_wiki_path)
    if not wiki_root.exists():
        log.warning("PKM wiki path does not exist: %s", wiki_root)
        return False

    subject_dir = wiki_root / "raw" / (subject or "Unsorted")
    subject_dir.mkdir(parents=True, exist_ok=True)

    dest = subject_dir / file_path.name
    try:
        shutil.copy2(str(file_path), str(dest))
    except Exception as e:
        log.error("Failed to copy to PKM wiki: %s", e)
        return False

    # Write to shared ingest queue
    queue_path = _get_queue_path(pkm_wiki_path, shared_path)
    _append_queue_entry(queue_path, file_path.name)

    log.info("Sent %s to PKM wiki at %s", file_path.name, dest)
    return True


def _get_queue_path(pkm_wiki_path: str, shared_path: Optional[str]) -> Path:
    if shared_path:
        shared = Path(shared_path)
        shared.mkdir(parents=True, exist_ok=True)
        return shared / "ingest_queue.md"
    return Path(pkm_wiki_path) / "logs" / "ingest_queue.md"


def _append_queue_entry(queue_path: Path, filename: str):
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"- [{now}] {filename} → ingested by KYLO, ready for wiki processing\n"
    try:
        with open(str(queue_path), "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        log.error("Failed to write ingest queue: %s", e)
