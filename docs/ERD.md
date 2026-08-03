# Persistence ERD

The coding-test implementation deliberately persists transparent CSV and JSON artifacts instead
of requiring a database. A production service can use the following model without changing the
external result schema.

```mermaid
erDiagram
    ANALYSIS_RUN ||--|{ PAGE_ANALYSIS : contains
    ANALYSIS_RUN ||--o{ DOCUMENT_GROUP : reconstructs
    DOCUMENT_GROUP ||--|{ GROUP_PAGE : orders
    PAGE_ANALYSIS ||--o| GROUP_PAGE : belongs_to
    PAGE_ANALYSIS ||--o{ AI_REVIEW : may_receive

    ANALYSIS_RUN {
        uuid id PK
        string file_hash
        string status
        int page_count
        datetime started_at
        datetime completed_at
    }
    PAGE_ANALYSIS {
        uuid id PK
        uuid run_id FK
        int source_page
        string document_type
        float confidence
        string extraction_method
        string classification_method
        boolean needs_review
    }
    DOCUMENT_GROUP {
        uuid id PK
        uuid run_id FK
        string document_type
        boolean is_complete
        float confidence
    }
    GROUP_PAGE {
        uuid group_id FK
        uuid page_id FK
        int inferred_sequence
        int detected_page_number
    }
    AI_REVIEW {
        uuid id PK
        uuid page_id FK
        string provider
        string model
        string predicted_type
        float confidence
        boolean agreed_with_rules
    }
```

Raw page text is intentionally absent from the default persistence model. If production debugging
requires it, it should be encrypted separately with strict retention and access controls.

