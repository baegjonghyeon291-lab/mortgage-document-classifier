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


def _partition_type_pages(
    pages: list[PageResult], markers: dict[int, tuple[int | None, int | None]]
) -> list[tuple[list[PageResult], int | None]]:
    """Split one document type into conservative document instances.

    Explicit ``Page N of M`` markers are the strongest boundary signal. Pages with the same
    total belong to separate instances when a page number repeats. Occurrence rank is used only
    to pair repeated numbered pages; pages without a marker are not forced into one of several
    competing instances.
    """

    by_total: dict[int, list[PageResult]] = defaultdict(list)
    without_total: list[PageResult] = []
    for page in pages:
        _, total = markers[page.source_page]
        if total is None:
            without_total.append(page)
        else:
            by_total[total].append(page)

    partitions: list[tuple[list[PageResult], int | None]] = []
    for total, total_pages in sorted(by_total.items()):
        by_number: dict[int, list[PageResult]] = defaultdict(list)
        for page in total_pages:
            number, _ = markers[page.source_page]
            if number is not None:
                by_number[number].append(page)

        instance_count = max((len(items) for items in by_number.values()), default=1)
        instances: list[list[PageResult]] = [[] for _ in range(instance_count)]
        for number in sorted(by_number):
            for index, page in enumerate(sorted(by_number[number], key=lambda item: item.source_page)):
                instances[index].append(page)
        partitions.extend((instance, total) for instance in instances if instance)

    if not partitions:
        # With no boundary evidence, retain the previous conservative assumption of one document.
        return [(sorted(without_total, key=lambda item: item.source_page), None)]

    if len(partitions) == 1:
        # A single explicit sequence can safely absorb its unnumbered cover/supplement pages.
        partitions[0][0].extend(without_total)
    else:
        # Several candidate documents exist. Avoid inventing membership without an identifier.
        partitions.extend(([page], None) for page in sorted(without_total, key=lambda item: item.source_page))

    return partitions


def group_pages(results: list[PageResult], full_text_by_page: dict[int, str]) -> list[DocumentResult]:
    buckets: dict[DocumentType, list[PageResult]] = defaultdict(list)
    markers: dict[int, tuple[int | None, int | None]] = {}
    for result in results:
        marker = detect_page_marker(full_text_by_page.get(result.source_page, ""))
        markers[result.source_page] = marker
        number, total = marker
        result.document_page = number
        result.document_page_count = total
        result.is_start = number == 1 if number is not None else None
        result.is_end = number == total if number is not None and total is not None else None
        if result.document_type != DocumentType.OTHER:
            buckets[result.document_type].append(result)

    documents: list[DocumentResult] = []
    for document_type, pages in sorted(buckets.items(), key=lambda item: item[0].value):
        partitions = _partition_type_pages(pages, markers)
        for sequence, (instance_pages, expected_total) in enumerate(partitions, start=1):
            document_id = f"{document_type.value}_{sequence:03d}"
            for page in instance_pages:
                page.document_id = document_id

            ordered = sorted(
                instance_pages,
                key=lambda item: (
                    item.document_page is None,
                    item.document_page if item.document_page is not None else item.source_page,
                ),
            )
            detected = sorted(
                {page.document_page for page in instance_pages if page.document_page is not None}
            )
            missing = (
                sorted(set(range(1, expected_total + 1)) - set(detected))
                if expected_total
                else []
            )
            complete = bool(expected_total) and not missing and len(instance_pages) == expected_total
            documents.append(
                DocumentResult(
                    document_id=document_id,
                    document_type=document_type,
                    source_pages=sorted(page.source_page for page in instance_pages),
                    ordered_source_pages=[page.source_page for page in ordered],
                    detected_page_numbers=detected,
                    missing_page_numbers=missing,
                    is_complete=complete,
                    confidence=round(
                        sum(page.confidence for page in instance_pages) / len(instance_pages), 3
                    ),
                )
            )
    return documents
