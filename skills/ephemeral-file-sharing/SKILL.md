---
name: ephemeral-file-sharing
description: Expiring public web links for files, CLI-only (gofile.io).
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [file-sharing, gofile, expiring-links]
    category: devops
tags: file-sharing, upload, gofile, expiry, download-link
---




# Ephemeral File Sharing

Give the user a public download link that expires on its own — no account, pure CLI. Use when they say "upload X to the web", "send someone a limited link", "a link that expires in a week". Sibling of `homelab-file-hosting` (self-hosted permanent links); use THIS skill for external hosts with built-in expiry.

## Golden rule: probe before committing

Never upload the real (possibly 1 GB+) file blind. Send a tiny probe (~50 bytes) to the candidate host and confirm you get a working JSON link back. Ephemeral hosts drift without warning:

- **file.io** — root 301s to www.file.io, POST to either returns 405/Gatsby SPA (API gone as of Sep 2026). Old tutorials saying `curl -F "file=@f" https://file.io` are stale — do not trust them, probe.
- **tmpfiles.org** — `/api/v1/upload` returned empty body.
- **transfer.pcloud.com** — returned HTML page, not JSON (their API wants different params/endpoint).
- **gofile.io** — verified working Sep 2026. Use it.

## gofile.io recipe (verified Sep 2026)

### 1. Upload (guest, no auth, ~1 GB fine)
```bash
curl -s --max-time 5400 -F "file=@/path/to/file" "https://upload.gofile.io/uploadfile"
```
Response JSON fields to use:
- `data.downloadPage` — the link to share (`https://gofile.io/d/XXXX`)
- `data.size` + `data.md5` — server-computed; match `data.size` against local file size for integrity
- `data.guestToken` / `data.code` / `data.id` — only needed for API management calls

### 2. Expiry semantics (free tier — report to user honestly)
- Guest/standard uploads kept **~10 days**; the clock **resets on every download**, so active content lives longer, inactive files die at ~10 days. Premium = permanent.
- State this to the user when they ask for "a week or so": "kept ~10 days, resets each download."

### 3. Verify BEFORE handing over the link
```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 30 "https://gofile.io/d/<CODE>"   # expect 200
```
- Do NOT hand-build the stream URL `https://{server}.gofile.io/download/{contentId}/{filename}` — it 301s to the download page. The `downloadPage` link is canonical.
- `api.gofile.io/contents/{id}?wt=<guestToken>` may return `error-token` for guest tokens — expected, don't chase it; the page 200 + size match is the real verification.

### 4. Pushing big files from the homelab
Stream from the server that holds the file — never copy 1 GB to the local box first:
- Run the ssh + curl upload as a **background** terminal with `notify_on_complete=true` (upload takes minutes on typical upstream).
- Keep the channel alive with `ssh -o ServerAliveInterval=30`.
- `--max-time 5400` (~90 min) is a sane ceiling for 1 GB.

## Pitfalls

- Hosts drift: probe-first catches dead APIs before you burn a big upload. Re-probe any host older than a few months, even one documented here.
- Guest links are **not revocable and not password-protected** — for sensitive/durable shares use `homelab-file-hosting` (self-hosted, you control deletion) instead.
- gofile free tier has a download-speed cap for guests; fine for casual sharing, bad for many recipients.
- No LRU: an expiring link should still be flagged in the reply ("dies ~10 days from upload unless downloaded") so the user isn't surprised later.