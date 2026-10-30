# Changelog

All notable changes to FilterDesk. The project follows a `0.x` versioning
scheme while the public CLI/GUI stabilizes.

## v0.44.0 — 2026-10-30

### Added

- N-port S-parameter core with port renumbering, port termination and parallel
  combination of grounded 2-port branches.
- Generic Touchstone `.sNp` reader/writer plus the
  `network info|renumber|terminate|combine` CLI commands.
- ADR-027 documents the supported interconnection model and its limits.

## v0.43.0 — 2026-10-30

### Changed

- Power-stress analysis now reports the worst per-element Vpk/Ipk across up to
  25 points of the current sweep instead of a single landmark frequency. Voltage
  and current maxima are tracked independently and shown with their frequencies.
- Build sheets note that peak V/I are worst-case values when a sweep was used.

## v0.42.0 — 2026-10-30

### Added

- Markdown/HTML build sheets now include the TX harmonic-rejection table when a
  harmonic reference is available, both from the GUI and from
  `analyze --harmonics --export-build-sheet`.

## v0.41.0 — 2026-10-29

### Added

- **Tune…** in the Measurements dock activates a stored capture and opens the
  existing VNA tuning workflow directly from the history.

## v0.40.0 — 2026-10-29

### Added

- Measurement metadata is now editable from **Measurements → Details…**:
  VNA, calibration, reference plane, cables, connectors, terminations, fixture,
  temperature, date, operator and notes.

## v0.39.0 — 2026-10-29

### Added

- **Measurement details** dialog: full provenance (VNA, calibration, reference
  plane, cables, connectors, fixture, temperature, operator, notes) and a
  comparison against the current analyzed design.

## v0.38.0 — 2026-10-29

### Added

- Persistent **measurement history** per project: import multiple Touchstone
  captures, keep VNA/calibration/reference-plane metadata, select the active
  overlay, delete individual records or clear the history.
- Stored measurements survive project save/load and are available to the VNA
  comparison/tuning workflow.

## v0.37.1 — 2026-10-29

### Fixed

- The coax notch plot now uses the same SI/log-frequency axis as the main
  S21/S11 plot, with plain tick numbers instead of exponent notation.

## v0.37.0 — 2026-10-29

### Added

- The coaxial-stub notch dialog now plots estimated S21/S11 and exports the
  response (including metadata) to CSV.

## v0.36.0 — 2026-10-29

### Added

- Coax stub notch cable presets (`RG-58`, `RG-8X`, `RG-213`, `RG-174`,
  `RG-316`, `LMR-400`, `LMR-600`) with typical frequency-dependent loss.
- Estimated S21/S11 notch response, notch depth, −3 dB bandwidth and loaded Q,
  with a selectable through-line impedance.

## v0.35.0 — 2026-10-29

### Added

- **Coaxial stub notch** calculator (`filterdesk coax-stub` and Tools):
  λ/4 open or λ/2 shorted shunt cable stub, with velocity factor, optional
  cable loss and physical/electrical length output.

## v0.34.1 — 2026-10-29

### Fixed

- Debian packaging now writes the `.deb` to `dist/` and removes the ~750 MB
  staging tree after each build. Set `KEEP_DEB_STAGE=1` only when debugging.

## v0.34.0 — 2026-10-29

### Added

- Contextual tooltips and status tips for the Specification fields, plot tabs
  and the main menu actions, in English and Spanish.

## v0.33.0 — 2026-10-29

### Added

- The 4-port mixed-mode dialog can export the full frequency set as CSV or JSON
  (Sdd21/Sdc21/Scd21/Scc21 in dB, plus reference impedances in JSON).

## v0.32.0 — 2026-10-29

### Added

- The **4-port mixed-mode** dialog now has a **Plot** tab with Sdd21, Sdc21,
  Scd21 and Scc21 versus frequency, alongside the existing table.

## v0.31.1 — 2026-10-29

### Added

- Closing a dirty project now asks **Save / Discard / Cancel**. Cancelling the
  save dialog keeps the application open; successful saves close normally.

## v0.31.0 — 2026-10-29

### Added

- **Tools → 4-port mixed-mode…** imports an `.s4p` Touchstone file and shows
  `Sdd21`, `Sdc21`, `Scd21` and `Scc21` in a table, with the mixed-mode reference
  impedances and a sampled view for very large files.

## v0.30.0 — 2026-10-29

### Added

