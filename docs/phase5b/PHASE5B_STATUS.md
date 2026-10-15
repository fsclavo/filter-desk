# Phase 5b completion record

**Date:** 2026-10-01  
**Status:** Complete  
**Version:** 0.5.2

## Delivered

- **Chebyshev Type II** — odd order, As, stopband-edge fc; Cauer LP/HP (ADR-013)
- **Elliptic** — odd order ≥3, Ap+As, ripple-edge fc; Cauer LP/HP
- **Constant-K** — image-parameter T-sections; LP/HP/BP/BS
- **M-derived** — m∈(0,1); LP/HP with finite ω∞
- Spec fields: `stopband_attenuation_db`, `m_parameter`; `STOPBAND_EDGE` cutoff
- GUI/CLI wired; unit tests vs scipy zpk shapes

## Deferred

- BP/BS order estimation (four-edge scipy *ord)

## BP/BS finite-zero follow-up (2026-10-02)

See `docs/phase5b/BPBS_FINITE_ZERO_STATUS.md` — Cheby II / elliptic / m-derived BP/BS shipped in v0.5.5.

## Even-order equal-R Cauer (2026-10-02)

See `EVEN_ORDER_CAUER_STATUS.md` — even-order Type II / elliptic shipped in v0.5.6.

## Order estimation (2026-10-02)

See `ORDER_ESTIMATE_STATUS.md` — Ap/As/fs helpers shipped in v0.5.7.

## Next

**Phase 6** — practical components (Q, ESR, parasitics, tolerances, E-series).
