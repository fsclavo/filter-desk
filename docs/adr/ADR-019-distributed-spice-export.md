# ADR-019: Distributed microstrip SPICE netlist export

- **Status:** Accepted
- **Date:** 2026-10-26
- **Relates to:** ADR-018

## Context

ADR-018 introduced distributed microstrip line/stub elements in the canonical
netlist and intentionally rejected SPICE export instead of emitting an
approximation. A basic export is still useful for checking a board in LTspice or
ngspice, provided the limitations are explicit.

## Decision

- Export distributed **series lines** as SPICE `T` elements:
  - port 1 is `(node_a, ground)`, port 2 is `(node_b, ground)`;
  - `Z0` is the line impedance and `TD = length·sqrt(eeff)/c`.
- Export **shunt stubs** as a `T` element whose far port is terminated:
  - open stub: high-value resistor (1e12 Ω);
  - short stub: low-value resistor (1 µΩ).
- The `T` element is **lossless**. The exported netlist includes the line loss
  as a comment but does not model it. LTspice/Qucs `.asc`/`.sch` graphical
  export remains unsupported for distributed circuits.
- Add an ngspice regression that compares a quarter-wave line's load voltage
  against the ABCD result when ngspice is available.

## Consequences

- Users can inspect and simulate the ideal transmission-line topology.
- Conductor/dielectric loss, dispersion, discontinuities and radiation remain
  outside the exported model and must be checked with a field solver or VNA.
- Higher-order/all-response distributed synthesis is still future work.
