from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentType


@dataclass(frozen=True, slots=True)
class GroundTruthRow:
    source_page: int
    document_type: DocumentType
    document_page: int
    source_file: str


def text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _page_texts(path: Path) -> list[str]:
    return [(page.extract_text() or "").strip() for page in PdfReader(str(path)).pages]


def build_ground_truth(
    shuffled_pdf: str | Path,
    reference_pdfs: dict[DocumentType, str | Path],
) -> list[GroundTruthRow]:
    lookup: dict[str, list[tuple[DocumentType, int, str]]] = {}
    for document_type, raw_path in reference_pdfs.items():
        path = Path(raw_path)
        for page_number, text in enumerate(_page_texts(path), 1):
            lookup.setdefault(text_fingerprint(text), []).append(
                (document_type, page_number, path.name)
            )

    rows: list[GroundTruthRow] = []
    for source_page, text in enumerate(_page_texts(Path(shuffled_pdf)), 1):
        matches = lookup.get(text_fingerprint(text), [])
        if len(matches) != 1:
            raise ValueError(
                f"Ground-truth match for shuffled page {source_page} is "
                f"{'missing' if not matches else 'ambiguous'} ({len(matches)} matches)"
            )
        document_type, document_page, source_file = matches[0]
        rows.append(GroundTruthRow(source_page, document_type, document_page, source_file))
    return rows

