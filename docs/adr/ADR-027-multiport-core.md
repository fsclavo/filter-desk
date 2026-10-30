# ADR-027: N-port S-parameter core and parallel branch combination

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-001, ADR-003, ADR-024

## Context

Diplexers and duplexers need a network representation beyond the existing
2-port `AnalysisResult` and mixed-mode 4-port transform. The core must stay
independent of scikit-rf and Touchstone I/O, and it must be explicit about the
kind of interconnection it models.

## Decision

- Add `analysis.multiport.SParameters`: one S-matrix per frequency for an equal
  real reference impedance. Frequencies must be strictly increasing.
- Provide three operations:
  - **port renumbering** (a permutation of 1-based ports),
  - **termination** of one port through its reflection coefficient, returning
    the reduced network,
  - **parallel combination** of grounded 2-port branches at a common input
    port, returning port 1 (common) plus one output per branch.
- The parallel operation converts each branch S-matrix to admittance, adds the
  common-input self admittances, keeps the branch outputs separate, and
  converts back to S. It models an ideal common node: input voltages are equal
  and input currents add. It does **not** insert an isolation network.
- Touchstone conversion lives in `io.touchstone`:
  `read_sparameters`, `write_sparameters` and `write_touchstone_snp`.
  Touchstone v1 files carry one scalar reference impedance, matching the core.
- Expose the operations through `filterdesk network info|renumber|terminate|
  combine`.

## Consequences

- The first diplexer can be built from two independently synthesized 2-port
  branches and analyzed as a 3-port with realistic branch-to-branch
  interaction at the common node.
- This is not yet a general arbitrary-port interconnect engine: it does not
  support per-port complex reference impedances, ideal thru junctions between
  arbitrary networks, or non-common-ground topologies.
- The parallel model is valid for branches that share the reference conductor
  and use the same real port impedance. Isolation and return-loss claims must
  be checked on the combined network, not on each branch alone.
