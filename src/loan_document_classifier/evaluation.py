from __future__ import annotations

from collections import Counter

from .models import DocumentType, PageResult


def evaluate(
    predictions: list[PageResult], ground_truth: dict[int, DocumentType]
) -> dict[str, object]:
    labels = list(DocumentType)
    prediction_by_page = {row.source_page: row.document_type for row in predictions}
    missing = sorted(set(ground_truth) - set(prediction_by_page))
    if missing:
        raise ValueError(f"Missing predictions for pages: {missing}")

    matrix: dict[str, Counter[str]] = {label.value: Counter() for label in labels}
    errors: list[dict[str, object]] = []
    correct = 0
    for page, actual in sorted(ground_truth.items()):
        predicted = prediction_by_page[page]
        matrix[actual.value][predicted.value] += 1
        if predicted == actual:
            correct += 1
        else:
            errors.append(
                {"source_page": page, "actual": actual.value, "predicted": predicted.value}
            )

    per_class: dict[str, dict[str, float | int]] = {}
    for label in labels:
        name = label.value
        tp = matrix[name][name]
        fp = sum(matrix[actual][name] for actual in matrix if actual != name)
        fn = sum(value for predicted, value in matrix[name].items() if predicted != name)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[name] = {
            "support": tp + fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    return {
        "total_pages": len(ground_truth),
        "correct_pages": correct,
        "accuracy": round(correct / len(ground_truth), 4) if ground_truth else 0.0,
        "per_class": per_class,
        "confusion_matrix": {key: dict(value) for key, value in matrix.items()},
        "errors": errors,
    }

