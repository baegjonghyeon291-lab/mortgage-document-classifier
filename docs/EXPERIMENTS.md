# Experiments and Error Analysis

## Dataset inventory

| Package | Pages | Ground truth | Embedded text | OCR fallback |
|---|---:|---|---:|---:|
| package 01 | 39 | Separated source PDFs | 39 | 0 |
| package 02 | 44 | Not supplied | 41 | 3 |

Package 01 contains 11 URLA, 1 income, 18 credit, and 9 title pages. It has no labeled `OTHER`
examples, so `OTHER` performance cannot be measured from this package.

## Baseline progression

| Version | Correct | Accuracy | Main observation |
|---|---:|---:|---|
| Initial explainable rules | 37/39 | 94.87% | Two sparse/titleless pages were missed |
| Evidence-rule revision | 39/39 | 100% | All supplied package 01 pages matched |

### Initial error 1: anonymized plat map

The title-report plat map had been replaced with an anonymization notice. There was no remaining
legal description or title-company header. The final pipeline recognizes an anonymized plat-map
marker as title-document evidence. This is a dataset-specific anonymization accommodation and
must not be presented as a general title classifier feature.

### Initial error 2: sparse P&L

The one-page P&L had no document title or column labels. It contained an occupation, monetary
values, signer information, and a registered tax-preparer identifier. The revision uses the tax
preparer identifier plus self-employment occupation as combined income-document evidence.

## Package 02 result summary

With selective OCR enabled, the current result distribution is:

| Type | Pages |
|---|---:|
| URLA_1003 | 10 |
| INCOME_DOC | 5 |
| CREDIT_REPORT | 15 |
| TITLE_REPORT | 14 |
| OTHER | 0 |

Pages 11, 26, and 40 have no embedded text. Poppler renders only those pages, Tesseract extracts
their text, and the same explainable classifier identifies all three as title reports. Pages 36
and 39 remain lower-confidence income pages and are explicitly marked for review.

## Interpretation limits

The 100% package 01 score is in-sample and template-specific. The rules were revised after its
two failures were inspected. It demonstrates reproducible debugging, not unbiased production
generalization. A credible next experiment needs a held-out set covering new lenders, issuers,
rotations, low-resolution scans, mixed document instances, and labeled `OTHER` pages.

## AI comparison plan

The code includes an opt-in structured AI adjudicator for low-confidence pages. It is disabled in
the supplied-data run because external sharing is prohibited and no approved external transfer
was assumed. The intended controlled experiment compares rule-only and hybrid runs on the same
held-out pages, reporting accuracy, AI calls, latency, and estimated cost. A local
OpenAI-compatible endpoint can run the same experiment without external document transfer.

## Local AI safety experiment

A local `qwen2.5:3b` model was run through Ollama with temperature 0 and structured JSON output.
An intentionally permissive first hybrid routed every page below 0.85 rule confidence to the
model and allowed high-confidence AI disagreements to replace the deterministic prediction. It
reduced package 01 accuracy from 100% to 76.92%, primarily by labeling titleless middle pages as
`OTHER` despite strong issuer/report evidence.

The production hybrid therefore uses AI as an adjudicator, not an authority:

- Only existing review pages or rule confidence below 0.75 are routed to AI.
- AI agreement may increase confidence.
- AI may resolve an `OTHER` page when confidence is at least 0.75.
- AI disagreement can never overwrite a supported rule prediction; it adds a review flag instead.
- Raw AI evidence is not persisted because models may echo borrower names or financial values.

This failed experiment is retained because it demonstrates why an LLM-only design was rejected
and turns model disagreement into an auditable human-review signal.

### Final guarded hybrid run

| Run | Pages | AI calls | Result | Wall time on test machine |
|---|---:|---:|---|---:|
| package 01 | 39 | 1 | 39/39 correct | 5.47 s |
| package 02 | 44 | 2 | 10 URLA, 5 income, 15 credit, 14 title | 20.25 s |

Package 02 time includes selective OCR of three image-only pages. The local AI agreed with the
W-2 income summary and disagreed with a tax-transcript continuation page. The disagreement did
not overwrite the supported `INCOME_DOC` rule result and the page remained marked for review.
