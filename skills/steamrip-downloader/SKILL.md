---
name: steamrip-downloader
title: SteamRIP Downloader
description: Find games via SteamRIP's exposed WP REST API; auto-download mega & BuzzHeavier/bzzhr links, hand other hosters to user.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gaming, download, mega, automation]
    category: productivity
---



## SteamRIP Downloader

Two layers:
1. **SteamRIP REST API** — find games + extract links with zero scraping
2. **BuzzHeavier (bzzhr.to) direct downloads** — auto-downloadable via the HTMX/HX-Redirect trick

| Hoster | Auto-download? |
|--------|:---:|
| mega.nz | ✅ Yes (mega.py) |
| bzzhr.to (BuzzHeavier) | ✅ Yes via HX-Redirect trick (below) |
| megadb.net | ✅ Yes via 302-Location trick (below) |
| gofile.io | ✅ Yes via UI click + network sniff (below) — guest download works, API is premium-gated |
| 1fichier, mediafire, etc | 🔗 Link only |

### User workflow (MANDATORY every download)

1. **After every download completes, ALWAYS ask: "want me to extract it too?"** — never auto-extract, never skip the question. User replies yes/no after the download.
2. If yes → extract with the **no-fluff method**:
   - `7z x -y -o'/path/to/Games' '<rar>' -i!"<GameFolder>/*" -x!"<GameFolder>/_CommonRedist*"`
   - Include ONLY the top-level game folder; exclude `_CommonRedist` (root AND inside the game folder), `Read_Me*`, `*.url` shortcuts, and any root-level junk.
   - If the archive has no clean top-level folder (files at root), create a per-game subfolder (`-o'/path/to/Games\<Game Name>'`) and exclude fluff there.
   - After extraction: verify the game .exe exists, report the launch path (game folder root exe preferred over deeper ones).
3. Warn user when `_CommonRedist` (VC++ runtimes) was skipped — game may need it if a `vcruntime`/`msvcp` DLL is missing on launch.

### Scripts (`/path/to/your-hermes-path\data\scripts\`)

- `bzzhr_direct.py <steamrip-post-url>` — extracts the direct download URL from a bzzhr.to share page (Playwright). Writes state to `bzzhr_direct.json`.
- `megadb_direct.py <megadb-share-url>` — extracts the direct URL from megadb.net (no browser needed). Same state file.
- `bzzhr_fetch.py [outdir]` — streams the direct URL (from state file) to disk with retry + resume (curl_cffi, filename auto-derived from Content-Disposition or URL path). Default outdir `/path/to/Games`.
- `bzzhr_fetch_state.py <state-json> [outdir]` — same as bzzhr_fetch.py but takes the state file as an arg (lets multiple hosters' states coexist; reads `referer` from state to override bzzhr's). Default outdir `/path/to/games`.
- `gofile_direct.py <gofile-share-url> [out-state-json]` — GENERIC gofile extractor (below).
- `gofile_sniff.py <share-url>` — debug variant that dumps all gofile API traffic during the click.
- `rip.py` — legacy Playwright scraper (mega auto-dl, others print links)

Venv python: `/path/to/your-hermes-path\.cache\runtimes\windows-x64\venv\Scripts\python.exe` (has playwright, mega, curl_cffi). Local Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe`.

### 1. SteamRIP REST API (open, no auth)

SteamRIP is WordPress (Jannah theme) behind Cloudflare; the WP REST API is fully open — plain curl with a browser UA works:

- Search games: `GET https://steamrip.com/wp-json/wp/v2/search?search=<game>&per_page=20`
- Post list: `GET https://steamrip.com/wp-json/wp/v2/posts?per_page=100&page=N`
- Post body (download links in rendered HTML): `GET https://steamrip.com/wp-json/wp/v2/posts/<id>`
- 108 wp/v2 routes exposed (pages, media, categories, menu-items...)

Caveats: Cloudflare is inconsistent — first hit may 403 ("Just a moment"); retry with browser UA. HTML pages are also curl-friendly with a browser UA.

### 2. BuzzHeavier direct download (the full flow)

bzzhr.to IS BuzzHeavier — SteamRIP's own host. Share pages (e.g. `https://bzzhr.to/sl4f4ut486xi`) sit behind Cloudflare turnstile + TLS-fingerprint WAF.

