---
name: yt-dlp-anti-bot
description: When yt-dlp hits 403s, harden with impersonation + backoff.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [youtube, yt-dlp, download, 403]
    category: media
triggers:
  - yt-dlp returns HTTP Error 403: Forbidden
  - YouTube downloads intermittently fail or skip tracks
  - user reports missing songs/tracks after a playlist download
  - setting up impersonation / curl_cffi for yt-dlp
---




# yt-dlp Anti-Bot Hardening (YouTube 403s)

YouTube intermittently rejects yt-dlp requests with `HTTP Error 403: Forbidden`. Pattern to recognize: failures hit DIFFERENT tracks each run, in bursts — that's IP throttling / bot detection, NOT a per-video block. A job can report "done" while silently skipping failed tracks (see below).

## The fix stack

1. **Upgrade yt-dlp + install curl_cffi PINNED `<0.16`**:
   ```bash
   pip install -U yt-dlp "curl_cffi<0.16"
   ```
   yt-dlp 2026.07+ rejects curl_cffi 0.16.x ("Only curl_cffi versions 0.5.10 and 0.10.x through 0.15.x are supported"). When curl_cffi is the wrong version, ALL impersonate targets show `(unavailable)` in `yt-dlp --list-impersonate-targets` even though `import curl_cffi` works fine.

2. **Pin in requirements.txt too** — `curl_cffi<0.16`. An unpinned entry silently reinstalls the broken latest version on every container restart (services whose entrypoint runs `pip install -r requirements.txt`).

3. **Python API: pass the ImpersonateTarget OBJECT, not a string**:
   ```python
   from yt_dlp.networking.impersonate import ImpersonateTarget
   ydl_opts = {'impersonate': ImpersonateTarget.from_str('chrome')}
   ```
   A raw string `{'impersonate': 'chrome'}` raises `AssertionError: ''` — an EMPTY message, so the job fails at info-fetch with a blank error. The CLI converts strings for you; the YoutubeDL() API does not.

4. **Stale process trap**: upgrading/downgrading curl_cffi while a service runs does NOT fix the running worker — it imported yt-dlp before the change. CLI tests pass but the service still errors. Always restart the container after version changes.

## Verifying the fix

```bash
# targets usable?
yt-dlp --list-impersonate-targets
# single-track test — real googlevideo URL = fingerprint works
yt-dlp --impersonate chrome -f bestaudio --get-url "<url>"
```

## Residual throttling → rotate + backoff

Some tracks still 403 even with impersonation. Gap-fill strategy (download ONLY missing tracks, don't re-run whole playlists):
- Rotate impersonation targets per attempt: `chrome`, `chrome-136`, `chrome-133`, `safari-18.0`, `safari-17.2`
- Rotate player clients: `android,web`, `web`, `tv,web`, `android_vr,web`
- Exponential backoff: `'retry_sleep_functions': {'http': lambda n: 25 * (2 ** min(n, 4))}`
- 60-90s sleeps between attempts; up to 8-12 attempts per track
- Keep per-track metadata (`-metadata artist/album/track`) and file naming identical to the service's output (`NN - Title.mp3`) so gap-fills blend in

## Pitfalls

- **"Job done" ≠ all tracks downloaded**: services report `Complete! N tracks processed` when the LOOP finishes, not when all succeeded. Always verify disk file count against playlist track count.
- **`docker exec -d` swallows output redirects**: `docker exec -d <c> python3 x.py > /tmp/x.log` writes the log on the HOST (often 0 bytes). Use `docker exec -d <c> sh -c "python3 -u x.py > /tmp/x.log 2>&1"` — and `python3 -u` for unbuffered output.
- **Block-buffered stdout**: service app stdout to docker logs lags; use jobs.json / event stores as source of truth for job state.
