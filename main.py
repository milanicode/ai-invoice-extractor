#!/usr/bin/env python3
"""Invoice PDF/JPEG/PNG → LLM extraction → Excel (single file or whole folder)."""

import argparse
import sys
from pathlib import Path

from config import OUTPUT_DIR
from excel_writer import append_invoice, reset_workbook
from extractors import extract_invoice
from file_loader import is_image, is_pdf, list_invoice_files, load_image
from pdf_reader import extract_text, render_pages


def process_file(path: Path, output: Path) -> tuple[str, str]:
    """Extract one invoice and append to Excel. Returns (provider, mode)."""
    if is_pdf(path):
        text = extract_text(path)
        if text:
            data, provider = extract_invoice(text=text)
            mode = "text"
        else:
            images = render_pages(path)
            data, provider = extract_invoice(images=images)
            mode = f"vision ({len(images)} page(s))"
    elif is_image(path):
        image_bytes, mime = load_image(path)
        data, provider = extract_invoice(images=[(image_bytes, mime)])
        mode = "vision (image)"
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    append_invoice(output, path.name, provider, data)
    return provider, mode


def process_inputs(paths: list[Path], output: Path, *, fresh: bool = False) -> int:
    if fresh:
        reset_workbook(output)
        print(f"Fresh Excel: {output}")

    ok = 0
    failed: list[tuple[str, str]] = []

    for path in paths:
        try:
            provider, mode = process_file(path, output)
            print(f"OK  {path.name}  [{provider}, {mode}]")
            ok += 1
        except Exception as exc:
            print(f"FAIL  {path.name}  →  {exc}", file=sys.stderr)
            failed.append((path.name, str(exc)))

    print("")
    print(f"Done: {ok}/{len(paths)} ok → {output}")
    if failed:
        print(f"Failed: {len(failed)}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract invoice data from PDF/JPEG/PNG files or a whole folder into Excel."
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="Invoice file or folder (e.g. incoming/2026-07)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "invoices.xlsx",
        help="Output Excel file (default: output/invoices.xlsx)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Overwrite Excel with a clean file before this run (no old rows)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with demo/sample-invoice.pdf",
    )
    args = parser.parse_args()

    if args.demo:
        target = Path(__file__).parent / "demo" / "sample-invoice.pdf"
    elif args.path:
        target = args.path
    else:
        parser.print_help()
        print(
            "\nExamples:\n"
            "  python main.py --demo --fresh\n"
            "  python main.py incoming/Example_Invoices --fresh\n"
            "  python main.py incoming/Example_Invoices/Nfe.png\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if not target.exists():
        print(f"File or folder not found: {target}", file=sys.stderr)
        sys.exit(1)

    try:
        files = list_invoice_files(target)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(files)} file(s)…")
    raise SystemExit(process_inputs(files, args.output, fresh=args.fresh))


if __name__ == "__main__":
    main()
