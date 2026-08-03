from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol
from urllib import request

from .models import DocumentType, ExtractedPage, PageResult


class AiClassifier(Protocol):
    def classify(self, page: ExtractedPage, baseline: PageResult) -> PageResult: ...


@dataclass(slots=True)
class OpenAICompatibleClassifier:
    """Opt-in adjudicator for OpenAI or a local OpenAI-compatible endpoint."""

    model: str
    base_url: str | None = None
    api_key: str | None = None

    def classify(self, page: ExtractedPage, baseline: PageResult) -> PageResult:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the 'ai' dependency group to enable AI adjudication") from exc

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        evidence_text = redact_sensitive_text(page.text)[:6000]
        schema = {
            "type": "object",
            "properties": {
                "document_type": {
                    "type": "string",
                    "enum": [kind.value for kind in DocumentType],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            },
            "required": ["document_type", "confidence", "evidence"],
            "additionalProperties": False,
        }
        response = client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Classify one mortgage-document page. Use only the supplied evidence. "
                        "Return OTHER when evidence is insufficient. Do not infer borrower facts."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Local baseline: {baseline.document_type.value} "
                        f"({baseline.confidence}).\nPage text:\n{evidence_text}"
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "page_classification",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        payload = json.loads(response.output_text)
        return merge_ai_decision(baseline, payload)


@dataclass(slots=True)
class OllamaClassifier:
    """Local-only Ollama adapter using the Python standard library."""

    model: str
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 120

    def classify(self, page: ExtractedPage, baseline: PageResult) -> PageResult:
        schema = {
            "type": "object",
            "properties": {
                "document_type": {
                    "type": "string",
                    "enum": [kind.value for kind in DocumentType],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            },
            "required": ["document_type", "confidence", "evidence"],
            "additionalProperties": False,
        }
        prompt = (
            "Classify this single mortgage-document page as URLA_1003, INCOME_DOC, "
            "CREDIT_REPORT, TITLE_REPORT, or OTHER. Use only supplied evidence. Return OTHER "
            "when evidence is insufficient. Evidence must quote short generic form markers, not "
            "borrower PII.\n\n"
            f"Local baseline: {baseline.document_type.value} ({baseline.confidence})\n"
            f"Page text:\n{redact_sensitive_text(page.text)[:3000]}"
        )
        body = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "format": schema,
                "messages": [
                    {"role": "system", "content": "You are a conservative document classifier."},
                    {"role": "user", "content": prompt},
                ],
                "options": {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 220},
                "keep_alive": "10m",
            }
        ).encode("utf-8")
        endpoint = self.base_url.rstrip("/") + "/api/chat"
        call = request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
        with request.urlopen(call, timeout=self.timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        payload = json.loads(response_payload["message"]["content"])
        return merge_ai_decision(baseline, payload)


def merge_ai_decision(baseline: PageResult, payload: dict[str, object]) -> PageResult:
    """Combine an AI adjudication with deterministic evidence conservatively."""
    ai_type = DocumentType(str(payload["document_type"]))
    ai_confidence = float(payload["confidence"])
    agreement = ai_type == baseline.document_type
    may_override = baseline.document_type == DocumentType.OTHER and ai_confidence >= 0.75
    final_type = ai_type if agreement or may_override else baseline.document_type
    final_confidence = (
        max(ai_confidence, baseline.confidence)
        if agreement
        else (ai_confidence if may_override else baseline.confidence)
    )
    baseline.document_type = final_type
    baseline.confidence = round(final_confidence, 3)
    baseline.needs_review = not agreement or final_confidence < 0.75
    baseline.classification_method = "hybrid"
    ai_marker = f"Local AI prediction: {ai_type.value}"
    baseline.evidence = list(dict.fromkeys(baseline.evidence + [ai_marker]))[:8]
    return baseline


def redact_sensitive_text(text: str) -> str:
    value = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]", text)
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL_REDACTED]", value)
    value = re.sub(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b", "[PHONE_REDACTED]", value)
    return value
