from loan_document_classifier.grouping import detect_page_marker, group_pages
from loan_document_classifier.models import DocumentType, PageResult


def test_detects_page_of_total() -> None:
    assert detect_page_marker("Commitment Conditions - Page 3 of 4") == (3, 4)


def test_rejects_invalid_page_range() -> None:
    assert detect_page_marker("Page 7 of 2") == (None, None)


def test_partial_sequence_without_explicit_total_is_not_complete() -> None:
    pages = [
        PageResult(i, DocumentType.CREDIT_REPORT, 0.9, False, "embedded", "rule")
        for i in (1, 2, 3)
    ]
    documents = group_pages(pages, {1: "Page 1", 2: "Page 2", 3: "Page 3"})
    assert not documents[0].is_complete
