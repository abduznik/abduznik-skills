---
name: circuit-design
description: >-
  Design electrical circuits programmatically — SKiDL netlist generation, custom
  SVG schematic renderer with 45° routing and IEEE 315 compliance, and raw KiCad
  S-expression authoring for full control. Covers the full pipeline from
  text-based circuit description to rendered SVG or KiCad netlist.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [kicad, skidl, electronics, netlist]
    category: software-development
---




# Circuit Design (Programmatic)

Three approaches for generating electrical circuit schematics from code, 
depending on what you need:

| Method | Output | Best For |
|--------|--------|----------|
| **A: SKiDL Pipeline** | KiCad netlist (`.kicad_sch`) | Full KiCad integration, ERC, BOM |
| **B: SVG Renderer** | SVG image (`.svg`) | Quick visualization, documentation, shareable diagrams |
| **C: Raw S-Expression** | KiCad `.kicad_sch` | Full control, custom symbols, no library dependency |

## Method A: SKiDL Pipeline

[SKiDL](https://github.com/devbisme/skidl) lets you describe circuits in Python
and output KiCad netlists/schematics.

### Workflow

```python
from skidl import Net, Part

# Create parts
r = Part('Device', 'R', value='10k', footprint='Resistor_SMD:R_0603_1608Metric')
led = Part('Device', 'LED', value='RED')
gnd = Net('GND')
vcc = Net('VCC')

# Connect
r[1] += vcc
r[2] += led['A']
led['K'] += gnd

# Generate
ERC()
generate_netlist()
```

### Key commands
```bash
# Generate KiCad schematic
python3 -c "from skidl import generate_schematic; generate_schematic()"

# ERC check
python3 -c "from skidl import ERC; ERC()"
```

### Pitfalls
- **Pin names vs numbers**: SKiDL accepts both. Use `Part['VCC']` or `Part[1]`.
- **Footprint assignment**: Some `Device` parts lack default footprints — set
  explicitly for BOM generation.
- **ERC warnings**: Unconnected pins on multi-unit packages (op-amps with
  unused channels) generate warnings unless you explicitly connect them to NC.
- **KiCad version**: SKiDL 0.x targets KiCad 6+. For KiCad 7/8, test your
  output; some symbol library paths changed.

## Method B: Custom SVG Renderer

A custom SVG schematic renderer with Manhattan (90°) and 45° diagonal routing,
plus a Lee maze autorouter for complex multi-net layouts. Produces IEEE 315-style
diagrams.

### Usage

```python
from renderer import SchematicRenderer

r = SchematicRenderer(cell_size=110)
r.add_component("U1", "ic", grid_x=0, grid_y=0,
                pins_left=[{"num": 6, "name": "GPIO2"}],
                pins_right=[{"num": 33, "name": "GND"}],
                name="ESP32-C3")
r.add_component("R1", "resistor", grid_x=4, grid_y=2, value="330")
r.add_component("D1", "led", grid_x=7, grid_y=2, value="RED")
r.add_net("GPIO2", [("U1", 6), ("R1", 1)])
r.render("output.svg")
```

### Scripts

The `scripts/` directory contains:
- **`renderer.py`** — Core renderer: grid layout, wire routing (Manhattan, 45° 
  diagonal, or maze autorouter), SVG output
- **`symbols.py`** — Component symbol drawing (resistor, capacitor, diode, LED, 
  IC, ground, VCC, header)
- **`generate_examples.py`** — Generates horizontal, diagonal, vertical, and
  complex multi-net example schematics
- **`demo.py`** — Quick demo: ESP32-C3 + resistor + LED circuit

Run: `python3 scripts/demo.py`

### Routing modes

| Mode | Quality | Speed | Use When |
|------|---------|-------|----------|
| Manhattan | Clean orthogonal | Fast | Simple circuits, no component overlap |
| 45° diagonal | Professional look | Medium | Components at y-offsets |
| Maze (Lee) | Optimal pathfinding | Slow | Dense boards, narrow channels |

### Pitfalls
- **svgwrite module**: Install with `pip install svgwrite`
- **Grid positioning**: Components are placed on a grid (default 100px cells).
  Off-grid positions produce unaligned wire stubs.
- **Pin direction**: Pins exit the component body in the direction specified
  ('L', 'R', 'U', 'D'). Wrong direction produces wires through the component.
- **Port conflicts**: The renderer does not check for overlapping components.
  Place them on distinct grid coordinates.

## Method C: Raw KiCad S-Expression

Directly author `.kicad_sch` files as S-expressions using the KiCad 10 format.
Gives full control over symbol placement, wire routing, and component definitions
without going through the KiCad GUI or any library middleware.

### When to use
- You need custom inline symbols (no external library dependency)
- You're automating schematic generation from a non-Python source
- You need exact control over every coordinate and property

### Tools

| Tool | Purpose |
|------|---------|
| `kiutils` | Python library for reading/writing KiCad files (S-expr parser) |
| `kicad-skip` | Older library for symbol and footprint editing |
| Raw string templates | Build S-expressions manually via Python f-strings |

### Example structure
```python
# Using kiutils to build a schematic
from kiutils.schematic import Schematic
from kiutils.items.sch_items import SchSymbol, SchSymbolPin

sym = SchSymbol(
    libId="Device:R",
    position=[100.0, 100.0],
    reference="R1",
    value="10k"
)
# Append to schematic symbols list, write via sch.to_file()
```

### See also
- `references/raw-sexpr-kicad.md` for a complete indicator-panel example
  with 6 inline custom symbols and their S-expression definition

### Pitfalls
- **Coordinate system**: KiCad uses mm with Y-up. A 2.54mm grid is standard.
- **UUIDs**: Every symbol and symbol instance needs a unique UUID.
- **Version field**: The `(version 20221018)` header is required by KiCad 7+.
- **Lib symbols vs inline**: Inline symbols go inside `(lib_symbols ...)` in the
  `.kicad_sch` file; library-referenced symbols need the library registered.

## Verification Checklist

- [ ] All component pins are connected to a net
- [ ] No unconnected pins (use NC markers for intentional disconnects)
- [ ] Each net has exactly one label (no floating labels)
- [ ] Power nets (VCC, GND) have PWR_FLAG components
- [ ] Wire endpoints snap to grid (standard 2.54mm KiCad grid)
- [ ] No overlapping wires across component bodies
- [ ] ERC passes with zero errors
- [ ] Netlist generation produces valid output
