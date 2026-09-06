---
name: retro-fansite
description: Use when building retro/2000s forum/fansite-styled sites.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [web, html, css, retro, fansite]
    category: creative
---


# Retro Fansite Aesthetic

A from-scratch, hand-coded HTML/CSS style for static sites (GitHub Pages, docs sites, project
landing pages) that genuinely reads as an early-2000s forum or fan-made project site — phpBB,
vBulletin, GeoCities, homebrew-scene fansites. This is a specific, opinionated look. It is **not**
"dark mode with retro colors" — that's the single most common wrong turn (see Anti-Patterns below).

Use this skill whenever the user asks for a retro/old-school/2000s/forum-styled site, or names this
aesthetic directly (phpBB/vBulletin/GeoCities era, "old forum", "fansite").

## The Core Test

Before shipping any page, ask: **could this have existed as static HTML in 2004, no framework, no
build step?** If the answer requires a modern CSS feature used for glow/depth/motion, cut it.

## Visual Rules (non-negotiable)

- **Light page background**, not dark mode. Real 2000s sites were overwhelmingly light grey/white
  (`#aab8cc`-ish outer background, `#ffffff` content well) with a **navy or steel-blue header
  band** — not dark-themed throughout. Dark mode as a default aesthetic is itself a 2010s+ pattern;
  using it undercuts the "old" read even with period-correct colors.
- **Real `<table>` layout**, not CSS grid/flexbox pretending to be tables. Use actual `<table
  class="layout">`, nested `<table>` for the two-column nav+content shell, and bordered `<table>`
  elements for every content panel, data table, and feature list. This is the single highest-impact
  authenticity signal — flexbox/grid dressed up with borders still reads as a modern site in a
  costume.
- **Hard 1px borders everywhere**, flat solid colors. Zero `border-radius`, zero `box-shadow`, zero
  `text-shadow` glow, zero `linear-gradient` (one narrow exception: a flat two-stop gradient on the
  header band is period-plausible if you must, but flat is safer). If you catch yourself writing
  `box-shadow` or a glow effect "to make it pop," stop — that's the SaaS-landing-page instinct
  bleeding in, not the target aesthetic.
- **Verdana/Arial/Tahoma body text**, no display/pixel fonts except optionally in a small site
  logo mark. Body font-size around **13px** (not 11-12px — too cramped reads as trying too hard;
  too large loses density). Headers are the same font family, just bold, not a separate typeface.
- **Underlined default links**, visited-link color distinct from unvisited (`#0000dd` / `#6a1fa0` is
  a safe period pair), hover color that's clearly different again (e.g. red `#dd0000`). This one
  detail does a lot of authenticity work almost for free.
- **Dense, not spacious.** Tight padding (4-9px in panels, not 16-24px), multiple short bordered
  panels stacked vertically rather than one page with generous whitespace. Real forum/wiki pages
  packed information in; generous whitespace reads as a modern landing page no matter the colors.
- **No hero sections, no big centered CTA buttons, no card grids.** These are unambiguously modern
  patterns. Feature lists go in a dense two-column bordered `<table>`, not a grid of elevated cards.
  A "download" link is a normal `<input type="button">` or plain link, not a big colored pill.
- **No decorative filler that doesn't serve the content**: skip hit counters, "best viewed in
  browser X" badges, and similar unless the user explicitly asks for that specific joke/flourish.
  Content density and real information should carry the page — cheap nostalgia gags read as
  padding and get called out.

## Structural Pattern

```
<table class="layout">                          full page, ~760-800px max-width, centered
  <tr><td class="banner">SITE NAME + tagline + top link bar</td></tr>
  <tr><td class="ticker"><marquee>...</marquee></td></tr>     optional, real <marquee>, not a joke
  <tr><td>
    <table style="width:100%">
      <tr>
        <td class="navcol">                     ~130-150px, bordered, sidebar link list
          <div class="navhead">SECTION</div>
          <ul><li><a>...</a></li></ul>
        </td>
        <td class="maincol">                    everything else
          <table class="panel">                 repeat per content section
            <tr><td class="panelhead">Title</td></tr>
            <tr><td class="panelbody">dense content, real prose + bordered sub-tables</td></tr>
          </table>
        </td>
      </tr>
    </table>
  </td></tr>
  <tr><td class="footer">plain text strip — license, copyright, links. no badges/counters.</td></tr>
</table>
```

A real `<marquee>` tag for a "what's new" ticker is period-correct and still renders in modern
browsers (deprecated but functional) — prefer it over faking the scroll with CSS keyframes; the
real tag is funnier and more honest to the bit.

