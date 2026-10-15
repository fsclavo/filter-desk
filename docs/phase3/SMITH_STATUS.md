# Smith chart (Phase 3 deferred UX)

**Date:** 2026-10-01 (S22 overlay 2026-10-05; Matplotlib export 2026-10-09; marker drag 2026-10-13)  
**Status:** Complete  
**Version:** 0.5.11

## Delivered

- **Smith tab** in the response plot panel (PyQtGraph Γ-plane chart)
- Constant-r / constant-x grid + unit circle
- **S11** (red) and **S22** (blue) loci with legend
- S11 start (green) / stop (purple) markers
- Frequency markers on the S11 locus (**draggable**; snap to nearest S11 sample)
- Cursor snaps to nearest S11 or S22 sample; readout shows both ports
- **Matplotlib export** (PNG/SVG/PDF): CLI `--export-smith`, GUI File → Export Smith chart…

## Geometry / export

- Pure helpers in `filterdesk.analysis.smith` (no Qt dependency)
- Static export in `filterdesk.plotting.smith_export` (Agg backend)

## Still deferred

- Smith-specific limit regions

## Tests

`tests/unit/test_smith.py`, `tests/unit/test_smith_export.py`
