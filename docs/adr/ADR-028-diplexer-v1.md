# ADR-028: LPF+HPF diplexer v1 on the N-port core

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-027

## Context

The N-port core can combine grounded 2-port branches at a common input. The
first practical system is an LPF+HPF diplexer for separating two bands.

## Decision

- Build the diplexer from two independently synthesized equal-impedance ladder
  branches: a low-pass and a high-pass filter with the same order, family,
  ripple/stopband rules and reference impedance.
- Analyze both branches on the same frequency grid, convert each to
  `SParameters`, and combine them with `parallel_branches`.
- Port order is fixed: **1 = common input**, **2 = low-pass output**,
  **3 = high-pass output**.
- Report:
  - worst insertion loss in each passband (`S21` for low, `S31` for high),
  - worst out-of-band transmission in each passband (`S31` / `S21`),
  - minimum input return loss (`S11`) in each passband,
  - the first `|S21| = |S31|` crossover between samples.
- Expose `filterdesk diplexer --low-cutoff … --high-cutoff … --output out.s3p`
  and optional per-branch `.s2p` outputs.

## Consequences

- The combined 3-port includes the real interaction between both branch input
  admittances. Do not claim branch performance from the individual 2-port
  analyses alone.
- Passband metrics include the transition region up to the nominal cutoff, so
  the worst rejection is usually at the band edge.
- This is an LC ladder diplexer model. It does not include an antenna port,
  transmitter/receiver duplexer isolation requirements, cavity resonators,
  component parasitics beyond the selected models, power handling or thermal
  validation.
