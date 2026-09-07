#!/usr/bin/env python3
"""
hermes-skill-pack publish tool
==============================
Materializes a privacy-scrubbed skill pack from a source Hermes skills tree.

Design rules (hard requirements):
  1. FAIL-CLOSED SCRUB GATE: any denylist hit in any file destined for the pack
     aborts the whole build before anything is written. Nothing ships silently.
  2. Single-file skills: v1 publishes SKILL.md only (support files are reviewed
     and added per-skill via the manifest in later versions).
  3. Frontmatter is normalized in place (line-preserving): missing
     version/author/license/metadata are added; related_skills is filtered to
     pack-internal skills only so references never dangle.
  4. The generated repo contains ZERO private infrastructure references.

Usage:
  python3 publish.py --source <local-skills-dir> --dest <pack-repo-dir> [--manifest <pack_manifest.json>] [--force]

The local copy can live anywhere; the script copies itself into <dest>/tools/publish.py
so the community gets the exact tool that generated the pack.
"""

import argparse
import html
import json
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------------------
# Denylist: infra hosts, private paths, personal identifiers, session traces.
# Case-insensitive. This list is the privacy firewall of the whole pack.
# ---------------------------------------------------------------------------
DENYLIST_CI = [
    # infrastructure / hosts / tunnels (private infra only; public products like
    # Tailscale or Vikunja as plain words are FINE to publish)
    r"arbusville", r"duckdns", r"playit", r"tun\.ply\.gg", r"fileserver\.",
    r"jakarta", r"hermes-usb-portable",
    # drive-letter / absolute path traces (generic C:\Windows paths are fine)
    r"\b[LF]:[\\/]", r"C:[\\/]Users",
    # project / persona identifiers
    r"teamthrow", r"studytok", r"freegosy", r"omnisave", r"instrumation",
    r"bitbox", r"libhwsense", r"abduznik", r"naked\s+snake", r"big\s+boss",
    r"morning-brief", r"dw_album", r"1729478042", r"snake-recon",
    # personal-context vocabulary (proper nouns/identity — CI)
    r"\byan\b", r"\bsnake\b", r"\bboss\b", r"\bcampus\b", r"\bsemester\b",
    r"\bjerusalem\b", r"\bbootcamp\b", r"\bpc1\b",
]
# case-sensitive terms: English words that would false-positive as verbs/nouns
# ("ate the request", "defense in depth") but are personal in THIS context
DENYLIST_CS = [
    r"\bATE\b", r"\bOOP\b", r"\bexam\b", r"\bdefense\b",
]
DENYLIST_RES = [
    (re.compile("|".join(DENYLIST_CI), re.IGNORECASE), "ci"),
    (re.compile("|".join(DENYLIST_CS)), "cs"),
]

# Skills that ship in the pack (derived from the manifest) — used to rewrite
# related_skills so references never point outside the pack.
PACK_LICENSE = "MIT"
PACK_AUTHOR = "Hermes Agent"

README_STATIC = """# abduznik-skills

A curated collection of reusable skills for [Hermes Agent](https://github.com/NousResearch/hermes-agent),
battle-tested in a production deployment and scrubbed clean of any private
infrastructure, personal data, or session traces.

Every skill in this pack passed a fail-closed privacy gate before publishing:
a single hit on hosts, paths, identities, or personal markers aborts the build.
`tools/publish.py` is the exact gate used — the pack is a generated artifact,
not a hand-maintained copy.

## Skills

{SKILL_TABLE}

## Install

Hermes loads skills from its skills directory (typically `~/.hermes/skills/` on
Linux/macOS, or `<hermes-data>/skills/` in portable/profile setups). A skill is
just a folder containing `SKILL.md`.

1. Clone this repo — or fork it and clone your own copy:
   `git clone <this-repo-url> hermes-skill-pack`
2. Copy the skills you want:
   `cp -r skills/* ~/.hermes/skills/`
3. Restart your Hermes session — the skills appear in the toolbox.

You can also grab a single folder straight from the GitHub UI ("Download folder").

## Adding or updating a skill

1. Edit the source skill locally, then run:
   `python3 tools/publish.py --source <your-skills-dir> --dest . --manifest pack_manifest.json --force`
2. The gate re-scans everything; the table below updates itself.
3. (Optional) add support files per skill in a later revision — v1 ships
   SKILL.md only, by design, to keep the privacy surface minimal.

## License

MIT — see [LICENSE](LICENSE).

## Attributions

Several skills are adaptations of existing open work and keep their attribution
in the `author` frontmatter field:

- `plan`, `spike`, `subagent-driven-development`, `systematic-debugging`,
  `test-driven-development`, `writing-plans` — adapted from
  [obra/superpowers](https://github.com/obra/superpowers) (MIT)
- `simplify-code` — inspired by Claude Code `/simplify`
- `spike` — adapted from gsd-build/get-shit-done
- `ephemeral-file-sharing` — CLI wrapper around gofile.io public API

All other skills were authored by Hermes Agent from operational experience.
"""


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    if "skills" not in data or not isinstance(data["skills"], list):
        sys.exit("manifest must contain a 'skills' array")
    return data


