---
name: obsidian-maps
description: Embed interactive maps in Obsidian via the Map View plugin.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [obsidian, maps, geospatial]
    category: productivity
---


# Obsidian Maps Integration

## Plugin: Map View (esm7)
Use **Map View** by esm7, NOT obsidian-maps (the official Bases plugin — requires Obsidian Bases feature, not standalone).
- Community plugin: `obsidian-map-view`
- GitHub: `esm7/obsidian-map-view`

## Two Location Formats

### 1. Frontmatter (one location per note)
```yaml
---
location: 50.0755, 14.4378
---
```
Note shows as a single pin on the map.

### 2. Inline geo links (multiple locations per note)
Requires `locations:` tag (plural) in frontmatter:
```yaml
---
tags:
  - locations
---
```
Then in the note body:
```markdown
[Place Name](geo:50.0880,14.4044) #tag-name
```
Each `[Name](geo:lat,lng)` becomes a separate pin. Inline tags (`#tag-name`) enable custom icon rules.

## Embedded Map Code Block
The code block uses **JSON** (not YAML). Format sourced from `mapState.ts`:

````markdown
```mapview
{"name":"View Name","mapZoom":13,"centerLat":50.0755,"centerLng":14.4378,"query":"tag:#place-tag","chosenMapSource":0,"autoFit":true}
```
````

### JSON fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | View name |
| `mapZoom` | number | Zoom level (1-19) |
| `centerLat` | number | Map center latitude |
| `centerLng` | number | Map center longitude |
| `query` | string | Filter query (e.g. `tag:#prague-place`) |
| `chosenMapSource` | number | Map tile source index |
| `autoFit` | boolean | Auto-zoom to fit all markers |
| `embeddedHeight` | number | Optional: height in pixels |
| `lock` | boolean | Optional: disable pan/zoom |

### Generating code blocks
Do NOT hand-write the JSON. Instead:
1. Open Map View sidebar → configure query/zoom/pan
2. Presets pane → **Copy Block**
3. Paste into note

Or: right-click in note editor → **"embed a Map View"** → enter search term.

## Query Syntax
- `tag:#hiking` — notes/markers with tag
- `name:Prague` — markers containing string
- `tag:#sleep*` — wildcard tags
- `linkedfrom:"filename"` — notes linking to filename
- Boolean: `tag:#dogs AND tag:#food`

## Workflow: Trip Planning
1. Create trip note with `locations:` tag in frontmatter
2. Add inline geo links: `[Place](geo:lat,lng) #trip-tag`
3. Embed map: ` ```mapview ``` ` block with query `tag:#trip-tag`
4. Open Map View sidebar → focus note → see all pins
5. Configure icon rules in Map View settings (Font Awesome icons)

## Pitfalls
- **obsidian-maps ≠ Map View**: `obsidian-maps` (obsidianmd) requires Bases feature. Use `obsidian-map-view` (esm7) for standalone embedding.
- **Code block is JSON, not YAML**: `centerLat`/`centerLng` (not `center`), `mapZoom` (not `zoom`), `query` (not `filter`). YAML-like syntax causes `SyntaxError: Unexpected token`.
- **Inline links need `locations:` tag**: without `locations:` (plural) in frontmatter, Map View skips scanning for `geo:` links to save performance.
- **Don't hand-write code blocks**: use Copy Block from Presets or the context menu embed command — the JSON structure is non-obvious and error-prone.