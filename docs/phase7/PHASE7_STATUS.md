# Phase 7 — Interactive tuning + optimization (status)

**Date:** 2026-10-15  
**Status:** Complete  
**Version:** 0.6.0

## Goal

Let designers move passband landmarks and impedances and re-run synthesis
(redesign-on-tune), tune individual parts, then optimize component values against
limit regions.

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

### Component-value optimizer (FR-P4)

- `optimization/variables.py` — `TunableParam` + `tunable_params` (every reactive/R
  nominal, including LC/Brune sub-parts and non-ideal L/C) and `apply_values`
  (returns a copy with new values).
- `optimization/objectives.py` — `limit_residuals` (per-sample, per-bound
  violations `≥ 0`) and `residual_norm`.
- `optimization/constraints.py` — `relative_bounds` (±`bound_pct` box, floored > 0).
- `optimization/solvers.py` — `OptimizeMethod` (least_squares / nelder_mead /
  differential_evolution / dual_annealing), `OptimizationConfig` (bound_pct,
  max_iter, backend, seed), `OptimizationResult` (initial/final cost, values,
  circuit, improvement) and `optimize_circuit` (guaranteed never worse than the
  nominal start).
- `services/session.py` — `DesignSession.optimize(config)` (no mutation).
- CLI — `filterdesk optimize … --limits limits.json [--method] [--bound]
  [--max-iter] [--json]`.
- GUI — **Design → Optimize to limits…** opens `OptimizeDialog` (method/bound/
  max-iter), runs off-thread, applies the tuned circuit through
  `EditCircuitCommand` (undo/redo) and re-analyzes; the status bar shows the
  cost change.
- GUI limits editor — the **Limits** dock gains an **Add limit** preset menu
  (passband/stopband |S21|, return loss, VSWR, Smith |S11|/|S22|); adding a
  preset selects the new row for inline editing, and enabled limits drive the
  optimizer.

### Per-part continuous tune (FR-U2)

- `services/retune.py` — `nudge_value(value, step_fraction, direction)`
  (multiplicative `value·(1 ± step)`, must stay positive).
- `services/session.py` — `element_steps` map (per-part relative step, default
  2%), `step_fraction` / `set_element_step`, and `nudged_value` (pure) /
  `nudge_element` (in-place).
- GUI — **Design → Component → Tune ±step / Set tune step…** (Design menu and
  schematic context menu), **Tune +** / **Tune −** toolbar buttons, and window
  shortcuts **Ctrl+]** / **Ctrl+[** on the selected component; each nudge goes
  through `SetElementValueCommand` (undo/redo) and the existing 80 ms debounce
  re-analyzes (NFR-4: debounced, and a running analyze thread is cancelled before
  a new one starts).
- Marker-driven retune — a marker can be bound to a spec landmark
  (`cutoff` / `f_center` / `bandwidth`) via the Markers dock **Binds** column;
  dragging that marker retunes the spec and re-synthesizes through
  `RetuneMarkerCommand` (spec + circuit + markers in one undo step). Plain
  marker drags only move the marker.

## Design notes

- Retune only produces a **validated spec**; the caller re-synthesizes. This keeps
  the transform pure and testable, and reuses existing validation (ADR-006 cutoff
  conventions, topology↔response rules).
- `scale_response` preserves the fractional bandwidth for BP/BS, so the relative
  shape does not change.
- The optimizer drives **per-sample** limit residuals (not a single worst point):
  the richer residual vector gives `least_squares` a usable numerical gradient
  where a kinked worst-point residual stalls. Nelder–Mead minimizes the squared
  norm and usually reaches zero violation on easy targets.

## Deferred (future polish, not blocking)

- Composable objectives beyond limit residuals (blueprint §20).

## Tests

- `tests/unit/test_retune.py` — cutoff/center/bandwidth retune, response-type
  guards, LP/HP and BP/BS scaling (fractional-BW preservation), non-positive
  factor rejection, impedance retune, `nudge_value`, per-part step + nudge, and
  session retune/scale re-synthesis.
- `tests/unit/test_optimization.py` — tunable enumeration, `apply_values`,
  relative bounds, residual satisfaction/violation, both solvers reducing cost,
  enabled-limit and config validation, session no-mutation, and the CLI.
- `tests/unit/test_gui_smoke.py` — **Design → Scale response…** and
  **Design → Optimize to limits…** actions (dialogs + workers stubbed),
  `OptimizeDialog` and the limits-panel preset menu, per-part tune nudging
  (toolbar/menu actions + shortcuts present; value steps up/down via
  `SetElementValueCommand`).
- `tests/unit/test_marker_retune.py` — marker landmark validation/serialization,
  the Markers-panel Binds combo, and cutoff-bound marker drag retuning the spec
  (with undo) plus plain drags leaving the spec unchanged.
