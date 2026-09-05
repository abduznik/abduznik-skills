#!/usr/bin/env python3
"""
PDF to Pages — convert each page of a PDF into a PNG screenshot image.

Takes any PDF (datasheets, manuals, reports) and renders every page as a
high-resolution PNG, saved into a dated output folder.

Usage:
    python pdf_to_pages.py "path/to/datasheet.pdf"
    python pdf_to_pages.py "path/to/file.pdf" --dpi 300 --out ./my_pages
    python pdf_to_pages.py "path/to/file.pdf" --dpi 200 --format jpg --quality 90
    python pdf_to_pages.py "path/to/file.pdf" --pages 1-5          # first 5 pages only
    python pdf_to_pages.py "path/to/file.pdf" --pages 3,5,7-10    # specific page ranges

Dependencies: PyMuPDF (fitz) — pip install PyMuPDF
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF is required. Install with: pip install PyMuPDF", file=sys.stderr)
    sys.exit(1)


def parse_page_spec(spec: str, total: int) -> list[int]:
    """Parse a page range spec like '1-5', '3,5,7-10', or '1-5,8,11-13'.
    Returns a sorted, deduplicated list of 0-indexed page numbers.
    """
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start, end = int(start_s.strip()), int(end_s.strip())
                if start < 1 or end > total or start > end:
                    raise ValueError
                pages.update(range(start - 1, end))  # convert to 0-indexed
            except ValueError:
                print(f"WARNING: Invalid range '{part}' — skipping (valid: 1-{total})", file=sys.stderr)
        else:
            try:
                p = int(part)
                if 1 <= p <= total:
                    pages.add(p - 1)
                else:
                    print(f"WARNING: Page {p} out of range (1-{total}) — skipping", file=sys.stderr)
            except ValueError:
                print(f"WARNING: Invalid page '{part}' — skipping", file=sys.stderr)
    return sorted(pages)


def convert_pdf(
    pdf_path: str,
    out_dir: str | None = None,
    dpi: int = 250,
    fmt: str = "png",
    quality: int = 95,
    page_spec: str | None = None,
) -> dict:
    """Convert each page of a PDF to an image.

    Args:
        pdf_path: Path to the PDF file.
        out_dir: Output directory (auto-generated from PDF name if None).
        dpi: Resolution in DPI (default 250).
        fmt: Output format — 'png' or 'jpg' (default 'png').
        quality: JPEG quality 1-100 (default 95, only used for jpg).
        page_spec: Optional page range spec, e.g. '1-5' or '3,5,7-10'.

    Returns:
        dict with paths, page count, and stats.
    """
    pdf_path = os.path.abspath(pdf_path)
    pdf_name = Path(pdf_path).stem

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    if total_pages == 0:
        doc.close()
        raise ValueError(f"PDF has no pages: {pdf_path}")

    # Determine which pages to render
    if page_spec:
        page_nums = parse_page_spec(page_spec, total_pages)
        if not page_nums:
            print(f"No valid pages in spec '{page_spec}', rendering all pages.", file=sys.stderr)
            page_nums = list(range(total_pages))
    else:
        page_nums = list(range(total_pages))

    # Output directory
    if out_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.join(os.getcwd(), f"{pdf_name}_pages_{timestamp}")
    os.makedirs(out_dir, exist_ok=True)

    # Render
    zoom = dpi / 72  # PyMuPDF base resolution is 72 DPI
    mat = fitz.Matrix(zoom, zoom)

    ext = fmt.lower()
    results = []
    render_count = len(page_nums)

    print(f"📄 {pdf_name}.pdf — {total_pages} total pages, rendering {render_count} at {dpi} DPI")
    print(f"   Output: {out_dir}")
    print()

    for idx, page_num in enumerate(page_nums):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        if ext == "png":
            filename = f"page_{page_num + 1:04d}.png"
            out_path = os.path.join(out_dir, filename)
            pix.save(out_path)
        else:
            filename = f"page_{page_num + 1:04d}.jpg"
            out_path = os.path.join(out_dir, filename)
            pix.save(out_path, jpg_quality=quality)

        file_size = os.path.getsize(out_path)
        results.append({"page": page_num + 1, "path": out_path, "size_kb": round(file_size / 1024, 1)})

        # Progress bar
        pct = (idx + 1) / render_count * 100
        bar_len = 30
        filled = int(bar_len * (idx + 1) / render_count)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r   [{bar}] {idx + 1}/{render_count} — page {page_num + 1} ({results[-1]['size_kb']} KB)", end="")

    print("\n")

    doc.close()

    # Summary
    total_size_kb = sum(r["size_kb"] for r in results)
    summary = {
        "pdf": pdf_path,
        "total_pages": total_pages,
        "rendered_pages": render_count,
        "page_numbers": [r["page"] for r in results],
        "dpi": dpi,
        "format": ext,
        "quality": quality if ext == "jpg" else None,
        "output_dir": out_dir,
        "files": results,
        "total_size_kb": round(total_size_kb, 1),
    }

    print(f"✓ Done — {render_count} pages → {out_dir}")
    print(f"  Total: {round(total_size_kb / 1024, 2)} MB, {round(total_size_kb / render_count, 1)} KB avg per page")
    print()

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Convert each page of a PDF into a PNG/JPG screenshot image.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "datasheet.pdf"
  %(prog)s "datasheet.pdf" --dpi 300 --out ./pages
  %(prog)s "manual.pdf" --dpi 200 --format jpg --quality 90
  %(prog)s "file.pdf" --pages 1-5
  %(prog)s "file.pdf" --pages 3,5,7-10
        """,
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--dpi", type=int, default=250, help="Output resolution in DPI (default: 250)")
    parser.add_argument(
        "--format", "-f", choices=["png", "jpg", "jpeg"], default="png",
        help="Output image format (default: png)",
    )
    parser.add_argument("--quality", "-q", type=int, default=95, help="JPEG quality 1-100 (default: 95, JPEG only)")
    parser.add_argument("--out", "-o", help="Output directory (auto-generated if not specified)")
    parser.add_argument(
        "--pages", "-p",
        help="Page range(s) to render, e.g. '1-5', '3,5,7-10', '1-5,8,11-13'",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Normalize jpeg → jpg
    fmt = args.format.lower().replace("jpeg", "jpg")

    try:
        result = convert_pdf(
            pdf_path=args.pdf,
            out_dir=args.out,
            dpi=args.dpi,
            fmt=fmt,
            quality=args.quality,
            page_spec=args.pages,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        import json
        print(json.dumps(result))


if __name__ == "__main__":
    main()
