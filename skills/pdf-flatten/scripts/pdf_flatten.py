#!/usr/bin/env python3
"""
PDF Flatten — rasterize every page of a PDF into a high-res image,
then stitch them back into a new PDF.

The output PDF looks identical but every page is a pure bitmap (no selectable
text, no vector graphics). Useful for:
  - Flattening datasheets with weird fonts/vector artifacts
  - Ensuring consistent rendering across PDF viewers
  - Creating a "screenshot PDF" from the original

Usage:
    python pdf_flatten.py "datasheet.pdf"
    python pdf_flatten.py "datasheet.pdf" --dpi 300 -o flattened.pdf
    python pdf_flatten.py "datasheet.pdf" --dpi 250 --jpg --pages 1-5
    python pdf_flatten.py "datasheet.pdf" --json

Dependencies: PyMuPDF (fitz) — pip install PyMuPDF
"""

import argparse
import json
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
    """Parse a page range spec like '1-5', '3,5,7-10', returning 0-indexed list."""
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
                pages.update(range(start - 1, end))
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


def flatten_pdf(
    pdf_path: str,
    output_path: str | None = None,
    dpi: int = 250,
    fmt: str = "png",
    jpg_quality: int = 95,
    page_spec: str | None = None,
) -> dict:
    """
    Rasterize each page of a PDF to an image, then reconstruct into a new PDF.

    Args:
        pdf_path: Path to input PDF.
        output_path: Path for output PDF (auto-generated if None).
        dpi: Resolution in DPI.
        fmt: Intermediate image format — 'png' (lossless) or 'jpg' (smaller).
        jpg_quality: JPEG quality 1-100 (JPEG only).
        page_spec: Optional page range, e.g. '1-5' or '3,5,7-10'.

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

    # Determine page range
    if page_spec:
        page_nums = parse_page_spec(page_spec, total_pages)
        if not page_nums:
            print(f"No valid pages in spec '{page_spec}', using all pages.", file=sys.stderr)
            page_nums = list(range(total_pages))
    else:
        page_nums = list(range(total_pages))

    # Output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(os.getcwd(), f"{pdf_name}_flattened_{timestamp}.pdf")
    output_path = os.path.abspath(output_path)
    os.makedirs(Path(output_path).parent, exist_ok=True)

    # Render each page → image → insert into output PDF
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    ext = fmt.lower()

    doc_out = fitz.open()  # new empty PDF
    render_count = len(page_nums)
    page_results = []

    print(f"📄 {pdf_name}.pdf — {total_pages} total, rasterizing {render_count} at {dpi} DPI")
    print(f"   Output: {output_path}")
    print()

    for idx, page_num in enumerate(page_nums):
        page = doc.load_page(page_num)

        # Render page to pixmap (raw pixels)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # Convert pixmap to a temporary image in memory, then to PDF
        img_bytes = pix.tobytes(ext)

        # Open the image bytes as a fitz image, convert to PDF page
        img_doc = fitz.open(ext, img_bytes)  # open as image
        pdf_bytes = img_doc.convert_to_pdf()  # image → PDF bytes
        img_doc.close()

        # Insert as a page into the output
        page_pdf = fitz.open("pdf", pdf_bytes)
        doc_out.insert_pdf(page_pdf)
        page_pdf.close()

        # Stats
        w, h = pix.width, pix.height
        page_results.append({"page": page_num + 1, "width": w, "height": h, "dpi": dpi})

        # Progress
        pct = (idx + 1) / render_count * 100
        bar_len = 30
        filled = int(bar_len * (idx + 1) / render_count)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r   [{bar}] {idx + 1}/{render_count} — page {page_num + 1} ({w}×{h})", end="")

    print("\n")

    doc.close()

    # Save
    doc_out.save(output_path, deflate=True, garbage=4)
    doc_out.close()

    file_size = os.path.getsize(output_path)

    summary = {
        "input_pdf": pdf_path,
        "output_pdf": output_path,
        "total_pages": total_pages,
        "rasterized_pages": render_count,
        "dpi": dpi,
        "format": fmt,
        "jpg_quality": jpg_quality if fmt == "jpg" else None,
        "page_details": page_results,
        "output_size_kb": round(file_size / 1024, 1),
        "output_size_mb": round(file_size / (1024 * 1024), 2),
    }

    print(f"✓ Done — {render_count} pages → {output_path}")
    print(f"  Size: {summary['output_size_mb']} MB ({summary['output_size_kb']} KB)")
    print()

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Flatten a PDF by rasterizing every page to an image and rebuilding.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "datasheet.pdf"
  %(prog)s "datasheet.pdf" --dpi 300 -o flattened.pdf
  %(prog)s "file.pdf" --dpi 250 --jpg --pages 1-5
  %(prog)s "file.pdf" --json
        """,
    )
    parser.add_argument("pdf", help="Path to the input PDF file")
    parser.add_argument("--dpi", type=int, default=250, help="Output resolution in DPI (default: 250)")
    parser.add_argument(
        "--format", "-f", choices=["png", "jpg", "jpeg"], default="png",
        help="Intermediate image format. PNG = lossless but larger PDF. JPG = smaller PDF (default: png)",
    )
    parser.add_argument(
        "--quality", "-q", type=int, default=95,
        help="JPEG quality 1-100 (default: 95, JPEG only)",
    )
    parser.add_argument("--out", "-o", help="Output PDF path (auto-generated if not specified)")
    parser.add_argument(
        "--pages", "-p",
        help="Page range(s) to flatten, e.g. '1-5', '3,5,7-10', '1-5,8,11-13'",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    fmt = args.format.lower().replace("jpeg", "jpg")

    try:
        result = flatten_pdf(
            pdf_path=args.pdf,
            output_path=args.out,
            dpi=args.dpi,
            fmt=fmt,
            jpg_quality=args.quality,
            page_spec=args.pages,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
