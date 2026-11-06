# Changelog

All notable changes to FilterDesk. The project follows a `0.x` versioning
scheme while the public CLI/GUI stabilizes.

## v0.85.0 — 2026-11-06

### Added

- **Interdigital (vias)** routed layout: alternating shorting vias, via annular
  ring/clearance DRC, copper via flashes and Excellon via holes. Edge-coupled
  remains a sketch until its physical routing topology is implemented.

## v0.84.0 — 2026-11-06

### Added

- **Routed hairpin coupled-line layout** with DRC and Gerber/drill export:
  minimum width/gap/board-margin checks, RS-274X copper/outline Gerbers and an
  Excellon drill file. Gerber export rejects non-routed edge/interdigital
  sketches.
- **Hairpin (routed)** label in the coupled-line dialog and **Export Gerber…**
  action.

### Fixed

- Hairpin resonator pitch now leaves one real edge-to-edge gap between adjacent
  resonators instead of overlapping their facing arms.

## v0.83.0 — 2026-11-06

### Changed

- Moved **Theme**, **Font size** and **Language** under
  **Edit → Preferences**.
- Font-size changes now apply immediately and rescale schematic labels and
  pyqtgraph titles, axes, ticks and legends.

## v0.82.0 — 2026-11-06

### Added

- Configurable GUI font size: **View → Font size** with **Small**, **Default**,
  **Large** and **Extra large** presets. The choice is persisted in QSettings
  and applies on the next start; schematic labels follow the selected size.

### Changed

- The project now requires **Python 3.12+**, matching the Python version used
  by the AppImage and Debian bundles. CI and development environments use 3.12
  as well.

### Fixed

- Menu bar, menus and toolbar now follow the selected font size. On Windows the
  Qt-drawn menu bar is used so the native menu font cannot mismatch the app.
- A freshly opened window is no longer marked as having unsaved changes after
  the initial automatic synthesis. Closing an untouched window no longer asks
  “Save changes before closing?”.
- Avoiding that unnecessary modal dialog also avoids the PySide6/Qt shutdown
  crash (`Fatal Python error: bool_dealloc`) that occurred when the process
  exited while the dialog was still alive on Python 3.11.
- Local Debian builds now remove stale `FilterDesk-*-<arch>.deb` files from the
  output directory before writing the new package. Set `CLEAN_OLD_DEBS=0` to
  keep old packages for comparison.

## v0.81.1 — 2026-11-05

### Added

- **AppStream metadata** for the Linux AppImage and `.deb`, with application
  name, summary, description, homepage, bug tracker, categories, keywords,
  license, developer and release version.
- Release-workflow validation with `appstreamcli` and
  `desktop-file-validate`.

### Changed

- Linux desktop entry renamed to the reverse-DNS ID
  `io.github.fsclavo.filterdesk.desktop` so it matches the AppStream component.
- AppImage AppDir now installs the desktop file, icon and metainfo in their
  standard `usr/share/...` locations, with root-level compatibility links.

## v0.81.0 — 2026-11-05

### Added

- **Component-level model vs measurement comparison.** Import a measured Q or
  ESR curve from CSV and compare it with the selected part's manufacturer
  model, with a table, plot, RMS/maximum/mean-relative error and explicit
  outside-model-range flags.
- **Tools → Component library… → Model vs measurement…** and
  `filterdesk component-compare` with optional JSON output.
- Regression tests for the comparison metrics, GUI dialog and CLI.

### Limitations

- This is a curve-level comparison, not fixture de-embedding or a calibrated
  component-level VNA workflow.
- The model is interpolated in log-log space and clamped outside its range;
  extrapolated points are excluded from the error metrics.

## v0.80.1 — 2026-11-05

### Added

- Expanded the Coilcraft 0603CS starter catalog from 5 to 18 inductance values
  (3.9 nH–270 nH), each with datasheet Q(f) points at the datasheet test
  frequency, 900 MHz and 1.7 GHz where published.
- The Q(f) models now ship directly in `STARTER_PARTS`; loading the example JSON
  is no longer required to use them.