- **4-port mixed-mode analysis:** `filterdesk mixed-mode` reads an asymmetric
  `.s4p` Touchstone file and returns differential/common S blocks plus the
  cross-mode `Sdc`/`Scd` terms in JSON. This is a rigorous S-parameter transform;
  it does not invent an EM/device model.

## v0.29.4 — 2026-10-29

### QA

- Added a full preset-matrix regression test that verifies the plot state at
  auto-fit time: no stale cursors, only current harmonic markers, and the data
  range matches the active sweep.

## v0.29.3 — 2026-10-29

### Fixed

- A new analysis now hides the stale plot cursor before fitting the view. A
  cursor left outside the new frequency range no longer expands the X axis.

## v0.29.2 — 2026-10-29

### Fixed

- Auto plot fitting now runs **after** harmonic markers are refreshed. Stale
  harmonics from the previous filter no longer expand the X axis when switching
  between quick presets.

## v0.29.1 — 2026-10-29

### Fixed

- With **Auto** enabled, the plot view now refits whenever a new analysis has a
  different frequency span, even if the one-shot synthesis fit was missed.
  Reanalysing the same sweep keeps the current zoom for tuning.

## v0.29.0 — 2026-10-28

### Added

- **Auto** sweep mode in the toolbar. It chooses a plotting range from the
  filter type (including 2f/3f coverage for LPFs), updates the visible start/stop
  controls and keeps custom ranges when Auto is off.
- Suggested ranges now replace the fixed `fc/20 … fc*20` default for new
  sessions and CLI analyses.

### Changed

- Band-wizard applies keep their band-specific sweep; project loads infer Auto
  from whether the saved sweep still matches the suggested range.

## v0.28.2 — 2026-10-28

### Fixed

- After a deliberate synthesis, band-wizard apply, response scaling or project
  load, the frequency plots fit their data again even if the user had previously
  panned or zoomed. The one-shot fit does not keep auto-range latched during
  marker tuning.

## v0.28.1 — 2026-10-28

### Fixed

- Band-filter wizard snapping now uses **Preserve LC resonances** instead of
  independent L/C rounding. The series is selectable (E24/E48/E96), defaults to
  E96 above 100 MHz and warns when the snapped response misses the target.

## v0.28.0 — 2026-10-28

### Added

- VHF/UHF band presets: **2 m** (144–148 MHz), **1.25 m** (222–225 MHz,
  Region 2) and **70 cm** (420–450 MHz) in the GUI wizard and the `bands` /
  `synthesize --band` CLI paths.

## v0.27.1 — 2026-10-28

### Fixed

- The band-filter wizard now applies its band sweep to the visible start/stop
  frequency controls before analysis, and undo restores the previous range.
  Previously the analysis silently re-used the old default range.

### Changed

- AM/FM broadcast presets in the GUI now offer only **Band-stop (notch)**;
  amateur bands keep LPF, HPF, BPF and BSF. The service API remains general.

## v0.27.0 — 2026-10-28

### Added

- Unified **Band filter wizard** for every amateur and AM/FM broadcast preset,
  with **Quick** order-5 presets and a **Guided** requirements → candidate-order
  workflow for LPF, HPF, BPF and BSF.
- Guided LPF candidates report rejection at 2× and 3× the upper band edge;
  equal-port BPF/BSF designs search odd orders to avoid the ideal output
  transformer.

### Changed

- Replaced the separate **Band preset…** and **HF band filter wizard…** menu
  actions with **Design → Band filter wizard…**.

## v0.26.0 — 2026-10-28

### Added

- Self-contained Debian/Ubuntu `amd64` package (`FilterDesk-<ver>-amd64.deb`)
  with an `/opt/filterdesk` payload, `/usr/bin/filterdesk` launcher, desktop
  entry, icon and documentation.
- Release CI builds the `.deb` and verifies install, headless self-test and
  removal in a clean Ubuntu 22.04 container.

## v0.25.1 — 2026-10-28

### Fixed

- Thermal rise is no longer extrapolated from low-flux μ'' for suppression mixes
  31/43/52; those designs now report **not evaluated**. Power-rated mix 61 keeps
  the existing estimated thermal model.

## v0.25.0 — 2026-10-28

### Added

- Ferrite core table now includes FT37/FT50/FT82 sizes in 31, 52 and 61 mixes.
- Dimension/permeability consistency test for every ferrite AL entry, including
  the previously estimated FT114/FT140-31 values.

### Changed

- Clarified that ferrite AL values are typical μi/dimension-derived values with
  ±20–25 % batch spread, not individually measured vendor data.

