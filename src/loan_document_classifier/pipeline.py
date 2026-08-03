from __future__ import annotations

from pathlib import Path

from .ai import AiClassifier
from .classification import classify_page
from .extraction import NoOcrEngine, OcrEngine, extract_pages
from .grouping import group_pages
from .models import DocumentResult, PageResult


def analyze_pdf(
    pdf_path: str | Path,
    *,
    ocr_engine: OcrEngine | None = None,
    ai_classifier: AiClassifier | None = None,
    ai_review_threshold: float = 0.75,
) -> tuple[list[PageResult], list[DocumentResult]]:
    extracted = extract_pages(pdf_path, ocr_engine=ocr_engine or NoOcrEngine())
    results: list[PageResult] = []
    for page in extracted:
        result = classify_page(page)
        if ai_classifier and (result.needs_review or result.confidence < ai_review_threshold):
            result = ai_classifier.classify(page, result)
        results.append(result)

    text_by_page = {page.source_page: page.text for page in extracted}
    documents = group_pages(results, text_by_page)
    return results, documents
