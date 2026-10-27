# Validation matrix

This document records the evidence behind the **Model confidence** statuses. It
is not a claim that every model is validated on hardware.

## Automated cases

`tests/unit/test_validation_matrix.py` covers these synthesis paths:

| Case | Family / response | Order | Terminations |
| --- | --- | ---: | --- |
| `butter_lp_asymmetric` | Butterworth LP | 3 | 50 → 75 Ω |
| `butter_hp` | Butterworth HP | 4 | 50 → 50 Ω |
| `cheby1_lp_even` | Chebyshev I LP | 4 | 50 → 50 Ω |
| `cheby1_bp` | Chebyshev I BP | 4 | 50 → 50 Ω |
| `cheby1_bs` | Chebyshev I BS | 4 | 50 → 50 Ω |
| `cheby2_lp` | Chebyshev II LP | 5 | 50 → 50 Ω |
| `elliptic_lp` | Elliptic LP | 5 | 50 → 50 Ω |
| `bessel_lp` | Bessel LP | 5 | 50 → 50 Ω |
| `gaussian_lp` | Gaussian LP | 5 | 50 → 50 Ω |
| `legendre_lp` | Legendre LP | 5 | 50 → 50 Ω |

Checks per case:

- ABCD and scikit-rf run on the same 161-point logarithmic sweep.
- `S11` and `S21` agree with `rtol=1e-8`, `atol=1e-8`.
- All results are finite.
- Passivity: `|S11|² + |S21|² <= 1 + 1e-6`.
- Asymmetric ports produce an output transformer.

## Distributed microstrip v1

`tests/unit/test_distributed.py` covers:

- matched quarter-wave line ABCD against the analytic response;
- open/short stub input impedance at 45°;
- ABCD vs scikit-rf for a synthesized distributed circuit (`rtol=1e-7`);
- project v2 round-trip and BOM geometry columns;
- Butterworth order 3 vs the lumped response: passband `|ΔS21| <= 1 dB` and
  stopband no more than 6 dB worse at `2 f_c`;
- CLI JSON/Touchstone/BOM export.

The synthesis is limited to low-pass Butterworth/Chebyshev-I, order ≤ 5.
Orders 1–3 use the analytical stepped-impedance formulas; orders 4–5 use a
bounded numerical fit and are accepted only with passband error ≤ 1.5 dB and
stopband penalty ≤ 6 dB at `2 f_c`. It is marked **experimental**; ideal TEM, no
dispersion/discontinuities/radiation, and no hardware validation yet.

## Balun / TLT

`tests/unit/test_balun.py` covers:

- integer 1:N² Guanella line counts and zero-length reduction to the ideal
  transformer;
- the explicit parallel-input/series-output ABCD against the line formula;
- 1:4 Ruthroff zero-length reduction and bootstrap reciprocity;
- ABCD/scikit-rf agreement and ladder/project round-trips;
- choke common-mode impedance/attenuation and a five-point frequency sweep;
- exact open/short/resonant arm edge cases without NaN or divide warnings;
- winding option/DCR persistence and BOM propagation;
- non-1:4 limitations.

Guanella multi-line is still experimental; Ruthroff and common-mode behavior
are not full multi-line/EM models.

## Power stress

`tests/unit/test_stress.py` validates the nodal stress solve:

- series-resistor reference against the analytic source/load solution;
- 40 m BPF at center: 100 W gives ~100 Vpk and ~2 A peak, including near-short
  series resonators and near-open shunt tanks;
- finite-Q circuits, distributed line/stub circuits and a boundary T1;
- CLI/GUI wiring and error cases.

`TX Power` is the source **available** power. The analysis is linear and
frequency-domain; it does not model thermal drift or nonlinear saturation.

## SPICE validation

- **Independent MNA test:** parses the exported SPICE E/F transformer netlist and
  compares S21 with ABCD within `1e-8`.
- **CI with ngspice:** the `spice-validation` job installs ngspice and runs the
  MNA/export tests, including a distributed quarter-wave line exported as a
  lossless `T` element.
- **LTspice/Qucs:** syntax is tested, but external tool validation remains a
  manual release checklist item; Qucs `Tr` ratio orientation is still to be
  confirmed.

## Golden cases

Existing golden fixtures cover component values, response checkpoints and BOM
rows for equal and unequal terminations, even-order Chebyshev-I and transformer
outputs. Tolerances are recorded in each `expected_*.json`.

## Installed packages

Release builds run the version and headless `synthesize` smoke tests in CI.
The `package-acceptance-*` jobs now run the packaged `--self-test` (GUI
construction, synthesis, Touchstone round-trip, BOM and project round-trip) for
the Linux bundle/AppImage and the installed Windows app. A final visual check of
the installer shortcut and main window on a physical Windows desktop remains a
manual release step.

## VNA holdout

Real VNA captures are kept as holdout data, not used to fit the algorithm. The
protocol must record calibration, reference plane, cables/connectors,
terminations and fixture metadata. Magnitude-only data may not uniquely identify
all components; phase/delay and calibration remain part of the fit.

## Gaps

- High-flux ferrite loss and temperature rise need vendor/measurement data.
- Distributed synthesis is limited to low-order LP and has no hardware
  validation; stubs are manual elements, not a synthesized topology.
- Guanella/Ruthroff TLT models remain behavioral.
- LTspice/Qucs external checks are manual.
