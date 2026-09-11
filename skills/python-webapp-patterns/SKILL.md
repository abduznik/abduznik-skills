---
name: python-webapp-patterns
description: >
  Build Python web apps with FastAPI or Flask — static file serving, search-index
  frontends, PDF/binary serving, and Windows-specific pitfalls. Covers the
  local-index-first search pattern, binary response serving, and asyncio quirks.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [python, fastapi, flask, webapp]
    category: software-development
tags: [fastapi, flask, web, frontend, windows, search, pdf]
---




# Python Web App Patterns

Reusable patterns for building self-hosted Python web apps with FastAPI (or Flask)
that serve a vanilla JS frontend and handle binary content like PDFs.

## 1. Serving binary files (PDFs) on Windows

**Pitfall:** `FileResponse(path=str(path_obj))` can silently fail on Windows
when serving PDFs for iframe embedding. The browser receives the response but
the iframe shows blank or "Failed to load PDF". Root cause: Windows path
encoding quirks in Starlette's `FileResponse` implementation.

**Fix:** Read the file bytes manually and return a raw `Response`:

```python
from pathlib import Path
from fastapi.responses import Response

def serve_pdf(pdf_path: Path, filename: str) -> Response:
    content = pdf_path.read_bytes()
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}.pdf"',
            "Content-Length": str(len(content)),
            "Cache-Control": "public, max-age=3600",
        },
    )
```

Use `Content-Disposition: inline` (not `attachment`) for iframe embedding.
Set `Content-Length` explicitly — some browsers need it for PDF rendering.

`FileResponse` is still fine for HTML/text (e.g. serving `index.html`).

## 2. Local-index-first search with backend fallback

When building a search UI with Fuse.js over a local index that starts empty
(e.g. a datasheet library that grows over time), always wire a backend fallback:

**Pattern:**
1. Load index from `GET /api/index` on page init → build Fuse.js instance
2. On input (debounced 150ms): search Fuse.js locally
3. If Fuse.js returns 0 results AND query.length >= 2:
   - Fire `GET /search?q={query}` to the backend (with AbortController)
   - Backend searches remote sources, caches result, returns JSON
   - On success: re-fetch `/api/index`, rebuild Fuse.js, re-run local search
   - Show toast with result metadata
4. Cancel pending backend search on each new keystroke

**Key implementation details:**
- Use `AbortController` to cancel stale backend requests when user keeps typing
- Track a `pendingBackendSearch` reference; abort it before starting a new one
- After backend finds a result, the index has grown — re-init Fuse.js
- Don't re-fetch the index on every input focus; track `_indexLoaded` flag
- Suppress "Loaded 0 datasheets" toast on cold start (show only when count > 0)

```javascript
let pendingBackendSearch = null;

async function backendSearch(query) {
    if (pendingBackendSearch) pendingBackendSearch.abort();
    const controller = new AbortController();
    pendingBackendSearch = controller;

    try {
        const resp = await fetch(`/search?q=${encodeURIComponent(query)}`,
            { signal: controller.signal });
        if (!resp.ok) return;
        const result = await resp.json();
        if (result.status === 'found' || result.status === 'cached') {
            state.index = await apiGet('/api/index');
            rebuildFuse();  // re-init with new data
            performSearch(query);  // re-run local search
            showToast(`Found: ${result.part}`, 'success');
        }
    } catch (err) {
        if (err.name !== 'AbortError') console.warn('Backend search failed:', err);
    } finally {
        if (pendingBackendSearch === controller) pendingBackendSearch = null;
    }
}
```

## 3. FastAPI app structure for self-hosted tools

Recommended layout for a single-page app with API backend:

```
project/
├── backend/
│   ├── proxy.py          # FastAPI app + routes
│   ├── finder.py         # Business logic
│   ├── models.py         # Pydantic models
│   └── sources/          # Plugin architecture
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/
│   └── (runtime data, gitignored)
├── requirements.txt
└── run.py                # Entry point
```

**Route patterns:**
- `GET /` → `FileResponse` for `index.html`
- `GET /static/{path}` → `StaticFiles` mount for CSS/JS
- `GET /api/*` → JSON API endpoints
- `GET /pdf/{id}` → Binary content serving (use the Response pattern above)

**CORS:** For local dev, `allow_origins=["*"]` is fine. For production behind
a reverse proxy on the same origin, CORS isn't needed.

## 4. Asyncio on Windows — ConnectionResetError

```
ConnectionResetError: [WinError 10054] An existing connection was forcibly
closed by the remote host
```

This appears in asyncio callback error handlers on Windows when a client
(browser) closes a connection before the response is fully flushed. It is
**harmless** — the response was already sent. The error is a known Windows
ProactorEventLoop quirk. Ignore it; do not add error handling for it.

## 5. Index builder pattern

For tools that cache files locally (PDFs, images, documents), build a search
index by scanning the cache directory:

1. Walk `data/cache/**/*.ext` recursively
2. Read sidecar `.json` metadata files (same name, next to the cached file)
3. If no sidecar, extract metadata from filename/path
4. Auto-generate tags from vendor/category prefixes
5. Write `data/index.json` — flat array of entries
6. Rebuild on startup and after every batch operation

**Sidecar JSON pattern:** Every cached file gets a `.json` sibling with
`{source_url, downloaded_at, file_size_kb, ...}`. This survives file moves
and provides provenance without parsing filenames.