## v0.24.1 — 2026-10-28

### Fixed

- The Transformer / balun / unun dialog now exposes **Export TLT SPICE…** for
  integer-ratio Guanella and Ruthroff 1:4 step-up designs.

## v0.24.0 — 2026-10-28

### Added

- Ruthroff 1:4 voltage-balun SPICE export: single bootstrap TEM line, floating
  balanced load, CLI/GUI path and ngspice low-frequency validation.

## v0.23.0 — 2026-10-28

### Added

- Measured-vs-simulated cursor readout: while a Touchstone overlay is visible,
  the response cursor now appends interpolated measured S21/S11/VSWR/∠S21 and
  the four deltas against the simulation. Values outside the measured band show
  `—`; the existing readout fields are unchanged.

## v0.22.0 — 2026-10-28

### Added

- Open microstrip stubs now include the Hammerstad open-end/fringing length
  correction, using dispersive `eeff` and stored substrate geometry.

## v0.21.0 — 2026-10-27

### Added

- Microstrip line/stub analysis now uses Kirschning-Jansen frequency dispersion
  (`eeff(f)`, `Z0(f)`) when substrate `er`/height/width are available.
- Distributed synthesis records substrate data and evaluates high-order fits with
  dispersion enabled.

## v0.20.0 — 2026-10-27

### Added

- Mixed-mode 3-port boundary model (`Sdd`, `Scc`, zero symmetric cross-mode)
  with GUI table and CLI JSON.
- Guanella TLT SPICE test netlist (parallel/series `T` lines, center-node
  choke) validated against `Sdd21` with ngspice.

## v0.19.0 — 2026-10-27

### QA

- Extended the independent SciPy oracle to band-pass/band-stop Butterworth,
  Chebyshev I/II and elliptic designs (orders 3/5).
- Added an image-level Smith-chart baseline and tolerant pixel comparison.
- Documented the BP/BS and visual-regression evidence in the QA matrix.

## v0.18.0 — 2026-10-27

### QA

- Added an independent SciPy analog-prototype oracle for LP/HP Butterworth,
  Chebyshev I/II and elliptic synthesis.
- Added semantic visual QA for schematic geometry/labels/render and for SVG
  plots/Smith export.
- Added `docs/qa-matrix.md` with per-area evidence and known gaps.

## v0.17.0 — 2026-10-27

### Added

- Transformer/balun options now report per-winding DC resistance (20 °C), the
  selected winding option is persisted, and DCR/leakage appear in the GUI,
  CLI and BOM.

## v0.16.0 — 2026-10-27

### Added

- Choke baluns now expose a five-point common-mode frequency sweep (`|Zcm|` and
  series-choke attenuation) in the GUI Model tab and CLI JSON, separate from the
  differential 2-port.

### Fixed

- Exact-resonance/open/short ideal arms no longer emit divide/invalid warnings
  in ABCD or stress analysis; open shunt arms report infinite impedance and
  zero current without warnings.

## v0.15.0 — 2026-10-27

### Added

- 1:4/4:1 Ruthroff TLTs use an equal-delay bootstrap ABCD network.
- Chokes report a first-order series common-mode impedance/attenuation estimate
  at the lowest frequency, separately from the differential 2-port.

## v0.14.0 — 2026-10-27

### Added

- Distributed LP v3: order 4–5 Butterworth/Chebyshev-I designs use a bounded
  numerical fit and a strict response gate; rejected fits return an explicit
  error instead of a questionable design.
- Guanella TLTs with integer 1:N² ratios now use an explicit N-line
  parallel-input/series-output network. Other TLT ratios remain first-order.

## v0.13.0 — 2026-10-27

### Added

- **File → Recent projects** keeps up to ten recently opened/saved projects,
  removes missing entries and offers a clear-list action.
- Experimental distributed microstrip v1: canonical microstrip line/stub
  elements, ABCD/scikit-rf analysis, project v2 round-trip, BOM geometry,
  schematic rendering and order-1–3 Butterworth/Chebyshev-I LP synthesis.
  CLI `filterdesk distributed` supports JSON, Touchstone and BOM export.
- Distributed SPICE netlist export for microstrip lines and stubs using
  lossless `T` elements; LTspice `.asc`/Qucs `.sch` still reject distributed
  circuits.
- Packaged-artifact `--self-test` plus Linux/Windows clean-runner acceptance
  jobs covering GUI construction, synthesis, Touchstone round-trip, BOM export
  and project round-trip.

