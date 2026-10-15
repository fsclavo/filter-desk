# Phase 3 UX completion (undo / markers / limits)

**Date:** 2026-10-01 (marker drag 2026-10-09 / Smith drag 2026-10-13)  
**Status:** Complete  
**Version:** 0.5.11

## Delivered

- **Undo/Redo** (`Edit` menu, standard shortcuts) via `QUndoStack`
  - Component value edits
  - Synthesize (restores prior circuit / prototype / spec)
  - Marker and limit list edits
  - Marker drag on response plots and Smith (`Move marker`)
- **Markers** (≤8): dock editor, add-at-cursor (`Ctrl+M`), vertical lines on all plots; drag lines or Smith S11 spots to retune (snaps to sweep); persisted in project `extensions.markers`
- **Limits** (≤10): dock editor, frequency band + y min/max overlays, PASS/FAIL status; persisted in `extensions.limits`

## Still deferred

- Full schematic topology editor (insert / delete / type change)
- Optimizer wiring to limits (Phase 7)

## Tests

`tests/unit/test_phase3_ux.py`, `tests/unit/test_marker_drag.py`
