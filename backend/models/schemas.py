from typing import Optional, List
from pydantic import BaseModel


class FileRecord(BaseModel):
    id: int
    original_name: str
    current_name: str
    current_path: str
    md5_hash: Optional[str] = None
    subject: Optional[str] = None
    what: Optional[str] = None
    where_field: Optional[str] = None
    who: Optional[str] = None
    when_field: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = []
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    row_count: Optional[int] = None
    dimensions: Optional[str] = None
    language: Optional[str] = None
    origin: str = "imported"
    ocr_status: str = "pending"
    ai_confidence: float = 0.0
    status: str = "new"
    starred: bool = False
    user_note: Optional[str] = None
    wiki_status: str = "not_sent"
    date_added: Optional[str] = None
    date_modified: Optional[str] = None
    related_files: List[str] = []


class IngestResponse(BaseModel):
    status: str
    inbox_path: str
    original_name: str
    proposed_name: str
    subject: Optional[str] = None
    what: Optional[str] = None
    where: Optional[str] = None
    who: Optional[str] = None
    when: Optional[str] = None
    summary: str = ""
    tags: List[str] = []
    confidence: float = 0.0
    duplicates: list = []


class QueryResponse(BaseModel):
    answer: str
    citations: list = []
    chunks_used: int = 0
