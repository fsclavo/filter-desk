# FilterDesk — Master Backlog

**Purpose:** single actionable list of outstanding work, current status and
decisions. It is the first document to update when a feature, menu path, test
count or release changes.  
**Status:** living document.  
**Last verified:** 2026-10-26 · **App version:** 0.11.1 · **Release v0.11.1:** pending · **Previous:** [v0.11.0](https://github.com/fsclavo/filter-desk/releases/tag/v0.11.0).  
**Verification:** local suite 882 passed, 1 skipped; coverage 83.1 %. CI green:
https://github.com/fsclavo/filter-desk/actions/runs/40369935124 (re-check after
every push and update this URL).

Legend: **P0** blocks release/correctness · **P1** completes a shipped feature ·
**P2** future/optional. Effort: **S** ≤ ½ day · **M** 1–3 days · **L** > 3 days.

---

## 1. Current GUI map

- **Design** — filter-only workflow: Synthesize + Analyze, Band preset, Snap to
  E-series, Apply parasitics/Q, Monte-Carlo, Scale response, Optimize to limits,
  Component sensitivity, Parameter sweep, Check spec compliance, Tune to VNA,
  Component submenu.
- **Tools** — independent component/utility calculators: Matching network,
  Attenuator pad, Coil calculator, **Transformer / balun / unun**, Microstrip
  line.
- **File** — project/Touchstone import and all exports (BOM, SPICE, LTspice,
  Qucs, CSV, Smith chart).

The former separate `Balun / unun` tool was removed; the transformer/balun/unun
designer is now one dialog with **Design** and **Model** tabs.

---

## 2. Unreleased after v0.11.0

- [x] Flags table: wider stretched column, word wrap, full tooltip and a visible
      legend for `LF`, `SAT`, `FIT`, `HF`, `THERMAL`.
- [x] Removed the Winding diagram tab/SVG/build-sheet sidecar; the designer now
      has only **Design** and **Model**. The connection drawings were not
      reliable enough for Guanella/Ruthroff/choke assemblies.
- [x] Kept the electrical ratio/status information in the component table, BOM
      and schematic label (no winding drawing).
- [ ] Decide whether to cut **v0.11.1** with this UI fix (it is not in the
      v0.11.0 release assets); also includes the kind-specific TLT diagrams.

## 3. v0.11.0 feature set

- Exact unequal terminations via output transformer `T1` (ADR-017), including
  SPICE/LTspice/Qucs export.
- Classical even-order Chebyshev-I with output transformer; even elliptic
  intentionally rejected (odd-only).
- Post-synthesis spec compliance (API, CLI `--check`, GUI Design action).
- MNA validation of the SPICE transformer model; ngspice test skips if absent.
- Transformer-type unun/balun/power calculator; HF power cores and mixes
  31/43/52/61.
- Autotransformer/isolated topology; winding-options table 2:14 / 3:21 / 4:28
  with Lm, X/Z, flux, wire fit and HF caution.
- Microstrip line, quarter-wave transformer and stub calculators; substrate
  presets and first-order loss.
- VNA-guided tuning: magnitude by default, optional phase/delay, local/wide/
  global bounds, synthetic tests.
- Boundary `BAL1`: project model, ABCD/skrf analysis, BOM, exports and unified
  designer.
- Ratio labels show turns and impedance explicitly (`1:7 turns / 1:49 Z`); BOM,
  component table and schematic share the format.
- Winding flags are explicit (`LF`, `SAT`, `FIT`, `HF`, `THERMAL`), with a
  wrapped/stretched column, tooltip and visible legend; `Bsat/B` is labelled
  correctly and the FT140-43/100 W case gets a thermal flag.
- Material data now includes μi, Bsat, Curie and complex-permeability loss points
  for mixes 31/43/52/61; core loss, copper loss and a natural-convection thermal
  estimate replace the power-density heuristic.
- Added FT114/FT140-31, FT114-52 and FT350-61; smaller 31 AL values scaled from
  μi and flagged for datasheet verification.
- CLI `transformer` unified (transformer/unun/balun model and options); the old
  `balun` command was removed.
- CI `gui-stability`: 15-min job, per-pass `timeout 300`,
  `faulthandler_timeout`, `-vv --durations`, uploaded logs.

---

## 4. Open backlog

### P0 — before calling v0.11.0

- [x] Bump `pyproject.toml`/`filterdesk.__version__`, add `CHANGELOG.md`, tag
      and publish v0.11.0. (S)
- [x] Release workflow built Linux/Windows/AppImage assets and published
      https://github.com/fsclavo/filter-desk/releases/tag/v0.11.0. (S)
- [ ] Verify the unified GUI paths and CLI examples in the user manual against a
      fresh installed bundle. (S)

### P1 — correctness / validation

- [ ] **Physical winding drawing:** current output is intentionally the
      electrical connection only. A real wire-route/toroid drawing needs field
      validation, especially for Guanella/Ruthroff crossover and choke wiring. (M/L)
- [ ] **VNA hardware validation:** use the two available captures as holdout
      data; add a documented calibration/reference-plane protocol and compare
      phase/delay fits. (M)
- [ ] **Balun model depth:** full multi-line Guanella/Ruthroff, common-mode
      impedance in the differential 2-port, winding geometry, and validated
      SPICE/LTspice/Qucs export of the TLT section. (L)
- [ ] **Distributed netlist:** microstrip/stub/quarter-wave are calculators;
      add transmission-line/stub elements to circuits, ABCD/skrf, BOM and
      distributed synthesis. (L)
- [ ] External SPICE validation: open the generated netlists in ngspice,
      LTspice and Qucs; confirm Qucs `Tr` ratio orientation. (M)

### P2 — data / ergonomics

- [ ] More ferrite data: confirm the estimated FT114/FT140-31 AL values and add
      further 52/61 sizes with verified μi, Bsat/temperature and loss data. (M)
- [ ] Toroid/transformer GUI: persist the selected winding option in the
      project/BOM notes and add per-option DCR/leakage estimates when the model
      supports them. (M)
- [ ] Add a compact text-only winding schedule to the Markdown/HTML BOM header
      (currently the diagram is a sidecar SVG). (S)
- [ ] Update historical phase/status documents only when they are used as
      current references; do not treat them as the backlog. (S)

### Parked by design

- Even-order elliptic synthesis (would need general unequal-R Darlington/Cauer).
- `.lct` import (no reliable oracle).
- Mid-ladder transformers/baluns (current boundary insertion only).
- Full EM/3-D or coupled-inductor modeling.

---

## 5. Maintenance rule

Every change must update, in the same commit:

1. `docs/BACKLOG.md` — status/checkboxes and current menu/CLI paths.
2. `docs/user-manual.md` — user-facing workflow and limitations.
3. `README.md` — feature bullets if the user-visible feature set changes.
4. Tests and i18n catalog when a string/menu/CLI action changes.
