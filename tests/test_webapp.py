from loan_document_classifier.webapp import Handler, UPLOAD_PAGE


def test_upload_page_has_pdf_and_analysis_controls() -> None:
    assert 'name="pdf"' in UPLOAD_PAGE
    assert 'name="ocr"' in UPLOAD_PAGE
    assert 'name="ai"' in UPLOAD_PAGE
    assert 'action="/analyze"' in UPLOAD_PAGE


def test_session_ids_are_strict_hex_tokens() -> None:
    assert Handler._valid_session_id("012345abcdef")
    assert not Handler._valid_session_id("../../secrets")
    assert not Handler._valid_session_id("012345ABCDEf")
