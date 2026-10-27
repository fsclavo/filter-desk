# ADR-020: Distributed LP orders 4–5 via a gated numerical fit

- **Status:** Accepted
- **Date:** 2026-10-27
- **Relates to:** ADR-018, ADR-019

## Context

The analytical stepped-impedance mapping is accurate enough for low-order
Butterworth/Chebyshev-I low-pass filters, but it does not provide practical line
impedances for orders 4–5 on common substrates. Simply emitting the analytical
values would produce a design whose cutoff and passband no longer match the
lumped prototype.

## Decision

- Keep the analytical path for orders **1–3**.
- For orders **4–5**, fit per-section line impedances and electrical lengths
  against the lumped prototype response with `scipy.optimize.least_squares`.
- Use a bounded Z0 range (default **10–250 Ω**) and per-section angles bounded to
  **5–80°**. The requested angle is the initial guess; the fit may change each
  section.
- Accept a fit only when:
  - passband `|ΔS21| ≤ 1.5 dB` over `0.1 f_c … f_c`;
  - attenuation at `2 f_c` is no more than **6 dB worse** than the lumped
    prototype.
- If the gate fails, raise `DistributedSynthesisError` with the measured margins
  instead of returning the design.
- Mark high-order designs as `optimized=True`, include per-section angles in the
  circuit metadata, and warn whenever the fit uses very narrow/wide traces.
- SPICE export remains the lossless `T`-element approximation from ADR-019.

## Consequences

- Orders 4–5 are available when the requested impedance range is practical.
- High-order fits often sit near the Z0 limits and can require traces that are
  hard to fabricate; warnings and VNA/Touchstone verification are mandatory.
- All-response, stub-only/Kuroda, dispersion and hardware validation remain
  future work.
