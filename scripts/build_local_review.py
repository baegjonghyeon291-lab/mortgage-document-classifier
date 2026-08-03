from __future__ import annotations

import argparse
import html
import json
import subprocess
from pathlib import Path

from loan_document_classifier.extraction import PopplerTesseractOcrEngine, extract_pages


COLORS = {
    "URLA_1003": "#2563eb",
    "INCOME_DOC": "#059669",
    "CREDIT_REPORT": "#7c3aed",
    "TITLE_REPORT": "#d97706",
    "OTHER": "#64748b",
}


def build(
    pdf: Path,
    results_path: Path,
    output: Path,
    pdftoppm: str,
    tesseract: str,
    *,
    use_ocr: bool = True,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    page_dir = output / "pages"
    page_dir.mkdir(exist_ok=True)

    subprocess.run(
        [pdftoppm, "-jpeg", "-r", "110", str(pdf), str(page_dir / "page")],
        check=True,
        capture_output=True,
    )
    images = sorted(page_dir.glob("page-*.jpg"))

    ocr = PopplerTesseractOcrEngine(
        pdftoppm_command=pdftoppm,
        tesseract_command=tesseract,
    )
    extracted = extract_pages(pdf, ocr_engine=ocr if use_ocr else None)
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    results = {int(item["source_page"]): item for item in payload["pages"]}
    if len(images) != len(extracted):
        raise RuntimeError(f"Rendered {len(images)} images for {len(extracted)} PDF pages")

    cards: list[str] = []
    for page, image in zip(extracted, images):
        result = results[page.source_page]
        kind = result["document_type"]
        evidence = " · ".join(result.get("evidence", []))
        text = page.text or "[No text extracted; inspect the rendered page]"
        cards.append(
            f'<article class="page" data-type="{html.escape(kind)}" '
            f'data-review="{str(bool(result["needs_review"])).lower()}">'
            f'<header><span class="number">PDF {page.source_page}</span>'
            f'<span class="badge" style="--badge:{COLORS[kind]}">{html.escape(kind)}</span>'
            f'<strong>{float(result["confidence"]):.1%}</strong>'
            f'<button type="button" onclick="rotatePage(this,-90)" title="Rotate left">↺</button>'
            f'<button type="button" onclick="rotatePage(this,90)" title="Rotate right">↻</button></header>'
            f'<div class="body"><div class="imagebox"><img loading="lazy" src="pages/{image.name}" '
            f'alt="Rendered PDF page {page.source_page}" data-rotation="0"></div>'
            f'<section><dl><dt>Extraction</dt><dd>{html.escape(page.extraction_method)}</dd>'
            f'<dt>Classification</dt><dd>{html.escape(result["classification_method"])}</dd>'
            f'<dt>Document</dt><dd>{html.escape(str(result.get("document_id") or "-"))}</dd>'
            f'<dt>Evidence</dt><dd>{html.escape(evidence)}</dd></dl>'
            f'<details><summary>Extracted text - local sensitive data</summary>'
            f'<pre>{html.escape(text)}</pre></details></section></div></article>'
        )

    options = "".join(f"<option>{name}</option>" for name in COLORS)
    markup = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Loan Package Review</title>
<style>
:root{{--ink:#12213d;--muted:#64748b;--line:#dbe3ef;--bg:#f3f6fb}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Segoe UI,sans-serif}}
main{{max-width:1480px;margin:auto;padding:30px}}h1{{margin:0;font-size:30px}}.warning{{background:#fff7ed;border:1px solid #fdba74;color:#9a3412;padding:12px 16px;border-radius:12px;margin:16px 0}}
.toolbar{{position:sticky;top:0;z-index:2;background:#f3f6fbdd;backdrop-filter:blur(10px);display:flex;gap:10px;padding:12px 0}}
select,label{{background:white;border:1px solid var(--line);border-radius:9px;padding:8px 11px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.page{{background:white;border:1px solid var(--line);border-radius:15px;overflow:hidden;box-shadow:0 8px 30px #0f172a0a}}
.page header{{display:flex;align-items:center;gap:10px;padding:13px 16px;border-bottom:1px solid var(--line)}}.page header strong{{margin-left:auto}}.page button{{border:1px solid var(--line);background:white;border-radius:7px;padding:3px 8px;cursor:pointer;font-size:16px}}.number{{font-weight:800}}
.badge{{color:var(--badge);background:color-mix(in srgb,var(--badge) 10%,white);padding:4px 8px;border-radius:99px;font-size:11px;font-weight:800}}
.body{{display:grid;grid-template-columns:minmax(260px,45%) 1fr;gap:16px;padding:16px}}.imagebox{{aspect-ratio:1;display:grid;place-items:center;background:#eef2f7;overflow:hidden;border:1px solid var(--line)}}img{{max-width:100%;max-height:100%;transition:transform .18s ease}}dl{{display:grid;grid-template-columns:100px 1fr;gap:7px;margin:0 0 14px}}dt{{color:var(--muted)}}dd{{margin:0}}details{{border-top:1px solid var(--line);padding-top:12px}}summary{{cursor:pointer;font-weight:700;color:#b45309}}pre{{white-space:pre-wrap;word-break:break-word;max-height:430px;overflow:auto;background:#f8fafc;padding:12px;border-radius:9px;font-size:11px}}
@media(max-width:950px){{.grid{{grid-template-columns:1fr}}}}@media(max-width:620px){{main{{padding:18px}}.body{{grid-template-columns:1fr}}}}
</style></head><body><main><h1>Loan Package Review</h1>
<div class="warning"><strong>LOCAL ONLY:</strong> This viewer contains restricted page images and extracted document text. Do not publish or commit this folder.</div>
<div class="toolbar"><select id="type"><option value="">All document types</option>{options}</select><label><input id="review" type="checkbox"> Needs review only</label><span id="count"></span></div>
<div class="grid" id="pages">{''.join(cards)}</div></main><script>
const type=document.querySelector('#type'),review=document.querySelector('#review'),count=document.querySelector('#count');
function apply(){{let shown=0;document.querySelectorAll('.page').forEach(x=>{{x.hidden=(type.value&&x.dataset.type!==type.value)||(review.checked&&x.dataset.review!=='true');if(!x.hidden)shown++}});count.textContent=`${{shown}} pages`;}}
function rotatePage(button,delta){{const img=button.closest('.page').querySelector('img');const angle=(Number(img.dataset.rotation)+delta)%360;img.dataset.rotation=angle;img.style.transform=`rotate(${{angle}}deg)`;}}
type.addEventListener('change',apply);review.addEventListener('change',apply);apply();
</script></body></html>"""
    (output / "index.html").write_text(markup, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local-only review containing actual data")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pdftoppm", default="pdftoppm")
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--skip-ocr", action="store_true")
    args = parser.parse_args()
    build(
        args.pdf,
        args.results,
        args.output,
        args.pdftoppm,
        args.tesseract,
        use_ocr=not args.skip_ocr,
    )


if __name__ == "__main__":
    main()
