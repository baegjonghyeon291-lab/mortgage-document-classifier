# Explainable Mortgage Document Classifier

An auditable page classifier and document reconstruction pipeline for shuffled mortgage-loan
PDF packages. This is the document-understanding stage before field extraction and an Automated
Underwriting System (AUS); it does not make lending decisions.

**[Open the PII-minimized package 02 review demo](https://baegjonghyeon291-lab.github.io/mortgage-document-classifier/)**

## Why this submission is different

- Every result includes confidence, evidence, extraction method, and review status.
- Embedded PDF text is preferred; OCR is used only for image-only pages.
- Deterministic rules handle obvious forms, while ambiguous pages can be sent to an opt-in AI
  adjudicator through an OpenAI-compatible interface, including a local endpoint.
- Package 01 ground truth is reconstructed automatically from the separated originals.
- Shuffled source position and logical document position are modeled separately.
- Restricted input PDFs and generated outputs are excluded from Git.

## Supported document types

- `URLA_1003`: Uniform Residential Loan Application / Form 1003
- `INCOME_DOC`: paystubs, tax forms/transcripts, P&L, W-2, 1099, VOE
- `CREDIT_REPORT`: credit and employment verification reports
- `TITLE_REPORT`: title commitments, preliminary reports, chain-of-title reports
- `OTHER`: unsupported or insufficient-evidence pages

## Architecture

```mermaid
flowchart LR
    PDF["Shuffled PDF"] --> Extract["Page extraction"]
    Extract --> Gate{"Usable embedded text?"}
    Gate -->|Yes| Rules["Explainable rule scoring"]
    Gate -->|No| OCR["Selective OCR"]
    OCR --> Rules
    Rules --> Review{"Low confidence?"}
    Review -->|No| Group["Document reconstruction"]
    Review -->|Yes| AI["Local AI adjudication"]
    AI --> Guard["Rule-preserving safety guard"]
    Guard --> Group
    Group --> Output["CSV · JSON · HTML · metrics"]
```

See [PRD](docs/PRD.md), [technical design](docs/TECHNICAL_DESIGN.md), and
[data schema](docs/DATA_SCHEMA.md). A production-oriented [ERD](docs/ERD.md) is included as an
extension design; the coding-test runtime itself remains database-free.

For a concise reviewer walkthrough, use the [five-minute demo script](docs/DEMO_SCRIPT.md).

Run the final repository, test, and PII checks with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## Setup

Python 3.11 or later is required.

```bash
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev]"
```

For OCR and the review UI:

```bash
python -m pip install -e ".[all]"
```

Poppler (`pdftoppm`) and Tesseract must also be installed and available on `PATH` when `--ocr`
is used. OCR runs in isolated subprocesses so a native OCR failure cannot terminate the parser.

## Data placement

Do not commit the coding-test archive. Place files as follows:

```text
data/input/
├── package_01/
│   ├── package_01_shuffled.pdf
│   ├── URLA_1003.pdf
│   ├── INCOME_DOC.pdf
│   ├── CREDIT_REPORT.pdf
│   └── TITLE_REPORT.pdf
└── package_02_shuffled.pdf
```

## Commands

Build reproducible package 01 ground truth:

```bash
loan-doc build-ground-truth data/input/package_01 --output outputs/package_01/ground_truth.csv
```

Run the deterministic local pipeline:

```bash
loan-doc analyze data/input/package_01/package_01_shuffled.pdf --output outputs/package_01
```

Enable OCR fallback:

```bash
loan-doc analyze data/input/package_02_shuffled.pdf --output outputs/package_02 --ocr
```

Use an opt-in AI reviewer only for low-confidence pages:

```bash
loan-doc analyze data/input/package_02_shuffled.pdf --output outputs/package_02 \
  --ocr --ai-model YOUR_MODEL
```

For local Ollama, use `--ai-model qwen2.5:3b --ai-provider ollama`. The Ollama adapter uses only
the Python standard library and sends evidence to `http://localhost:11434` by default.
External AI use should be confirmed with the data owner before transmitting document evidence.

Windows local-tool setup used for the verified run:

```powershell
winget install --id oschwartz10612.Poppler -e
winget install --id UB-Mannheim.TesseractOCR -e
winget install --id Ollama.Ollama -e
ollama pull qwen2.5:3b
```

Evaluate package 01:

```bash
loan-doc evaluate outputs/package_01/results.json outputs/package_01/ground_truth.csv \
  --output outputs/package_01/metrics.json
```

Launch the review UI:

```bash
streamlit run app.py
```

Every `analyze` command also creates a dependency-free `report.html`. This is the reliable review
fallback for locked-down environments where native Streamlit dependencies are unavailable.
Open `submission/package_02_report.html` directly in a browser to review the supplied result.

## Measured package 01 baseline

The current deterministic pipeline classifies 39 of 39 supplied package 01 pages correctly
(100% page accuracy): 11 URLA, 1 income, 18 credit, and 9 title pages. This is an in-sample,
template-specific result, not a claim of production generalization. The forms contain repeated,
highly distinctive headers, and two sparse edge cases were analyzed explicitly.

The initial baseline scored 37/39 (94.87%). Its two errors were:

1. An anonymized plat-map page with all substantive content removed.
2. A one-page P&L containing amounts and a tax-preparer identifier but no document title.

The final rules capture those general evidence types while keeping the pages reviewable. A proper
production assessment requires unseen lenders, issuers, scans, rotations, and OCR degradation.

The verified local hybrid used `qwen2.5:3b` through Ollama. Package 01 retained 100% accuracy with
one AI review. Package 02 invoked AI for two low-confidence income pages; one agreement raised
confidence, while one disagreement preserved the rule result and remained flagged for review.

## Important assumptions

The prompt describes contiguous document grouping, but the supplied package pages are globally
shuffled. The implementation therefore distinguishes `source_page` from `document_page` and uses
internal page markers for reconstruction. The supplied archive contains two shuffled packages,
despite the prompt mentioning three packages.

## Current limitations and next steps

- The small reference set contains only one document per supported type.
- Document identity grouping must add borrower-independent report IDs for multi-document packages.
- OCR quality depends on the local Tesseract installation and scan quality.
- AI calibration needs a larger held-out dataset and cost/latency measurement.
- `OTHER` has no labeled examples in package 01, so its precision cannot be measured there.
- Page thumbnails and side-by-side ground-truth comparison should be added to the UI.
- Production use needs encrypted storage, retention controls, PII-aware observability, and access
  auditing.
