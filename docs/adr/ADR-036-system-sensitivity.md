# ADR-036: Deterministic system sensitivity

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-032, ADR-033

## Context

E-series and parasitic models show a nominal response, but not which component
matters most. For duplexers, a small value error can change TX/RX isolation more
than insertion loss. A deterministic perturbation is easier to audit than a
Monte Carlo run and is a useful first step.

## Decision

- Add `analyze_system_sensitivity(design, delta_pct)`.
- For every physical L/C/R part in every branch, perturb the value by +delta and
  -delta, reanalyze only that branch, rebuild the combined N-port and recompute
  the system metrics.
- Report the worse direction per component:
  - branch, reference and kind;
  - impact score;
  - isolation delta (duplexer);
  - insertion-loss delta;
  - out-of-band delta.
- Sort by descending impact.
- Expose **Sensitivity…** in the designer and `--sensitivity PCT` on the system
  CLI commands.
- This is deterministic, not a statistical yield analysis.

## Consequences

- Users can identify the components that most affect isolation or band metrics.
- The result depends on the selected delta and nominal design; it is not a
  tolerance distribution or worst-case guarantee.
- Monte Carlo/yield remains a separate future feature.
