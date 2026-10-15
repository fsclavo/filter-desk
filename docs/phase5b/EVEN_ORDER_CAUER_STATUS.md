# Even-order equal-R Cauer

**Date:** 2026-10-02  
**Status:** Complete  
**Version:** 0.5.6

## Delivered

- **Chebyshev Type II** and **Elliptic** accept even orders (elliptic ≥2)
- Equal-R series-L / shunt-series-LC Cauer ladders via multi-start |S21| fitting when exact Darlington expansion fails
- Transmission zeros remain at the analytic prototype frequencies

## Notes

- Even-order **Cheby II** matches scipy closely (typically ≪ 0.5 dB)
- Even-order **elliptic** equal-R is an approximation (classic theory often wants a transformer); stopband As is still met in tests
- GUI no longer forces odd order for these families

## Tests

`tests/unit/test_phase5b_families.py` — `test_cheby2_even_order_matches_scipy`, `test_elliptic_even_order_matches_scipy`
