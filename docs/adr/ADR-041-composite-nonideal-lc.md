# ADR-041: Non-ideal sub-parts for series/parallel LC resonators

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-016, ADR-033, ADR-039

## Context

BPF/duplexer branches use compact `IdealSeriesLC`/`IdealParallelLC` arms.
Global parasitics and assigned parts previously could not apply DCR, SRF, ESR or
ESL to those sub-parts, so real-part application was incomplete.

## Decision

- Add optional sub-part model fields to `IdealSeriesLC` and `IdealParallelLC`:
  inductor series resistance, parallel capacitance/SRF, capacitor ESR/ESL.
- Extend the ABCD evaluator to include those models in the series-LC impedance
  and parallel-LC admittance.
- Extend `nonidealize_circuit` and assigned-part application to populate the
  fields for series/parallel resonators.
- Persist the fields in the native project format and preserve them during
  component edits.
- Keep Brune/dual-Brune arms value-only for now; they still report a warning.
- Ideal/default values remain backward compatible (all new fields default to
  zero/None).

## Consequences

- BPF, duplexer, triplexer and multiplexer branches can now use real L/C values
  and available DCR/SRF/ESR/ESL.
- The model remains first-order and catalog-level; vendor curves, thermal,
  power and EM validation are still absent.
- Brune finite-zero arms remain a future extension.