### Changed

- Regenerated `examples/component_library_models.json` with all 23 starter parts
  and the expanded Q curves.

## v0.80.0 — 2026-11-05

### Added

- **Export stored measurements** from the Measurements dock as `.s2p` plus a
  `.s2p.vna.json` metadata sidecar, preserving VNA/calibration/reference-plane
  provenance.
- **Import Q/ESR curves from CSV** into the component library, both from
  **Tools → Component library… → Import Q/ESR curve…** and with
  `filterdesk component-curve`. The parser accepts comments, an optional header
  and SI suffixes, validates/sorts points and stores model confidence/source.
- `examples/component_curve_template.csv` and updated library/measurement
  documentation.

### Tests

- Touchstone/metadata round-trip for exported measurements.
- CSV curve parsing/validation, GUI import and CLI import.

## v0.79.1 — 2026-11-03

### Changed

- Dependency bumps: ruff 0.17.3, mypy 2.4.1, pytest 9.2.0, setup-uv 10.3.3 and
  upload-artifact v7.
- Package self-test no longer shows a Qt window; GUI display remains covered by
  the dedicated stability job.

### Reverted

- Hypothesis 6.170.13 was reverted to 6.170.5: it aborted Python natively in the
  property-based unit tests on CI.

## v0.79.0 — 2026-11-01

### Added

- `examples/component_library_models.json` with the ten starter parts.
- Coilcraft 0603CS Q(f) points from the public Document 195 datasheet.
- Murata C0G parts remain catalog-only; no ESR curve was invented.
- `examples/README.md` with import/apply instructions.

## v0.78.0 — 2026-11-01

### Added

- Optional **manufacturer Q(f)/ESR(f) curves** in component-library JSON.
- Log-log interpolation, provenance/confidence fields and GUI details.
- Native project persistence for inductor Q curves and capacitor ESR curves.
- ABCD analysis uses frequency-dependent loss; **Apply assigned parts** applies
  curves to simple L/C arms.
- ADR-048 documenting the no-vendor-SPICE policy and composite-resonator limit.

### Limitations

- Composite series/parallel resonators keep constant DCR/ESR and warn.
- Temperature, DC bias, mounting and full vendor SPICE decks are not modeled.

## v0.77.0 — 2026-11-01

### Added

- **DXF layout export** for the conceptual coupled-line sketches, with
  `TOP_COPPER` and `BOARD_OUTLINE` layers in millimetres.
- SVG/DXF export from the GUI and CLI (`--layout-output FILE.dxf`).
- ADR-047 documenting the geometry handoff and the absence of an internal EM
  solver.

### Limitations

- DXF is not a routed fabrication layout; bends, vias, copper thickness,
  discontinuities and EM validation remain external work.

## v0.76.0 — 2026-11-01

### Added

- **Conceptual layout sketches** for coupled-line BPF: edge-coupled, hairpin
  and interdigital.
- To-scale SVG export from **Design → Coupled-line BPF…** and
  `filterdesk coupled-line --layout … --layout-output …`.
- ADR-046 documenting the sketch-only scope.

### Limitations

- Hairpin/interdigital sketches use uniform average width/gap and idealized
  bends; there is no routed layout, shorting-via model, discontinuity
  compensation or EM validation.

## v0.75.0 — 2026-11-01

### Added

- **Coupled-microstrip geometry synthesis**: zero-thickness Hammerstad-Jensen
  even/odd model plus bounded multi-start width/gap fit.
- Width, gap, even/odd effective permittivity and residual in the coupled-line
  BPF table, CLI JSON and GUI.
- Substrate selection in **Design → Coupled-line BPF…** and `--substrate` in
  `filterdesk coupled-line`.
- ADR-045 documenting the geometry model and its limits.

### Limitations

- Finite copper thickness, dispersion, discontinuities, hairpin/interdigital
  layout and EM coupling are not modeled.
- Geometry is a first-pass estimate; verify with a 2-D/3-D field solver or VNA.