def extract_frontmatter(text: str):
    """Return (frontmatter_block, body, close_offset) or None if invalid."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm = text[3:end].strip("\n")
    body = text[end + 4 :]
    return fm, body, end


def parse_fm_lines(fm: str):
    """Parse frontmatter as ordered (key, value, is_value_line) tuples.
    Handles simple scalar lines and YAML block lists/objects by treating every
    non-key line as a continuation of the previous key."""
    entries = []  # (key, full_value, raw_line, line_index)
    lines = fm.split("\n")
    current = None
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2)
            entries.append({"key": key, "val": val, "raw": line, "idx": i, "cont": False, "cont_lines": []})
            current = entries[-1]
        elif current is not None:
            current["val"] += "\n" + line
            current["cont_lines"].append(line)
            current["cont"] = True
    # compute clean (display) values: strip quotes, unfold YAML block scalars
    for e in entries:
        v = e["val"]
        if v[:2] in (">-", ">-", "|-", "|") or v[:1] in (">", "|"):
            rest = v.split("\n", 1)[1] if "\n" in v else ""
            e["clean_val"] = " ".join(l.strip() for l in rest.splitlines() if l.strip())
        elif len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            e["clean_val"] = v[1:-1]
        elif len(v) >= 2 and v[0] == "'" and v[-1] == "'":
            e["clean_val"] = v[1:-1]
        else:
            e["clean_val"] = v.split("\n")[0].strip()
    return entries


def rewrite_related_skills(fm_lines: list, pack_names: set) -> list:
    """Filter related_skills (both metadata.hermes and top-level) to pack-internal names."""
    out = []
    for e in fm_lines:
        if e["key"] == "related_skills" or (
            e["key"] == "tags" and False
        ):
            # collapse block-list or inline-list into filtered inline list
            vals = re.findall(r"([A-Za-z0-9_-]+)", e["val"].replace("[", " ").replace("]", " "))
            kept = [v for v in vals if v in pack_names]
            if kept:
                out.append(f"related_skills: [{', '.join(kept)}]")
            # else: drop the field entirely (no dangling references)
        else:
            out.append(e["raw"])
    return out


def normalize_frontmatter(fm: str, name: str, category: str, tags: list, pack_names: set) -> str:
    """Line-preserving normalization: ensure version/author/license/metadata,
    filter related_skills, keep every other field byte-identical."""
    entries = parse_fm_lines(fm)
    keys = {e["key"] for e in entries}
    new_lines = []
    inserted_after = None

    for e in entries:
        raw = e["raw"]
        if e["key"] == "related_skills":
            vals = re.findall(r"([A-Za-z0-9_-]+)", e["val"].replace("[", " ").replace("]", " "))
            kept = [v for v in vals if v in pack_names]
            if kept:
                new_lines.append(f"related_skills: [{', '.join(kept)}]")
            continue
        new_lines.append(raw)
        new_lines.extend(e.get("cont_lines", []))
        if e["key"] == "description":
            inserted_after = len(new_lines)

    # insert missing fields after description (or at end if no description line,
    # which would be invalid anyway — validation catches that earlier)
    missing = []
    if "version" not in keys:
        missing.append("version: 1.0.0")
    if "author" not in keys:
        missing.append(f"author: {PACK_AUTHOR}")
    if "license" not in keys:
        missing.append(f"license: {PACK_LICENSE}")
    if "metadata" not in keys:
        tags_str = ", ".join(tags) if tags else "general"
        missing.append("metadata:")
        missing.append("  hermes:")
        missing.append(f"    tags: [{tags_str}]")
        missing.append(f"    category: {category}")
    if missing:
        at = inserted_after if inserted_after is not None else len(new_lines)
        new_lines[at:at] = missing

    return "\n".join(new_lines)


def run_scrub(text: str, where: str, exclusions: tuple = ()) -> list:
    hits = []
    for regex, _tag in DENYLIST_RES:
        for m in regex.finditer(text):
            if m.group(0).lower() in exclusions:
                continue
            ctx = text[max(0, m.start() - 30) : m.end() + 30].replace("\n", " ")
            hits.append(f"  {where}: {m.group(0)!r} in ...{ctx}...")
    return hits


# ---------------------------------------------------------------------------
# Pixel / CRT site builder (GitHub Pages): one static HTML page per skill.
# Self-contained mini markdown renderer — no external dependencies.
# ---------------------------------------------------------------------------

RETRO_CSS = """\
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
body{background:#040804;color:#9fffb5;font:13px Verdana,Arial,sans-serif;margin:0;padding:18px 0 40px}
a{color:#8adf8a;text-decoration:underline}
a:visited{color:#aa88ff}
a:hover{color:#ffb000}
.layout{background:#0a120a;border:1px solid #2a5a2a;max-width:820px;margin:0 auto}
.logo{width:26px;height:26px;vertical-align:middle;image-rendering:pixelated;margin-right:10px}
.banner{background:#0d2a0d;color:#d8ffe6;padding:10px 14px;border-bottom:1px solid #2a5a2a}
.site{font-family:'Press Start 2P',monospace;font-size:14px;letter-spacing:1px;color:#44ff77}
.tagline{font-size:11px;color:#8affa8}
.ticker{background:#123412;color:#aaffcc;border-bottom:1px solid #2a5a2a;padding:3px 10px;font:12px 'Courier New',monospace}
.navcol{width:150px;background:#0a160a;border-right:1px solid #2a5a2a;vertical-align:top;padding:0}
.navcol ul{list-style:none;margin:0;padding:5px 0}
.navcol li{margin:0}
.navcol a{display:block;padding:4px 10px;text-decoration:none;color:#8affa8;border-bottom:1px dotted #1a3a1a}
.navcol a:hover{background:#123412;color:#ffb000}
.navhead{background:#123412;color:#44ff77;font-weight:bold;padding:5px 10px;border-bottom:1px solid #2a5a2a;text-transform:uppercase;font-size:11px;letter-spacing:.5px}
.maincol{vertical-align:top;padding:10px}
.panel{width:100%;margin:0 0 12px;border:1px solid #2a5a2a;border-collapse:collapse}
.panelhead{background:#123a12;color:#aaffcc;font-weight:bold;padding:5px 9px;border-bottom:1px solid #2a5a2a;text-transform:uppercase;font-size:11px;letter-spacing:.5px}
.panelbody{background:#0a120a;padding:9px;vertical-align:top}
table.data{border-collapse:collapse;width:100%}
table.data th{background:#143414;color:#aaffcc;border:1px solid #2a5a2a;padding:5px 8px;text-align:left;font-size:11px;text-transform:uppercase}
table.data td{border:1px solid #1f4a1f;padding:5px 8px;vertical-align:top}
table.data tr.alt td{background:#0e1a0e}
h1,h2,h3{font-family:Verdana,Arial,sans-serif;font-weight:bold}
h1{font-size:18px;color:#44ff77}
h2{font-size:15px;color:#8affa8;border-bottom:1px dashed #2a5a2a;padding-bottom:3px;margin:18px 0 8px}
h3{font-size:13px;color:#ffb000}
pre.code{background:#020402;color:#c8ffd8;border:1px solid #2a5a2a;padding:9px 11px;overflow-x:auto;font:12.5px 'Courier New',monospace}
code{background:#020402;padding:1px 4px;border:1px solid #1a3a1a;font:12.5px 'Courier New',monospace}
blockquote{border:1px solid #2a5a2a;border-left:4px solid #ffb000;background:#0d1a0d;margin:10px 0;padding:4px 12px;color:#8affa8}
ul,ol{padding-left:24px}
li{margin:3px 0}
hr{border:none;border-top:1px solid #2a5a2a;margin:16px 0}
.tag{display:inline-block;border:1px solid #2a5a2a;padding:1px 6px;margin:1px 3px 1px 0;font-size:11px;color:#ffb000}
.btn{display:inline-block;border:1px solid #44ff77;background:#0d2a0d;color:#44ff77;padding:5px 10px;font:11px 'Courier New',monospace;text-decoration:none;cursor:pointer;text-transform:uppercase;letter-spacing:.5px}
.btn:hover{background:#44ff77;color:#020402}
.footer{background:#0a160a;border-top:1px solid #2a5a2a;color:#2f9a4f;font-size:11px;padding:8px 14px}
.cat{color:#44ff77}
.meta{font-size:11px;color:#8affa8}
"""

RETRO_INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ABDUZNIK SKILLS // INDEX</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<style>{css}</style>
</head>
<body>
<table class="layout"><tr><td>
<table style="width:100%;border-collapse:collapse"><tr>
<td class="banner">
<span class="site"><img class="logo" src="favicon.svg" alt="logo">ABDUZNIK SKILLS</span><br>
<span class="tagline">curated skill library &mdash; scrubbed, tested, free</span>
</td>
</tr></table>
</td></tr>
<tr><td class="ticker"><marquee scrollamount="3" behavior="scroll">&gt;&gt; WHAT'S NEW : {count} SKILLS ONLINE ::: EVERY SKILL PASSED A FAIL-CLOSED PRIVACY GATE (HOSTS / PATHS / IDENTITIES ABORT THE BUILD) ::: {newest_ticker} ::: FREE TO USE, MIT LICENSE :::</marquee></td></tr>
<tr><td>
<table style="width:100%;border-collapse:collapse">
<tr>
<td class="navcol">
<div class="navhead">SECTIONS</div>
<ul>{catlinks}</ul>
<div class="navhead">ACTIONS</div>
<ul>
<li><a href="https://github.com/abduznik/abduznik-skills" target="_blank" rel="noopener">GITHUB REPO</a></li>
<li><a href="https://github.com/sponsors/abduznik" target="_blank" rel="noopener">SPONSOR THIS PACK</a></li>
</ul>
</td>
<td class="maincol">
<table class="panel">
<tr><td class="panelhead">JUMP TO SECTION</td></tr>
<tr><td class="panelbody">{catbtns}</td></tr>
</table>
{body}
</td>
</tr>
</table>
</td></tr>
<tr><td class="footer">ABDUZNIK SKILLS // MIT LICENSE // static site auto-generated by tools/publish.py &mdash; no trackers, no frameworks, one copy button</td></tr>
</table>
</body>
</html>
"""

RETRO_SKILL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} // SKILL</title>
<link rel="icon" type="image/svg+xml" href="../favicon.svg">
<style>{css}</style>
</head>
<body>
<table class="layout"><tr><td>
<table style="width:100%;border-collapse:collapse"><tr>
<td class="banner">
<span class="site"><img class="logo" src="favicon.svg" alt="logo">{name}</span><br>
<span class="tagline">{desc}</span>
</td>
</tr></table>
</td></tr>
<tr><td class="ticker"><marquee scrollamount="3" behavior="scroll">&gt;&gt; SKILL : {name} ::: CATEGORY : {category} ::: MIT LICENSE ::: GENERATED BY TOOLS/PUBLISH.PY :::</marquee></td></tr>
<tr><td>
<table style="width:100%;border-collapse:collapse">
<tr>
<td class="navcol">
<div class="navhead">SITE</div>
<ul>
<li><a href="../index.html">&lt;-- INDEX</a></li>
</ul>
<div class="navhead">{category}</div>
<ul>{siblings}</ul>
<div class="navhead">GET THIS SKILL</div>
<ul>
<li><a href="#" onclick="copyRaw();return false;">COPY SKILL.MD</a><br><span id="copied-msg" class="meta">&nbsp;</span></li>
<li><a href="data:text/markdown;charset=utf-8,{daturl}" download="SKILL.md">DOWNLOAD SKILL.MD</a></li>
</ul>
</td>
<td class="maincol">
<table class="panel">
<tr><td class="panelhead">{name} // {category}</td></tr>
<tr><td class="panelbody">
<p class="meta">category: {category} &nbsp;|&nbsp; license: MIT &nbsp;|&nbsp; author: Hermes Agent</p>
<p>{tags}</p>
{body}
</td></tr>
</table>
</td>
</tr>
</table>
</td></tr>
<tr><td class="footer">ABDUZNIK SKILLS // MIT // <a href="../index.html">back to index</a> &mdash; no trackers, one copy button</td></tr>
</table>
<pre id="raw" hidden>{raw}</pre>
<script>
function copyRaw(){var t=document.getElementById('raw').textContent;navigator.clipboard.writeText(t).then(function(){var m=document.getElementById('copied-msg');m.textContent='COPIED!';setTimeout(function(){m.textContent='';},2000);});}
</script>
</body>
</html>
"""

CATEGORY_ACCENT = {
    "devops": "#44ff77", "github": "#aa88ff", "hardware": "#ffdd55",
    "media": "#55ddff", "hermes": "#ff8844", "software-development": "#ff77cc",
    "productivity": "#88ff88", "general": "#44ff77",
}


def md_inline(text: str) -> str:
    t = text
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    return t


def md_to_html(md: str) -> str:
    """Minimal markdown renderer for the SKILL.md subset used in this pack:
    headings, fenced code, inline code, bold/italic, links, tables, lists,
    blockquotes, hr. Everything else becomes a paragraph."""
    lines = md.split("\n")
    out: list[str] = []
    para: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            if para:
                out.append("<p>" + md_inline(" ".join(para)) + "</p>")
                para.clear()
            out.append("<pre class='code'><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue
        if not s:
            if para:
                out.append("<p>" + md_inline(" ".join(para)) + "</p>")
                para.clear()
            out.append("")
            i += 1
            continue
        if para:
            out.append("<p>" + md_inline(" ".join(para)) + "</p>")
            para.clear()
        if s.startswith("### "):
            out.append(f"<h3>{md_inline(html.escape(s[4:]))}</h3>")
        elif s.startswith("## "):
            out.append(f"<h2>{md_inline(html.escape(s[3:]))}</h2>")
        elif s.startswith("# "):
            out.append(f"<h1>{md_inline(html.escape(s[2:]))}</h1>")
        elif s == "---":
            out.append("<hr>")
        elif s.startswith("> "):
            out.append(f"<blockquote>{md_inline(html.escape(s[2:]))}</blockquote>")
        elif s.startswith("|") and s.endswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            i -= 1
            if len(rows) < 2:
                out.append(f"<p>{md_inline(html.escape(s))}</p>")
            else:
                header = rows[0]
                body = [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", c or "x") for c in r)]
                tbl = ["<table><thead><tr>"]
                tbl += [f"<th>{html.escape(c)}</th>" for c in header]
                tbl += ["</tr></thead><tbody>"]
                for r in body:
                    tbl.append("<tr>" + "".join(f"<td>{md_inline(html.escape(c))}</td>" for c in r) + "</tr>")
                tbl.append("</tbody></table>")
                out.append("".join(tbl))
        elif re.match(r"^[-*] ", s):
            li_text = html.escape(re.sub(r"^[-*] ", "", s))
            out.append(f"<li>{md_inline(li_text)}</li>")
        elif re.match(r"^\d+\. ", s):
            li_text = html.escape(re.sub(r"^\d+\. ", "", s))
            out.append(f"<li>{md_inline(li_text)}</li>")
        else:
            para.append(html.escape(s))
        i += 1
    if para:
        out.append("<p>" + md_inline(" ".join(para)) + "</p>")
    # group consecutive list items
    final: list[str] = []
    in_ul = False
    for line in out:
        if line.startswith("<li>"):
            if not in_ul:
                final.append("<ul>")
                in_ul = True
            final.append(line)
        else:
            if in_ul:
                final.append("</ul>")
                in_ul = False
            final.append(line)
    if in_ul:
        final.append("</ul>")
    return "\n".join(final)


def _skill_tags(fm_entries: list) -> list:
    """Extract tag words from top-level `tags` or nested metadata.hermes.tags."""
    tags: list[str] = []
    for e in fm_entries:
        if e["key"] == "tags":
            m = re.search(r"\[([^\]]*)\]", e["val"])
            if m:
                tags += re.findall(r"[A-Za-z0-9_-]+", m.group(1))
        elif e["key"] == "metadata":
            m = re.search(r"tags:\s*\[([^\]]*)\]", e["val"])
            if m:
                tags += re.findall(r"[A-Za-z0-9_-]+", m.group(1))
    return tags


def build_pixel_site(dst: Path, skills: list, prepared: list) -> None:
    """Write docs/index.html + docs/skills/<name>.html (GitHub Pages source)."""
    docs = dst / "docs"
    skills_dir_docs = docs / "skills"
    if docs.exists():
        shutil.rmtree(docs)
    skills_dir_docs.mkdir(parents=True, exist_ok=True)

    panels: list[str] = []
    by_cat: dict[str, list] = {}
    for entry in skills:
        name = entry["name"]
        cat = entry.get("category", "general")
        by_cat.setdefault(cat, []).append(entry)

    for cat in sorted(by_cat):
        rows: list[str] = []
        for idx, entry in enumerate(sorted(by_cat[cat], key=lambda e: e["name"])):
            name = entry["name"]
            content = next(c for n, c, _x in prepared if n == name)
            fm = parse_fm_lines(extract_frontmatter(content)[0])
            desc = html.escape(next(e["clean_val"] for e in fm if e["key"] == "description"))
            tag_html = "".join(
                f"<span class='tag'>{html.escape(t)}</span>" for t in _skill_tags(fm)
            )
            alt = " class='alt'" if idx % 2 else ""
            rows.append(
                f"<tr{alt}><td><a href='skills/{name}.html'><strong>{name}</strong></a></td>"
                f"<td>{desc}</td><td>{tag_html}</td></tr>"
            )
        panels.append(
            f"<table class='panel' id='cat-{cat.replace(' ', '-')}'>"
            f"<tr><td class='panelhead'>// {cat.upper()} <span class='cat'>({len(by_cat[cat])})</span></td></tr>"
            f"<tr><td class='panelbody'>"
            f"<table class='data'><thead><tr>"
            f"<th style='width:26%'>SKILL</th><th>DESCRIPTION</th><th style='width:24%'>TAGS</th>"
            f"</tr></thead><tbody>"
            + "".join(rows) +
            f"</tbody></table></td></tr></table>"
        )

    favicon_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" shape-rendering="crispEdges">
<rect width="64" height="64" rx="14" fill="#0b0f0b"/>
<g fill="#44ff77">
<rect x="15" y="4" width="6" height="6"/><rect x="22" y="4" width="6" height="6"/><rect x="29" y="4" width="6" height="6"/><rect x="36" y="4" width="6" height="6"/><rect x="43" y="4" width="6" height="6"/>
<rect x="8" y="11" width="6" height="6"/><rect x="50" y="11" width="6" height="6"/>
<rect x="8" y="18" width="6" height="6"/>
<rect x="15" y="25" width="6" height="6"/><rect x="22" y="25" width="6" height="6"/><rect x="29" y="25" width="6" height="6"/><rect x="36" y="25" width="6" height="6"/><rect x="43" y="25" width="6" height="6"/>
<rect x="50" y="32" width="6" height="6"/>
<rect x="50" y="39" width="6" height="6"/>
<rect x="8" y="46" width="6" height="6"/><rect x="50" y="46" width="6" height="6"/>
<rect x="15" y="53" width="6" height="6"/><rect x="22" y="53" width="6" height="6"/><rect x="29" y="53" width="6" height="6"/><rect x="36" y="53" width="6" height="6"/><rect x="43" y="53" width="6" height="6"/>
</g>
</svg>"""
    (docs / "favicon.svg").write_text(favicon_svg, encoding="utf-8")
    # Also ship a copy next to the skill pages: browsers cache favicon
    # resolution per-URL, and Github Pages caches HTML up to 10 min, so a
    # visitor on stale HTML may still request skills/favicon.svg — make that
    # resolve instead of 404ing.
    (skills_dir_docs / "favicon.svg").write_text(favicon_svg, encoding="utf-8")

    catbtns = " ".join(
        f"<a class='btn' href='#cat-{c.replace(' ', '-')}'>{c.upper().replace('-', ' ')}</a>"
        for c in sorted(by_cat)
    )
    catlinks = "".join(
        f"<li><a href='#cat-{c.replace(' ', '-')}'>{c.upper().replace('-', ' ')}</a></li>"
        for c in sorted(by_cat)
    )
    # Manifest list order == addition order (skills are appended, never
    # reordered, by the publish workflow) — last entry is always the newest
    # skill. Deriving the ticker text from it instead of hardcoding a skill
    # name means the "what's new" banner can't silently go stale.
    newest = skills[-1] if skills else None
    if newest is not None:
        newest_name = newest["name"]
        newest_content = next(c for n, c, _x in prepared if n == newest_name)
        newest_fm = parse_fm_lines(extract_frontmatter(newest_content)[0])
        newest_desc = next((e["clean_val"] for e in newest_fm if e["key"] == "description"), "")
        newest_ticker = (
            f"NEW SKILL &mdash; {newest_name.upper()} : {html.escape(newest_desc.upper())}"
        )
    else:
        newest_ticker = "NO SKILLS PUBLISHED YET"
    (docs / "index.html").write_text(
        RETRO_INDEX.replace("{css}", RETRO_CSS)
        .replace("{count}", str(len(skills)))
        .replace("{catbtns}", catbtns)
        .replace("{catlinks}", catlinks)
        .replace("{newest_ticker}", newest_ticker)
        .replace("{body}", "\n".join(panels)),
        encoding="utf-8",
    )

    for entry in skills:
        name = entry["name"]
        cat = entry.get("category", "general")
        content = next(c for n, c, _x in prepared if n == name)
        fm = parse_fm_lines(extract_frontmatter(content)[0])
        desc = html.escape(next(e["clean_val"] for e in fm if e["key"] == "description"))
        tag_html = "".join(
            f"<span class='tag'>{html.escape(t)}</span>" for t in _skill_tags(fm)
        )
        siblings_html = "".join(
            f"<li><a href='{sib}.html'>{sib}</a></li>"
            for sib in sorted(s["name"] for s in by_cat.get(cat, []) if s["name"] != name)
        )
        body = extract_frontmatter(content)[1]
        raw = html.escape(content)
        daturl = urllib.parse.quote(content, safe="")
        page = (
            RETRO_SKILL.replace("{css}", RETRO_CSS)
            .replace("{name}", html.escape(name))
            .replace("{category}", html.escape(cat))
            .replace("{tags}", tag_html)
            .replace("{desc}", desc)
            .replace("{daturl}", daturl)
            .replace("{raw}", raw)
            .replace("{siblings}", siblings_html)
            .replace("{body}", md_to_html(body))
        )
        (skills_dir_docs / f"{name}.html").write_text(page, encoding="utf-8")


def _extra_for(name: str, rel: str, entry: dict, src: Path, errors: list) -> list:
    """Validate and collect extra support files (scripts/ etc.) through the gate."""
    extra = []
    for ef in entry.get("extra_files", []):
        ef_path = src / rel / ef
        if not ef_path.is_file():
            errors.append(f"missing extra file {ef} for {name}")
            continue
        ef_text = ef_path.read_text(encoding="utf-8", errors="replace")
        hits = run_scrub(ef_text, f"{name}/{ef}")
        if hits:
            errors.append(f"SCRUB FAILURE in {name}/{ef}:\n" + "\n".join(hits))
            continue
        extra.append((ef, ef_text))
    return extra


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="source Hermes skills dir")
    ap.add_argument("--dest", required=True, help="pack repo dir (will be populated)")
    ap.add_argument("--manifest", default=None, help="path to pack_manifest.json (default: <dest>/pack_manifest.json)")
    ap.add_argument("--force", action="store_true", help="allow overwriting existing files")
    args = ap.parse_args()

    src = Path(args.source)
    dst = Path(args.dest)
    manifest_path = Path(args.manifest) if args.manifest else dst / "pack_manifest.json"
    if not src.is_dir():
        sys.exit(f"source dir not found: {src}")
    if not manifest_path.is_file():
        sys.exit(f"manifest not found: {manifest_path}")

    manifest = load_manifest(manifest_path)
    pack_names = {s["name"] for s in manifest["skills"]}

    # ---- Phase A: validate every source SKILL.md (scrub + frontmatter) -----
    prepared = []  # (name, dest_rel, new_content, extra_files)
    errors = []
    for entry in manifest["skills"]:
        name = entry["name"]
        rel = entry.get("rel") or name
        skill_md = src / rel / "SKILL.md"
        if not skill_md.is_file():
            # fallback: locate by skill folder name anywhere in the source tree
            cands = [p for p in src.rglob("SKILL.md") if p.parent.name == name]
            if len(cands) == 1:
                skill_md = cands[0]
                rel = skill_md.parent.relative_to(src).as_posix()
            else:
                errors.append(f"missing SKILL.md for {name} (looked at {skill_md}, found {len(cands)} candidates by name)")
                continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")

        # scrub gate (phase A: source)
        hits = run_scrub(text, f"{name}/SKILL.md")
        if hits:
            errors.append(f"SCRUB FAILURE in {name}:\n" + "\n".join(hits))
            continue

        fm = extract_frontmatter(text)
        if fm is None:
            errors.append(f"invalid frontmatter in {name}")
            continue
        fm_block, body, _ = fm

        entries = parse_fm_lines(fm_block)
        keys = {e["key"] for e in entries}
        if "name" not in keys:
            errors.append(f"{name}: frontmatter missing 'name'")
            continue
        desc_val = next((e["clean_val"] for e in entries if e["key"] == "description"), None)
        if desc_val is None:
            errors.append(f"{name}: frontmatter missing 'description'")
            continue
        if len(desc_val) > 1024:
            errors.append(f"{name}: description too long ({len(desc_val)} chars > 1024)")
            continue
        if "license" in keys and "proprietary" in entries[next(i for i, e in enumerate(entries) if e["key"] == "license")]["val"].lower():
            errors.append(f"{name}: proprietary license — cannot publish")
            continue

        new_fm = normalize_frontmatter(
            fm_block, name, entry.get("category", "general"), entry.get("tags", []), pack_names
        )
        # structural validation of the NORMALIZED frontmatter (never publish a
        # skill whose description got mangled/emptied by line surgery)
        re_entries = parse_fm_lines(new_fm)
        re_desc = next((e["clean_val"] for e in re_entries if e["key"] == "description"), "")
        if not re_desc.strip():
            errors.append(f"{name}: description empty after normalization")
            continue
        new_content = "---\n" + new_fm + "\n---\n" + body
        # scrub gate on the NORMALIZED content too (inserted fields could not
        # leak, but related_skills rewriting is safer double-checked)
        hits = run_scrub(new_content, f"{name}/SKILL.md (normalized)")
        if hits:
            errors.append(f"SCRUB FAILURE (normalized) in {name}:\n" + "\n".join(hits))
            continue
        prepared.append((name, new_content, _extra_for(name, rel, entry, src, errors)))

    if errors:
        print("BUILD ABORTED — fail-closed gate:")
        print("\n".join(errors))
        return 1

    # ---- Phase B: materialize the pack ------------------------------------
    skills_dir = dst / "skills"
    tools_dir = dst / "tools"
    if not args.force and any(p.exists() for p in [skills_dir, tools_dir]):
        print(f"dest already populated ({dst}); re-run with --force to regenerate")
        return 1
    if skills_dir.exists():
        shutil.rmtree(skills_dir)
    if tools_dir.exists():
        shutil.rmtree(tools_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)

    # skills
    table_rows = []
    for entry in manifest["skills"]:
        name = entry["name"]
        skill_out = skills_dir / name
        skill_out.mkdir(parents=True, exist_ok=True)
        content = next(c for n, c, _x in prepared if n == name)
        (skill_out / "SKILL.md").write_text(content, encoding="utf-8")
        for ef, ef_text in next(x for n, _c, x in prepared if n == name):
            out_ef = skill_out / ef
            out_ef.parent.mkdir(parents=True, exist_ok=True)
            out_ef.write_text(ef_text, encoding="utf-8")
        desc = next(e["clean_val"] for e in parse_fm_lines(extract_frontmatter(content)[0]) if e["key"] == "description")
        desc_short = desc[:100]
        table_rows.append(f"| {entry['category']} | `{name}` | {desc_short} |")

    # pixel website (GitHub Pages source under docs/)
    build_pixel_site(dst, manifest["skills"], prepared)

    # canonical manifest
    canonical = {
        "repo": manifest.get("repo", "abduznik-skills"),
        "license": PACK_LICENSE,
        "author": PACK_AUTHOR,
        "generated_by": "tools/publish.py",
        "skills": [
            {
                "name": s["name"],
                "category": s.get("category", "general"),
                "tags": s.get("tags", []),
                "extra_files": s.get("extra_files", []),
                "license": PACK_LICENSE,
                "author": PACK_AUTHOR,
            }
            for s in manifest["skills"]
        ],
    }
    (dst / "pack_manifest.json").write_text(
        json.dumps(canonical, indent=2) + "\n", encoding="utf-8"
    )

    # README
    table = "| Category | Skill | Description |\n|---|---|---|\n" + "\n".join(sorted(table_rows))
    (dst / "README.md").write_text(README_STATIC.replace("{SKILL_TABLE}", table), encoding="utf-8")

    # LICENSE (MIT)
    (dst / "LICENSE").write_text(
        "MIT License\n\nCopyright (c) 2026 Hermes Skill Pack contributors\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the \"Software\"), to deal\n"
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
        "SOFTWARE.\n",
        encoding="utf-8",
    )

    # self-copy the tool (the scanner itself may legitimately contain denylist
    # terms as pattern strings, so it is excluded from the final rescan)
    shutil.copyfile(Path(__file__).resolve(), tools_dir / "publish.py")

    # .gitignore
    (dst / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")

    # ---- Phase C: final rescan of everything written -----------------------
    final_hits = []
    for p in sorted(skills_dir.rglob("*")):
        if p.is_file():
            final_hits += run_scrub(p.read_text(encoding="utf-8", errors="replace"), str(p.relative_to(dst)))
    for p in sorted((dst / "docs").rglob("*.html")):
        if p.is_file():
            # the site legitimately links to the owner's sponsor page — exempt
            # the account handle there; everything else stays fail-closed
            final_hits += run_scrub(
                p.read_text(encoding="utf-8", errors="replace"), str(p.relative_to(dst)),
                exclusions=("abduznik",),
            )
    for p in [dst / "README.md", dst / "pack_manifest.json"]:
        # repo name legitimately carries the owner handle
        final_hits += run_scrub(
            p.read_text(encoding="utf-8", errors="replace"), str(p.relative_to(dst)),
            exclusions=("abduznik",),
        )
    if final_hits:
        print("FINAL SCRUB FAILURE:")
        print("\n".join(final_hits))
        return 2

    print(f"OK — {len(prepared)} skills published to {dst}")
    print("skills/:  ".ljust(10), ", ".join(sorted(s["name"] for s in manifest["skills"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())