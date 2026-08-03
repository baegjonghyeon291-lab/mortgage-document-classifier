from loan_document_classifier.classification import classify_page
from loan_document_classifier.models import DocumentType, ExtractedPage


def page(text: str) -> ExtractedPage:
    return ExtractedPage(1, text, "embedded", len(text))


def test_classifies_urla() -> None:
    result = classify_page(page("Uniform Residential Loan Application Fannie Mae Form 1003"))
    assert result.document_type == DocumentType.URLA_1003
    assert result.confidence > 0.8


def test_classifies_title() -> None:
    result = classify_page(page("First American Title Commitment for Title Insurance Page 3 of 4"))
    assert result.document_type == DocumentType.TITLE_REPORT


def test_unknown_page_requires_review() -> None:
    result = classify_page(page("A short document with no supported markers"))
    assert result.document_type == DocumentType.OTHER
    assert result.needs_review


def test_classifies_anonymized_title_plat() -> None:
    result = classify_page(page("[ Plat map removed in anonymized sample ]"))
    assert result.document_type == DocumentType.TITLE_REPORT


def test_classifies_sparse_income_statement_using_tax_preparer_evidence() -> None:
    result = classify_page(page("Realtor $231,239.00 CTEC #A183652"))
    assert result.document_type == DocumentType.INCOME_DOC


def test_classifies_chain_of_title() -> None:
    result = classify_page(page("24 MONTH CHAIN OF TITLE REPORT Land Records"))
    assert result.document_type == DocumentType.TITLE_REPORT


def test_classifies_income_verification_summary() -> None:
    result = classify_page(page("IRS Form Types: W-2 Income Summary"))
    assert result.document_type == DocumentType.INCOME_DOC
