# QA matrix

This is the practical QA view: what is tested, how, and what is still a known
limit. It complements the model-confidence registry and the validation matrix.

## Numerical QA

| Area | Evidence | Status / limit |
| --- | --- | --- |
| LP/HP synthesis (Butterworth, Chebyshev I/II, elliptic) | Independent SciPy analog-prototype oracle in `test_numerical_oracle.py`, LP and HP, orders 3/5 | Strong magnitude oracle; BP/BS use the existing cross-backend matrix |
| Synthesis component values | Golden fixtures (`test_golden_synthesis.py`, `test_golden_transformers.py`) | Several representative cases, not every order/family |
| ABCD vs scikit-rf | `test_validation_matrix.py`, `test_distributed.py`, `test_balun.py` | `rtol=1e-8` for lumped; distributed has its own tolerances |
| SPICE/MNA | Independent MNA parser, ngspice CI, transformer and distributed line tests | LTspice/Qucs external opening is still manual |
| Stress | Analytic series-resistor, BPF 100 W, finite-Q, T1, distributed, edge cases | Linear frequency-domain model; no thermal/nonlinear stress |
| Balun/TLT | Guanella multi-line, Ruthroff 1:4, choke CM sweep, DCR/option persistence | No full mixed-mode 3/4-port or EM model |
| Microstrip/stub/calculators | Unit tests and boundary cases | First-order models; no field solver |
| Distributed LP | Analytic order 1–3; gated numerical order 4–5 | LP only, no dispersion/discontinuities/hardware |
| Monte Carlo/optimization | Unit/property tests | Model-limited by the underlying circuit |

## Diagram / export QA

| Artifact | Evidence | Status / limit |
| --- | --- | --- |
| Schematic symbols | `test_visual_qa.py`: group IDs, scene bounds, pairwise non-overlap, labels, rendered non-background pixels | Semantic geometry QA; no pixel-golden screenshot |
| Distributed schematic | `test_distributed_gui.py` group IDs; included in the same scene geometry checks when present | Basic symbol/label coverage |
| Magnitude/phase/impedance plots | `test_visual_qa.py`: SVG contains axes, legend and >30 polylines; data/legend tests in `test_gui_smoke.py` | No clipping/overlap visual regression across platforms |
| Smith chart export | `test_smith_export.py` + `test_visual_qa.py`: SVG has title, S11/S22, axes and >20 paths | No pixel-golden comparison |
| Plot SVG export | `test_svg_export_patch.py` and `test_visual_qa.py` | Format/structure only |
| Schematic export / Qucs | String/structure tests | No external visual check in Qucs |
| BOM/Markdown/HTML | `test_build_sheet.py` content/structure | No browser print layout snapshot |
| Packaged GUI | `--self-test` and package-acceptance jobs | Headless startup; physical Windows visual check remains manual |

The visual-render checks use a Linux offscreen baseline. They are skipped on
Windows because Qt image/font rasterization differs; Windows coverage uses the
packaged `--self-test` and package-acceptance jobs instead.

## Known QA gaps

- No image-diff/SSIM visual regression yet; diagram QA is structural/semantic.
- BP/BS have cross-backend coverage but do not yet have a SciPy independent oracle.
- No hardware VNA validation for baluns, distributed filters or thermal estimates.
- LTspice/Qucs external file opening is manual.
- Full mixed-mode 3/4-port and EM modeling are out of scope.

## Commands

```bash
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/lint-imports
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

Focused QA:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
  tests/unit/test_numerical_oracle.py \
  tests/unit/test_visual_qa.py \
  tests/unit/test_validation_matrix.py \
  tests/unit/test_spice_mna.py
```
