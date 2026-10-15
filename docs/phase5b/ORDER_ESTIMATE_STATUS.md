# Order estimation from Ap / As / edges

**Date:** 2026-10-02  
**Status:** Complete  
**Version:** 0.5.7

## Delivered

- `filterdesk.synthesis.order_estimate.estimate_minimum_order` wrapping scipy
  `buttord` / `cheb1ord` / `cheb2ord` / `ellipord` (analog)
- Families: Butterworth, Chebyshev I, Chebyshev II, Elliptic
- Responses: low-pass and high-pass
- CLI: `filterdesk estimate-order --family … --f-pass … --f-stop … --ap … --as …`
- GUI: **Estimate N** on the specification panel (stopband-f field + Ap/As)

## Notes

- Cheby II: Ap is max passband loss for estimation; synthesis cutoff remains the **stopband** edge (Estimate N copies `f_stop` into cutoff)
- Bessel / Gaussian / Legendre / image-parameter families: not supported (no classical As/fs order formula)
- BP/BS order estimation deferred (use LP prototype edges)

## Tests

`tests/unit/test_order_estimate.py`
