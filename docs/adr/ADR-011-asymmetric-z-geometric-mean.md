# ADR-011: Asymmetric source/load impedance

> **Status:** Superseded for realization by ADR-017 (exact output transformer).
> The analysis formulas for unequal ports remain valid.

- **Status:** Accepted
- **Date:** 2026-09-30
- **Phase:** 4

## Context

Phase 1 forced \(Z_S = Z_L\). Real designs often need unequal terminations. Exact synthesis for arbitrary \(Z_L/Z_S\) (especially even-order Chebyshev where \(g_{n+1}\neq 1\)) needs Norton transforms or ratio-specific prototypes.

## Decision

**Geometric-mean reactive scaling** for Phase 4:

\[
Z_0 = \sqrt{Z_S\, Z_L}
\]

- All ladder L/C (and resonator) values are scaled with this \(Z_0\).
- Ports keep the true \(Z_S\) and \(Z_L\); ABCD→S uses unequal-port formulas (already in `LadderABCDAnalyzer`).
- Equal-Z designs are unchanged (\(Z_0 = Z_S = Z_L\)).

## Limitations (documented)

- Not a full Norton / minimum-inductance redesign; large \(Z_L/Z_S\) ratios will show return-loss asymmetry and may not meet classic equal-ripple Chebyshev passband shape at both ports.
- Even-order Chebyshev still ignores prototype \(g_{n+1}\neq 1\) (same as Phase 1 equal-Z); a dedicated transformer or ratio table is deferred.
- `ScikitRFAnalyzer` cascades elements at a common reference \(z_0=\sqrt{Z_S Z_L}\) and renormalizes the result to \([Z_S, Z_L]\), so unequal-Z analysis is now supported by both backends (see ADR-014).

## Consequences

- `validate_spec` no longer rejects \(Z_S \neq Z_L\).
- Golden tests cover a small unequal-Z Butterworth LP case via ABCD.
