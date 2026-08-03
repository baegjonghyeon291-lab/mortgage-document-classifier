from __future__ import annotations

import argparse
import html
import json
import os
import secrets
import shutil
import subprocess
import sys
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .ai import OllamaClassifier
from .extraction import PopplerTesseractOcrEngine
from .io import result_payload, write_json, write_page_csv
from .pipeline import analyze_pdf
from .report import write_html_report


MAX_UPLOAD_BYTES = 50 * 1024 * 1024


UPLOAD_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Loan Package Review</title>
<style>
:root{--ink:#12213d;--muted:#64748b;--line:#dbe3ef;--blue:#2563eb;--bg:#f3f6fb}*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 Segoe UI,sans-serif}main{max-width:760px;margin:7vh auto;padding:28px}
.panel{background:white;border:1px solid var(--line);border-radius:20px;padding:30px;box-shadow:0 18px 60px #0f172a12}h1{font-size:32px;margin:0 0 8px}.sub{color:var(--muted);margin:0 0 28px}
.drop{display:block;border:2px dashed #a9b8cc;border-radius:16px;padding:34px;text-align:center;background:#f8fafc;cursor:pointer}.drop:hover{border-color:var(--blue);background:#eff6ff}.drop strong{display:block;font-size:17px}.drop span{color:var(--muted)}
input[type=file]{position:absolute;left:-9999px}.options{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}.option{border:1px solid var(--line);border-radius:12px;padding:13px;background:#fff}.option small{display:block;color:var(--muted);margin-left:24px}
button{width:100%;border:0;border-radius:12px;background:var(--blue);color:white;padding:14px;font-size:16px;font-weight:800;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}.privacy{margin:18px 0 0;color:#9a3412;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:11px;font-size:13px}
#fileName{margin-top:12px;color:var(--blue);font-weight:700}.loading{position:fixed;inset:0;background:#0f172ae8;color:white;display:none;place-items:center;text-align:center;z-index:5}.loading.show{display:grid}.spinner{width:48px;height:48px;border:5px solid #ffffff35;border-top-color:white;border-radius:50%;animation:spin .8s linear infinite;margin:auto}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:600px){main{padding:16px}.panel{padding:22px}.options{grid-template-columns:1fr}}
</style></head><body><main><section class="panel"><h1>Loan Package Review</h1><p class="sub">대출 패키지 PDF의 페이지 분류 결과를 확인합니다.</p>
<form id="form" method="post" action="/analyze" enctype="multipart/form-data">
<label class="drop" for="pdf"><strong>PDF 파일 선택</strong><span>최대 50MB · 파일은 분석 후 자동 삭제</span><div id="fileName"></div></label><input id="pdf" name="pdf" type="file" accept="application/pdf,.pdf" required>
<div class="options"><label class="option"><input name="ocr" type="checkbox" checked> OCR 사용<small>이미지로 된 페이지 읽기</small></label><label class="option"><input name="ai" type="checkbox" checked> 추가 검토<small>판단이 애매한 페이지만 확인</small></label></div>
<button id="submit" type="submit" disabled>분석 시작</button></form>
<p class="privacy">로컬 전용: PDF와 분석 결과는 이 PC 밖으로 전송되지 않습니다.</p></section></main>
<div id="loading" class="loading"><div><div class="spinner"></div><h2>PDF 분석 중</h2><p>페이지 수와 OCR 대상에 따라 잠시 걸릴 수 있습니다.</p></div></div>
<script>const f=document.querySelector('#pdf'),b=document.querySelector('#submit'),n=document.querySelector('#fileName'),form=document.querySelector('#form');f.addEventListener('change',()=>{n.textContent=f.files[0]?.name||'';b.disabled=!f.files.length});form.addEventListener('submit',()=>document.querySelector('#loading').classList.add('show'));</script></body></html>"""


class AnalyzerServer(ThreadingHTTPServer):
    runtime_root: Path
    project_root: Path
    pdftoppm: str
    tesseract: str
    ollama_url: str
    model: str


class Handler(BaseHTTPRequestHandler):
    server: AnalyzerServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(UPLOAD_PAGE)
            return
        if parsed.path == "/health":
            self._send_json({"status": "ok"})
            return
        if parsed.path == "/reset":
            session_id = parse_qs(parsed.query).get("session", [""])[0]
            self._delete_session(session_id)
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if parsed.path.startswith("/sessions/"):
            self._serve_session_file(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/analyze":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        upload_path: Path | None = None
        try:
            fields, filename, pdf_data = self._parse_upload()
            session_id = secrets.token_hex(6)
            session_dir = self.server.runtime_root / session_id
            session_dir.mkdir(parents=True, exist_ok=False)
            upload_path = session_dir / "upload.pdf"
            upload_path.write_bytes(pdf_data)
            self._run_analysis(upload_path, session_dir, fields)
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", f"/sessions/{quote(session_id)}/")
            self.end_headers()
        except Exception as exc:
            self._send_error_page(type(exc).__name__, str(exc))
        finally:
            if upload_path is not None:
                upload_path.unlink(missing_ok=True)

    def _parse_upload(self) -> tuple[dict[str, str], str, bytes]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            raise ValueError("Upload must be between 1 byte and 50MB")
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Expected a multipart PDF upload")
        body = self.rfile.read(length)
        message = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
        )
        fields: dict[str, str] = {}
        filename = ""
        pdf_data = b""
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition") or ""
            if name == "pdf":
                filename = part.get_filename() or "upload.pdf"
                pdf_data = part.get_payload(decode=True) or b""
            else:
                fields[name] = (part.get_content() or "").strip()
        if not filename.lower().endswith(".pdf") or not pdf_data.startswith(b"%PDF-"):
            raise ValueError("The selected file is not a valid PDF")
        return fields, filename, pdf_data

    def _run_analysis(self, upload: Path, session: Path, fields: dict[str, str]) -> None:
        use_ocr = "ocr" in fields
        use_ai = "ai" in fields
        ocr = (
            PopplerTesseractOcrEngine(
                pdftoppm_command=self.server.pdftoppm,
                tesseract_command=self.server.tesseract,
            )
            if use_ocr
            else None
        )
        ai = (
            OllamaClassifier(model=self.server.model, base_url=self.server.ollama_url)
            if use_ai
            else None
        )
        pages, documents = analyze_pdf(upload, ocr_engine=ocr, ai_classifier=ai)
        analysis_dir = session / "analysis"
        write_json(analysis_dir / "results.json", result_payload(pages, documents))
        write_page_csv(analysis_dir / "pages.csv", pages)
        write_html_report(analysis_dir / "report.html", pages, documents, title="Uploaded PDF")

        builder = self.server.project_root / "scripts" / "build_local_review.py"
        command = [
                sys.executable,
                str(builder),
                str(upload),
                str(analysis_dir / "results.json"),
                str(session / "review"),
                "--pdftoppm",
                self.server.pdftoppm,
                "--tesseract",
                self.server.tesseract,
            ]
        if not use_ocr:
            command.append("--skip-ocr")
        subprocess.run(
            command,
            check=True,
            env={**os.environ, "PYTHONPATH": str(self.server.project_root / "src")},
        )
        index = session / "review" / "index.html"
        markup = index.read_text(encoding="utf-8").replace(
            "<div class=\"warning\">",
            f'<div class="warning"><a href="/">새 PDF 분석</a> · '
            f'<a href="/reset?session={session.name}">현재 결과 삭제</a><br>',
            1,
        )
        index.write_text(markup, encoding="utf-8")

    def _serve_session_file(self, request_path: str) -> None:
        parts = [unquote(part) for part in request_path.split("/") if part]
        if len(parts) < 2 or parts[0] != "sessions":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        session_id = parts[1]
        if not self._valid_session_id(session_id):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        relative = Path(*parts[2:]) if len(parts) > 2 else Path("index.html")
        root = (self.server.runtime_root / session_id / "review").resolve()
        target = (root / relative).resolve()
        if root not in target.parents and target != root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "image/jpeg"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _delete_session(self, session_id: str) -> None:
        if self._valid_session_id(session_id):
            target = (self.server.runtime_root / session_id).resolve()
            if target.parent == self.server.runtime_root.resolve() and target.is_dir():
                shutil.rmtree(target)

    @staticmethod
    def _valid_session_id(value: str) -> bool:
        return len(value) == 12 and all(char in "0123456789abcdef" for char in value)

    def _send_html(self, markup: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = markup.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, object]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error_page(self, title: str, message: str) -> None:
        self._send_html(
            "<!doctype html><meta charset='utf-8'><title>Analysis failed</title>"
            "<style>body{font:16px Segoe UI;max-width:760px;margin:10vh auto;padding:24px}"
            "a{color:#2563eb}</style>"
            f"<h1>분석 실패: {html.escape(title)}</h1><p>{html.escape(message)}</p>"
            "<p><a href='/'>업로드 화면으로 돌아가기</a></p>",
            HTTPStatus.BAD_REQUEST,
        )

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.address_string()}] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local loan package review server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--runtime-root", type=Path, default=Path("outputs/runtime"))
    parser.add_argument("--pdftoppm", default="pdftoppm")
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    runtime_root = args.runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    server = AnalyzerServer((args.host, args.port), Handler)
    server.runtime_root = runtime_root
    server.project_root = project_root
    server.pdftoppm = args.pdftoppm
    server.tesseract = args.tesseract
    server.ollama_url = args.ollama_url
    server.model = args.model
    print(f"Loan Package Review: http://{args.host}:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
