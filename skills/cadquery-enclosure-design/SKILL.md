---
name: cadquery-enclosure-design
description: "Use when designing 3D-printed enclosures for boards."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cadquery, enclosure, 3d-print, stl, electronics]
    category: software-development
---




# Parametric 3D-printed enclosure design (CadQuery)

Class of task: design a printable case/box for a microcontroller board + display/module, iterate with the user over STLs until print-ready. Deliverable = watertight STLs + STEP + per-part renders, verified against the drawn concept.

## Workflow order (non-negotiable)

1. **HARD GATE — do NOT export or hand over ANY STL until every critical dimension is CERTAIN.** Certainty comes from exactly two sources, in order: (a) the vendor datasheet for the exact SKU (not a lookalike, not a generic category page — the SKU's own spec/mechanical-drawing PDF), or (b) the user's caliper measurement of the actual part in hand (mm, with positions for holes/pins/connectors). If neither source exists for a dimension, STOP AND ASK — present the short list of numbers needed, state it as a blocker, and wait. NEVER infer from a similar part, NEVER carry an assumption across SKUs, NEVER "fix it in the next print" — each reprint costs time and money. Same-looking parts differ hugely, so always verify board dimensions AND whether the board has mounting holes (some are castellated/no holes, some clones have corner holes — VERIFY, don't assume from memory). When a datasheet's mechanical drawing exists, extract geometry programmatically from the PDF (pymupdf text+drawings coordinates at 1mm≈2.8346pt scale) rather than eyeballing renders.
2. **Choose the CAD engine.** CadQuery (Python) over Blender/OpenSCAD when the agent may have no vision: parametric, numeric, verifiable by math, exports STL+STEP. Install cadquery + matplotlib + trimesh + rtree + manifold3d into a Python 3.11 venv (CadQuery wheels may not exist for newer interpreters).
3. **One spec module of named parameters** (`box_spec_vN.py`) — every dimension a key in one dict. The user tunes one line to adjust; the builder imports it.
4. Build: outer profile, pockets/cavities, fasteners; export STL + STEP; render preview PNGs from `shape.tessellate()` via matplotlib Poly3DCollection. Render each half separately AND an exploded assembly — the user checks renders; never trust your own eyes.
5. **Concept-driven sanity check** (see references/stl-verification.md): the spec declares what SHOULD exist; probes derive from that spec. Watertight + extents + volume + fuse on top.
6. Deliver: send the two STLs as separate files, each part's render + assembly render, and state verified dimensions. Fix from slicer feedback and rebuild in seconds.
7. **Deliverable docs (when the user asks for a datasheet/paper):** produce a proper spec sheet for the model + components — title block, dimensioned drawing of each part, assembly + fit details, BOM/fastener table, and notes. Use the `pdf` skill (reportlab platypus JSON spec) with real margins, headings, a clean layout and **auto-scaled embedded renders** (re-render the part to a known size, placed on a drawing frame with a scale bar) so it doesn't look pasted — never a dump of raw text.

## Enclosure design rules (encode into every design)

- Two-part case joined by M2 screws; **only ONE half carries the 4 long pillars** with pilots; the other half gets plain counterbored through-holes. Pillars must sit CLEAR of the module PCB footprint (verify circle-vs-rect distance ≥ pillar radius).
- **Walls thin and outer corners curved** — ~2.0 mm walls, rounded outer profile (~R5). Thick walls get called out. Match the cavity profile's corner radius to outer radius minus wall so corners keep full thickness.
- **Outside openings ONLY where hardware needs them**: USB-C slot, screen window, buttons. No decorative/assumed cable channels — ribbons route inside between the open halves. "Why is there a hole?" means you added one the hardware doesn't need.
- Boards WITHOUT holes: drop-in socket/tray (snug, components-down) or 4 nudge pins positioned on the board's REAL hole pattern — never screw holes into a hole-less board.
- **Self-tap M2 pilots are unthreaded at ~Ø1.8** — the screw force-cuts its thread into the print on first assembly. This is intended and desired; for repeated take-apart mention heat-set brass inserts instead.
- Board stack depth (components-down tray/socket) = PCB thickness + tallest component + ~0.2 mm clearance, and the board's top must land FLUSH with the mating face — a few tenths of error = collision when halves close.
- Confirm with calipers and expose as params: module total thickness, real mounting-hole positions. State which numbers are assumptions.
- **FIT PHILOSOPHY:** anything that must fit snugly gets a **ramped/tapered opening sized a bit SMALLER than the part** — the part force-pushes over a lead-in chamfer/ramp and clicks into place. Undersize printed openings by ~0.1–0.15 mm per side for press-retention on PCBs (mouth flared +0.4–0.5 for alignment, grip band below nominal). A part that "goes in but plays around" is a fitting violation — the pocket was built too big. If the mating part would otherwise float or need glue, add an interlock (tapered pocket, retention lip, snap bump) instead of leaving it loose.
- **PORTS & HOLES: always OVERSHOOT, never precise, never undershoot.** Connector/port openings get generous slack: ~2–3 mm wider and ~2 mm taller than the connector envelope, positioned by the connector's real mounted height (see PCB-height rule). A port hole cut to the connector size will be filed out by hand; a generous slot never is.
- **PCB HEIGHT: boards with a Type-C/THT connector are NOT flush-mounted.** The connector body sits ON TOP of the PCB (components side), so its centerline and shell-top are offset above the board surface by the connector body height (~3.2 mm shell for USB-C, plus the PCB thickness below). When a board sits in a recessed tray, compute the port opening from the connector's real z-occupancy (board top → board top minus shell height, i.e. toward the cavity), not from the board midpoint or an old mount position.
- **DELIVERY GATE: never export STL/STEP without having passed the dimension-certainty gate.** The STL set is only "ready to slice" when every dim is either datasheet-verified for the exact SKU or user-measured. If the user says a dimension on the printed part is wrong, that's a gate violation — go back to the source, never re-guess.

## Iteration discipline

- Change one concept at a time per rebuild; re-run the full sanity spec after every change.
- Slicer reports like "missing wall", "hole in air", "floating cylinders" are REAL geometry bugs (cut in a void / misaligned cut), not rendering artifacts — probe the mesh, don't argue.
- Keep a reusable, generic checker (`sanity_check.py` + JSON spec) separate from the design; it is meant to be hardened further (jittered probe bundles, clearance/contains probes) and reused on future part sets.
- **Recurring failure modes that caused reprints (encode, don't repeat):**
  - A display/module's active area is NOT at the module's geometric center and NOT flush with the PCB top edge — read its position from the mechanical drawing before cutting the window. Assuming a lookalike part's dimensions (different vendor, different board size, active-area offset) silently shifts every cutout and clearance.
  - A board's mounting holes are not a given — some boards are castellated with no holes at all. NEVER emit screw holes or nudge pins into a board without having verified the hole pattern from datasheet or caliper, after having researched it.
  - Outside openings should be hardware-driven only. Decorative/assumed cable channels get rejected; route internal cables between the open halves.
  - When a board moves to a new mount height (recessed tray), recompute EVERY cutout and probe from CURRENT geometry — carrying the previous revision's z-bands or probe targets forward produces a floating hole.
  - Sanity-checker probes must be derived from the spec constants, not reused from an older revision, or they probe into intentionally-open voids and misfire.
