---
name: pdf-flatten
description: Use when flattening PDFs to page images or raster PDFs.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [pdf, rasterize, flatten, vision, pymupdf]
    category: software-development
---




# PDF Flatten

## Overview

Flatten any PDF into a pixel-perfect raster form: either a set of per-page
images (PNG/JPG) or a rebuilt PDF where every page is a high-DPI render.
This kills the text layer intentionally — the result is exactly what a vision
model or a human sees when they look at the page. Built for datasheet
workflows, scanned-document archival, and feeding documents to image-based
models.

Two scripts ship with this skill (in `scripts/`):

- `pdf_to_pages.py` — render pages to images: `--dpi` (default 250),
  `--out`, `--format png|jpg`, `--quality`, `--pages 1-5` / `3,5,7-10`,
  `--json` for machine-readable output.
- `pdf_flatten.py` — rebuild the whole PDF from rendered pages.

Both use PyMuPDF: `pip install pymupdf`.

## When to Use

- A PDF must be consumed as images (vision models, screenshots in a container).
- Vector/text artifacts break downstream tooling and you need "what you see".
- Datasheets or scanned docs where the selectable-text layer is corrupt or
  missing.
- **Don't use for:** text extraction or search — this converts to pixels by
  design. Use extraction tooling instead when text matters.

## Scanned PDF Detection (before flattening)

An image-only PDF has no text layer. Detect it cheaply with PyMuPDF — if all
three return empty, it's scanned and rasterization is the only path:

```python
page = doc[i]
text = page.get_text('text')     # ''
blocks = page.get_text('blocks')  # []
words = page.get_text('words')    # []
```

## Usage

```bash
# Every page as PNG at 250 DPI
python3 scripts/pdf_to_pages.py input.pdf

# Custom DPI + output dir
python3 scripts/pdf_to_pages.py input.pdf --dpi 300 --out ./pages

# JPEG with quality control
python3 scripts/pdf_to_pages.py input.pdf --format jpg --quality 90

# Page range (big documents)
python3 scripts/pdf_to_pages.py input.pdf --pages 1-5

# Rebuild a flat, raster-only PDF
python3 scripts/pdf_flatten.py input.pdf -o flattened.pdf --dpi 250
```

## Batch / Pipeline Pattern

Chain both scripts for N documents in one pass: gather files, iterate,
render each page, rebuild each PDF into a dated output folder. Keep the
pipeline idempotent — skip already-rendered outputs.

## Common Pitfalls

1. **Memory on large page counts** — rendering 600+ pages at 300 DPI is
   heavy; process page ranges (`--pages`) or reduce `--dpi`.
2. **The text layer is gone on purpose** — do not "flatten then extract
   text"; flatten only when pixels are the deliverable.
3. **Output dates/timestamps** — write outputs to a dated folder so reruns
   don't collide.
4. **Rebuilt PDF size** — 250 DPI PNG inside PDF can be large; JPEG with
   `--quality 90` is a good compressor for photo-like pages.
5. **PyMuPDF version drift** — pin `pymupdf` in requirements; save/`doc.save`
   keyword names changed across versions.

## Verification Checklist

- [ ] Rendered page count equals source page count (or the requested range)
- [ ] Rebuilt PDF opens and every page is an image (no selectable text)
- [ ] Output dimensions match source aspect ratio
- [ ] Spot-check 1-2 pages visually before distribution