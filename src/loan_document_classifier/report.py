from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from .models import DocumentResult, PageResult


COLORS = {
    "URLA_1003": "#2563eb",
    "INCOME_DOC": "#059669",
    "CREDIT_REPORT": "#7c3aed",
    "TITLE_REPORT": "#d97706",
    "OTHER": "#64748b",
}


def _escape(value: object) -> str:
    return html.escape(str(value if value is not None else "-"))


def write_html_report(
    path: str | Path,
    pages: list[PageResult],
    documents: list[DocumentResult],
    *,
    title: str = "Mortgage Package Analysis",
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter(page.document_type.value for page in pages)
    cards = "".join(
        f'<article class="metric"><span>{_escape(label)}</span>'
        f'<strong style="color:{COLORS[label]}">{counts.get(label, 0)}</strong></article>'
        for label in COLORS
    )
    rows = "".join(
        "<tr "
        f'data-type="{page.document_type.value}" data-review="{str(page.needs_review).lower()}">'
        f"<td>{page.source_page}</td>"
        f'<td><span class="badge" style="--badge:{COLORS[page.document_type.value]}">'
        f"{page.document_type.value}</span></td>"
        f"<td>{page.confidence:.1%}</td>"
        f"<td>{'Review' if page.needs_review else 'Ready'}</td>"
        f"<td>{_escape(page.extraction_method)}</td>"
        f"<td>{_escape(page.classification_method)}</td>"
        f"<td>{_escape(page.document_page)}</td>"
        f"<td>{_escape(' · '.join(page.evidence))}</td>"
        "</tr>"
        for page in pages
    )
    document_rows = "".join(
        "<tr>"
        f"<td>{_escape(document.document_id)}</td>"
        f"<td>{_escape(document.document_type.value)}</td>"
        f"<td>{len(document.source_pages)}</td>"
        f"<td>{_escape(', '.join(map(str, document.ordered_source_pages)))}</td>"
        f"<td>{_escape(', '.join(map(str, document.missing_page_numbers)) or 'None')}</td>"
        f"<td>{document.confidence:.1%}</td>"
        "</tr>"
        for document in documents
    )
    safe_title = _escape(title)
    chart_data = json.dumps(dict(counts), ensure_ascii=True)
    markup = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{safe_title}</title>
<style>
:root{{--ink:#14213d;--muted:#64748b;--line:#e2e8f0;--bg:#f6f8fc;--panel:#fff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,Segoe UI,sans-serif}}
main{{max-width:1440px;margin:auto;padding:36px}} header{{display:flex;justify-content:space-between;gap:24px;align-items:end}}
h1{{margin:0;font-size:30px;letter-spacing:-.03em}} .eyebrow{{color:#2563eb;font-weight:700;text-transform:uppercase;letter-spacing:.12em;font-size:11px}}
.subtitle{{color:var(--muted);margin:8px 0 0}} .metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:28px 0}}
.metric,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 8px 24px #0f172a0a}}
.metric{{padding:18px}} .metric span{{display:block;color:var(--muted);font-size:11px;font-weight:700}} .metric strong{{font-size:30px}}
.panel{{padding:20px;margin-top:18px;overflow:hidden}} .toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}
select,label{{border:1px solid var(--line);border-radius:9px;background:white;padding:8px 10px}} label{{cursor:pointer}}
.table-wrap{{overflow:auto;max-height:540px}} table{{border-collapse:collapse;width:100%;min-width:980px}} th{{position:sticky;top:0;background:#f8fafc;text-align:left;color:#475569;font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
th,td{{border-bottom:1px solid var(--line);padding:11px 10px;vertical-align:top}} tbody tr:hover{{background:#f8fafc}}
.badge{{display:inline-block;border-radius:99px;color:var(--badge);background:color-mix(in srgb,var(--badge) 11%,white);padding:4px 8px;font-size:11px;font-weight:800}}
.meta{{color:var(--muted);font-size:12px}} footer{{margin:26px 0;color:var(--muted);font-size:12px}}
@media(max-width:800px){{main{{padding:20px}}.metrics{{grid-template-columns:repeat(2,1fr)}}header{{display:block}}}}
</style></head><body><main>
<header><div><div class="eyebrow">Explainable document intelligence</div><h1>{safe_title}</h1><p class="subtitle">Page-level evidence, selective OCR, and logical document reconstruction.</p></div><div class="meta">{len(pages)} pages · {len(documents)} groups</div></header>
<section class="metrics">{cards}</section>
<section class="panel"><div class="toolbar"><strong>Page classifications</strong><select id="typeFilter"><option value="">All types</option>{''.join(f'<option>{x}</option>' for x in COLORS)}</select><label><input id="reviewFilter" type="checkbox"> Needs review only</label></div>
<div class="table-wrap"><table><thead><tr><th>Source</th><th>Type</th><th>Confidence</th><th>Status</th><th>Extraction</th><th>Classifier</th><th>Doc page</th><th>Evidence</th></tr></thead><tbody id="pageRows">{rows}</tbody></table></div></section>
<section class="panel"><strong>Reconstructed documents</strong><div class="table-wrap"><table><thead><tr><th>Document ID</th><th>Type</th><th>Pages</th><th>Inferred order</th><th>Missing</th><th>Confidence</th></tr></thead><tbody>{document_rows}</tbody></table></div></section>
<footer>No extracted text or borrower PII is persisted in this report. Distribution: <code>{_escape(chart_data)}</code></footer>
</main><script>
const type=document.querySelector('#typeFilter'), review=document.querySelector('#reviewFilter');
function filter(){{document.querySelectorAll('#pageRows tr').forEach(r=>{{r.hidden=(type.value&&r.dataset.type!==type.value)||(review.checked&&r.dataset.review!=='true')}})}}
type.addEventListener('change',filter);review.addEventListener('change',filter);
</script></body></html>"""
    target.write_text(markup, encoding="utf-8")

