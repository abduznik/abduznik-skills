---
name: pdf-surgical-edits
description: "Redact, draw, and add text to existing PDFs via PyMuPDF."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [pdf, redact, annotate, pymupdf]
    category: software-development
tags: [pdf, pymupdf, hebrew, rtl, bidi, redaction, editing]
---


# PDF Surgical Edits

Modify existing PDF pages in-place: blank regions, redraw shapes, insert text. Uses PyMuPDF (`pymupdf`).

## Prerequisites

```bash
python -m pip install PyMuPDF
# For RTL/Hebrew/Arabic text:
python -m pip install python-bidi
```

## Workflow: Redact → Draw → Insert

### 1. Redact (blank an area)

Removes all drawings AND text in the rect. Fills with a color (usually white).

```python
import pymupdf
doc = pymupdf.open('input.pdf')
page = doc[0]
page.add_redact_annot(pymupdf.Rect(x0, y0, x1, y1), fill=(1, 1, 1))
page.apply_redactions()
```

**Redaction removes everything** in the rect — vector shapes, text, images. Grid lines inside the rect are also removed. Redraw them after if needed.

### 2. Draw shapes (rebuild grid, add colored blocks)

```python
def draw_rect(page, x0, y0, x1, y1, fill=None, color=(0,0,0), width=0.5):
    shape = page.new_shape()
    shape.draw_rect(pymupdf.Rect(x0, y0, x1, y1))
    if fill:
        shape.finish(fill=fill, color=fill, width=width)
    else:
        shape.finish(color=color, width=width)
    shape.commit()
```

### 3. Insert text

#### LTR text (English, numbers, codes)

```python
page.insert_text(
    pymupdf.Point(x, y), 'Hello 123',
    fontfile='C:/Windows/Fonts/tahoma.ttf', fontname='tah', fontsize=6
)
```

#### RTL text (Hebrew, Arabic) — REQUIRES python-bidi

**pymupdf does NOT apply Unicode bidi.** Hebrew text inserted in logical order renders backwards in PDF viewers. Convert to visual order first:

```python
from bidi.algorithm import get_display

visual = get_display('תרגול-1 אלגוריתמים')
page.insert_text(
    pymupdf.Point(x, y), visual,  # visual order, NOT logical
    fontfile='C:/Windows/Fonts/tahoma.ttf', fontname='tah', fontsize=6
)
```

**Right-align Hebrew text** — calculate x from right edge:

```python
def rtl(page, x_right, y, text, fontsize=6, char_width=0.38):
    visual = get_display(text)
    w = len(text) * fontsize * char_width
    page.insert_text(
        pymupdf.Point(x_right - w, y), visual,
        fontfile='C:/Windows/Fonts/tahoma.ttf', fontname='tah', fontsize=fontsize
    )
```

`char_width` of 0.38 works for Tahoma at small sizes. Verify with a test render for other fonts.

## PDF Table Structure Analysis

Map table columns/rows from text coordinates:

```python
blocks = page.get_text('dict')['blocks']
for b in blocks:
    if 'lines' not in b:
        continue
    for line in b['lines']:
        for span in line['spans']:
            text = span['text'].strip()
            bbox = span['bbox']  # (x0, y0, x1, y1)
            cx = (bbox[0] + bbox[2]) / 2
            # Map cx to column based on header positions
```

Steps:
1. Extract header text positions to find column boundaries
2. Assign each data block to a column by x-center
3. Map y-positions to row labels using the hour/time column

## Enumerating Vector Elements

Use `page.get_drawings()` to list all vector shapes — useful for identifying which drawings belong to which table area:

```python
for i, d in enumerate(page.get_drawings()):
    rect = d.get('rect')
    fill = d.get('fill')
    if rect:
        print(f'[{i}] rect={rect} fill={fill}')
```

## Pitfalls

- **Redaction kills grid lines.** Redrawing a table cell removes the dividers inside it. Redraw them explicitly after redaction.
- **Hebrew text reversed without bidi.** Always use `get_display()` from python-bidi for RTL scripts. `insert_htmlbox` with `dir="rtl"` CSS also fails — it renders LTR.
- **Font path is OS-specific.** Tahoma: `C:/Windows/Fonts/tahoma.ttf` (Windows). On Linux/macOS use Noto Sans Hebrew or similar.
- **Save to same path fails.** `doc.save(path)` errors if path == the opened file. Use incremental save or open from original source.
- **Verify with vision_analyze.** Text extraction may show different order than visual rendering. Always render a crop and verify for layout-critical edits.