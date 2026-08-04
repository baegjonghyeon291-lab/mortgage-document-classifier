# Technical Design

## Architecture

```text
PDF
  -> page reader
  -> embedded-text quality gate
  -> OCR fallback
  -> feature extraction
  -> deterministic rule scorer
  -> optional AI adjudicator for ambiguous pages
  -> consistency checks
  -> document grouping and page-order inference
  -> CSV / JSON / metrics / review UI
```

## Main decisions

### Page-oriented PDF processing

The task requires source-page preservation, page images, and page-level fallback behavior.
A page-oriented PDF library is therefore the primary parser. A whole-document parser such as
Kordoc was considered, but it is better suited to extracting one consolidated document body
than preserving per-page evidence and rendering.

### Selective OCR

Embedded text is cheaper and usually more accurate than OCR. OCR is invoked only when text is
missing or unusable. The supplied package 02 has three such pages, so unconditional OCR would
add latency without improving most pages.

### Hybrid classification

Distinctive form names and issuers provide deterministic evidence. Rules handle high-confidence
pages; an AI adapter handles ambiguous pages when explicitly enabled. This reduces cost and
data disclosure while preserving a real AI role in hard cases.

### Explainability contract

Every prediction stores class scores, matched evidence, confidence, method, and review flags.
The AI adapter must return the same structured contract as the deterministic classifier.

### Ground-truth reconstruction

Package 01 pages are matched against the separated originals using normalized extracted-text
fingerprints. The builder fails on unmatched or ambiguous fingerprints instead of silently
creating questionable labels.

### Conservative document reconstruction

Grouping does not equate one document type with one document instance. Explicit `Page N of M`
markers define sequence candidates, repeated page numbers create additional instances, and
different totals remain separate. When several candidates compete for an unnumbered page and no
stable identifier is available, the page stays in a separate incomplete group instead of being
assigned with false confidence. This favors auditable uncertainty over an apparently complete but
incorrect reconstruction.

## Failure handling

- Encrypted or unreadable PDF: stop with an actionable error.
- Empty embedded text: attempt OCR when configured; otherwise mark `needs_review`.
- AI unavailable: retain deterministic prediction and mark the fallback in metadata.
- Conflicting page markers: keep both evidence and mark the document incomplete.
- No supported evidence: classify as `OTHER` with low confidence.

## Security

- Input and output directories are ignored by Git.
- Raw extracted text is not logged by default.
- External AI is disabled by default.
- AI requests should use redacted evidence snippets rather than entire documents.
- File hashes support caching without using borrower names as identifiers.

## Alternatives not selected

- AI-only vision classification: simple but expensive, less reproducible, and disclosure-heavy.
- Rule-only production design: strong on supplied forms but brittle on unseen templates.
- Model fine-tuning: insufficient labeled diversity for a credible generalization claim.
- Whole-document parsing only: loses page-level structure required by the task.