### Changed

- **Vpk / Ipk** now use a nodal solve at the reference frequency with the actual
  source/load impedances and boundary T1/BAL1, instead of the constant-current
  rule of thumb. Resonances, mismatch and distributed line/stub elements are
  included; `TX Power` is the source available power.

### Fixed

- **Band Preset → Band Pass** now uses order 5 (odd), so a 50 Ω design no longer
  shows an ideal output transformer T1 with a 1.164:1 ratio.
- Smith chart and response plots no longer show `S11 meas` / `S22 meas` legend
  entries when no measured Touchstone file is loaded.

## v0.12.0 — 2026-10-26

### Added

- Central model-confidence registry with GUI badges, a contextual filter
  **Model status** strip, a Help → Model confidence inventory and an
  Assumptions section in Markdown/HTML build sheets.
- Cross-backend validation matrix, ngspice CI job and
  `docs/validation-matrix.md`.
- VNA measurement metadata sidecars, CLI holdout evaluation, fit-quality notes
  and a reproducible measurement protocol.
- Manual **Update spec from circuit** action: derives the target cutoff (or
  center/bandwidth) from the analyzed response while preserving family, order
  and topology; the circuit is untouched and the action is undoable.
- HF receive-band BPF wizard: band/requirements → candidate order table →
  apply → optional E24 snap, reusing the normal BOM and measurement workflow.
- Ham-radio onboarding in README/manual: five-minute path, common tasks,
  glossary, Spanish introduction and discoverability/search terms.

## v0.11.1 — 2026-10-26

### Fixed

- Balun ratios display turns and impedance explicitly (`1:7 turns / 1:49 Z`).
- `Bsat/B` is labelled correctly and winding flags are readable with a wrapped
  column, tooltip and visible legend.
- Core-loss/thermal estimates use the material complex-permeability data and
  explicit assumptions.

### Removed

- Winding diagram tab, SVG export and build-sheet sidecar. The connection
  drawings were not reliable enough for Guanella/Ruthroff/choke assemblies; the
  designer now has only **Design** and **Model** tabs.

## v0.11.0 — 2026-10-26

### Added

- Exact unequal terminations via an ideal output transformer (`T1`) with an
  SPICE/MNA-validated model.
- Classical even-order Chebyshev-I synthesis with an output transformer.
- Post-synthesis spec-compliance checks in the API, CLI (`--check`) and GUI.
- Transformer/balun/unun designer with autotransformer and isolated topologies,
  winding options (2:14 / 3:21 / 4:28), core/wire/flux checks, Lm/Lk/Rp, and
  explicit electrical-connection winding diagrams.
- Boundary `BAL1` model for ideal, Guanella, Ruthroff and choke baluns; project,
  ABCD/skrf analysis, BOM and partial SPICE/LTspice/Qucs export.
- HF power toroids: FT114/FT140/FT240/FT290-43, FT114/FT140/FT240-61,
  FT114/FT140/FT240-52, FT240/FT350-61 and FT114/FT140/FT240-31.
- Ferrite material data (μi, Bsat, Curie, complex-permeability loss points) and
  first-order core-loss/copper-loss/natural-convection thermal estimates.
- Microstrip line, quarter-wave transformer and open/short stub calculators
  with substrate presets and first-order losses.
- VNA-guided tuning with optional phase/delay, local/wide/global bounds and
  synthetic regression fixtures.
- Unified `filterdesk transformer` CLI; the separate `balun` command was
  removed. The GUI uses one transformer/balun/unun designer under **Tools**.
- Winding diagrams and build-sheet SVG sidecars.
- CI `gui-stability` timeouts, faulthandler dumps and uploaded logs.

### Changed

- Design menu is filter-only; component calculators live under **Tools**.
- Balun ratios display both turns and impedance (`1:7 turns / 1:49 Z`), and
  `Bsat/B` is labelled as a safety margin.
- Winding flags are explicit: `LF`, `SAT`, `FIT`, `HF`, `THERMAL`.

### Known limitations

- Even-order elliptic synthesis is intentionally not supported.
- The balun TLT model is behavioral; it is not a full multi-line
  Guanella/Ruthroff or EM simulation. Common-mode behavior is not represented in
  the differential two-port.
- Thermal estimates use low-flux complex permeability and a natural-convection
  approximation, not vendor high-flux curves or a thermal simulation.
- Physical wire-route drawings are not generated; only the electrical
  connection is shown.
