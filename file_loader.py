"""Discover and load invoice files (PDF, JPEG, PNG)."""

from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = PDF_SUFFIXES | IMAGE_SUFFIXES

MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def is_pdf(path: Path) -> bool:
    return path.suffix.lower() in PDF_SUFFIXES


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def image_mime(path: Path) -> str:
    return MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def load_image(path: Path) -> tuple[bytes, str]:
    return path.read_bytes(), image_mime(path)


def list_invoice_files(path: Path) -> list[Path]:
    """Return supported invoice files from a file or folder (non-recursive)."""
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported file type: {path.suffix}. "
                f"Use PDF, PNG, JPG, or WEBP."
            )
        return [path]

    if not path.is_dir():
        raise ValueError(f"Not a file or folder: {path}")

    files = [
        p
        for p in sorted(path.iterdir())
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    if not files:
        raise ValueError(
            f"No invoice files found in {path}. "
            f"Drop PDF / PNG / JPG / WEBP files there."
        )
    return files
