from __future__ import annotations

import re
from collections import defaultdict

from .models import DocumentResult, DocumentType, PageResult


PAGE_PATTERNS = (
    re.compile(r"\bpage\s+(\d{1,3})\s+of\s+(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\bpage\s+(\d{1,3})\b", re.IGNORECASE),
)


def detect_page_marker(text: str) -> tuple[int | None, int | None]:
    total_match = PAGE_PATTERNS[0].search(text)
    if total_match:
        current, total = int(total_match.group(1)), int(total_match.group(2))
        if 0 < current <= total <= 500:
            return current, total
        return None, None

    match = PAGE_PATTERNS[1].search(text)
    if match:
        current = int(match.group(1))
        if 0 < current <= 500:
            return current, None
    return None, None


def group_pages(results: list[PageResult], full_text_by_page: dict[int, str]) -> list[DocumentResult]:
    buckets: dict[DocumentType, list[PageResult]] = defaultdict(list)
    for result in results:
        if result.document_type != DocumentType.OTHER:
            buckets[result.document_type].append(result)

    documents: list[DocumentResult] = []
    for document_type, pages in sorted(buckets.items(), key=lambda item: item[0].value):
        document_id = f"{document_type.value}_001"
        totals: list[int] = []
        for page in pages:
            number, total = detect_page_marker(full_text_by_page.get(page.source_page, ""))
            page.document_id = document_id
            page.document_page = number
            page.document_page_count = total
            page.is_start = number == 1 if number is not None else None
            page.is_end = number == total if number is not None and total is not None else None
            if total is not None:
                totals.append(total)

        ordered = sorted(
            pages,
            key=lambda item: (
                item.document_page is None,
                item.document_page if item.document_page is not None else item.source_page,
            ),
        )
        detected = sorted({page.document_page for page in pages if page.document_page is not None})
        # Completeness requires an explicit total. A consecutive partial range (for example 1-11
        # from an 18-page report) must not be reported as complete merely because it has no gaps.
        expected_total = max(totals, default=0)
        missing = sorted(set(range(1, expected_total + 1)) - set(detected)) if expected_total else []
        complete = bool(expected_total) and not missing and len(detected) == expected_total
        documents.append(
            DocumentResult(
                document_id=document_id,
                document_type=document_type,
                source_pages=sorted(page.source_page for page in pages),
                ordered_source_pages=[page.source_page for page in ordered],
                detected_page_numbers=detected,
                missing_page_numbers=missing,
                is_complete=complete,
                confidence=round(sum(page.confidence for page in pages) / len(pages), 3),
            )
        )
    return documents
