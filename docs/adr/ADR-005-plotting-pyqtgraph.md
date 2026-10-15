# ADR-005: PyQtGraph primary interactive plotting

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

Need responsive pan/zoom, multi-trace overlays, markers, and limits. Matplotlib is ubiquitous but slower for interactive retune. scikit-rf plotting is convenient but ties UI to skrf.

## Decision

1. **Interactive plots:** PyQtGraph behind a `PlotBackend` protocol.
2. **Static export (PNG/PDF/SVG):** Matplotlib.
3. **Smith chart:** PyQtGraph custom Γ-plane grid + S11 locus (v0.5.4; see `docs/phase3/SMITH_STATUS.md`).
4. GUI panels consume `AnalysisResult`, not plotting-library objects.

## Consequences

- Extra dependency vs Matplotlib-only; justified by tuning UX.
- Smith chart implemented in-app (S11); S22 / export still open.
