# Phase 7 — Interactive tuning + optimization (status)

**Date:** 2026-10-15  
**Status:** In progress  
**Version:** 0.5.11

## Goal

Let designers move passband landmarks and impedances and re-run synthesis
(redesign-on-tune), then optimize component values against limit regions.

## Delivered

### Retune / redesign-on-change (FR-U2 core)

- `services/retune.py`:
  - `RetuneRequest` — partial overrides (`cutoff_hz`, `f_center_hz`,
    `bandwidth_hz`, `z_source_ohm`, `z_load_ohm`); `None` keeps the current value.
  - `retune_spec(spec, request)` — apply + validate (reuses
    `filter_spec_from_mapping`).
  - `retune_cutoff` / `retune_center` / `retune_bandwidth` — response-typed
    helpers (raise on the wrong response type).
  - `scale_response(spec, factor)` — constant-shape frequency scaling: LP/HP scale
    the cutoff; BP/BS scale center **and** bandwidth (fractional bandwidth kept).
- `services/session.py` — `DesignSession.retune(request)` and
  `.scale_response(factor)` set the new spec and re-synthesize.
- GUI — **Design → Scale response…** asks for a factor and applies it through
  `SynthesizeCommand` (spec + circuit undo/redo), then re-analyzes.

## Design notes

- Retune only produces a **validated spec**; the caller re-synthesizes. This keeps
  the transform pure and testable, and reuses existing validation (ADR-006 cutoff
  conventions, topology↔response rules).
- `scale_response` preserves the fractional bandwidth for BP/BS, so the relative
  shape does not change.

## Deferred (rest of Phase 7)

- Per-part continuous tune (drag a component value / step size).
- `optimization/` package (objectives/constraints/solvers — limit-residual least
  squares + bounded Nelder–Mead) wired to `LimitRegion[]` (also B3.3).
- Background workers + debounce + cancel stale jobs for tune/optimize (NFR-4).
- GUI Tune/Optimize toolbar actions and interactive marker-driven retune.

## Tests

- `tests/unit/test_retune.py` — cutoff/center/bandwidth retune, response-type
  guards, LP/HP and BP/BS scaling (fractional-BW preservation), non-positive
  factor rejection, impedance retune, and session retune/scale re-synthesis.
- `tests/unit/test_gui_smoke.py` — **Design → Scale response…** action
  (`QInputDialog` stubbed) doubling the cutoff via `SynthesizeCommand`.
