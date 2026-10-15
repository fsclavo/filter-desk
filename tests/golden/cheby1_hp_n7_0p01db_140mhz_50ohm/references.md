# References — cheby1_hp_n7_0p01db_140mhz_50ohm

## Specification

- Family: Chebyshev Type I
- Order: 7 (odd → g_{n+1} = 1)
- Ripple: A_p = 0.01 dB
- Response: high-pass
- f_c = 140 MHz at **ripple edge** (ADR-006)
- Z_S = Z_L = 50 Ω
- Topology: `ladder_hp_series_c_input` (ADR-009)

## Formulas

See `docs/math/chebyshev_type_i.md` and `docs/math/transforms.md`.

g-values computed with:

- ε = sqrt(10^(A_p/10) − 1)
- β = asinh(1/ε)
- γ = sinh(β/n)

Cross-checked against published tables for A_p ∈ {0.1, 0.5} dB, n ∈ {3, 5}.

## Literature

1. A. B. Williams & F. J. Taylor — *Electronic Filter Design Handbook* (Chebyshev prototype equations).
2. G. L. Matthaei, L. Young, E. M. T. Jones — *Microwave Filters, Impedance-Matching Networks, and Coupling Structures*.
3. Optional external oracle: ELSIE Student Edition comparison (maintainer appendix; do not commit proprietary binaries).

## Status

- Prototype g-values + scaled L/C: **frozen in Phase 0**
- Frequency-response metrics: **Phase 2**
