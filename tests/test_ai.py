from loan_document_classifier.ai import merge_ai_decision, redact_sensitive_text
from loan_document_classifier.models import DocumentType, PageResult


def baseline(kind: DocumentType, confidence: float) -> PageResult:
    return PageResult(1, kind, confidence, False, "embedded", "rule")


def test_ai_disagreement_cannot_overwrite_strong_rule() -> None:
    result = merge_ai_decision(
        baseline(DocumentType.CREDIT_REPORT, 0.84),
        {"document_type": "OTHER", "confidence": 0.99, "evidence": ["ambiguous"]},
    )
    assert result.document_type == DocumentType.CREDIT_REPORT
    assert result.needs_review


def test_ai_can_resolve_other_page() -> None:
    result = merge_ai_decision(
        baseline(DocumentType.OTHER, 0.2),
        {"document_type": "TITLE_REPORT", "confidence": 0.9, "evidence": ["title marker"]},
    )
    assert result.document_type == DocumentType.TITLE_REPORT


def test_ai_cannot_overwrite_low_confidence_supported_rule() -> None:
    result = merge_ai_decision(
        baseline(DocumentType.INCOME_DOC, 0.52),
        {"document_type": "OTHER", "confidence": 0.98, "evidence": ["$231,239.00"]},
    )
    assert result.document_type == DocumentType.INCOME_DOC
    assert "$231,239.00" not in result.evidence


def test_redacts_common_pii() -> None:
    text = redact_sensitive_text("SSN 123-45-6789 email a@example.com phone 800-555-1212")
    assert "123-45-6789" not in text
    assert "a@example.com" not in text
    assert "800-555-1212" not in text