## A Working Palette (steal this, don't reinvent)

```css
body            { background:#aab8cc; color:#101010; font:13px Verdana,Arial,sans-serif; }
a               { color:#0000dd; }
a:visited       { color:#6a1fa0; }
a:hover         { color:#dd0000; }
.layout         { background:#ffffff; border:1px solid #16294a; max-width:800px; }
.banner         { background:#0f2148; color:#fff; }           /* header band */
.navcol         { background:#dce4f1; border-right:1px solid #9fb0cc; }
.navhead        { background:#16294a; color:#fff; }             /* sidebar section label */
.panelhead      { background:#cddaee; color:#0f2148; }          /* content panel title bar */
.ticker         { background:#fff2b0; color:#5a0000; }          /* marquee strip */
table.data th   { background:#cddaee; color:#0f2148; }
table.data tr.alt td { background:#eef2f8; }                    /* zebra-stripe alt rows */
```

Adjust hue if the project has its own brand color (swap the navy for a different dark accent), but
keep the *structure*: light outer bg, white content well, dark header band, pale-blue-grey panel
chrome, zebra-striped data tables.

## Code Blocks and Rich Content (don't let "retro" mean "shallow")

A real forum/wiki-era site still had code snippets, data tables, and callout boxes — just styled
flat. Don't drop content depth or technical detail to fit the aesthetic; style rich content *within*
it:

```css
pre.code   { background:#0c1424; color:#cfe0ff; border:1px solid #16294a;
             font:12.5px "Courier New",monospace; padding:8px 10px; }
table.callout td.callouthead { background:#fff2c0; color:#7a4b00; font-weight:bold; }
table.callout td.calloutbody { background:#fffbee; }
```

Use `<pre class="code">` for real command/code examples (not screenshots), and a `table.callout`
(amber header bar) for "watch out" / "gotcha" notes. Both stay flat and bordered — no syntax-
highlighting library, no glow.

## Content Philosophy

If the user says the site feels "dry" or "thin," the fix is almost never more visual decoration —
it's **more real information**. Prefer:
- Actual code/config samples over prose describing them.
- Real project stats (line counts, module counts, version, project age) pulled from the actual repo
  — never invent numbers, and skip a stat if the honest number would look bad (e.g. a very low
  download count) rather than omitting context that makes it misleading.
- Splitting one dense "everything" page into several linked pages under a shared sub-nav strip
  (breadcrumb-style: `Section: A · B · C · current`) once a topic has enough real depth — more
  pages of real content beats one page of decoration.
- Multi-page technical documentation (architecture, internals, gotchas/pitfalls) presented in full
  on-site, not just linked out to an external repo — the "A to Z" test: could a newcomer learn the
  whole system from this site alone?

## Anti-Patterns (mistakes already made and corrected building this style)

1. **Dark mode as the default look.** First draft used a near-black navy background with glowing
   cyan headers and gradient buttons — got called out immediately as "still modern... a Tailwind
   wanna-be." Dark backgrounds read as 2015+ dashboard/SaaS aesthetics, not 2004 fansite. Default to
   light.
2. **CSS Grid/Flexbox "card" layouts even with retro colors.** Bordered `<div>` grids with padding
   and subtle shadows still read as modern component design language. Use real `<table>` markup.
3. **Glow, shadow, gradient buttons.** `text-shadow` on headers, `box-shadow` on panels, gradient
   `<button>` fills — all instantly modern regardless of hue. Flat and hard-edged only.
4. **Hero sections and big CTA buttons.** A centered pitch + giant colored "Download Now" button is
   a landing-page pattern from the 2010s app-marketing playbook, not a 2000s info page.
5. **Decorative filler standing in for content** (hit counters, "best viewed at 1024x768" badges)
   used as *padding* rather than as an intentional, requested flourish — reads as low-effort once a
   reader notices there's nothing real backing it up.
6. **Font too small.** 11px body text read as cramped/hard-to-read once actually reviewed — 13px is
   the sweet spot between authentic density and usability.
7. **Summarizing deep technical content instead of presenting it.** Linking out to "full docs
   elsewhere" instead of bringing real depth onto the page itself makes the site feel thin no matter
   how good the visual styling is.

## Process Note

Build one representative page first (usually the homepage) and check it in an actual browser
before replicating the pattern across every page — the visual calibration (light vs dark, table vs
flex, font size, density) is the part most likely to need a correction round, and it's cheaper to
correct once than to redo N pages.