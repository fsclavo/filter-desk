# FilterDesk — Master Backlog

**Purpose:** single actionable list of every outstanding item so development can be
resumed without re-reading the whole blueprint per phase.  
**Scope:** (A) deferred items from completed phases 0–5b, (B) quality / CI debt,
(C) roadmap phases 6–11.  
**Status:** living document — check boxes as work lands.  
**Date:** 2026-10-15 · **App version:** 0.6.2

Legend: **P0** blocks correctness/CI · **P1** completes the value of finished
phases · **P2** future roadmap. Effort: **S** ≤ ½ day · **M** 1–3 days · **L** > 3 days.

---

## A. Quality / CI debt (P0) — **DONE (2026-10-15)**

| ID | Task | Resolution |
| --- | --- | --- |
| Q1 | Make `mypy` (strict) green — **49 errors** | Fixed in `__main__.py`, `spec_panel.py`, `cauer_extract.py`, `component_table.py`, `pyqtgraph_patches.py`; mypy now clean (61 files) |
| Q2 | `scipy` `import-untyped` | Added `scipy.*` to `[tool.mypy.overrides]` (matches existing skrf/Qt pattern) |
| Q3 | Duplicate dev deps | Removed `[project.optional-dependencies].dev`; `[dependency-groups].dev` is now the single source |
| Q4 | Reproducible builds | Added `uv.lock`; CI (`.github/workflows/test.yml`) and README now use `uv sync --frozen` / `uv run` |

### Q1 breakdown — mypy error map

| File | Errors | Cause |
| --- | --- | --- |
| `__main__.py` | 21 | `result` variable reused between `synthesize()` and `estimate-order`, so `SynthesisResult` is inferred where `OrderEstimateResult` is returned (lines 527–557) |
| `gui/panels/spec_panel.py` | 14 | `FilterSpec(**dict[str, object])` unpacking (lines 373, 377) |
| `synthesis/cauer_extract.py` | 5 | `float`/`float64` reassignment; `Any` returns (lines 66, 86, 97, 268) |
| `synthesis/families/chebyshev_ii.py` | 1 (+2 notes) | missing `scipy` stubs |
| `synthesis/families/elliptic.py` | 1 | missing `scipy` stubs |
| `synthesis/order_estimate.py` | 1 | missing `scipy` stubs |
| `gui/panels/component_table.py` | 4 | `str` assigned to `float`; `_add_row` arg type (lines 98–103) |
| `gui/pyqtgraph_patches.py` | 2 | monkey-patch attr `_filterdesk_svg_qt6_patch` (lines 66, 72) |

### A2 — Repo / process — **DONE (2026-10-15)**

- [x] `git init` (branch `main`) + baseline commit `4a32d65`.

---

## B. Deferred from completed phases 0–5b (P1) — **closed (2026-10-15, ADR-014)**

### B1. Synthesis / math

| ID | Item | Detail / limitation | Refs | Status |
| --- | --- | --- | --- | --- |
| B1.1 | **Even-order Chebyshev Type I** | Modified even-order prototype for equal terminations (reflection zero relocated to DC): exact continued-fraction Darlington synthesis, symmetric positive arms, least-squares fallback at high order. `docs/math/chebyshev_type_i.md` §5 | — | **DONE (2026-10-15)** |
| B1.2 | **True asymmetric \(Z_S \neq Z_L\)** | Only geometric-mean scaling \(Z_0=\sqrt{Z_S Z_L}\); large ratios may not meet equiripple shape at both ports. Needs Norton / minimum-inductance / ratio tables | ADR-011, ADR-014 | **Decided (accepted)** |
| B1.3 | **M-derived BP/BS** | Shipped in v0.5.5 via generic LP→BP/BS finite-zero transform (`test_m_derived_bp_smoke`); ADR-013 | `docs/phase5b/BPBS_FINITE_ZERO_STATUS.md` | **DONE (2026-10-15)** |
| B1.4 | **Order estimation — BP/BS** | `estimate_minimum_order` takes band edges (BP/BS via scipy 2-element wp/ws); CLI `estimate-order --pass-band LO HI --stop-band LO HI`; GUI Estimate N still LP/HP-only | `docs/phase5b/ORDER_ESTIMATE_STATUS.md` | **DONE (2026-10-15)** |
| B1.5 | **Order estimation — other families** | Bessel/Gaussian/Legendre via numeric prototype search (LP/HP); Constant-K/M-derived still unsupported | ADR-014 | **DONE (2026-10-15)** |
| B1.6 | **Even-order elliptic** | Equal-R is an |S21| fit approximation, not exact classic theory (transformer-free) | ADR-013, ADR-014 | **Decided (accepted)** |
| B1.7 | **Order cap by tables** | Bessel/Gaussian 1–10, Legendre 2–9; caps kept intentional (tables verified) — extension needs prototype-generation research | ADR-014 | **Decided (keep caps)** |

### B2. Analysis

