# FilterDesk — Master Backlog

**Purpose:** single actionable list of every outstanding item so development can be
resumed without re-reading the whole blueprint per phase.  
**Scope:** (A) deferred items from completed phases 0–5b, (B) quality / CI debt,
(C) roadmap phases 6–11.  
**Status:** living document — check boxes as work lands.  
**Date:** 2026-10-15 · **App version:** 0.5.11

Legend: **P0** blocks correctness/CI · **P1** completes the value of finished
phases · **P2** future roadmap. Effort: **S** ≤ ½ day · **M** 1–3 days · **L** > 3 days.

---

## A. Quality / CI debt (P0)

| ID | Task | Refs | Effort |
| --- | --- | --- | --- |
| Q1 | Make `mypy` (strict) green — **49 errors in 8 files**; CI `.github/workflows/test.yml` currently fails | see table below | M |
| Q2 | Add `scipy-stubs` to dev deps *or* add `scipy.*` to `[tool.mypy.overrides]` (resolves 6 `import-untyped`) | `pyproject.toml` | S |
| Q3 | De-duplicate dev deps: `[project.optional-dependencies].dev` and `[dependency-groups].dev` list the same tools | `pyproject.toml:19,60` | S |
| Q4 | Add `uv.lock` for reproducible builds (blueprint NFR-6) and switch CI to `uv sync --frozen` | blueprint §10,§30 | S |

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

### A2 — Repo / process (deferred by user request)

- [ ] `git init` + baseline commit (currently **not** a git repository).

---

## B. Deferred from completed phases 0–5b (P1)

### B1. Synthesis / math

| ID | Item | Detail / limitation | Refs |
| --- | --- | --- | --- |
| B1.1 | **Even-order Chebyshev Type I** | Still assumes \(g_{n+1}=1\); genuine equal-ripple asymmetric termination not handled | `docs/math/chebyshev_type_i.md` §7, ADR-011 |
| B1.2 | **True asymmetric \(Z_S \neq Z_L\)** | Only geometric-mean scaling \(Z_0=\sqrt{Z_S Z_L}\); large ratios may not meet equiripple shape at both ports. Needs Norton / minimum-inductance / ratio tables | ADR-011, `docs/math/transforms.md` §3 |
| B1.3 | **M-derived BP/BS** | Only LP/HP implemented | `docs/math/constant_k_m_derived.md`, ADR-013 |
| B1.4 | **Order estimation — BP/BS** | `estimate_minimum_order` supports LP/HP only | `docs/phase5b/ORDER_ESTIMATE_STATUS.md` |
| B1.5 | **Order estimation — other families** | Bessel/Gaussian/Legendre/Constant-K/M-derived unsupported (no classical formula) | `docs/phase5b/ORDER_ESTIMATE_STATUS.md` |
| B1.6 | **Even-order elliptic** | Equal-R is an |S21| fit approximation, not exact classic theory (transformer-free) | ADR-013, `EVEN_ORDER_CAUER_STATUS.md` |
| B1.7 | **Order cap by tables** | Bessel/Gaussian 1–10, Legendre 2–9; decide closed-form/root extension | `domain/specs.py:141-150` |

### B2. Analysis

| ID | Item | Detail | Refs |
| --- | --- | --- | --- |
| B2.1 | **skrf analyzer unequal-Z** | `ScikitRFAnalyzer` assumes equal port \(Z_0\); unequal-Z only works via ABCD | ADR-011, `PHASE2_STATUS`/`PHASE4_STATUS` |

### B3. GUI / UX

| ID | Item | Detail | Refs |
| --- | --- | --- | --- |
| B3.1 | **Schematic topology editor** | View is read-only; no insert / delete / change element type (largest deferred UX item) | `PHASE3_STATUS.md`, `PHASE3_UX_STATUS.md`, blueprint §23/§35 |
| B3.2 | **Smith limit regions** | Limits not drawn/evaluated on the Smith chart | `SMITH_STATUS.md` |
| B3.3 | **Optimizer ↔ limits wiring** | Limits exist but nothing consumes them yet | `PHASE3_UX_STATUS.md` (→ Phase 7) |

### B4. Interop / IO

