---
name: canonical-thumbnail
description: Generate YourChannel canonical video thumbnails with hero renders. Takes hero name, layout (A=hero left, B=hero right), title/subtitle text, and outputs 1280x720 PNG with YourChannel branding.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [thumbnails, video, youtube, content-creation]
    category: media
usage: |
  python make_thumbnails.py --hero Reinhardt --layout a --title "YOURCHANNEL" --subtitle "COMPILATION"
  python make_thumbnails.py --hero Doomfist --layout b --title "HOW TO NOT" --subtitle "PLAY DOOMFIST"
---



# Canonical Thumbnail Generator

Generates branded YourChannel video thumbnails with hero character renders.

## Location
Script: `/path/to/media\overwatch\videos\overwatch vids\scripts\make_thumbnails.py`

## Usage
```bash
cd "/path/to/your/media/"
python scripts/make_thumbnails.py --hero HeroName --layout a --title "TITLE" --subtitle "SUBTITLE"
```

## Arguments
| Arg | Default | Description |
|-----|---------|-------------|
| `--hero` | Doomfist | Hero name (must match `render_<name>.webp` in render dir) |
| `--layout` | a | `a` = hero left, text right-hugged / `b` = hero right, text left-hugged |
| `--title` | YOURCHANNEL | Title text (red, 160px) |
| `--subtitle` | (empty) | Subtitle text (white, 120px, omitted if empty) |
| `--logo-size` | 210 | YourChannel logo size in pixels |
| `--out-dir` | (default) | Custom output directory |
| `--render-dir` | (default) | Custom hero render directory |
| `--bg-color` | 0F0F14 | Background color as hex (no #) |

## Layouts
- **Layout A**: Hero flipped left, text right-hugged with RED bottom bar + accent stripe
- **Layout B**: Hero right, text left-hugged minimalist with thin RED bottom bar

## Output
1280x720 PNG to `thumbnails/thumbnail_{hero}_{layout}.png`

## Dependencies
- `Pillow`
- Hero renders: `/path/to/\media\\overwatch\\render\\render_<Hero>.webp`
- Logo: `/path/to/\your-hermes-path\\remotion-project\\public\\logo.png`
- Font: Windows Impact

## Missing hero renders

If `--hero Torbjorn` fails with `FileNotFoundError`, that hero likely has no `render_<Hero>.webp` yet. See `references/missing-hero-renders.md` for how to pull renders from the Overwatch wiki.

To list available heroes:
```bash
ls "/path/to/your/media/" | grep -oP 'render_\K\w+' | sort
```
