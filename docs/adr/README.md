# ADR index (Phase 0)

| ADR | Title | Status |
| --- | --- | --- |
| [001](ADR-001-domain-not-skrf.md) | Domain model independent of scikit-rf | Accepted |
| [002](ADR-002-license-apache-pyside-lgpl.md) | Apache-2.0 + PySide6 LGPL | Accepted |
| [003](ADR-003-dual-analyzers-abcd-skrf.md) | ABCD + scikit-rf analyzers | Accepted |
| [004](ADR-004-native-json-project.md) | Versioned JSON native project | Accepted |
| [005](ADR-005-plotting-pyqtgraph.md) | PyQtGraph primary plotting | Accepted |
| [006](ADR-006-cutoff-ripple-conventions.md) | Cutoff / ripple conventions | Accepted |
| [007](ADR-007-deferred-distributed-elements.md) | Defer TL/transformers | Superseded by 018 for microstrip v1 |
| [008](ADR-008-dataclasses-not-pydantic.md) | dataclasses, not Pydantic | Accepted |
| [009](ADR-009-milestone-topology-series-c-hp.md) | Milestone HP topology | Accepted |
| [010](ADR-010-bp-bs-frequency-definition.md) | BP/BS \(f_0\), BW | Accepted |
| [011](ADR-011-asymmetric-z-geometric-mean.md) | Asymmetric Z via geometric mean | Accepted |
| [012](ADR-012-phase5-families.md) | Phase 5 families (Bessel/Gaussian/Legendre; 5b zeros) | Accepted |
| [013](ADR-013-phase5b-finite-zeros.md) | Phase 5b Cheby II / elliptic / K-m | Accepted |
| [014](ADR-014-p1-debt-closure.md) | P1 debt closure (skrf unequal Z, order estimate, PlotBackend) | Accepted |
| [015](ADR-015-cross-cutting-decisions.md) | Cross-cutting decisions (layers, file extension, pytest-qt) | Accepted |
| [016](ADR-016-inductor-model.md) | Real inductor model (Q(f), SRF, DC bias, winding) | Accepted |

- [ADR-017](ADR-017-exact-unequal-terminations.md) — exact unequal terminations via output transformer
- [ADR-018](ADR-018-distributed-microstrip-v1.md) — distributed microstrip elements and v1 LP synthesis
- [ADR-019](ADR-019-distributed-spice-export.md) — SPICE netlist export for distributed lines/stubs
- [ADR-020](ADR-020-distributed-lp-numerical-fit.md) — gated numerical fit for distributed LP orders 4–5
