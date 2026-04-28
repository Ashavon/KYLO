import re
from pathlib import Path
from typing import Optional


_SEGMENT_RE = re.compile(r"^\[([^\]]+)\]$")
_VALID_NAME_RE = re.compile(
    r"^\[([A-Za-z][A-Za-z0-9\-]*)\]"         # [Subject]
    r"_\[([A-Za-z][A-Za-z0-9\-]*)\]"          # _[What]
    r"(?:_\[([A-Za-z][A-Za-z0-9\-]*)\])?"     # _[Where] optional
    r"(?:_\[([A-Za-z][A-Za-z0-9\-]*)\])?"     # _[Who] optional
    r"(?:_\[(\d{4}(?:-\d{2}(?:-\d{2})?)?|"   # _[When] YYYY or YYYY-MM or YYYY-MM-DD
    r"\d{4}-Q[1-4])\])?"                        # or YYYY-QN
    r"\.[a-zA-Z0-9]+$"
)


def build_name(subject: str, what: str, where: Optional[str], who: Optional[str],
               when: Optional[str], extension: str) -> str:
    """
    Assemble a KYLO filename from its five segments.
    Segments that are None/empty/'None' are omitted.
    """
    def clean(val: Optional[str]) -> Optional[str]:
        if not val or val.strip().lower() in ("none", "unknown", "n/a", ""):
            return None
        val = val.strip()
        val = re.sub(r"\s+", "-", val)
        val = re.sub(r"[^A-Za-z0-9\-]", "", val)
        return val if val else None

    subject_clean = clean(subject) or "Unknown"
    what_clean = clean(what) or "Document"

    parts = [f"[{subject_clean}]", f"[{what_clean}]"]
    for seg in (where, who, when):
        val = clean(seg)
        if val:
            parts.append(f"[{val}]")

    ext = extension if extension.startswith(".") else f".{extension}"
    return "_".join(parts) + ext


def parse_name(filename: str) -> Optional[dict]:
    """
    Parse a KYLO filename back into its segment dict.
    Returns None if the filename does not match the convention.
    """
    name = Path(filename).stem
    ext = Path(filename).suffix
    segments = name.split("_")
    parsed = {"subject": None, "what": None, "where": None, "who": None, "when": None, "ext": ext}
    keys = ["subject", "what", "where", "who", "when"]
    for i, seg in enumerate(segments[:5]):
        m = _SEGMENT_RE.match(seg)
        if m:
            parsed[keys[i]] = m.group(1)
    if parsed["subject"] and parsed["what"]:
        return parsed
    return None


def is_kylo_name(filename: str) -> bool:
    return _VALID_NAME_RE.match(filename) is not None


def ai_result_to_name(ai_result: dict, original_path: Path) -> str:
    """Convert an Ollama classification result to a KYLO filename."""
    ext = original_path.suffix
    return build_name(
        subject=ai_result.get("subject"),
        what=ai_result.get("what"),
        where=ai_result.get("where"),
        who=ai_result.get("who"),
        when=ai_result.get("when"),
        extension=ext,
    )
