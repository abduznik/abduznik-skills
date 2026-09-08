---
name: goatcounter-analytics
description: Query GoatCounter visitor analytics via the REST API.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [analytics, goatcounter, visitor-stats, api]
    category: devops
tags: analytics, goatcounter, visitor-stats, api, pageviews
---


# GoatCounter Analytics via API

Query visitor analytics for any GoatCounter-tracked site programmatically.
Use when asked about site traffic, visitor counts, popular pages, or
referrers. Works with any GoatCounter account — not tied to a specific site.

- Dashboard (human-readable): `https://<your-code>.goatcounter.com`
- Site code: the short name you chose when creating the site
- Privacy: no cookies, no personal data collected, GDPR-safe by default

## Auth

All API calls need a bearer token, scoped to your GoatCounter account.

```
Authorization: Bearer <TOKEN>
```

Get/rotate a token at `https://<your-code>.goatcounter.com/settings/api`
(read-only "Read statistics" scope is enough for reporting; do not request
write scopes unless you need to create/modify sites).

**The token is a secret.** Never print it in full in output, logs, or
commit it to a repo. Store it in an env var or credential file and
reference it by name (e.g. `$GOATCOUNTER_TOKEN`).

## Base URL

```
https://<your-code>.goatcounter.com/api/v0
```

## Common calls

### 1. Verify the token / get account info
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://<your-code>.goatcounter.com/api/v0/me"
```

### 2. Pageviews per path over a date range
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://<your-code>.goatcounter.com/api/v0/stats/hits?start=2026-09-01&end=2026-09-08"
```
Returns one entry per path with a `count` (total hits in range) and a daily
breakdown. This is the main endpoint for "how many visitors did we get."

Note: dates are interpreted in the account's configured timezone, so a hit
near midnight may land on a different day than expected in UTC.

### 3. List of paths tracked
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://<your-code>.goatcounter.com/api/v0/paths"
```

### 4. Detailed stats for one page (browser/OS/referrer breakdown)
```bash
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://<your-code>.goatcounter.com/api/v0/stats/{page}/{id}"
```
`{id}` comes from the `path_id` field returned by the `/stats/hits` call.

### 5. Send a pageview from a backend
```bash
curl -s -X POST -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"no_dnt":true,"hits":[{"path":"/some/path"}]}' \
  "https://<your-code>.goatcounter.com/api/v0/count"
```
Use this for tracking non-browser events. For sites with the JS snippet
already on pages, this is redundant.

## Quick "how many visitors this week" recipe

```bash
START=$(date -d '7 days ago' +%F)
END=$(date +%F)
curl -s -H "Authorization: Bearer $GOATCOUNTER_TOKEN" \
  "https://<your-code>.goatcounter.com/api/v0/stats/hits?start=$START&end=$END" \
  | jq '[.hits[] | {path: .path, count: .count}]'
```

## Adding tracking to a new page

Add this tag before `</head>` on any HTML page:

```html
<script data-goatcounter="https://<your-code>.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```

## Gotchas

- `/api/v0/stats/total` is **not** a real endpoint — use `/api/v0/stats/hits`
  and sum/inspect the `count` fields instead.
- Requests from bots, headless browsers, and plain `curl` against the site
  itself do **not** register as visits — the counter only fires from the
  `count.js` script running in an actual browser tab.
- Rate limits apply to the public API; the `/api/v0/count` backend endpoint
  has a higher limit than the JS-facing `/count` endpoint.
