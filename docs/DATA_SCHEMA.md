# Result Data Schema

## Page result

| Field | Type | Meaning |
|---|---|---|
| `source_page` | integer | 1-based location in the shuffled PDF |
| `document_type` | enum | Predicted page class |
| `confidence` | float | Calibrated value from 0 to 1 |
| `needs_review` | boolean | Prediction should be reviewed manually |
| `extraction_method` | enum | `embedded`, `ocr`, or `none` |
| `classification_method` | enum | `rule`, `ai`, `hybrid`, or `fallback` |
| `evidence` | string array | Human-readable matched evidence |
| `class_scores` | object | Raw score by supported document type |
| `document_id` | string/null | Reconstructed logical document identity |
| `document_page` | integer/null | Inferred page position inside the document |
| `document_page_count` | integer/null | Explicit or inferred total pages |
| `is_start` | boolean/null | Whether this is the logical first page |
| `is_end` | boolean/null | Whether this is the logical last page |
| `text_length` | integer | Extracted character count for diagnostics |

Extracted text and text previews are intentionally excluded from persisted page results because
they may contain PII. The review application should retrieve page content only from the active,
access-controlled analysis session.

## Document result

| Field | Type | Meaning |
|---|---|---|
| `document_id` | string | Stable ID within one analysis run |
| `document_type` | enum | Document class |
| `source_pages` | integer array | Locations in the shuffled input |
| `ordered_source_pages` | integer array | Best reconstruction of document order |
| `detected_page_numbers` | integer array | Explicit internal page numbers found |
| `missing_page_numbers` | integer array | Gaps implied by page markers |
| `is_complete` | boolean | Whether the inferred page range is complete |
| `confidence` | float | Aggregate document confidence |

## Persistence model

The coding-test implementation uses JSON and CSV for transparency and reproducibility. A future
service can persist `AnalysisRun`, `PageAnalysis`, `DocumentGroup`, and ordered group membership
records without changing this external contract.
