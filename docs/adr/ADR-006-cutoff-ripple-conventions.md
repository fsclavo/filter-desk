# ADR-006: Cutoff and ripple conventions

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

Chebyshev and elliptic filters have multiple cutoff definitions (−3 dB vs ripple edge). Ambiguity causes synthesis/analysis mismatches and bad golden comparisons.

## Decision

1. **Default cutoff** for Chebyshev Type I (and elliptic passband edge): the **ripple-edge** frequency where the response leaves the passband ripple corridor.
2. Butterworth default cutoff: **−3 dB** (half-power), classic prototype ωc = 1.
3. Bessel: delay-normalized prototypes; magnitude cutoff mapping documented per table source when family is implemented (Phase 5).
4. UI and `FilterSpec` must label the convention explicitly (`cutoff_definition` field).
5. Optional future: convert between ripple-edge and −3 dB via closed-form factors — never silently.

## Milestone implication

The Phase 1 golden design uses **ripple-edge** `f_c = 140 MHz` for Chebyshev Type I, Ap = 0.01 dB.

## Consequences

- Math docs and fixtures must state `cutoff_definition`.
- Import from other tools must map their convention explicitly.
