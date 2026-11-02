# ADR-043: General N-port connection and circulator/isolator models

- **Status:** Accepted
- **Date:** 2026-11-01
- **Relates to:** ADR-027, ADR-028, ADR-040

## Context

The N-port core could renumber ports, terminate a port and combine grounded
2-port branches, but it could not connect arbitrary port pairs or cascade
networks. The system designer also had no non-reciprocal building block for
antenna-sharing and isolator studies.

## Decision

- Add `SParameters.connect(networks, connections)` for ideal port-pair
  connections between any number of networks.
- Use a wave-domain connection matrix rather than an admittance Schur
  complement, because ideal through networks have singular Y matrices.
- Preserve external ports in network/port order; connected ports disappear.
- Add `SParameters.cascade(other)` as the 2-port convenience wrapper.
- Add `network cascade` and `network connect` CLI commands.
- Add first-order ideal circulator and isolator models:
  - 3-port circulation `1→2`, `2→3`, `3→1`;
  - independent insertion loss, isolation and return-loss magnitudes;
  - isolator = circulator with port 3 terminated in the reference impedance.
- Add **Tools → Circulator / isolator…** with Touchstone `.s3p`/`.s2p` export
  and a CLI `circulator` / `isolator`.
- Do not claim a physical ferrite-junction or cavity model. Phase, bandwidth,
  power handling, magnet bias and cavity dimensions remain out of scope.

## Consequences

- Arbitrary reciprocal networks can be cascaded or connected for analysis.
- Ideal thru networks, attenuators and measured `.sNp` blocks can be combined
  without a Y-matrix singularity.
- Circulators/isolators are useful for topology studies and Touchstone export,
  but are not validated hardware models.
- Cavity filters require a separate coupling-matrix/physical model and VNA/EM
  validation; they remain future work.