| ID | Item | Detail | Refs |
| --- | --- | --- | --- |
| B2.1 | **skrf analyzer unequal-Z** | `ScikitRFAnalyzer` cascades at \(z_0=\sqrt{Z_S Z_L}\) then renormalizes to \([Z_S, Z_L]\); matches ABCD <1e-9 | ADR-014 · **DONE (2026-10-15)** |

### B3. GUI / UX

| ID | Item | Detail | Status |
| --- | --- | --- | --- |
| B3.1 | **Schematic topology editor** | Select an element, then **Design → Component**: edit value, convert L↔C (reactance-preserving), insert series/shunt L/C before/after, delete; right-click shortcut too; full undo/redo — `PHASE3_STATUS.md`, blueprint §23/§35 | **DONE (2026-10-15)** |
| B3.2 | **Smith limit regions** | Constant-\|Γ\| limits (`s11_mag` / `s22_mag`) drawn on the Smith chart and evaluated in pass/fail | **DONE (2026-10-15)** |
| B3.3 | **Optimizer ↔ limits wiring** | `optimization/` minimizes per-sample limit residuals (`LimitRegion[]`); CLI `optimize` + GUI **Design → Optimize to limits…** | **DONE (2026-10-15)** |

### B4. Interop / IO

| ID | Item | Detail | Status |
| --- | --- | --- | --- |
| B4.1 | **Touchstone reader (import)** | `io/touchstone/reader.py` (`TouchstoneData`/`read_touchstone`/`parse_touchstone`); HZ..GHZ, RI/MA/DB, `R z0`, comments, wrapped records, `.s1p`/`.sNp` port inference; GUI **File → Import Touchstone…** (worker + `DesignSession.set_measured`) and CLI `touchstone-info` — blueprint FR-I2, §27 | **DONE (2026-10-15)** |
| B4.2 | **`services.compare`** | `services/compare.py` (`CompareResult`/`compare_results`): overlap-band align + S21/S11 dB RMS & max error; GUI dashed measured overlay on mag/VSWR/Smith with **View → Show measured overlay** toggle; CLI `compare SIM MEAS [--json]` | **DONE (2026-10-15)** |
| B4.3 | **`plotting/protocol.py` `PlotBackend`** | Static-export abstraction materialized: `PlotBackend` protocol + `MatplotlibBackend` (via `get_plot_backend()`); CLI/GUI export route through it. Interactive GUI keeps PyQtGraph directly | **DONE (2026-10-15)** — ADR-014 |

---

## C. Roadmap — remaining phases (P2)

### Phase 6 — Practical components (Q, ESR, parasitics, tolerances, E-series) — **DONE

- [x] **E-series module** `components_std/e_series.py` (E6/E12/E24/E48/E96) + `snap.py` — FR-P1 (engine + CLI `snap`)
- [x] Snap strategies: independent / L-only / C-only / preserve LC resonances — FR-P1
- [x] **Non-ideal element layers** (composition, blueprint §22): `NonIdealInductor` (series R / Q@f, Cpar), `NonIdealCapacitor` (ESR, ESL) — FR-P2
- [x] Extend ABCD analyzer for lossy/parasitic elements — FR-P2
- [x] Apply parasitics end-to-end: `session.apply_nonideal`, CLI `analyze` flags, GUI **Design → Apply parasitics / Q…** (undo/redo) — FR-P2
- [x] GUI: **Design → Snap to E-series…** dialog (series + strategy) with undo/redo — FR-P1
- [x] GUI: non-ideal fields in component table (Parasitic column + per-part Edit parasitics / Q) — FR-P2
- [x] Tolerances: Monte-Carlo / worst-case passband analysis — `montecarlo/` engine + stats + CLI `montecarlo` (FR-P3 core)
- [x] Golden tests for finite-Q and E24-snapped cases — `tests/unit/test_phase6_golden.py` + `tests/golden/{cheby1_lp_n5_e24_snapped,butterworth_lp_n5_q100}`
- [x] Manual library R / L / C (core RLC) in the schematic — **Design → Component → Insert** series/shunt R/L/C; R edits/tunes/optimizes/MC/SPICE. (jX deferred — no SPICE mapping.)

### Phase 7 — Interactive tuning + optimization + limits — **DONE (2026-10-15)**

- [x] `services/retune.py` — retune cutoff/center/bandwidth/Z + `scale_response` (redesign on tune) — FR-U2 core
- [x] Per-part continuous tune (relative step per component, `nudge_value`; GUI Tune ±step + Ctrl+]/Ctrl+[) — FR-U2
- [x] `optimization/` package: `objectives.py`, `constraints.py`, `solvers.py`, `variables.py` — FR-P4
- [x] Solver: limit-residual least squares + bounded Nelder–Mead (SciPy) — FR-P4
- [x] Wire optimizer to `LimitRegion[]` (B3.3) — CLI `optimize` + GUI **Design → Optimize to limits…**
- [x] Background workers + debounce + cancel-stale for tune — NFR-4 (80 ms debounce + analyze-thread cancel)
- [x] GUI **Design → Scale response…** action (undo/redo) — FR-U2
- [x] GUI **Design → Optimize to limits…** action (undo/redo) — FR-P4
- [x] GUI **Design → Component → Tune ±step / Set tune step…**, toolbar buttons + shortcuts — FR-U2
- [ ] (optional polish) interactive marker-driven retune — see §D

