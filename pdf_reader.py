from io import BytesIO
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

from config import MIN_TEXT_CHARS, PDF_RENDER_SCALE


def extract_text(pdf_path: Path) -> str | None:
    """Return embedded PDF text, or None when there is too little to use."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
    combined = "\n\n".join(pages).strip()
    if len(combined) < MIN_TEXT_CHARS:
        return None
    return combined


def render_pages(pdf_path: Path, scale: float | None = None) -> list[bytes]:
    """Render each PDF page to PNG bytes for vision models."""
    scale = scale or PDF_RENDER_SCALE
    doc = pdfium.PdfDocument(str(pdf_path))
    images: list[bytes] = []
    try:
        for index in range(len(doc)):
            page = doc[index]
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            buffer = BytesIO()
            pil_image.save(buffer, format="PNG")
            images.append((buffer.getvalue(), "image/png"))
    finally:
        doc.close()

    if not images:
        raise ValueError(f"Could not render pages from PDF: {pdf_path.name}")
    return images
