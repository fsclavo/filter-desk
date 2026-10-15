# ADR-003: Dual network analyzers — ABCD ladder + scikit-rf

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

Interactive tuning, Monte Carlo, and optimization need fast repeated analyses of mostly ladder LC networks. scikit-rf `Circuit` is general but may be slower for thousands of evaluations.

## Decision

1. Define `NetworkAnalyzer` protocol returning domain `AnalysisResult`.
2. Implement **`LadderABCDAnalyzer`** as the default fast path for series/shunt ladders (Phase 2).
3. Implement **`ScikitRFAnalyzer`** for cross-validation and future non-ladder topologies.
4. Derived metrics (IL, RL, VSWR, group delay) computed in pure NumPy from S-parameters.

## Consequences

- Phase 2 must ship both analyzers and golden cross-checks.
- Topology realization must expose enough structure for ABCD cascading (ordered arms).
- Non-ladder elements later may force skrf/MNA path without redesigning the protocol.
