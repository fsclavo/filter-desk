# ADR-009: Milestone topology — series-C input high-pass ladder

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

High-pass ladders have two dual realizations (series-C input vs shunt-L input). The first golden milestone must freeze one.

## Decision

Milestone topology id: **`ladder_hp_series_c_input`**

- Derived from low-pass prototype with **series-first** arms (LP: series L, shunt C, …).
- After LP→HP reactance transform: **series C, shunt L, series C, …** ending with series C for odd order.

Shunt-L input HP is a first-class topology in Phase 1 but is **not** the milestone golden.

## Consequences

- Golden fixture values are unique to this topology.
- Dual network must be tested separately with its own fixture.