## v0.74.0 — 2026-11-01

### Added

- **Design → Coupled-line BPF…** and `filterdesk coupled-line` for narrowband
  parallel-coupled half-wave-resonator bandpass filters.
- Butterworth (any order 1–9) and Chebyshev-I (odd order, equal 50 Ω)
  synthesis with J-inverter values, `Z0e`/`Z0o` and coupling table.
- Ideal 2-port response and Touchstone `.s2p` export.
- ADR-044 documenting the electrical-only scope and missing layout/EM steps.

### Limitations

- Physical coupled-microstrip width/gap, hairpin/interdigital layout,
  discontinuities, dispersion and EM coupling are not synthesized.
- Results are experimental until validated with a field solver or VNA.

## v0.73.0 — 2026-11-01

### Added

- **General N-port connection:** `SParameters.connect` and `cascade` with
  wave-domain port-pair elimination, plus `network cascade/connect` CLI.
- **Circulator / isolator:** first-order ideal 3-port/2-port models with
  insertion loss, isolation and return-loss fields.
- **Tools → Circulator / isolator…** and `circulator`/`isolator` CLI export.
- ADR-043 documenting the connection model and non-reciprocal limits.

### Limitations

- Cavity filters still need a coupling-matrix/physical model and VNA/EM
  validation.
- The circulator model is not a physical ferrite-junction model.

## v0.72.0 — 2026-11-01

### Added

- **File → Import → NanoVNA sweep…** reads S11/S21 directly over USB serial.
- Serial port discovery, baud/start/stop/points controls and a scan-mask fallback.
- Measurement provenance with model, firmware, port and calibration assumption.
- ADR-042 documenting the independent protocol client and GPL-3.0 boundary.

### Limitations

- S12/S22 are not measured and are stored as zero.
- The device's active calibration is assumed; no calibration is written.
- Real NanoVNA hardware validation remains pending.

## v0.71.0 — 2026-11-01

### Added

- **File → Open example** submenu for the bundled tutorial projects.
- Bilingual example titles and status tips.

## v0.70.0 — 2026-11-01

### Added

- **Open example** in **Help → Tutorials…** for the 40 m preselector, 80 m
  100 W TX low-pass and 2 m diplexer walkthroughs.
- Bundled example projects under `src/filterdesk/assets/examples/`.

## v0.69.0 — 2026-11-01

### Added

- **Help → Tutorials…** with three bilingual guided walkthroughs:
  receiver preselector, 100 W transmitter LPF and 2 m diplexer/VNA comparison.
- Copyable CLI commands for each tutorial.

## v0.68.0 — 2026-10-30

### Added

- Structural validation harness for LTspice `.asc`, Qucs `.sch` and SPICE
  exports: headers, symbols/instances, ports, wires, flags and component refs.
- Validation matrix for LP/HP/BP/BS exports plus negative structural tests.

### Notes

- LTspice/Qucs are not installed in the build environment. True external-tool
  validation remains an explicit P0 blocker; no false validation is claimed.

## v0.67.0 — 2026-10-30

### Added

- Non-ideal sub-part models for `IdealSeriesLC`/`IdealParallelLC`: inductor
  DCR/SRF and capacitor ESR/ESL.
- Global parasitics and assigned real parts now apply to series/parallel
  resonators used by BPF, duplexer, triplexer and multiplexer branches.
- Native project persistence and component edits preserve the sub-part models.
- ADR-041 documents the extension; Brune arms remain value-only.

## v0.66.0 — 2026-10-30

### Added

- **Compare measurements…** in the system designer for 2-port VNA captures.
- Common→output and adjacent output↔output path comparison with S21/S11
  RMS/max errors.
- Explicit assumption: unused ports terminated in 50 Ω; not a true N-port VNA
  measurement.
- ADR-040 documents the method and limits.

## v0.65.0 — 2026-10-30

### Added

- **Apply assigned parts** in the designer: replace simple L/C values with the
  assigned part value, apply available DCR/SRF or ESR/ESL and reanalyze.
