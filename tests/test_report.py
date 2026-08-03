from loan_document_classifier.models import DocumentType, PageResult
from loan_document_classifier.report import write_html_report


def test_html_report_excludes_text_preview(tmp_path) -> None:
    page = PageResult(
        source_page=1,
        document_type=DocumentType.URLA_1003,
        confidence=0.99,
        needs_review=False,
        extraction_method="embedded",
        classification_method="rule",
        evidence=["Fannie Mae Form 1003"],
        text_preview="SECRET BORROWER NAME",
    )
    output = tmp_path / "report.html"
    write_html_report(output, [page], [])
    rendered = output.read_text(encoding="utf-8")
    assert "Fannie Mae Form 1003" in rendered
    assert "SECRET BORROWER NAME" not in rendered

