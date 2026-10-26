# ADR-007: Deferred distributed / transformer elements

- **Status:** Superseded for the microstrip-v1 scope by ADR-018; original deferral otherwise accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

Transmission lines, stubs, transformers, coupled inductors, and distributed equivalents are common in general RF design tools. Implementing them early would distort the lumped-filter product.

## Decision

- **Out of scope** until after Monte Carlo / LCT phases (roadmap “later”).
- Domain `Element` hierarchy may reserve abstract extension points / unused enum values, but **no physics**, GUI editors, or synthesizers for these types in Phases 0–8.
- Analysis backends must not assume only R/L/C forever (protocol stays general).

## Consequences

- Cleaner Phase 1–8 delivery.
- Schematic library stays R/L/C (+ non-ideal RLC layers) initially.
