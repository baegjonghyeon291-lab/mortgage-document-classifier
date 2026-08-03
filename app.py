from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from loan_document_classifier.io import result_payload
from loan_document_classifier.pipeline import analyze_pdf


st.set_page_config(page_title="Mortgage Package Inspector", page_icon="📄", layout="wide")
st.title("Mortgage Package Inspector")
st.caption("Explainable page classification and logical document reconstruction")

uploaded = st.file_uploader("Upload a shuffled mortgage PDF", type=["pdf"])
if uploaded:
    with tempfile.TemporaryDirectory(prefix="loan-doc-") as folder:
        input_path = Path(folder) / "input.pdf"
        input_path.write_bytes(uploaded.getvalue())
        with st.spinner("Analyzing pages..."):
            pages, documents = analyze_pdf(input_path)
        payload = result_payload(pages, documents)

    counts = Counter(page.document_type.value for page in pages)
    columns = st.columns(5)
    for column, label in zip(
        columns, ["URLA_1003", "INCOME_DOC", "CREDIT_REPORT", "TITLE_REPORT", "OTHER"]
    ):
        column.metric(label, counts.get(label, 0))

    frame = pd.DataFrame(page.to_dict() for page in pages)
    show_review = st.toggle("Show only pages needing review")
    if show_review:
        frame = frame[frame["needs_review"]]
    st.dataframe(
        frame[
            [
                "source_page", "document_type", "confidence", "needs_review",
                "extraction_method", "classification_method", "document_page", "evidence",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Reconstructed documents")
    st.dataframe(pd.DataFrame(document.to_dict() for document in documents), use_container_width=True)
    st.download_button(
        "Download JSON results",
        json.dumps(payload, ensure_ascii=False, indent=2),
        file_name="classification-results.json",
        mime="application/json",
    )
