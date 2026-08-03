# Product Requirements Document

## 1. Product summary

This project classifies every page in a shuffled mortgage-loan PDF package, reconstructs
documents where possible, and produces evidence-backed results that a reviewer can audit.
It is the document-understanding stage that precedes data extraction and an Automated
Underwriting System (AUS).

## 2. Users

- Mortgage operations reviewers validating incoming loan packages
- Engineers building downstream extraction and underwriting pipelines
- Coding-test reviewers evaluating problem framing, trade-offs, and reproducibility

## 3. Goals

1. Classify each page as `URLA_1003`, `INCOME_DOC`, `CREDIT_REPORT`, `TITLE_REPORT`, or
   `OTHER`.
2. Report confidence, decision method, and human-readable evidence for every prediction.
3. Group pages into logical documents and infer document page order, start, end, and gaps
   when evidence is available.
4. Build reproducible ground truth from package 01 and report measured performance.
5. Generate package 02 results as CSV and JSON, plus a reviewer-friendly visualization.
6. Minimize external AI disclosure and provide deterministic local fallback behavior.

## 4. Non-goals

- Making lending decisions or implementing an AUS
- Extracting all borrower, income, credit, or collateral fields
- Training or fine-tuning a production model from the small supplied dataset
- Claiming generalization beyond the supplied forms without additional evaluation data

## 5. Functional requirements

### PDF ingestion

- Validate that the input is a readable PDF.
- Preserve the original 1-based source page number.
- Extract embedded text page by page.
- Invoke OCR only when embedded text is absent or below a configurable quality threshold.

### Classification

- Calculate explainable class scores from positive and negative evidence.
- Make high-confidence deterministic decisions locally.
- Route ambiguous pages to a pluggable AI classifier when enabled.
- Return `OTHER` or `needs_review=true` instead of forcing an unsupported decision.

### Reconstruction

- Detect explicit page markers such as `Page N of M`.
- Assign a logical `document_id` using type and document identity evidence.
- Distinguish shuffled `source_page` from inferred `document_page`.
- Detect missing or duplicate document-page numbers.

### Evaluation and output

- Reconstruct package 01 ground truth from the four separated source PDFs.
- Export page results to CSV and JSON.
- Report accuracy, per-class precision/recall/F1, confusion matrix data, and errors.
- Record extraction method, classification method, runtime, and AI usage.

## 6. Success criteria

- A clean environment can run the project from documented commands.
- All 39 package 01 pages receive a verified ground-truth label.
- Package 01 metrics are generated from code, not manually entered.
- All 44 package 02 pages receive a result or explicit review status.
- A reviewer can explain every prediction using stored evidence.
- No supplied PDF is tracked by Git.

## 7. Product assumptions and ambiguities

- The prompt mentions three packages, while the supplied archive contains two shuffled
  packages plus four separated ground-truth documents.
- Because the supplied pages are shuffled globally, contiguous source pages do not define a
  logical document. Reconstruction therefore uses document identity and internal page markers.
- External API use is opt-in because the archive is restricted from external sharing.

## 8. Reviewer experience

The reviewer should be able to filter by document type, low confidence, OCR use, AI use, and
incorrect predictions. Selecting a page should show its thumbnail, extracted evidence,
classification scores, ground truth when available, and reconstructed document position.

