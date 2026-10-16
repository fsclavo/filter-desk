# Phase 10 — Broader export + measured S2P compare (status)

**Date:** 2026-10-15  
**Status:** In progress  
**Version:** 0.5.11

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

## Deferred

- LTspice `.asc` exporter.
- Qucs `.sch` exporter.

## Tests

- `tests/unit/test_csv_export.py` — header/values round-trip, custom columns,
  unknown/empty column errors, DAT export + length mismatch, Touchstone →
  `AnalysisResult` round-trip, and CLI (`analyze --export-csv`, `to-csv`, bad
  input).
- `tests/unit/test_gui_smoke.py` — **File → Export CSV…** action writes a file.
