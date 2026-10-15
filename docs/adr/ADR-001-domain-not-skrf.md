# ADR-001: Domain model is independent of scikit-rf

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

scikit-rf provides excellent network analysis, Touchstone I/O, and a `Circuit` builder. It is tempting to use `skrf.Network` / `skrf.Circuit` as the application’s primary data model.

## Decision

FilterDesk owns a **canonical domain model** (`FilterSpec`, `Circuit`, `Element`, `AnalysisResult`, etc.). scikit-rf is used only behind an **analysis/I/O adapter**.

## Consequences

- GUI, synthesis, optimizer, Monte Carlo, and native file I/O never import scikit-rf types.
- Alternative analyzers (ABCD ladder, future MNA) can share the same domain.
- Adapter mapping cost is accepted; correctness tests cross-check backends.
