# ADR-026: Open-end/stub fringing correction

- **Status:** Accepted
- **Date:** 2026-10-28
- **Relates to:** ADR-025

## Context

An open microstrip stub does not end at its physical length: the fringing field
adds an effective electrical length. Ignoring it biases short/open stubs,
especially on thick substrates and at lower impedance.

## Decision

- Add the Hammerstad open-end extension:
  `Δl/h = 0.412·((eeff+0.3)/(eeff−0.258))·((W/h+0.262)/(W/h+0.813))`.
- Apply it to **open shunt stubs** using the dispersive `eeff(f)` and stored
  `er`/height/width; short stubs are unchanged.
- Keep the physical length in the BOM; the extension is an analysis correction.
- A missing-geometry element falls back to the previous ideal open.
- Step-width discontinuity and radiation/dispersion of the fringing capacitance
  are **not** included in this step; they remain future work.

## Consequences

- Open-stub phase/impedance is closer to a fabricated board without changing the
  BOM length.
- The correction is quasi-static and first-order; the physical layout must still
  be verified with a field solver or VNA.
