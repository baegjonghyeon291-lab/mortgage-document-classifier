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


def test_repeated_page_sequences_become_separate_documents() -> None:
    pages = [
        PageResult(i, DocumentType.INCOME_DOC, 0.9, False, "embedded", "rule")
        for i in (10, 20, 30, 40)
    ]
    documents = group_pages(
        pages,
        {
            10: "Page 1 of 2",
            20: "Page 1 of 2",
            30: "Page 2 of 2",
            40: "Page 2 of 2",
        },
    )

    assert [document.ordered_source_pages for document in documents] == [[10, 30], [20, 40]]
    assert all(document.is_complete for document in documents)
    assert pages[0].document_id != pages[1].document_id


def test_different_explicit_totals_become_separate_documents() -> None:
    pages = [
        PageResult(i, DocumentType.TITLE_REPORT, 0.9, False, "embedded", "rule")
        for i in (1, 2, 3, 4)
    ]
    documents = group_pages(
        pages,
        {1: "Page 1 of 2", 2: "Page 2 of 2", 3: "Page 1 of 4", 4: "Page 2 of 4"},
    )

    assert len(documents) == 2
    assert documents[0].is_complete
    assert not documents[1].is_complete
    assert documents[1].missing_page_numbers == [3, 4]


def test_unnumbered_page_is_not_forced_into_competing_sequences() -> None:
    pages = [
        PageResult(i, DocumentType.INCOME_DOC, 0.9, False, "embedded", "rule")
        for i in (1, 2, 3, 4, 5)
    ]
    documents = group_pages(
        pages,
        {
            1: "Page 1 of 2",
            2: "Page 1 of 2",
            3: "Page 2 of 2",
            4: "Page 2 of 2",
            5: "Income summary without page marker",
        },
    )

    assert len(documents) == 3
    assert documents[-1].source_pages == [5]
    assert not documents[-1].is_complete
