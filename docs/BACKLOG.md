# FilterDesk — Master Backlog

**Purpose:** single actionable list of outstanding work, current status and
decisions. It is the first document to update when a feature, menu path, test
count or release changes.  
**Status:** living document.  
**Last verified:** 2026-10-26 · **App version:** 0.10.2 · **Next release:** v0.11.0 (pending).  
**Verification:** local suite 881 passed, 1 skipped; coverage 83.2 %. CI is
re-checked after every push; update the run URL here when it changes.

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
designer is now one dialog with **Design**, **Model** and **Winding** tabs.

---

## 2. Recently completed (unreleased since v0.10.2)

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
- Winding diagram: connection schematic + stylized toroid SVG, schedule, GUI
  **Winding** tab and build-sheet sidecar.
- CLI `transformer` unified (transformer/unun/balun model and options); the old
  `balun` command was removed.
- CI `gui-stability`: 15-min job, per-pass `timeout 300`,
  `faulthandler_timeout`, `-vv --durations`, uploaded logs.

---

## 3. Open backlog

### P0 — before calling v0.11.0

- [ ] Bump `pyproject.toml` to **0.11.0**, add changelog/release notes, tag and
      publish. (S)
- [ ] Re-run and record the final CI run URL, test count and coverage in this
      file. (S)
- [ ] Verify the unified GUI paths and CLI examples in the user manual. (S)

### P1 — correctness / validation

- [ ] **Physical winding drawing:** current output is a connection schematic +
      stylized toroid. A real wire-route drawing needs field validation,
      especially for Guanella/Ruthroff crossover and choke wiring. (M/L)
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

- [ ] More ferrite data: FT114/FT140-31 and further 52/61 sizes with verified
      AL, μi, Bsat/temperature and optional Steinmetz/core-loss coefficients. (M)
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

## 4. Maintenance rule

Every change must update, in the same commit:

1. `docs/BACKLOG.md` — status/checkboxes and current menu/CLI paths.
2. `docs/user-manual.md` — user-facing workflow and limitations.
3. `README.md` — feature bullets if the user-visible feature set changes.
4. Tests and i18n catalog when a string/menu/CLI action changes.