1. **Referer requirement**: opening a share page directly (fresh browser, no referer) redirects to the steamrip.com homepage. MUST navigate from the SteamRIP post: post page → click `a[href*="bzzhr.to"]` (opens popup) → turnstile passes there.
2. **Turnstile**: passes with real Chrome, `headless=False`, residential IP. Poll `page.title()` until it's not "Just a moment" (up to ~90s).
3. **The HTMX trick** (from r/SteamRip, "Another way to get BuzzHeavier direct download link"): the page has `<a hx-get*="/download">`. In-page fetch of `window.location.origin + hx-get` with headers `HX-Request: true` and `HX-Current-URL: <page url>` → server replies 204 with an **`HX-Redirect`** response header = the direct URL, e.g. `https://ts.bzzhr.to/d/<shareId>?v=<token>`. (This is the bookmarklet: `javascript:(async()=>{try{const b=document.querySelector('a[hx-get*="/download"]');if(!b)throw"Download button not found or site layout changed.";const r=await fetch(window.location.origin+b.getAttribute("hx-get"),{headers:{"HX-Request":"true","HX-Current-URL":window.location.href}});const l=r.headers.get("HX-Redirect");if(l)window.location.href=l;else alert("Direct link not found.")}catch(e){alert("Error: "+e)}})();`)
4. **Download**: `ts.bzzhr.to` needs no cookies (token is in the URL), but send `cf_clearance` anyway. WAF resets connections probabilistically per TLS fingerprint: plain curl & aria2c get reset ~always; **curl_cffi `impersonate="chrome124"` passes** — use a retry loop (1–3 tries typical). Files are `.rar` (3+ GB).

### 3. megadb.net direct download (302-Location trick)

megadb.net is another SteamRIP file host (classic XFileSharingPro-style). Share page e.g. `https://megadb.net/<id>`. No browser needed — plain curl_cffi works:

1. GET the share page (keep session cookies) — sets `lang`/`aff` cookies.
2. Wait ~12s (page countdown).
3. POST form data to the same URL with `allow_redirects=False`: `op=download2`, `id=<share id>`, `rand=`, `referer=<page url>`, `method_free=`, `method_premium=`.
4. Server answers **302 with `Location: http://fs<NN>.megadb.xyz:8080/d/<token>/<filename>`** — that's the direct file link. Browsers silently block it because it's plain HTTP (mixed content) — that's why SteamRIP users need the extension workaround. curl_cffi just reads the header.
5. Direct links support Range (206) → resumable via `bzzhr_fetch.py` (it falls back to the URL basename for the filename since megadb's Content-Disposition is bare `attachment`).

Pitfalls: WAF resets are flaky (same as bzzhr) — retry loop in `megadb_direct.py` handles it. Cookies iteration in curl_cffi is dict-like (`.items()`, not `.name` attributes).

### 4. gofile.io direct download (UI click + network sniff)

The gofile **API is premium-gated** (`/contents/{id}` → `error-notPremium`), but the **guest web UI download works for free** — the Download button fires a request to `https://store<N>.gofile.io/download/web/<fileId>/<filename>` (or `file-eu-par-1.gofile.io` etc.), and that URL streams with just the `accountToken` cookie.

The catch: the `accountToken` must be **bound to the file** — a fresh guest token from `POST /accounts` alone gets an HTML stub, NOT the file. The binding happens when the share page's own JS loads the content (it calls `GET /contents/<id>?...` with its session token). So the flow is:

1. Open the share page in a real Chrome (persistent context, headless=False — same setup as bzzhr).
2. Wait for `#filemanager_itemslist` to render (the page auto-creates + binds a guest token).
3. Click the file row's download control (`#filemanager_itemslist button:has-text("")` is the reliable selector; fallbacks in the script).
4. Capture the `store*.gofile.io/download/web/...` request (Playwright `expect_download` or a request sniffer) — that's the direct URL.
5. Save `{direct, cookies: [accountToken], referer: "https://gofile.io/"}` to a state json.
6. Stream with `bzzhr_fetch_state.py <state> /path/to/games` (curl_cffi chrome124 works; the CDN doesn't need impersonation but cookies+referer are required).

`gofile_direct.py` automates steps 1-5 generically — no hardcoded file IDs or store servers; it derives everything live from the page. Filename comes from Content-Disposition (UTF-8 encoded). Works for any gofile share.

Pitfalls: clicking the control may trigger a browser download event instead of a nav — expect_download handles it; if the selector misses, screenshot at `gofile_err*.png` for debugging. megadb has been observed serving `down_for_maintenance` for all files site-wide (host outage) — don't hammer it, fall back to gofile/bzzhr.

### Pitfalls

- curl_cffi `Response` does NOT support `with` (no context manager) — use try/finally + `.close()`.
- aria2c/wget/plain curl cannot download from ts.bzzhr.to — TLS fingerprint reset. Use curl_cffi chrome124.
- bzzhr.to has official API docs (w.bzzhr.to PUT upload, /api/fs, /api/locations) but `/api/*` is connection-reset for non-browser TLS and `w.bzzhr.to` doesn't resolve publicly — the API is unusable externally. Don't waste time on it.
- SteamRIP REST API: always send a browser UA; first request sometimes 403s — retry once.
- Mega downloads go to `/path/to/games` by default (rip.py `OUT` variable).
- GoFile API requires premium accounts for direct downloads — always manual.
