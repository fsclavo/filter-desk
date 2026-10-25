# Approximation families — Phase 0 index

| Family | Spec doc | Phase | Notes |
| --- | --- | --- | --- |
| Butterworth | `butterworth.md` | 1 | −3 dB cutoff (ADR-006) |
| Chebyshev Type I | `chebyshev_type_i.md` | 1 | Ripple-edge cutoff; **milestone** |
| Bessel | ADR-012 + tables | 5 | Mag-normalized; order ≤10 |
| Gaussian | ADR-012 + tables | 5 | Finite-order approx; order ≤10 |
| Legendre | ADR-012 + tables | 5 | Papoulis; order 2…9 |
| Chebyshev Type II | `chebyshev_type_ii.md` | 5b | Finite zeros (Cauer); even/odd |
| Elliptic / Cauer | `elliptic.md` | 5b | Ap+As; odd only (≥3) |
| Constant-K | `constant_k_m_derived.md` | 5b | Image-parameter |
| M-derived | `constant_k_m_derived.md` | 5b | Image-parameter |

Shared transforms: `transforms.md`.

Each family implementation must provide: definition, inputs, algorithm, unit tests, ≥1 golden example (blueprint §27).
