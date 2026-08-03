# Five-minute Demo Script

## 1. Frame the problem (30 seconds)

The input is not one clean document. It is a globally shuffled mortgage package. The system must
preserve the source page, identify the page type, and reconstruct logical document order before an
AUS can extract borrower or collateral fields.

## 2. Show the data audit (45 seconds)

- package 01: 39 pages with four separated reference PDFs
- package 02: 44 unlabeled pages
- 80 of 83 pages have embedded text
- three package 02 pages are image-only and need OCR
- the prompt says three packages, but the archive contains two shuffled packages

## 3. Run the pipeline (60 seconds)

```powershell
python -m loan_document_classifier.cli analyze `
  data/input/package_02_shuffled.pdf `
  --output outputs/package_02 `
  --ocr `
  --ai-model qwen2.5:3b `
  --ai-provider ollama
```

Explain that embedded text is preferred, OCR is selective, and only low-confidence pages reach the
local LLM. No supplied page is transmitted externally.

## 4. Open the report (60 seconds)

Open `submission/package_02_report.html`. Show:

- document-type counts
- page-level confidence and decision evidence
- OCR and hybrid classification methods
- the "Needs review" filter
- reconstructed document groups and inferred page order

Point out page 39: the local LLM disagreed with the tax-transcript rule. The supported rule label
was preserved and the page stayed in review instead of being silently changed.

## 5. Show evaluation and failed experiment (60 seconds)

Package 01 scores 39/39 in the supplied template-specific set. Do not present this as generalized
production accuracy. Show `docs/EXPERIMENTS.md`: a permissive LLM override reduced accuracy to
76.92%. The final guardrail restored 100% by treating AI as an adjudicator rather than authority.

## 6. Close with production next steps (45 seconds)

- evaluate unseen lenders and labeled `OTHER` pages
- detect multiple same-type document instances using stable report identifiers
- calibrate confidence on a larger holdout set
- add encrypted storage, retention, and access auditing
- connect reconstructed documents to structured field extraction and AUS rules

