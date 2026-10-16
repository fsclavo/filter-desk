# Phase 10 — Broader export + measured S2P compare (status)

**Date:** 2026-10-15  
**Status:** In progress  
**Version:** 0.6.0

## Goal

Export simulation/measured traces and netlists beyond Touchstone: CSV/DAT
traces, LTspice `.asc`, Qucs `.sch`.

## Delivered

### CSV / DAT trace export

- `io/csv_export/`:
  - `export_csv(result, path, *, columns, comment)` — header-annotated CSV of
    standard traces (`frequency_hz`, `s21_db`, `s11_db`, `s22_db`, `s21_mag`,
    `s11_mag`, `vswr`, `group_delay_s`, `il_db`, `rl_db`, plus `zin_ohm` /
    `zout_ohm`). Metadata lines are prefixed `#`; the column header is a normal
    row so generic CSV tools parse it.
  - `export_dat(freq, values, path, *, comment)` — two-column DAT trace.
  - `analysis_from_touchstone(data)` — 2-port `TouchstoneData` → `AnalysisResult`.
  - `CsvExportError` for unknown/empty columns or shape mismatch.
- CLI — `analyze … --export-csv PATH`; `to-csv INPUT.{s2p} OUTPUT.csv
  [--columns …]`.
- GUI — **File → Export CSV…** writes the current analysis.

### SPICE / LTspice netlist export

- `io/spice/`:
  - `spice_netlist(circuit, *, title, ac, source_name)` — LTspice-compatible flat
    netlist: AC source + source/load resistances, one line per primitive, ground
    mapped to `0`, `.ac` directive from the sweep, `.backanno` / `.end`.
  - LC and Brune arms and non-ideal L/C expand into primitives with internal
    nodes (`LX1L`/`CX1C`, `LL1`/`RL1r`/`CL1cp`, …); zero DCR stays ideal.
  - `SpiceExportError` for empty/unsupported circuits.
- CLI — `analyze … --export-spice PATH`.
- GUI — **File → Export SPICE netlist…**.

## Deferred

- LTspice `.asc` *schematic* (needs a geometry/layout model; the SPICE netlist is
  the portable, simulator-ready path).
- Qucs `.sch` exporter.

## Tests

- `tests/unit/test_csv_export.py` — header/values round-trip, custom columns,
  unknown/empty column errors, DAT export + length mismatch, Touchstone →
  `AnalysisResult` round-trip, and CLI (`analyze --export-csv`, `to-csv`, bad
  input).
- `tests/unit/test_spice_export.py` — netlist directives/terminations, ground→0,
  series-LC and non-ideal L/C expansion, zero-DCR ideal, empty-circuit error, and
  CLI `analyze --export-spice`.
- `tests/unit/test_gui_smoke.py` — **File → Export CSV…** and **File → Export
  SPICE netlist…** actions write files.
