# FilterDesk — Master Backlog

**Purpose:** single actionable list of outstanding work, current status and
decisions. It is the first document to update when a feature, menu path, test
count or release changes.  
**Status:** living document.  
**Last verified:** 2026-10-28 · **App version:** 0.22.0 · **Released:**
[v0.22.0](https://github.com/fsclavo/filter-desk/releases/tag/v0.22.0) ·
**Previous:**
[v0.21.0](https://github.com/fsclavo/filter-desk/releases/tag/v0.21.0) ·
**Next:** v0.23.0 planning.

**Verification:** local suite **1013 passed** with ngspice (3 skipped without); coverage **83.33 %**.
Main CI: https://github.com/fsclavo/filter-desk/actions/runs/40531208496
Release workflow: https://github.com/fsclavo/filter-desk/actions/runs/40531208808

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

## 3. v0.22.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.22.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 4. v0.21.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.21.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 5. v0.20.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.20.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 6. v0.19.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.19.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 7. v0.18.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.18.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 8. v0.17.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.17.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 9. v0.16.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.16.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 10. v0.15.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.15.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 11. v0.14.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.14.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 12. v0.13.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.13.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 13. v0.12.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.12.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 14. Open backlog

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
- [x] **Guanella multi-line:** integer 1:N² Guanella ratios now use an explicit
      N-line parallel/series network.
- [x] **1:4 Ruthroff depth:** equal-delay bootstrap ABCD; other ratios remain
      first-order.
- [x] **Choke common-mode estimate:** series-choke `Zcm` and attenuation at
      `f_min` are reported separately from the differential 2-port.
- [x] **Choke common-mode sweep:** five-point `Zcm`/attenuation table and CLI
      JSON, separate from the differential 2-port.
- [x] **Mixed-mode 3-port + Guanella SPICE:** block-diagonal `Sdd/Scc`, GUI/CLI
      reporting and ngspice-validated Guanella differential export.
- [ ] **Asymmetric 4-port/EM + Ruthroff SPICE:** full cross-mode and Ruthroff
      export remain future work. (L)
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
- [x] **Distributed LP orders 4–5:** bounded numerical fit with strict
      passband/stopband gates (post-v0.13.0, in `Unreleased`).
- [x] **Guanella multi-line model:** integer 1:N² ratios use an explicit N-line
      parallel/series network (post-v0.13.0).
- [x] **1:4 Ruthroff and choke common-mode estimate:** equal-delay bootstrap
      network plus separate `Zcm`/attenuation (post-v0.14.0).
- [x] **ABCD edge cases:** exact open/short/resonant arms are clamped to finite
      stand-ins; stress handles an open shunt without warnings.
- [x] **Winding realism:** DCR low/high, leakage and the selected option are
      persisted and shown in GUI/CLI/BOM.
- [x] **QA hardening:** SciPy independent LP/HP/BP/BS oracle, semantic
      diagram/SVG checks, Smith image baseline and `docs/qa-matrix.md`.
- [x] **Microstrip dispersion:** Kirschning-Jansen `eeff(f)`/`Z0(f)` for line and
      stub analysis.
- [x] **Open-end fringing:** Hammerstad open-stub length correction.
- [ ] **Distributed synthesis depth:** all-response distributed design,
      stub-only/Kuroda topologies, step discontinuities and hardware validation. (L)

- [ ] Confirm the estimated FT114/FT140-31 AL values and add more 31/52/61 core
      sizes with verified material data. (M)
- [x] Persist the selected winding option in project/BOM notes.
- [x] Add DCR/leakage estimates per winding option (DCR at 20 °C; leakage from
      the coupling model).

- [ ] **Measured-vs-simulated cursor readout:** when a Touchstone overlay is
      visible, append the measured values and their differences to the cursor
      readout so the built filter can be compared with the calculation:
      `S21 meas` + `ΔS21` (dB), `S11 meas` + `ΔS11` (dB), `VSWR meas` + `ΔVSWR`,
      and `∠S21 meas` + `Δ∠S21` (degrees). Definitions:
      `ΔS21 = S21_dB − S21_meas_dB`, `ΔS11 = S11_dB − S11_meas_dB`,
      `ΔVSWR = VSWR − VSWR_meas`, `Δ∠S21 = ∠S21 − ∠S21_meas` (wrapped to ±180°).
      Because the simulated and VNA grids do not necessarily match, interpolate
      the measured complex `S11`/`S21` onto the cursor frequency (real/imag, with
      unwrapped phase for the phase delta) and show `—` outside the measured
      band. Only shown while the measured overlay is visible; keep the existing
      readout fields. (S/M)
      - Acceptance: synthetic sim/meas fixtures with different frequency grids
        verify interpolation and the four deltas; out-of-band shows `—`;
        GUI smoke test.
      - Later/optional (not part of v1): group-delay and `|Zin|` differences,
        dedicated ΔS21/ΔS11 curves tab, band RMS/max comparison, and delay
        alignment before comparing phase.

### Parked by design

- Even-order elliptic synthesis (needs general unequal-R Darlington/Cauer).
- `.lct` import (no reliable oracle).
- Mid-ladder transformers/baluns (boundary insertion only).
- Full EM/3-D or coupled-inductor modeling.
- Physical winding drawings (removed; not considered reliable).

---

## 15. Ham-radio onboarding and discoverability

- [x] README/manual onboarding sections for radio amateurs: first-five-minute
      path, common tasks, glossary, Spanish introduction and natural search
      terms.
- [x] Package metadata description/keywords include amateur radio, homebrew,
      toroid, balun and VNA.

## 16. Maintenance rule

Every change must update, in the same commit:

1. `docs/BACKLOG.md` — status/checkboxes, test count, GUI/CLI paths.
2. `docs/user-manual.md` — user-facing workflow and limits.
3. `CHANGELOG.md` — user-visible changes, especially release entries.
4. `README.md` — feature bullets when the visible feature set changes.
5. Tests, i18n and `docs/validation-matrix.md` when models/validation change.
