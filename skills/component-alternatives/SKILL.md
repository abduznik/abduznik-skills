---
name: component-alternatives
description: Find replacements for obsolete military components.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [components, alternatives, obsolete]
    category: software-development
tags: [electronics, components, military, cross-reference, replacement]
---


# Component Alternatives — Finding Replacements

When a part is obsolete, NRND, or needs a modern equivalent: find what fits the same footprint and pinout, decode military variants, check what's actually purchasable.

## Pipeline

### 1. Establish the baseline
- Get the datasheet (use `datasheet-hunting` pipeline)
- Extract the **exact pinout** from the pin configuration diagram — every pin, every function
- Note the package type (DIP, PLCC, SOIC, etc.) and pin count
- Note the architecture: parallel vs serial, voltage vs current output, internal reference vs external

### 2. Determine the military designation
- Search for `"<PART>" SMD OR JAN OR "MIL-STD-883"`
- SMD numbers follow the pattern `5962-xxxxx` — the DLA Land & Maritime Microcircuit Drawing
- The SMD drawing lists device types, case outlines, and lead finishes
- Military part number format: `5962-<drawing>0<device type><case outline><lead finish>`
  - Example: `5962-8778902EA` = drawing 87789, device type 02 (AD558T), case E (16-pin DIP), lead finish A
- `/883` suffix = MIL-STD-883 Class B screened
- S and T grades are typically the military temperature range (-55°C to +125°C)

### 3. Search for pin-compatible alternatives
- Search: `"<PART>" "pin compatible" OR "pin-to-pin" OR "drop-in replacement" OR "same pinout"`
- Search: `"<PART>" cross reference equivalent`
- Check the manufacturer's product page for "pin-for-pin alternate" suggestions (TI is good at this)
- Check Octopart/DigiKey for "similar" or "alternatives" sections

### 4. Verify compatibility
For each candidate:
- **Pin-for-pin**: same pinout, same package? Compare pin diagrams side by side
- **Electrical**: same supply voltage range? Same output type (voltage vs current)? Same resolution?
- **Timing**: settling time, conversion speed — does it match the application requirements?
- **Interface**: same bus interface (parallel/SPI/I2C)? Same control signals (CE/CS/WR)?
- **Temperature**: does the candidate cover the required operating range?

### 5. Assess availability
- Check DigiKey, Mouser, Octopart for active stock
- For military: check DLA inventory, Rochester Electronics (rocelec.com), or UTC (used test companies)
- Note: obsolete parts may still be available from surplus dealers but with no warranty on authenticity

## The Hard Truth

Many classic ICs (AD558, DAC0800 series, early ADCs) have **unique pinouts** that no other manufacturer copied. In these cases:
- The same part in military grades IS available (AD558S/T, 5962-87789)
- Functional alternatives exist but require board rework (different pinout)
- Document both options: "drop-in" (same part, military grade) vs "redesign" (different part, new layout)

## Military Variant Quick Reference

| Pattern | Meaning |
|---------|---------|
| `5962-xxxxx` | Standard Microcircuit Drawing (SMD) number |
| `/883` or `/883B` | MIL-STD-883 Class B screened |
| `M` in part name | Military temperature die variant |
| `S`, `T` suffix | Military temperature grade (-55°C to +125°C) |
| `Q` suffix (TI) | CERDIP package |
| `JAN` / `M38510` | Joint Army-Navy qualified part |

## Pitfalls

- **web_extract with ddgs backend fails consistently** on PDF URLs and many sites — fall back to `curl` + pymupdf extraction
- **Browser use times out** on PDF-heavy sites (analog.com, alldatasheet) — download via curl first, then extract
- **`python3` on Windows** points to the Microsoft Store stub — use the Hermes venv python at `C:/Hermes/.cache/runtimes/windows-x64/venv/Scripts/python.exe`
- **Pin-compatible ≠ functionally equivalent** — a part with the same pinout may have different electrical characteristics (output impedance, settling time, supply range). Always verify the electrical specs match the application.
- **"Obsolete" doesn't mean unavailable** — many obsolete ICs are still stocked by distributors and surplus dealers. Check before assuming you need a replacement.
- **Military drawings lag behind commercial datasheets** — the SMD drawing may reference an older revision. Cross-check specs against the current commercial datasheet.

## Verification
- Pinout: extracted from datasheet PDF, not from memory or third-party sources
- Military designation: sourced from DLA microcircuit drawing or manufacturer military databook
- Availability: cite the source (distributor page, search snippet) and date
- Compatibility: compare electrical specs side by side, not just pinout

## Related
- `datasheet-hunting` — finding and downloading the original datasheet
- `component-sourcing` — Octopart/DigiKey lookups for pricing and stock
- `datasheet-aggregation` — automated spec extraction and summary generation