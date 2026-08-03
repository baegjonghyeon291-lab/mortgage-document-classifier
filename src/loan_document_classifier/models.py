from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class DocumentType(StrEnum):
    URLA_1003 = "URLA_1003"
    INCOME_DOC = "INCOME_DOC"
    CREDIT_REPORT = "CREDIT_REPORT"
    TITLE_REPORT = "TITLE_REPORT"
    OTHER = "OTHER"


@dataclass(slots=True)
class ExtractedPage:
    source_page: int
    text: str
    extraction_method: str
    text_length: int
    image_count: int = 0
    extraction_warning: str | None = None


@dataclass(slots=True)
class PageResult:
    source_page: int
    document_type: DocumentType
    confidence: float
    needs_review: bool
    extraction_method: str
    classification_method: str
    evidence: list[str] = field(default_factory=list)
    class_scores: dict[str, float] = field(default_factory=dict)
    document_id: str | None = None
    document_page: int | None = None
    document_page_count: int | None = None
    is_start: bool | None = None
    is_end: bool | None = None
    text_length: int = 0
    text_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["document_type"] = self.document_type.value
        # Extracted text may contain PII and is intentionally excluded from persisted outputs.
        value.pop("text_preview", None)
        return value


@dataclass(slots=True)
class DocumentResult:
    document_id: str
    document_type: DocumentType
    source_pages: list[int]
    ordered_source_pages: list[int]
    detected_page_numbers: list[int]
    missing_page_numbers: list[int]
    is_complete: bool
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["document_type"] = self.document_type.value
        return value
