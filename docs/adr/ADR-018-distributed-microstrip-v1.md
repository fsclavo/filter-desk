# ADR-018: Distributed microstrip elements and v1 low-pass synthesis

- **Status:** Accepted
- **Date:** 2026-10-26
- **Supersedes:** ADR-007 for the distributed-microstrip v1 scope

## Context

The lumped filter workflow is the product core, but PCB builders need a bounded
way to move a low-pass design into microstrip lines. A full general distributed
synthesis engine (all responses, arbitrary order, discontinuities, EM) is much
larger than the current application. The domain must stay independent of the
microstrip calculator package, and both analyzers must see the same canonical
elements.

## Decision

- Add two canonical distributed elements:
  - `MicrostripLineElement` — a series TEM line with `Z0`, electrical length,
    `eeff` and first-order loss;
  - `MicrostripStubElement` — an open/short shunt stub with the same electrical
    parameters.
- Analysis uses ideal TEM ABCD sections. The scikit-rf adapter reuses the same
  element conversion, so both backends stay consistent.
- Project format **v2** stores the distributed geometry and still loads v1
  projects. The BOM/build sheet carries substrate, width, length, angle and stub
  kind.
- Add an **experimental** v1 low-pass realization:
  - Butterworth and Chebyshev-I, order **1–3**;
  - stepped-impedance cascade of high-/low-impedance microstrip lines;
  - electrical length is adjusted within the requested limits to keep `Z0`
    inside the selected range;
  - the model is marked `experimental`, not validated on hardware.
- Stubs are available for manual circuits and BOM/analysis; v1 synthesis uses
  line sections only. Series stubs, Kuroda transformations, coupled lines,
  dispersion, discontinuities and EM simulation remain out of scope.
- SPICE/LTspice/Qucs export for distributed circuits fails with an explicit
  error rather than emitting an incorrect approximation.
- Stress estimation skips distributed elements; it has no lumped arm impedance.

## Consequences

- A low-order LP board can be designed and exported to BOM/Touchstone from the
  GUI or CLI.
- The model confidence is explicit; users must verify the physical board.
- Full distributed synthesis (all responses, higher orders, stub-only/Kuroda
  topologies) remains future work.
