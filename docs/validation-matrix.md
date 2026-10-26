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

## SPICE validation

- **Independent MNA test:** parses the exported SPICE E/F transformer netlist and
  compares S21 with ABCD within `1e-8`.
- **CI with ngspice:** the `spice-validation` job installs ngspice and runs the
  MNA/export tests.
- **LTspice/Qucs:** syntax is tested, but external tool validation remains a
  manual release checklist item; Qucs `Tr` ratio orientation is still to be
  confirmed.

## Golden cases

Existing golden fixtures cover component values, response checkpoints and BOM
rows for equal and unequal terminations, even-order Chebyshev-I and transformer
outputs. Tolerances are recorded in each `expected_*.json`.

## Installed packages

Release builds run the version and headless `synthesize` smoke tests in CI. A
manual acceptance pass still checks the AppImage and Windows installer on a
clean machine, including GUI startup, one synthesis, one Touchstone import and
one BOM export.

## VNA holdout

Real VNA captures are kept as holdout data, not used to fit the algorithm. The
protocol must record calibration, reference plane, cables/connectors,
terminations and fixture metadata. Magnitude-only data may not uniquely identify
all components; phase/delay and calibration remain part of the fit.

## Gaps

- High-flux ferrite loss and temperature rise need vendor/measurement data.
- Distributed elements are not integrated in the netlist.
- Guanella/Ruthroff TLT models remain behavioral.
- LTspice/Qucs external checks are manual.
