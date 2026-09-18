---
name: skit-thumbnail
description: Generate YouTube thumbnails for skit videos. Extracts a frame (random or specific timestamp), crops it into a rounded-rect polaroid with drop shadow, SKIT label bar above, title+subtitle on the right, channel logo below. Everything auto-fits within margins.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [thumbnails, youtube, video, content-creation]
    category: media
usage: |
  python skit_thumbnail.py clip.mp4 --title "Excuse Me, Sir" --subtitle "Overwatch"
  python skit_thumbnail.py clip.mp4 --title "Short Title" --subtitle "" --output custom.png
  python skit_thumbnail.py clip.mp4 --title "My Title" --subtitle "Sub" --frame-time 0
---


# Skit Thumbnail Generator

## Location
Script: `/path/to/scripts/skit_thumbnail.py`

## Usage
```bash
cd "/path/to/project"
python scripts/skit_thumbnail.py path/to/clip.mp4 --title "Title Text" --subtitle "Subtitle Text"
```

## Arguments
| Arg | Description |
|-----|-------------|
| `video` | Path to the skit video clip (positional, required) |
| `--title` | Title text in red (auto-sized to fit column) |
| `--subtitle` | Subtitle text in white, same font size as title |
| `--frame-time` | Timestamp in seconds for frame extraction (default: random). Use `0` for the very first frame. |
| `--output` | Custom output path (default: auto-named in `skit_thumbnails/`) |

## Design
- **Left stack**: Red SKIT bar (rounded pill, left-aligned text) → 4px gap → Photo (rounded-rect, white border, drop shadow)
- **Right column**: Title (red) + Subtitle (white) at same font size (determined by longer string) → accent line → channel logo (scaled to fill)
- **Background**: Dark slate with diagonal stripe accents, red top/bottom bars
- **Margins**: 50px left, 25px all other sides, 28px gap between frame and text

## Pitfalls (learned the hard way)
- ❌ **Don't use full-bleed blurred frame as background** — user rejected it, prefers clean dark slate with diagonal stripes
- ❌ **Don't put SKIT label inside the photo** — it goes ABOVE in a separate red bar (pill shape, left-aligned text)
- ❌ **Don't add a second SKIT badge in the right zone** — one is enough (the bar above the photo)
- ❌ **Don't under-size text to leave empty space** — title + subtitle should be the same large font, auto-determined by the longer string
- ❌ **Don't use tiny corner logos** — logo must be large (200-440px) and centered in remaining space
- ❌ **Don't redesign from scratch** — user prefers iterative refinement of the existing polaroid layout
- ❌ **Don't guess the title/subtitle** — ask the user what text they want, or if they already told you, use exactly what they said (subtitle is often just "Overwatch" for Overwatch skits)
- ❌ **Don't extract from a random frame without asking** — always ask the user which frame they want, then use `--frame-time` to pin it (0 = first frame, or a specific second)
- ✅ SKIT bar text at 45px (1.5x of initial try), left-aligned with 15px padding
- ✅ Title & subtitle share ONE font size via calc_font_size (binary search on longer string)
- ✅ Everything auto-fits within margins: 50px left, 25px elsewhere

## YouTube upload after thumbnail

After the user picks a thumbnail, upload the video to the channel:

```bash
cd "/path/to/scripts-upload/scripts"
python yt_upload.py "path/to/video.mp4" \
  --title "SkitName In Overwatch | My Channel" \
  --thumbnail "path/to/thumb.png" \
  --private --schedule "YYYY-MM-DDT14:00:00Z"
```

**Title convention (channel skits):** `"[Skit Name] In Overwatch | My Channel"` — always this format for skit videos. The subtitle (e.g. "Overwatch") goes in the thumbnail only, not the YouTube title.

**Schedule:** User's timezone is IDT (UTC+3). 5pm IDT = 14:00 UTC. Ask the user what time to publish.

## Workflow patterns

**Quick single thumbnail:**
```
python scripts/skit_thumbnail.py clip.mp4 --title "Title" --subtitle "Subtitle"
```
Picks a random mid-clip frame. Re-run if user doesn't like the result.

**Batch comparison (user-picky workflow):**
Generate 3 thumbnails at different timestamps, show them inline, let the user pick.

1. Check video duration: `ffprobe -v error -show_entries format=duration -of csv=p=0 clip.mp4`
2. Pick 3 spread-out timestamps (e.g. early/mid/late thirds minus margins)
3. Generate each:
   ```
   python scripts/skit_thumbnail.py clip.mp4 --title "T" --subtitle "S" --frame-time 3 --output "skit_thumbnails/clip_t1.png"
   python scripts/skit_thumbnail.py clip.mp4 --title "T" --subtitle "S" --frame-time 12 --output "skit_thumbnails/clip_t2.png"
   python scripts/skit_thumbnail.py clip.mp4 --title "T" --subtitle "S" --frame-time 22 --output "skit_thumbnails/clip_t3.png"
   ```
4. Present all 3 inline via `MEDIA:` paths
5. If none works, iterate with 3 more timestamps
6. Once picked, that PNG is the final thumbnail for the upload step

## Script maintenance notes
- `--frame-time` was added retrospectively (original script only had random extraction). If you patch the script, the function to modify is `extract_frame(video_path, timestamp=None)` — it replaces the old `extract_random_frame()`. Argparse entry in `main()` needs both the new flag in the parser and passing it through to `make_skit_thumbnail()`.

## Output
1280×720 PNG, saved to `skit_thumbnails/<clipname>_skit_thumb.png`.
