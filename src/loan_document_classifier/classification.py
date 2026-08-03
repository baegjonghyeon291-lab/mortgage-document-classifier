from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .models import DocumentType, ExtractedPage, PageResult


@dataclass(frozen=True, slots=True)
class Rule:
    pattern: str
    weight: float
    evidence: str


RULES: dict[DocumentType, tuple[Rule, ...]] = {
    DocumentType.URLA_1003: (
        Rule(r"uniform residential loan application", 8, "Uniform Residential Loan Application"),
        Rule(r"fannie mae form 1003", 7, "Fannie Mae Form 1003"),
        Rule(r"freddie mac form 65", 6, "Freddie Mac Form 65"),
        Rule(r"lender loan information", 3, "Lender Loan Information"),
        Rule(r"borrower information", 2, "Borrower Information"),
        Rule(r"unmarried addendum|continuation sheet", 3, "URLA addendum or continuation"),
    ),
    DocumentType.INCOME_DOC: (
        Rule(r"wage and income transcript", 8, "Wage and Income Transcript"),
        Rule(r"profit\s*(?:&|and)\s*loss|profit/loss", 8, "Profit and Loss"),
        Rule(r"form w-?2|w-?2 wage", 7, "W-2 form"),
        Rule(r"form 1099|form 1040", 7, "Tax form"),
        Rule(r"pay\s*stub|paystub", 7, "Paystub"),
        Rule(r"employer identification number|employee.?s social security number", 5, "Employment tax fields"),
        Rule(r"sensitive taxpayer data", 4, "Taxpayer transcript marker"),
        Rule(r"gross profit|net income|operating expenses", 3, "Income statement fields"),
        Rule(r"\bctec\s*#", 5, "Registered tax preparer identifier"),
        Rule(r"\brealtor\b", 2, "Self-employment occupation"),
        Rule(r"irs form types?:|income summary", 7, "IRS income verification summary"),
        Rule(r"page\s+\d+\s+of\s+\d+.*sensitive taxpayer data", 6, "Tax transcript continuation"),
    ),
    DocumentType.CREDIT_REPORT: (
        Rule(r"credit report", 8, "Credit Report"),
        Rule(r"credit score disclosure", 8, "Credit Score Disclosure"),
        Rule(r"repositories?:", 5, "Credit repositories field"),
        Rule(r"xactus", 4, "Xactus issuer"),
        Rule(r"equifax|experian|transunion", 4, "Credit bureau"),
        Rule(r"tradeline|creditor|account history", 3, "Credit tradeline fields"),
        Rule(r"report id:", 2, "Report ID"),
        Rule(r"370 reed rd", 3, "Credit-report issuer address"),
        Rule(r"consumer reporting agency", 5, "Consumer reporting agency disclosure"),
        Rule(r"employment record available", 4, "Employment verification report"),
    ),
    DocumentType.TITLE_REPORT: (
        Rule(r"commitment for title insurance", 9, "Commitment for Title Insurance"),
        Rule(r"preliminary (?:title )?report", 8, "Preliminary Title Report"),
        Rule(r"title commitment", 8, "Title Commitment"),
        Rule(r"clta preliminary report form", 7, "CLTA Preliminary Report"),
        Rule(r"first american title|fidelity national title", 5, "Title company"),
        Rule(r"schedule [ab]", 3, "Title schedule"),
        Rule(r"legal description|exhibit a", 3, "Legal description exhibit"),
        Rule(r"commitment conditions|proposed insured", 3, "Title commitment terms"),
        Rule(r"plat map removed in anonymized sample", 8, "Anonymized title plat map"),
        Rule(r"chain of title report", 9, "Chain of Title Report"),
    ),
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _confidence(top_score: float, second_score: float) -> float:
    if top_score <= 0:
        return 0.2
    strength = 1 - math.exp(-top_score / 8)
    separation = 1 / (1 + math.exp(-(top_score - second_score) / 3))
    return round(min(0.995, 0.5 * strength + 0.5 * separation), 3)


def classify_page(page: ExtractedPage) -> PageResult:
    normalized = normalize_text(page.text)
    scores: dict[str, float] = {kind.value: 0.0 for kind in DocumentType}
    matched: dict[DocumentType, list[str]] = {kind: [] for kind in RULES}

    for kind, rules in RULES.items():
        for rule in rules:
            if re.search(rule.pattern, normalized, flags=re.IGNORECASE):
                scores[kind.value] += rule.weight
                matched[kind].append(rule.evidence)

    ranked = sorted(
        ((DocumentType(name), score) for name, score in scores.items() if name != "OTHER"),
        key=lambda item: item[1],
        reverse=True,
    )
    top_type, top_score = ranked[0]
    second_score = ranked[1][1]

    if top_score < 3:
        predicted = DocumentType.OTHER
        confidence = 0.2 if page.text_length == 0 else 0.45
        evidence = ["No sufficiently distinctive supported-document evidence"]
        method = "fallback"
        needs_review = True
    else:
        predicted = top_type
        confidence = _confidence(top_score, second_score)
        evidence = matched[top_type]
        method = "rule"
        needs_review = confidence < 0.75 or top_score - second_score < 3

    return PageResult(
        source_page=page.source_page,
        document_type=predicted,
        confidence=confidence,
        needs_review=needs_review,
        extraction_method=page.extraction_method,
        classification_method=method,
        evidence=evidence,
        class_scores=scores,
        text_length=page.text_length,
        text_preview=re.sub(r"\s+", " ", page.text).strip()[:240],
    )
