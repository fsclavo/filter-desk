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

### LTspice `.asc` schematic export

- `io/spice/ltspice_asc.py`:
  - `ltspice_asc(circuit, *, title, ac)` / `write_ltspice_asc(...)` produce a
    graphical LTspice schematic (`.asc`) that opens directly.
  - Connectivity uses **net-label `FLAG` items placed exactly on component pins**
    (same-named flags are one net), so no fragile wire routing is needed; ground
    is `FLAG 0`.
  - Standard symbol pin offsets (`ind`/`res` = (16,16)/(16,96), `cap` =
    (16,0)/(16,64), `voltage` = (0,16)/(0,96)) drive placement; ideal L/C/R and
    series/parallel LC arms are supported, plus auto V1 (AC 1) + `Rsource` +
    `Rload`. Unsupported arms (Brune) raise `SpiceExportError`.
  - The netlist `.cir` writer remains the portable simulator-ready path.
- CLI — `analyze … --export-asc PATH`.
- GUI — **File → Export → LTspice (.asc)…**.

### Qucs `.sch` schematic export (best-effort)

- `io/qucs/`:
  - `qucs_schematic(circuit, *, title, z0_ohm)` / `write_qucs_schematic(...)`
    produce a Qucs XML schematic with `<Components>` + `<Wires>` and S-parameter
    test ports `P1`/`P2`.
  - Layout: series elements on a horizontal rail (R/C/L ports at ±30 px), shunt
    elements dropped to `GND`; wire endpoints touch component pins (geometric
    connectivity). Ideal L/C/R and series/parallel LC arms supported; unsupported
    arms raise `SpiceExportError`.
- CLI — `analyze … --export-qucs PATH`.
- GUI — **File → Export → Qucs (.sch)…**.
- Best-effort: generated layout is not validated against a running Qucs here.

## Deferred

- None (LTspice `.asc` and Qucs `.sch` delivered; SPICE netlist + Touchstone
  remain the primary interchange paths).

## Tests

- `tests/unit/test_csv_export.py` — header/values round-trip, custom columns,
  unknown/empty column errors, DAT export + length mismatch, Touchstone →
  `AnalysisResult` round-trip, and CLI (`analyze --export-csv`, `to-csv`, bad
  input).
- `tests/unit/test_spice_export.py` — netlist directives/terminations, ground→0,
  series-LC and non-ideal L/C expansion, zero-DCR ideal, empty-circuit error, and
  CLI `analyze --export-spice`; plus `.asc` structure, pin↔FLAG alignment,
  series-LC internal node, unsupported-arm error, and CLI `analyze --export-asc`.
- `tests/unit/test_gui_smoke.py` — **File → Export** submenu (Smith/CSV/Touchstone/
  SPICE/LTspice) and each export action writes a file.