### Phase 8 — Monte Carlo — **DONE (2026-10-15)**

- [x] `montecarlo/` package: `engine.py` (`run_monte_carlo`), `stats.py` (`wilson_interval`) — FR-P3 core
- [x] Uniform ±tol (then Normal) — FR-P3 core
- [x] Envelopes, yield vs limits, percentiles — FR-P3 core
- [x] Per-element tolerance/distribution (`ElementTolerance`, `MonteCarloConfig.overrides`; session + CLI `--element-tol` + GUI Set tolerance… / table Tol column)
- [x] Performance: float32 trial buffer + `progress(done,total)`; 10k×512 ≈ 5 s (NFR-5) — GUI worker emits progress
- [x] GUI: MC run dialog (`MonteCarloDialog`) + envelope overlay (View toggle)

### Phase 9 — `.lct` file I/O (best-effort)

- [ ] Collect ≥10 user-owned `.lct` samples (`tests/lct_roundtrip/corpus/`, private) — `LCT_INVESTIGATION_PLAN.md`
- [ ] Binary vs text classification + differential analysis
- [ ] `io/lct/{parser,exporter,model_mapper}.py` with `LctDocument` DTO ≠ domain
- [ ] `CompatibilityReport` (mapped / dropped / approximated); `docs/lct_compatibility.md`
- [ ] Semantic round-trip tests on redistributable corpus only
- [ ] Go/no-go decision per plan table

### Phase 10 — Broader export + measured S2P compare

- [x] **LTspice/SPICE netlist export** — `io/spice` (`spice_netlist`/`write_spice_netlist`) + CLI `analyze --export-spice` + GUI **File → Export SPICE netlist…**
- [ ] LTspice `.asc` *schematic* (needs a geometry/layout model; netlist is the portable path)
- [ ] Qucs `.sch` exporter
- [x] CSV / two-column DAT trace export — `io/csv_export` + CLI `analyze --export-csv` / `to-csv` + GUI **File → Export CSV…**
- [x] Touchstone reader import + `.s1p` (B4.1 — `touchstone-info` CLI + GUI import)
- [x] Measured-vs-simulated overlay UX (`services.compare`, B4.2)

### Phase 11 — Packaging & Windows

- [x] PyInstaller onedir build (`packaging/filterdesk.spec`) + smoke test (`FilterDesk --version`, CLI synth/analyze/MC) — validated locally
- [x] Linux portable `tar.gz` + Windows onedir ZIP (`.github/workflows/release.yml`)
- [x] Linux AppImage — best-effort job (`continue-on-error`) + `packaging/appimage/build_appimage.sh`
- [x] glibc baseline documented — Ubuntu 22.04 / glibc 2.35 (`docs/packaging.md`)
- [x] `release.yml` CI on tags `v*` + GitHub Release with artifacts
- [x] Qt LGPL-3 compliance artifacts — `packaging/NOTICE-third-party.md` + `collect_qt_licenses.py` (LGPL/GPL texts into `licenses/`)

---

## D. Cross-cutting / open questions (when relevant) — **closed (2026-10-16, ADR-015)**

- [x] **pytest-qt** — adopted for GUI interaction tests (`import-linter` + `pytest-qt` in dev deps)
- [x] Interactive marker-driven retune — bind a marker to a landmark (`cutoff` / `f_center` / `bandwidth`) in the Markers dock and drag to redesign (single undo step)
- [x] **Global optimizers** — `differential_evolution` + `dual_annealing` added (never worse than nominal)
- [x] **Project extension** — `.filterdesk.json` (plain JSON), no `.fdsk` container
- [x] Native Rust/C acceleration — not pursued (ABCD path sufficient: 10k MC ≈ 5 s)
- [x] Product naming — **FilterDesk** (binary `filterdesk`); no trademark registration planned
- [x] Import-linter enforcement of layer rules in CI — 5 contracts in `pyproject.toml` + CI step

---

## E. Suggested order to resume

1. **Q1–Q4** — green CI + reproducible lockfile (unblocks everything).
2. **A2** — `git init` + baseline commit.
3. **B1–B4** — close the cheap, high-value gaps (Touchstone reader, BP/BS &
   family order-estimate, M-derived BP/BS, schematic editor).
4. **Phase 6** — practical components (largest user-visible value next).
5. Phases 7 → 11 in order.

Each phase exit requires: docs update, golden expansion, risk review, no
dependency-rule violations (blueprint §35).
