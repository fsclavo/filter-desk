# Changelog

All notable changes to FilterDesk. The project follows a `0.x` versioning
scheme while the public CLI/GUI stabilizes.

## v0.13.0 — 2026-10-26

### Added

- **File → Recent projects** keeps up to ten recently opened/saved projects,
  removes missing entries and offers a clear-list action.
- Experimental distributed microstrip v1: canonical microstrip line/stub
  elements, ABCD/scikit-rf analysis, project v2 round-trip, BOM geometry,
  schematic rendering and order-1–3 Butterworth/Chebyshev-I LP synthesis.
  CLI `filterdesk distributed` supports JSON, Touchstone and BOM export.
- Packaged-artifact `--self-test` plus Linux/Windows clean-runner acceptance
  jobs covering GUI construction, synthesis, Touchstone round-trip, BOM export
  and project round-trip.

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