| ID | Item | Detail | Refs |
| --- | --- | --- | --- |
| B4.1 | **Touchstone reader (import)** | Only `io/touchstone/writer.py` exists; FR-I2 required import + export. Add `reader.py` + worker | blueprint FR-I2, §27 |
| B4.2 | **`services.compare`** | Compare simulated vs measured `AnalysisResult` (overlay) | blueprint §27, Phase 10 |
| B4.3 | **`plotting/protocol.py` `PlotBackend`** | GUI imports PyQtGraph directly; plotting backend abstraction never materialized | blueprint §24 |

---

## C. Roadmap — remaining phases (P2)

### Phase 6 — Practical components (Q, ESR, parasitics, tolerances, E-series)

- [ ] **E-series module** `components_std/e_series.py` + `snap.py` (E6–E96) — FR-P1
- [ ] Snap strategies: independent / L-only / C-only / preserve LC resonances — FR-P1
- [ ] **Non-ideal element layers** (composition, blueprint §22): `NonIdealInductor` (series R / Q@f, Cpar), `NonIdealCapacitor` (ESR, ESL) — FR-P2
- [ ] Extend ABCD analyzer for lossy/parasitic elements
- [ ] GUI: E-series snap action; non-ideal fields in component table
- [ ] Golden tests for finite-Q and E24-snapped cases (blueprint §29 items 9–10)
- [ ] Manual library R / L / C / jX (core RLC) in schematic library (blueprint §7)

### Phase 7 — Interactive tuning + optimization + limits

- [ ] `services/retune.py` — tune part / width / center (redesign on tune) — FR-U2
- [ ] `optimization/` package: `objectives.py`, `constraints.py`, `solvers.py` — FR-P4
- [ ] Solver: limit-residual least squares + bounded Nelder–Mead (SciPy); global methods later — blueprint §20
- [ ] Wire optimizer to `LimitRegion[]` (B3.3)
- [ ] Background workers + debounce + cancel stale jobs — NFR-4
- [ ] GUI Tune/Optimize toolbar actions; undo integration

### Phase 8 — Monte Carlo

- [ ] `montecarlo/` package: `engine.py`, `stats.py` — FR-P3
- [ ] Uniform ±tol first (then Normal); per-element tolerance/distribution on instances
- [ ] Envelopes, yield vs limits, percentiles, optional thin sample traces
- [ ] Performance: reuse freq grid; 1k usable, 10k with progress — NFR-5
- [ ] GUI: MC run dialog + envelope overlay

### Phase 9 — ELSIE `.lct` I/O (best-effort)

- [ ] Collect ≥10 user-owned `.lct` samples (`tests/lct_roundtrip/corpus/`, private) — `LCT_INVESTIGATION_PLAN.md`
- [ ] Binary vs text classification + differential analysis
- [ ] `io/lct/{parser,exporter,model_mapper}.py` with `LctDocument` DTO ≠ domain
- [ ] `CompatibilityReport` (mapped / dropped / approximated); `docs/lct_compatibility.md`
- [ ] Semantic round-trip tests on redistributable corpus only
- [ ] Go/no-go decision per plan table

### Phase 10 — Broader export + measured S2P compare

- [ ] LTspice `.asc` exporter (from `Circuit` + schematic layout)
- [ ] Qucs `.sch` exporter
- [ ] CSV / two-column DAT trace export
- [ ] Touchstone Type I/II + `.s1p` (finish B4.1)
- [ ] Measured-vs-simulated overlay UX (`services.compare`, B4.2)

### Phase 11 — Packaging & Windows

- [ ] PyInstaller onedir build + smoke test (`filterdesk --version`, headless synth)
- [ ] Linux AppImage + portable `tar.gz` (appimagetool); resolve Qt platform plugin path (blueprint §31 **Open**)
- [ ] glibc baseline documented (Ubuntu 22.04 / manylinux)
- [ ] `release.yml` CI; Windows onedir ZIP (`windows-latest`) — blueprint §32
- [ ] Qt LGPL-3 compliance artifacts (notices + source offer) — ADR-002

---

## D. Cross-cutting / open questions (when relevant)

- **pytest-qt** investment timing (GUI interaction tests) — blueprint §37.12
- **Project extension** `.filterdesk.json` vs compressed `.fdsk` — §37.9
- Native Rust/C acceleration for MC *only if* ABCD Python insufficient — §37.13
- Product naming / trademark (avoid ELSIE/Tonne marks) — §37.14
- Import-linter enforcement of layer rules in CI (blueprint §12, §28)

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
