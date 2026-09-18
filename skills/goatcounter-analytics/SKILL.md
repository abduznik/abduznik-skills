---
name: goatcounter-analytics
description: Query GoatCounter visitor analytics for Terraria Fetcher site.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [analytics, goatcounter, visitor-stats, api]
    category: devops
tags: analytics, goatcounter, visitor-stats, api, pageviews
---


# GoatCounter Analytics — Terraria Fetcher

This site (`https://example.github.io/my-site/`) has GoatCounter
visitor analytics wired in via a script tag on every page. Numbers can be
pulled programmatically instead of opening the dashboard manually.

- Dashboard (human-readable): https://mysite.goatcounter.com
- Site code: `mysite`
- Privacy: no cookies, no personal data collected, GDPR-safe by default

## Auth

All API calls need a bearer token, scoped to this GoatCounter account.

```
Authorization: Bearer <TOKEN>
```

Get/rotate a token at https://mysite.goatcounter.com/settings/api
(read-only "Read statistics" scope is enough for reporting; do not request
write scopes unless you actually need to create/modify sites).

**The token is a secret.** Never print it in full in output, logs, or
commit it to a repo. Store it in whatever secret store this agent has
available (env var, credential file) and reference it by name.

Token stored at: `/path/to/.env` as `GOATCOUNTER_TOKEN`

## Base URL

```
https://mysite.goatcounter.com/api/v0
```

## Common calls

### 1. Verify the token / get account info
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://mysite.goatcounter.com/api/v0/me"
```

### 2. Pageviews per path over a date range
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://mysite.goatcounter.com/api/v0/stats/hits?start=2026-09-01&end=2026-09-08"
```
Returns one entry per path with a `count` (total hits in range) and a daily
breakdown. This is the main endpoint for "how many visitors did we get."

Note: dates are interpreted in the account's configured timezone
(`UTC`), so a hit near midnight may land on a different day than
expected in UTC.

### 3. List of paths tracked
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://mysite.goatcounter.com/api/v0/paths"
```

### 4. Detailed stats for one page (browser/OS/referrer breakdown)
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://mysite.goatcounter.com/api/v0/stats/{page}/{id}"
```
`{id}` comes from the `path_id` field returned by the `/stats/hits` call.

### 5. Send a pageview from a backend (not needed for this site — the
JS snippet already does this client-side; use only if tracking a
non-browser event)
```bash
curl -s -X POST -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"no_dnt":true,"hits":[{"path":"/some/path"}]}' \
  "https://mysite.goatcounter.com/api/v0/count"
```

## Quick "how many visitors this week" recipe

```bash
START=$(date -d '7 days ago' +%F)
END=$(date +%F)
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://mysite.goatcounter.com/api/v0/stats/hits?start=$START&end=$END" \
  | jq '[.hits[] | {path: .path, count: .count}]'
```

## Pages tracked on this site

All 5 pages carry the tracking snippet (verified live 2026-09-08):

- `/terraria-fetcher/` (index.html)
- `/terraria-fetcher/tree.html`
- `/terraria-fetcher/compare.html`
- `/terraria-fetcher/bosses.html`
- `/terraria-fetcher/fetcher.html`

If a new HTML page is added to the site, it needs this tag added before
`</head>` to be tracked:

```html
<script data-goatcounter="https://mysite.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```

## Gotchas

- `/api/v0/stats/total` is **not** a real endpoint — use `/api/v0/stats/hits`
  and sum/inspect the `count` fields instead.
- Requests from bots, headless browsers, and plain `curl` against the site
  itself do **not** register as visits — the counter only fires from the
  `count.js` script running in an actual browser tab.
- Rate limits apply to the public API; the `/api/v0/count` backend endpoint
  has a higher limit than the JS-facing `/count` endpoint.
