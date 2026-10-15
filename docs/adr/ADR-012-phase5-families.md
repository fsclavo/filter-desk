# ADR-012: Phase 5 approximation families

- **Status:** Accepted
- **Date:** 2026-09-30
- **Phase:** 5

## Decision

### All-pole families (ladder g-values) — Phase 5

| Family | Cutoff (ADR-006) | Source of \(g_k\) | Order |
| --- | --- | --- | --- |
| Bessel–Thomson | \(\omega_{-3\mathrm{dB}}=1\) | Fitted to `scipy.signal.besselap(..., norm="mag")` | 1…10 |
| Gaussian | \(\omega_{-3\mathrm{dB}}=1\) | Ladder fitted to \(|H|\approx e^{-a\omega^2}\) (finite-order approx.) | 1…10 |
| Legendre (Papoulis) | \(\omega_{-3\mathrm{dB}}=1\) | Fitted Optimum-L ladders (`legendre.py` / tables) | 2…9 |

\(g_0=g_{n+1}=1\). Existing LP/HP/BP/BS ladder realizers apply unchanged.

### Deferred to Phase 5b

| Family | Reason |
| --- | --- |
| Chebyshev Type II | Finite \(j\omega\) zeros need Cauer tank arms |
| Elliptic / Cauer | Same + modular-\(k\) design; highest risk |
| Constant-K / M-derived | Image-parameter (not modern approx.) |

## Consequences

- GUI exposes Bessel / Gaussian / Legendre.
- Goldens/tests emphasize Bessel vs scipy; Gaussian/Legendre are table-backed approximations.
