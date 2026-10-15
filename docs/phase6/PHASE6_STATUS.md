# Phase 6 — Practical components (status)

**Date:** 2026-10-15  
**Status:** In progress  
**Version:** 0.5.11

## Goal

Attach real-world component reality to the ideal synthesized ladder: preferred
value selection (E-series), finite Q / ESR / parasitics, tolerances, and the
downstream analysis/GUI support (FR-P1, FR-P2).

## Delivered

### E-series + snapping (FR-P1) — engine + CLI

- `components_std/e_series.py` — IEC 60063 base tables for **E6, E12, E24, E48,
  E96** (normalized per decade); `base_values`, `e_series_values`,
  `nearest_e_series` (log-distance, decade-safe).
- `components_std/snap.py` — `SnapStrategy`:
  - `independent` — snap every L and C (and R) independently
  - `l_only` / `c_only` — snap only the reactive part requested
  - `preserve_lc_resonances` — for LC resonators and Brune arms, snap L first
    then choose the C that best holds the L·C product, keeping resonance drift
    small while every part stays on-grid
  - returns a copied `Circuit` plus a `SnapReport` (per-part original → snapped,
    `delta_pct`, `max_delta_pct`).
- `services/session.py` — `DesignSession.snap_components(series, strategy)`.
- CLI — `filterdesk snap … --series E24 --strategy preserve_lc_resonances
  [--json]` (synthesize → snap → report + snapped component list).
- GUI — **Design → Snap to E-series…** opens `SnapDialog` (series + strategy),
  applies through `SnapCommand` (full undo/redo over the whole circuit), refreshes
  the table/schematic, reports the max change in the status bar and re-analyzes.

## Design notes

- Snapping never mutates the input circuit (frozen dataclasses + `replace`);
  callers swap in the returned copy.
- `preserve_lc_resonances` deliberately trades a slightly larger value change
  for smaller resonance drift; with coarse series (E24 near a gap such as 1.4)
  the improvement can be nil, and it grows toward E96/E192.
- Resistors snap under `independent` / `preserve_lc_resonances`, and are left
  untouched under `l_only` / `c_only`.

## Deferred (rest of Phase 6)

- Non-ideal element layers (`NonIdealInductor`, `NonIdealCapacitor`) + ABCD
  support for lossy/parasitic elements (FR-P2).
- GUI: non-ideal fields in the component table.
- Golden tests for finite-Q and E24-snapped cases.
- Manual library R / L / C / jX in the schematic library.

## Tests

- `tests/unit/test_components_std.py` — table shape, `nearest_e_series` anchors
  (including decade crossing), per-strategy snap behavior, resonance-preserving
  improvement (E96), session + CLI (`snap`, `--json`).
- `tests/unit/test_gui_smoke.py` — `SnapCommand` apply/undo and the
  Design → Snap action (dialog stubbed) with on-grid result.
