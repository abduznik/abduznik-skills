---
name: jellyseerr-watch-suggestions
description: Use when suggesting watch picks filtered by your library.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jellyseerr, sonarr, radarr, media, suggestions]
    category: media
---




# Watch Suggestions Filtered by Your Library

## Overview

Generate watch recommendations that actually make sense for YOUR library:
pull trending titles from a Jellyseerr instance, filter out everything you
already own (Sonarr series / Radarr movies) and everything already requested
(Jellyseerr requested/processing states), then rank the survivors by vote
average. Great for a weekly "what's new worth watching" digest — no
duplicates, no "suggest my own library back to me".

Ships `scripts/watch_suggest.py` — a zero-dependency implementation
(urllib only). All endpoints/credentials come from environment variables, so
it runs anywhere and never hardcodes infrastructure.

## When to Use

- Weekly media digests ("what should I watch this weekend").
- Automating discovery when the library is large enough that remembering what
  you own is hard.
- **Don't use for:** metadata browsing or request submission — this skill
  only filters and ranks.

## Configuration (env vars)

| Var | Meaning |
|---|---|
| `SEERR_URL` | Jellyseerr base (default `http://localhost:5055`) |
| `SONARR_URL` / `RADARR_URL` | Sonarr/Radarr bases (defaults `localhost:8989` / `:7878`) |
| `SONARR_API_KEY` / `RADARR_API_KEY` | API keys for owned-library queries |
| `SEERR_USER` / `SEERR_PASSWORD` | Jellyseerr local auth for trending + request state |

## Algorithm

1. Build owned sets: Sonarr `/api/v3/series` and Radarr `/api/v3/movie`,
   lowercase titles.
2. Login to Jellyseerr once (keep the cookie jar), then:
   - pending set: `/api/v1/media?filter=requested` and `filter=processing`
     (`take=100`).
   - trending: `/api/v1/discover/trending?page=1..3&language=en` for both
     `movie` and `tv` media types.
3. Dedupe by lowercase title; skip anything owned or pending.
4. Sort by `voteAverage`, print top N with year, type and a short overview.

## Common Pitfalls

1. **Cookie jar must persist across requests** — log in once and reuse the
   same opener; a fresh opener per request loses the session.
2. **Title collisions across media types** — a film and a show can share a
   name; dedupe within type or keep type in the key.
3. **Pagination defaults** — Jellyseerr `take` defaults are small; pass
   `take=100&skip=0` explicitly or you miss most of the catalog.
4. **Credentials in code = instant leak** — always env vars; the included
   script refuses to run without them.
5. **Language param** — `language=en` changes the discovery surface; match it
   to the user's library language to avoid foreign-language noise.

## Verification Checklist

- [ ] Script runs without errors using only env-var config
- [ ] Owned titles from Sonarr/Radarr never appear in the output
- [ ] Titles in requested/processing state never appear
- [ ] Output sorted by vote average, top N printed with overviews