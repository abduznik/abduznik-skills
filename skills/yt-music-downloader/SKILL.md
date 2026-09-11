---
name: yt-music-downloader
description: Search YouTube Music for album playlists and push them to a download server for offline storage.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [youtube-music, download, albums, yt-dlp]
    category: media
category: media
triggers:
  - user asks to "push", "download", "grab", or "get" an album from YouTube Music
  - user says "find the album link" or "send it to the server"
  - user mentions your-download-api, your-server download server
---



# YT Music Album Downloader

Search YouTube Music for an album (by artist + name), find its official OLAK5uy_ playlist, and push it to a download server that yt-dlps + SFTPs it to a music library.

## Workflow

1. **Recommend albums** (optional) — analyze user's taste bands, suggest similar albums
2. **User picks one** — they say which album they want
3. **Search YT Music API** using the innertube `youtubei/v1/search` endpoint
4. **Extract the album playlist** from the `musicCardShelfRenderer` response
5. **Push to server** via POST to `/api/download` with `{url, artist, album}`

## YT Music Innertube API

**Endpoint:** `https://music.youtube.com/youtubei/v1/search?alt=json`

**Headers:**
```
Content-Type: application/json
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Origin: https://music.youtube.com
X-YouTube-Client-Name: 67
X-YouTube-Client-Version: 1.20250101.00.00
```

**Request body (search):**
```json
{
  "context": {
    "client": {
      "clientName": "WEB_REMIX",
      "clientVersion": "1.20250101.00.00"
    }
  },
  "query": "Artist AlbumName"
}
```

## Response Parsing

The album result lives in the first section's `musicCardShelfRenderer`:

```
contents.tabbedSearchResultsRenderer.tabs[0]
  .tabRenderer.content.sectionListRenderer.contents[0]
  .musicCardShelfRenderer
```

| Field | Path | Format |
|-------|------|--------|
| **Title** | `.title.runs[0].text` | "Iowa" |
| **Browse ID** | `.title.runs[0].navigationEndpoint.browseEndpoint.browseId` | `MPREb_...` |
| **Playlist ID** | `.buttons[0].buttonRenderer.command.watchPlaylistEndpoint.playlistId` | `OLAK5uy_...` |
| **Artist** | `.subtitle.runs` text, filtering out "Album", " • " | "Slipknot" |

**Album playlist URL:** `https://music.youtube.com/playlist?list=OLAK5uy_XXXXXXXXXX`

### Structure Notes
- Browse IDs (`MPREb_...`) and playlist IDs (`OLAK5uy_...`) are in **different** nested dicts — never in the same dict together
- The `subtitle.runs` array has the format: `["Album", " • ", "ArtistName"]` — filter out the static parts
- Response tree depth for album data is ~12-16 levels deep

## Album Discovery (helper)

When the user gives bands they like, recommend albums from OTHER bands that hit the same lanes:

| Taste | Similar bands/albums |
|-------|---------------------|
| FFDP / Disturbed (groove/hard rock) | Parkway Drive, From Ashes to New, Volbeat, All That Remains, Bad Wolves |
| Korn (nu-metal) | Slipknot, System of a Down, Mudvayne, Deftones, Linkin Park |
| Rammstein (industrial/NDH) | Eisbrecher, Oomph!, Megaherz, Stahlmann |
| Windrose (power/folk) | Gloryhammer, Sabaton, Powerwolf, Alestorm, Beast in Black |

## Script

There's a reusable Python script at **`/path/to/Coding\your-download-api\dw_push.py`** that does the full workflow in one shot. See `templates/dw_push.py` in this skill.

## Pitfalls

- The innertube API requires proper `Origin` and `X-YouTube-Client-*` headers or it returns empty
- Subtitle text contains "Album" / " • " separators — strip those when extracting artist name
- Not all albums have a YT Music auto-generated OLAK5uy_ playlist. Topic-channel-only albums may not have one.
- The server runs on port <your-port> (not 5001 — that's Dockge). Always double-check port if curl fails.
- If the server returns `Cannot POST /api/download`, the Flask app (`app.py`) isn't running on that port.
