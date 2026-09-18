---
name: wiki-media-asset-pipeline
description: Scrape structured image asset data from Fandom/MediaWiki APIs, build dual-resolution dictionaries (icon + full render), process images for web deployment, and integrate into static HTML/CSS/JS sites.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [mediawiki, fandom, web-scraping, image-processing]
    category: software-development
category: mlops
tags:
  - mediawiki
  - fandom
  - web-scraping
  - image-processing
  - static-site
  - game-assets
  - pillow
---


# Wiki Media Asset Pipeline

Extract hero/character image assets from Fandom/MediaWiki APIs, organize into dual-resolution dictionaries (small icon + full render), compress for web, and deploy.

## Audio/Voiceline Discovery

Every hero's voice lines and sound effects are organized on the wiki:
- **Page:** `<Hero>/Quotes` — complete list of all voicelines
- **Category:** `Category:<Hero> sound files` — fallback audio archive
- **Files named** like `Doomfist - And they say Doomfist is dead.ogg` — the
  filename IS the spoken text

**`scripts/fandom_map.py`** handles all audio queries:

```bash
# List all heroes that have sound files
python scripts/fandom_map.py audio overwatch --list-heroes

# List ALL audio for a hero (766 files for Doomfist)
python scripts/fandom_map.py audio overwatch Doomfist

# Search for a specific voiceline by spoken text
python scripts/fandom_map.py audio overwatch Doomfist --search "and they say"

# Get the download URL for a specific audio file
python scripts/fandom_map.py info overwatch "Doomfist - And they say chivalry is dead.ogg"
```

Results include spoken text, direct .ogg download URL, file size, and format.
All cached in `.fandom_cache/` for instant re-use across sessions.

## Quick Navigation Script (The Map)

**`scripts/fandom_map.py`** is the "eyes" for any Fandom wiki. Instead of
hand-crafting API queries every session, run one command:

```bash
python scripts/fandom_map.py discover <wiki>   # Full site map
python scripts/fandom_map.py images  <wiki> <prefix>  # List images by prefix
python scripts/fandom_map.py search  <wiki> <query>   # Search pages
python scripts/fandom_map.py info    <wiki> <filename> # File details
python scripts/fandom_map.py audio   <wiki> <hero>     # Hero voicelines
python scripts/fandom_map.py audio   <wiki> <hero> --search "text"  # Search voicelines
python scripts/fandom_map.py audio   <wiki> --list-heroes  # List heroes with audio
python scripts/fandom_map.py cache   <wiki>           # Show cached data
```

Examples:
```bash
# Full site healthcheck + category structure + image prefix discovery
python scripts/fandom_map.py discover overwatch

# Find all hero icons (256x256 PNGs)
python scripts/fandom_map.py images overwatch "Icon-"

# Find all OW2 hero renders + audio files
python scripts/fandom_map.py images overwatch "OW2_"

# Get exact CDN URL for a specific file
python scripts/fandom_map.py info overwatch "Icon-Reaper.png"

# Search for hero ability pages
python scripts/fandom_map.py search overwatch "Hero abilities"

# Find a Doomfist voiceline by text
python scripts/fandom_map.py audio overwatch Doomfist --search "and they say"

# Find all heroes that have audio
python scripts/fandom_map.py audio overwatch --list-heroes
```

All results are cached in `.fandom_cache/` for instant re-use.

## Trigger

Reach for this skill when building a web project that needs:
- Character/hero portrait images from a game wiki
- A searchable grid of character portraits
- Both small thumbnails (selector UI) and large renders (hero banners, cards)
- Image compression/favicon generation via Pillow
- GitHub Actions for community-driven content contributions

## Workflow

### 1. Discover Assets via MediaWiki API

Fandom wikis expose a standard MediaWiki API at `https://<wiki>.fandom.com/api.php`.

**List all images with a prefix pattern (e.g. hero icons):**

```bash
curl -s "https://overwatch.fandom.com/api.php?action=query&list=allimages&aiprefix=Icon-&ailimit=200&format=json"
```

Filter results client-side: only `.png`, exclude non-hero entries (abilities, skins, achievements).

**Get downloadable URLs for specific files:**

```bash
curl -s "https://overwatch.fandom.com/api.php?action=query&titles=File:Icon-Reaper.png|File:Icon-Genji.png&prop=imageinfo&iiprop=url&format=json"
```

The response includes the full CDN URL with a `?cb=` revision timestamp — use as-is for production.

### 2. Build Dual-Resolution Dictionary

Every hero gets TWO URLs in the master list:

| Field | Purpose | Example resolution |
|-------|---------|-------------------|
| `icon` | Small square portrait for selector grids | 128×128px native |
| `render` | Full-body character art for banners/cards | 500+ px tall |

**JS array structure:**

```javascript
{name:'HeroName', icon:'<thumb-url>', render:'<full-url>'}
```

Use `icon` in: searchable grids, dropdown selectors, compact lists.
Use `render` in: hero section banners, roster cards, large hero portraits.

**Pitfall:** If you replace ALL occurrences of icon URLs with render URLs (or vice versa) via a global find-replace, you'll corrupt the dictionary's render or icon fields. Always patch individual entries or rebuild the dictionary from scratch after bulk swaps.

### 3. Image Processing for Web

Use Pillow (PIL) for compression:

```python
from PIL import Image
img = Image.open('source.png')
web = img.resize((400, int(400 * img.height / img.width)), Image.LANCZOS)
web.save('output.webp', 'WEBP', quality=85)
```

**Favicon creation** — multi-size ICO:

```python
fav32 = img.resize((32, 32), Image.LANCZOS)
fav16 = img.resize((16, 16), Image.LANCZOS)
fav32.save('favicon.ico', 'ICO', sizes=[(32, 32), (16, 16)])
```

**Nav logo** — resize to fit 60px nav bar height:
```python
nav = img.resize((52, 52), Image.LANCZOS)
nav.save('logo-nav.png', 'PNG', optimize=True)
```

### 4. GitHub Actions for Community Content

When users can submit content (fan art, roster applications):

- Form submits via GitHub Issues API (creates an issue)
- A `repository_dispatch` or `issues: labeled` workflow triggers
- Workflow waits random time, processes content, commits to repo
- The `actions/github-script@v7` action handles issue comments and state changes

### 5. Image Rendering Patterns

**Full-body renders** (tall, dramatic): Use `object-fit: cover; object-position: center top` on cards.
**Square icons** (selector grid): Use `object-fit: contain` with fixed width/height + border-radius for circular styling.
**Floating hero section** (parallax): `height: 65vh; filter: drop-shadow(...)` for dramatic effect — icons don't work well here.

## Pitfalls

- **Corrupting dictionary fields during bulk patching:** A global find-replace on URLs will hit BOTH the icon and render fields in the dictionary, as well as element src attributes. Always scope replacements carefully or rebuild the dictionary from a clean source.
- **Wiki URL changes:** Fandom wiki image URLs include a CDN hash (`images/a/a9/`) and a revision timestamp (`?cb=...`). The hash can change if the file is re-uploaded. Store both URLs in the dictionary so you can update individually.
- **Fandom API rate limits:** The API has no documented rate limit but batch queries with 50+ titles can fail. Split into batches of 24-30 titles when querying `imageinfo`.
- **URL encoding:** Hero names with special characters (Lúcio, Torbjörn) need URL encoding (`L%C3%BAcio`) in API queries but can use the plain name in the dictionary and HTML.
- **Pillow on Windows:** Use the system Python (e.g. `/home\<user>\AppData\Local\Programs\Python\Python311\python.exe`) not the sandbox Python for image processing, since the sandbox may lack PIL.
