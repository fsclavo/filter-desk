# ADR-037: System Monte-Carlo tolerance / yield

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-036, ADR-033

## Context

Deterministic sensitivity identifies the most influential components, but not
the probability of meeting a specification under random tolerances. A system
Monte-Carlo run is needed for yield estimates, especially for duplexer isolation.

## Decision

- Add `SystemMonteCarloConfig` and `analyze_system_montecarlo`.
- Draw independent multiplicative factors for every physical L/C/R part in every
  branch, using uniform ±tol or normal sigma = tol/100.
- Rebuild the combined N-port for each trial and collect:
  - worst isolation (duplexer);
  - maximum insertion loss;
  - worst out-of-band transmission.
- Yield criteria:
  - duplexer: isolation ≥ target and max insertion loss ≤ target;
  - diplexer/multiplexer: max insertion loss ≤ target and worst OOB ≤ target.
- Report yield, pass count, failure counts and min/percentile/max statistics.
- Expose **Monte Carlo…** in the designer. Default is 200 trials; large runs can
  take seconds.
- This is a tolerance model, not thermal, power, EM, vendor-model or hardware
  validation.

## Consequences

- Users can estimate yield and see isolation/insertion distributions.
- Results depend on the tolerance distribution, seed and nominal design.
- The GUI run is synchronous in v1; background execution can be added later.
