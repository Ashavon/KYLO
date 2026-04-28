import io
import logging
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False
    log.warning("pytesseract or Pillow not installed — OCR disabled")


def ocr_image_file(path: Path) -> str:
    if not _TESSERACT_AVAILABLE:
        return ""
    try:
        img = Image.open(str(path))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        log.error("OCR failed for %s: %s", path, e)
        return ""


def ocr_pdf_page(page_bytes: bytes) -> str:
    """Run OCR on raw image bytes (e.g. a rendered PDF page)."""
    if not _TESSERACT_AVAILABLE:
        return ""
    try:
        img = Image.open(io.BytesIO(page_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        log.error("OCR on page bytes failed: %s", e)
        return ""


def is_available() -> bool:
    return _TESSERACT_AVAILABLE
