# ADR-045: Coupled-microstrip geometry synthesis

- **Status:** Accepted
- **Date:** 2026-11-01
- **Relates to:** ADR-018, ADR-044

## Context

ADR-044 delivered the electrical coupled-line BPF and even/odd impedance
targets, but a builder still needed an external calculator for width and gap.

## Decision

- Add a zero-thickness, quasi-static Hammerstad-Jensen forward model for
  symmetric coupled microstrip:
  - even/odd impedance and effective permittivity from `W/h`, `S/h` and `er`;
  - free-space single-line impedance in the even/odd correction equations;
  - validated against the published alumina example (`u=1`, `g=0.5`,
    `er=10` → `Z0e≈59 Ω`, `Z0o≈37 Ω`).
- Invert the model with a bounded, multi-start least-squares fit to target
  `Z0e`/`Z0o`.
- Expose `width_mm`, `gap_mm`, `eeff_even`, `eeff_odd` and residuals in the
  coupled-line BPF section table and CLI JSON.
- Use the selected substrate height and `er`; warn on narrow traces/gaps and
  when the normalized geometry leaves the validated range.
- Keep hairpin/interdigital layout, finite thickness, dispersion,
  discontinuities, radiation and EM coupling out of scope.

## Consequences

- A coupled-line BPF now produces practical first-pass PCB dimensions.
- The result is still not fabrication-ready: verify with a 2-D/3-D field solver
  or VNA, especially for narrow gaps and thick copper.
- Hairpin/interdigital layout remains the next distributed milestone.
