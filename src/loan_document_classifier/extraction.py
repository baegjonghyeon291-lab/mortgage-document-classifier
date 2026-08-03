from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Protocol

from pypdf import PdfReader

from .models import ExtractedPage


class OcrEngine(Protocol):
    def extract_page(self, pdf_path: Path, page_index: int) -> str: ...


class NoOcrEngine:
    def extract_page(self, pdf_path: Path, page_index: int) -> str:
        return ""


class TesseractOcrEngine:
    """Optional OCR adapter. Imports native dependencies only when it is used."""

    def __init__(self, language: str = "eng", dpi: int = 200) -> None:
        self.language = language
        self.dpi = dpi

    def extract_page(self, pdf_path: Path, page_index: int) -> str:
        try:
            import fitz
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "OCR requires the 'ocr' dependency group and a Tesseract installation"
            ) from exc

        with fitz.open(pdf_path) as document:
            page = document[page_index]
            pixmap = page.get_pixmap(dpi=self.dpi, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            return pytesseract.image_to_string(image, lang=self.language).strip()


class PopplerTesseractOcrEngine:
    """OCR adapter using standalone Poppler and Tesseract executables.

    This avoids binding the pipeline to native Python wheels and keeps OCR failures isolated in
    subprocesses with captured diagnostics.
    """

    def __init__(
        self,
        language: str = "eng",
        dpi: int = 200,
        pdftoppm_command: str = "pdftoppm",
        tesseract_command: str = "tesseract",
    ) -> None:
        self.language = language
        self.dpi = dpi
        self.pdftoppm_command = pdftoppm_command
        self.tesseract_command = tesseract_command

    def extract_page(self, pdf_path: Path, page_index: int) -> str:
        pdftoppm = shutil.which(self.pdftoppm_command) or self.pdftoppm_command
        tesseract = shutil.which(self.tesseract_command) or self.tesseract_command
        page_number = page_index + 1
        with tempfile.TemporaryDirectory(prefix="loan-doc-ocr-") as folder:
            prefix = Path(folder) / "page"
            render = subprocess.run(
                [
                    pdftoppm,
                    "-f", str(page_number),
                    "-l", str(page_number),
                    "-r", str(self.dpi),
                    "-singlefile",
                    "-png",
                    str(pdf_path),
                    str(prefix),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if render.returncode != 0:
                raise RuntimeError(f"pdftoppm failed: {render.stderr.strip()}")
            image = prefix.with_suffix(".png")
            ocr = subprocess.run(
                [tesseract, str(image), "stdout", "-l", self.language, "--psm", "1"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if ocr.returncode != 0:
                raise RuntimeError(f"tesseract failed: {ocr.stderr.strip()}")
            return ocr.stdout.strip()


def _image_count(page: object) -> int:
    try:
        resources = page.get("/Resources") or {}
        objects = resources.get("/XObject") or {}
        return sum(
            1 for reference in objects.values() if reference.get_object().get("/Subtype") == "/Image"
        )
    except Exception:
        return 0


def extract_pages(
    pdf_path: str | Path,
    *,
    ocr_engine: OcrEngine | None = None,
    min_embedded_chars: int = 20,
) -> list[ExtractedPage]:
    path = Path(pdf_path)
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("Encrypted PDF cannot be read without a password") from exc

    ocr = ocr_engine or NoOcrEngine()
    results: list[ExtractedPage] = []
    for index, page in enumerate(reader.pages):
        warning = None
        try:
            embedded = (page.extract_text() or "").strip()
        except Exception as exc:
            embedded = ""
            warning = f"embedded text extraction failed: {type(exc).__name__}"

        text = embedded
        method = "embedded" if len(embedded) >= min_embedded_chars else "none"
        if method == "none":
            try:
                ocr_text = ocr.extract_page(path, index).strip()
            except Exception as exc:
                ocr_text = ""
                warning = f"OCR failed: {type(exc).__name__}: {exc}"
            if ocr_text:
                text = ocr_text
                method = "ocr"

        results.append(
            ExtractedPage(
                source_page=index + 1,
                text=text,
                extraction_method=method,
                text_length=len(text),
                image_count=_image_count(page),
                extraction_warning=warning,
            )
        )
    return results
