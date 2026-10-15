# BP/BS for finite-zero families

**Date:** 2026-10-02  
**Status:** Complete  
**Version:** 0.5.5

## Delivered

- LP→BP / LP→BS transforms for Cauer / m-derived arms with finite zeros
- New circuit elements:
  - `IdealBruneLC` — series of series-LC + parallel-LC (Z = Zs + Zp)
  - `IdealDualBruneLC` — parallel of both (Z = Zs ‖ Zp)
- ABCD analysis, project I/O, schematic/table/CLI support
- Enabled for **Chebyshev Type II**, **Elliptic**, and **M-derived** (plus existing constant-k BP/BS)

## Still deferred

- Even-order equal-R Cauer (done — v0.5.6)
- Order estimation from As/fs (done — v0.5.7; BP/BS edges still open)
- Norton asymmetric-Z redesign

## Tests

`tests/unit/test_phase5b_families.py` — Cheby II BP vs `scipy.signal.lp2bp_zpk`; elliptic BP/BS; m-derived BP smoke
