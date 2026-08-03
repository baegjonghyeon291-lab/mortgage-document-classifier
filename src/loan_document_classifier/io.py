from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import DocumentResult, PageResult


def write_json(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_page_csv(path: str | Path, pages: Iterable[PageResult]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [page.to_dict() for page in pages]
    fieldnames = [
        "source_page", "document_type", "confidence", "needs_review",
        "extraction_method", "classification_method", "document_id", "document_page",
        "document_page_count", "is_start", "is_end", "text_length", "evidence",
        "class_scores",
    ]
    with target.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row["evidence"] = " | ".join(row["evidence"])
            row["class_scores"] = json.dumps(row["class_scores"], ensure_ascii=False)
            writer.writerow(row)


def result_payload(pages: list[PageResult], documents: list[DocumentResult]) -> dict[str, object]:
    return {
        "pages": [page.to_dict() for page in pages],
        "documents": [document.to_dict() for document in documents],
    }