- Composite BPF sub-parts receive the value but report that per-subpart
  parasitic modeling is not yet available.
- BOM/report notes record applied models and warnings.
- ADR-039 documents the supported scope.

## v0.64.0 — 2026-10-30

### Added

- **Assign parts…** dialog for automatic nearest-part and manual real-part
  assignment to physical L/C components.
- Conservative auto-assignment with a configurable maximum value delta;
  unmatched parts stay unassigned.
- Manufacturer, MPN and package columns in the BOM, combined CSV, build sheets
  and HTML/PDF report.
- ADR-038 documents the BOM-metadata-only boundary.

## v0.63.0 — 2026-10-30

### Added

- System Monte-Carlo CLI flags on `diplexer`, `band-diplexer`, `duplexer`,
  `triplexer` and `multiplexer`: `--montecarlo`, `--mc-trials`, `--mc-tol`,
  `--mc-distribution`, `--mc-seed`, `--mc-max-il` and `--mc-max-oob`.
- Text and JSON yield output for system CLI runs.

## v0.62.0 — 2026-10-30

### Added

- Direct **PDF** export for the system report, alongside standalone HTML.
- Qt PDF rendering reuses the embedded report images; no external assets.
- **Export report…** file dialog now offers HTML and PDF.

## v0.61.0 — 2026-10-30

### Added

- **Export report…** in the system designer: standalone HTML with system
  metrics, embedded magnitude plot, one schematic per branch, combined BOM and
  model notes.
- `render_magnitude_png` and `render_system_report_html`; no external image
  files are required.

## v0.60.0 — 2026-10-30

### Added

- **Monte Carlo…** in the system designer: uniform/normal L/C/R tolerances,
  configurable trials, seed and yield criteria.
- `analyze_system_montecarlo` reporting yield, pass/fail counts and
  isolation/insertion/out-of-band statistics.
- ADR-037 records the tolerance-model scope.

## v0.59.0 — 2026-10-30

### Added

- **Sensitivity…** in the system designer: perturb every L/C/R by ±delta,
  reanalyze the combined network and rank the impact on isolation, insertion
  loss and out-of-band transmission.
- `analyze_system_sensitivity` service and `--sensitivity PCT` on the system
  CLI commands.
- ADR-036 records the deterministic (non-Monte-Carlo) scope.

## v0.58.0 — 2026-10-30

### Added

- Curated component catalog of real Murata C0G 0603 capacitors and Coilcraft
  0603CS inductors with catalog-level values and source links.
- **Tools → Component library…** browser with kind/search filters, details and
  copy-MPN action.
- Versioned `filterdesk.components` JSON import/export and `filterdesk
  components` CLI.
- ADR-035 records the catalog-only boundary and data provenance.

## v0.57.0 — 2026-10-30

### Added

- **Export schematic…** for the current branch as PNG, SVG or PDF.
- Printable light rendering (white background, black lines) independent of the
  application theme.
- Export button lives in the Schematic tab and follows the selected branch.

## v0.56.0 — 2026-10-30

### Added

- Versioned `.fdsys.json` system project with **Open system…** / **Save
  system…** in the designer.
- Persists bands, order/family, ripple/stopband, Z0, sweep, E-series and
  parasitics; opening rebuilds circuits, metrics and plots.
- Validated JSON schema with `format`/`version` and kind-specific checks.
- ADR-034 documents the persistence boundary.

## v0.55.0 — 2026-10-30

### Added

- Configurable **Multiplexer (N bands)** mode in the designer with an editable
  label/center/bandwidth table and add/remove controls.
- Dynamic sample table, magnitude curves and branch schematics for any band
  count; ports are common followed by bands in frequency order.
- General `filterdesk multiplexer --band LABEL:CENTER:BANDWIDTH` CLI with
  `.sNp`, repeatable `--branch-output`, BOM and E-series snap support.

## v0.54.0 — 2026-10-30

### Added

- **Parasitics…** in the system designer: finite inductor Q, DCR, Cp, SRF and
  capacitor ESR/ESL with combined-network reanalysis.
