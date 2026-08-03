from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import os

from .ai import OllamaClassifier, OpenAICompatibleClassifier
from .evaluation import evaluate
from .extraction import PopplerTesseractOcrEngine
from .ground_truth import build_ground_truth
from .io import result_payload, write_json, write_page_csv
from .models import DocumentType
from .pipeline import analyze_pdf
from .report import write_html_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="loan-doc")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="classify and reconstruct one shuffled PDF")
    analyze.add_argument("pdf", type=Path)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--ocr", action="store_true", help="enable Tesseract OCR fallback")
    analyze.add_argument("--ai-model", help="enable AI review with this model")
    analyze.add_argument("--ai-provider", choices=["ollama", "openai"], default="ollama")
    analyze.add_argument("--ai-base-url", help="OpenAI-compatible endpoint; use localhost for local AI")
    analyze.add_argument("--ai-key-env", default="OPENAI_API_KEY", help="environment variable holding API key")

    truth = sub.add_parser("build-ground-truth", help="match package 01 to separated originals")
    truth.add_argument("package_dir", type=Path)
    truth.add_argument("--output", type=Path, required=True)

    score = sub.add_parser("evaluate", help="evaluate a page-results JSON file")
    score.add_argument("results", type=Path)
    score.add_argument("ground_truth", type=Path)
    score.add_argument("--output", type=Path, required=True)
    return parser


def _build_truth(package_dir: Path, output: Path) -> None:
    references = {
        DocumentType.URLA_1003: package_dir / "URLA_1003.pdf",
        DocumentType.INCOME_DOC: package_dir / "INCOME_DOC.pdf",
        DocumentType.CREDIT_REPORT: package_dir / "CREDIT_REPORT.pdf",
        DocumentType.TITLE_REPORT: package_dir / "TITLE_REPORT.pdf",
    }
    rows = build_ground_truth(package_dir / "package_01_shuffled.pdf", references)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["source_page", "document_type", "document_page", "source_file"]
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "source_page": row.source_page,
                    "document_type": row.document_type.value,
                    "document_page": row.document_page,
                    "source_file": row.source_file,
                }
            )


def _evaluate(results_path: Path, truth_path: Path, output: Path) -> None:
    from .models import PageResult

    raw = json.loads(results_path.read_text(encoding="utf-8"))
    predictions = [
        PageResult(
            source_page=int(item["source_page"]),
            document_type=DocumentType(item["document_type"]),
            confidence=float(item["confidence"]),
            needs_review=bool(item["needs_review"]),
            extraction_method=item["extraction_method"],
            classification_method=item["classification_method"],
        )
        for item in raw["pages"]
    ]
    with truth_path.open(encoding="utf-8-sig") as stream:
        truth = {
            int(row["source_page"]): DocumentType(row["document_type"])
            for row in csv.DictReader(stream)
        }
    write_json(output, evaluate(predictions, truth))


def main() -> None:
    args = _parser().parse_args()
    if args.command == "analyze":
        ai_classifier = None
        if args.ai_model:
            if args.ai_provider == "ollama":
                ai_classifier = OllamaClassifier(
                    model=args.ai_model,
                    base_url=args.ai_base_url or "http://localhost:11434",
                )
            else:
                api_key = os.getenv(args.ai_key_env)
                if not api_key:
                    raise SystemExit(f"Missing AI API key in {args.ai_key_env}")
                ai_classifier = OpenAICompatibleClassifier(
                    model=args.ai_model,
                    base_url=args.ai_base_url,
                    api_key=api_key,
                )
        pages, documents = analyze_pdf(
            args.pdf,
            ocr_engine=PopplerTesseractOcrEngine() if args.ocr else None,
            ai_classifier=ai_classifier,
        )
        args.output.mkdir(parents=True, exist_ok=True)
        write_json(args.output / "results.json", result_payload(pages, documents))
        write_page_csv(args.output / "pages.csv", pages)
        write_html_report(args.output / "report.html", pages, documents, title=args.pdf.stem)
        print(f"Analyzed {len(pages)} pages into {len(documents)} document groups")
    elif args.command == "build-ground-truth":
        _build_truth(args.package_dir, args.output)
        print(f"Wrote ground truth to {args.output}")
    elif args.command == "evaluate":
        _evaluate(args.results, args.ground_truth, args.output)
        print(f"Wrote metrics to {args.output}")


if __name__ == "__main__":
    main()
