# FilterDesk — Master Backlog

**Purpose:** single actionable list of outstanding work, current status and
decisions. It is the first document to update when a feature, menu path, test
count or release changes.  
**Status:** living document.  
**Last verified:** 2026-10-26 · **App version:** 0.13.0 · **Release:** prepared,
not published · **Previous:**
[v0.12.0](https://github.com/fsclavo/filter-desk/releases/tag/v0.12.0) ·
**Next:** v0.14.0 planning.

**Verification:** local suite **946 passed, 2 skipped** (ngspice unavailable locally); coverage **82.93 %**.
Main CI: https://github.com/fsclavo/filter-desk/actions/runs/40490137920
Release workflow: https://github.com/fsclavo/filter-desk/actions/runs/40409343943

Legend: **P0** blocks release/correctness · **P1** completes a shipped feature ·
**P2** future/optional. Effort: **S** ≤ ½ day · **M** 1–3 days · **L** > 3 days.

---

## 1. Current GUI map

- **Design** — filter-only workflow: Synthesize + Analyze, Band preset, Snap to
  E-series, Apply parasitics/Q, Monte-Carlo, Scale response, Optimize to limits,
  Component sensitivity, Parameter sweep, Check spec compliance, Tune to VNA,
  **Distributed microstrip realization**, Component submenu.
- **Tools** — independent calculators: Matching network, Attenuator pad, Coil
  calculator, **Transformer / balun / unun**, Microstrip line.
- **File** — project/Touchstone import and exports: BOM, SPICE, LTspice, Qucs,
  CSV and Smith chart; **Recent projects** for the last ten files.
- **Help** — Model confidence inventory and user manual.
- The transformer/balun/unun designer has only **Design** and **Model** tabs;
  winding diagrams were removed.

---

## 2. Completed after v0.11.0

- [x] Flags table: stretched/wrapped column, full tooltip and visible legend for
      `LF`, `SAT`, `FIT`, `HF`, `THERMAL`.
- [x] Removed the Winding diagram tab/SVG/build-sheet sidecar; only Design and
      Model remain.
- [x] Contextual filter **Model status** strip (synthesis, analysis, components,
      T1/BAL1).
- [x] Central confidence registry, Help → Model confidence, confidence badges in
      transformer/microstrip/VNA dialogs.
- [x] Build-sheet **Assumptions** section.
- [x] Cross-backend validation matrix (10 synthesis paths), ngspice CI job and
      `docs/validation-matrix.md`.
- [x] VNA measurement metadata sidecar, CLI holdout evaluation, fit-quality notes
      and `docs/vna-measurement-protocol.md`. Real captures remain P0.
- [x] Manual **Update spec from circuit** action: derives cutoff/center/bandwidth
      from the response while preserving family/order/topology; circuit untouched,
      undoable, with explicit preview.
- [x] HF receive-band BPF wizard: band/requirements → candidate order table →
      apply → optional E24 snap; reuses normal BOM/VNA workflow.
- [x] Measured-overlay legends are hidden until a Touchstone file is loaded;
      Smith chart and response plots no longer advertise empty `meas` traces.
- [x] Distributed microstrip v1: line/stub domain elements, ABCD/skrf, project
      v2, BOM geometry, schematic, experimental LP synthesis (order ≤ 3) and CLI.
- [x] **File → Recent projects** (up to ten files, persisted, missing-entry
      cleanup and clear action).
- [x] **Band Preset → Band Pass** uses order 5 so 50 Ω ports stay equal and no
      ideal output transformer T1 is inserted.
- [x] **Power stress** now uses a nodal solve with source/load, T1/BAL1 and
      distributed line/stub elements; Vpk/Ipk are no longer a constant-arm
      rule of thumb.

---

## 3. v0.13.0 release (prepared, not published)

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.13.0.
- [x] CHANGELOG/manual/backlog updated.
- [ ] Tag, publish and verify Windows/Linux/AppImage assets.
- [ ] Release URL recorded above.

---

## 4. v0.12.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.12.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 5. Open backlog

### P0 — release quality

- [x] **Clean-machine package acceptance:** AppImage and Windows installer run a
      headless `--self-test` on clean CI runners (GUI construction, synthesize,
      Touchstone import/export, BOM, project round-trip). Physical-desktop
      visual check remains the only manual residue. (S)
- [ ] **LTspice/Qucs external validation:** open representative netlists/schematics
      and confirm syntax, transformer ratio orientation and node mapping. (M)
- [ ] **VNA holdout (hardware):** run the two real captures through the new
      protocol and record calibration/reference-plane metadata. The tooling and
      synthetic holdout tests are ready. (M)

### P1 — validation / model depth

- [ ] **High-flux thermal validation:** replace low-flux μ'' estimates with vendor
      high-flux curves or measurements; validate FT140/FT240 temperature rise. (M/L)
- [ ] **Balun model depth:** full multi-line Guanella/Ruthroff, common-mode
      impedance in the differential 2-port and validated TLT export. (L)
- [x] **Distributed netlist v1:** line/stub elements are integrated into the
      domain, ABCD/skrf, project v2, BOM and an experimental order-1–3 LP
      synthesis. Full response coverage, higher orders, stub-only/Kuroda
      topologies and EM remain future work. (L)
- [x] **Installed-package regression:** CI now exercises Linux bundle/AppImage
      and the installed Windows app headlessly; see `docs/packaging.md`. (M)

### P2 — data / ergonomics

- [x] **Distributed SPICE export:** microstrip lines and stubs now export as
      lossless SPICE `T` elements, with open/short stub terminations; LTspice
      `.asc`/Qucs remain unsupported.
- [ ] **Distributed synthesis depth:** higher-order/all-response distributed
      design, stub-only/Kuroda topologies, dispersion/discontinuity models and
      hardware validation. (L)

- [ ] Confirm the estimated FT114/FT140-31 AL values and add more 31/52/61 core
      sizes with verified material data. (M)
- [ ] Persist the selected winding option in project/BOM notes. (S)
- [ ] Add DCR/leakage estimates per winding option once the model supports them. (M)

### Parked by design

- Even-order elliptic synthesis (needs general unequal-R Darlington/Cauer).
- `.lct` import (no reliable oracle).
- Mid-ladder transformers/baluns (boundary insertion only).
- Full EM/3-D or coupled-inductor modeling.
- Physical winding drawings (removed; not considered reliable).

---

## 6. Ham-radio onboarding and discoverability

- [x] README/manual onboarding sections for radio amateurs: first-five-minute
      path, common tasks, glossary, Spanish introduction and natural search
      terms.
- [x] Package metadata description/keywords include amateur radio, homebrew,
      toroid, balun and VNA.

## 7. Maintenance rule

Every change must update, in the same commit:

1. `docs/BACKLOG.md` — status/checkboxes, test count, GUI/CLI paths.
2. `docs/user-manual.md` — user-facing workflow and limits.
3. `CHANGELOG.md` — user-visible changes, especially release entries.
4. `README.md` — feature bullets when the visible feature set changes.
5. Tests, i18n and `docs/validation-matrix.md` when models/validation change.