- `apply_system_parasitics` and `rebuild_system_design`; metrics, curves,
  schematic and BOM stay on the same non-ideal circuits.
- BOM notes record the applied parasitic assumptions.

## v0.53.0 — 2026-10-30

### Added

- **E-series snap** in the system designer (None/E24/E48/E96): snap every
  branch, reanalyze the combined network and update curves, metrics, schematic
  and BOM together.
- `snap_system_design` with preserved LC resonances and per-branch snap reports.
- System CLI `--bom-series` now snaps and reanalyzes, with a BOM note recording
  the series and maximum delta.

### Fixed

- Removed the mismatch between ideal-only metrics and a separately snapped BOM.

## v0.52.0 — 2026-10-30

### Added

- Combined system BOM/build sheet for diplexer, band-diplexer, duplexer and
  triplexer: system metrics, branch column, component rows, assumptions and
  CSV/Markdown/HTML output.
- **Export build sheet…** in the designer and `--export-build-sheet`,
  `--bom-series`, `--bom-group` on the four system CLI commands.

## v0.51.0 — 2026-10-30

### Added

- **Schematic** tab in the diplexer / multiplexer designer, reusing the main
  filter designer's ladder view with one sub-tab per branch (Low/High, TX/RX or
  Low/Mid/High).

### Fixed

- Mode-specific port summaries (LPF/HPF, duplexer, triplexer) and the generic
  “combined network” wording in the model note.
- Schematic views fit their branch and hide scrollbars when shown in the
  designer tabs.

## v0.50.0 — 2026-10-30

### Added

- **Magnitude** tab in the diplexer / multiplexer designer: log-frequency,
  dB S-parameter curves for output paths, input return loss and worst
  output-to-output isolation, with a −160 dB plot floor.

### Fixed

- The band-specific input rows no longer reserve the height of the tallest mode,
  removing the large blank gap in LPF+HPF and BPF+BPF modes.
- The **Export mid .s2p…** button is hidden outside the triplexer mode, including
  at initial dialog construction.
- Common input fields are paired into two-column rows for a more compact dialog.

## v0.49.0 — 2026-10-30

### Added

- Multi-band BPF multiplexer service with labelled bands, per-band insertion
  loss, worst out-of-band transmission, return loss and adjacent crossovers.
- Three-band **Triplexer** mode in the GUI and `filterdesk triplexer` CLI.
  Ports: **1 = common, 2 = low, 3 = mid, 4 = high**.
- ADR-031 documents the general multiplexer model.

## v0.48.0 — 2026-10-30

### Added

- LC TX/RX duplexer with fixed ports **1 = antenna, 2 = TX, 3 = RX**,
  insertion/return-loss metrics and TX↔RX isolation in both bands.
- Automatic order search to meet a minimum isolation target; reports clearly
  when the target is not met.
- `filterdesk duplexer` CLI and a **Duplexer TX/RX** mode in the GUI.
- ADR-030 documents the model and its limits.

## v0.47.0 — 2026-10-30

### Added

- BPF+BPF diplexer with independent center/bandwidth per branch, overlap and
  sweep-coverage validation, and the same combined 3-port metrics.
- `filterdesk band-diplexer` CLI and a **BPF + BPF** mode in
  **Tools → Diplexer designer…**.
- ADR-029 documents the extension.

## v0.46.0 — 2026-10-30

### Added

- **Tools → Diplexer LPF+HPF…** GUI: branch requirements, combined 3-port
  metrics, a 21-point response sample table and `.s3p`/branch `.s2p` exports.
- English/Spanish strings for the diplexer dialog.

## v0.45.0 — 2026-10-30

### Added

- LPF+HPF diplexer service and `filterdesk diplexer` command. The combined
  3-port uses port 1 as common, port 2 as low-pass and port 3 as high-pass.
- Passband insertion loss, out-of-band transmission, input return loss and
  crossover reporting, plus optional per-branch `.s2p` exports.
- ADR-028 documents the v1 model and its limits.

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
