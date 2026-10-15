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

### Non-ideal element layers (FR-P2) — engine + analysis

- `domain/circuit.py` — `NonIdealInductor` (`series_resistance_ohm`,
  `parallel_capacitance_f`) modeling `(R + jωL) || 1/(jωCp)` and
  `NonIdealCapacitor` (`esr_ohm`, `esl_h`) modeling `R + jωL + 1/(jωC)`; both
  expose `self_resonant_frequency_hz` (`None` when the parasitic is absent) and
  join the `Element` union / `component_table`.
- `analysis/adapters/abcd_ladder.py` — series/shunt ABCD for both types via
  `Z_nonideal_inductor` / `Z_nonideal_capacitor`.
- `components_std/nonideal.py` — `inductor_resistance_ohm_from_q`
  (`2π·f_ref·L/Q`), `make_nonideal_inductor` / `make_nonideal_capacitor`, and
  `nonidealize_circuit(...)` (copy; Q or explicit DCR on inductors, ESR/ESL on
  capacitors; untouched elements are left ideal).
- `domain/project.py` — field serialization/deserialization for both types.
- `services/session.py`, `gui/panels/component_table.py` — value lookup/edit and
  table display preserve the loss/parasitic fields.
- `services/session.py` — `DesignSession.apply_nonideal(...)`.
- CLI — `filterdesk analyze … [--inductor-q Q --q-frequency F] [--inductor-dcr R]
  [--inductor-cpar C] [--capacitor-esr R] [--capacitor-esl L]` applies the losses
  before analysis (and echoes them in `--json` under `nonideal`).
- GUI — **Design → Apply parasitics / Q…** opens `NonIdealDialog`, applies through
  `NonIdealCommand` (full undo/redo), then refresh + re-analyze.

## Design notes

- Snapping never mutates the input circuit (frozen dataclasses + `replace`);
  callers swap in the returned copy.
- `preserve_lc_resonances` deliberately trades a slightly larger value change
  for smaller resonance drift; with coarse series (E24 near a gap such as 1.4)
  the improvement can be nil, and it grows toward E96/E192.
- Resistors snap under `independent` / `preserve_lc_resonances`, and are left
  untouched under `l_only` / `c_only`.
- Non-ideal elements use an explicit physical model (R/L/C) rather than a single
  omnibus component: an inductor is `(R + jωL) || 1/(jωCp)`, a capacitor is
  `R + jωL + 1/(jωC)`. A zero loss/parasitic value reproduces the ideal element
  exactly (verified by equality against `IdealInductor`/`IdealCapacitor`).

## Deferred (rest of Phase 6)

- GUI: non-ideal fields in the component table (display/edit of Q/ESR/parasitics).
- Tolerances (Monte-Carlo / worst-case).
- Golden tests for finite-Q and E24-snapped cases.
- Manual library R / L / C / jX in the schematic library.

## Tests

- `tests/unit/test_components_std.py` — table shape, `nearest_e_series` anchors
  (including decade crossing), per-strategy snap behavior, resonance-preserving
  improvement (E96), session + CLI (`snap`, `--json`).
- `tests/unit/test_gui_smoke.py` — `SnapCommand` apply/undo and the
  Design → Snap action (dialog stubbed) with on-grid result.
- `tests/unit/test_nonideal.py` — self-resonant frequencies, lossless
  non-ideal ≡ ideal S-parameters, `ω_ref·L/Q` helper, finite-Q and ESR passband
  loss, `q_frequency_hz` requirement, project round-trip field preservation, and
  the `analyze` CLI flags (human / JSON / missing-frequency error).
- `tests/unit/test_gui_smoke.py` — `NonIdealCommand` apply/undo and the
  Design → Apply parasitics action (dialog stubbed).
