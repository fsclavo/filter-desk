# Order estimation from Ap / As / edges

**Date:** 2026-10-15  
**Status:** Complete  
**Version:** 0.5.11

## Delivered

- `filterdesk.synthesis.order_estimate.estimate_minimum_order` wrapping scipy
  `buttord` / `cheb1ord` / `cheb2ord` / `ellipord` (analog)
- Families: Butterworth, Chebyshev I, Chebyshev II, Elliptic
- Responses: low-pass, high-pass, **band-pass, band-stop** (B1.4)
- CLI: `filterdesk estimate-order --family … (--f-pass … --f-stop … | --pass-band LO HI --stop-band LO HI) --ap … --as …`
- GUI: **Estimate N** on the specification panel (stopband-f field + Ap/As; LP/HP)

## Band (BP/BS) estimation

- Pass `f_pass_low_hz`, `f_pass_high_hz`, `f_stop_low_hz`, `f_stop_high_hz`.
- BP requires `f_stop_low < f_pass_low < f_pass_high < f_stop_high`; BS requires
  `f_pass_low < f_stop_low < f_stop_high < f_pass_high`.
- scipy receives 2-element analogue `wp`/`ws`; `natural_freq_hz` is the
  geometric mean of the two prototype corner frequencies
  (`natural_freq_low_hz`/`natural_freq_high_hz` hold the pair).
- `omega_ratio` is the stop/pass **bandwidth** ratio.

## Notes

- Cheby II: Ap is max passband loss for estimation; synthesis cutoff remains the **stopband** edge (Estimate N copies `f_stop` into cutoff)
- Bessel / Gaussian / Legendre / image-parameter families: not supported (no classical As/fs order formula)
- GUI Estimate N does not collect BP/BS stopband edges yet (API + CLI only)

## Tests

`tests/unit/test_order_estimate.py`
