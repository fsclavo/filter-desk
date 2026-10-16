# ADR-015: Cross-cutting (§D) decisions

- **Status:** Accepted
- **Date:** 2026-10-16
- **Phase:** post-Phase 11

## Context

The backlog §D "cross-cutting / open questions" listed items that needed a
decision or a small piece of work: layer-rule enforcement, GUI test tooling, the
native project extension, the optimiser's method set, product naming, and whether
to add native acceleration.

## Decisions

### Layer rules enforced in CI — **adopted**

`import-linter` contracts (in `pyproject.toml`, run via `uv run lint-imports`,
wired into `.github/workflows/test.yml`) enforce:

- `filterdesk.domain` is independent (no outbound deps to analysis/synthesis/
  services/gui/io/montecarlo/optimization/components_std/plotting); the sole
  allowed exception is the shared `filterdesk.analysis.types` DTO used by project
  persistence.
- `filterdesk.analysis` (core) does not depend on GUI/services/synthesis/IO/engines.
- `filterdesk.synthesis` does not depend on GUI/services/IO/MC/optimizer/plotting.
- `filterdesk.montecarlo` / `filterdesk.optimization` are engine services, not
  importing GUI/services/synthesis.
- **Only** `filterdesk.analysis.adapters.skrf_analyzer` imports `scikit-rf`
  (reinforces ADR-001).

### Native project extension — **`.filterdesk.json`**

The native project format stays **plain, human-readable JSON** with the
`.filterdesk.json` extension. Rationale: diff-friendly, greppable, no bespoke
compression; project files are small (a circuit + spec + overlays). A compressed
`.fdsk` container is not adopted (compression belongs at the archive/transport
layer, not in the authoring format).

### pytest-qt — **adopted**

`pytest-qt` is a dev dependency used for real GUI interaction tests
(`tests/unit/test_gui_qtbot.py`, e.g. clicking a toolbar action). Offscreen
smoke tests remain for construction/menu wiring; `pytest-qt` is reserved for
genuine input-event behaviour.

### Global optimizers — **added**

`optimization/solvers.py` gained `differential_evolution` and `dual_annealing`
(bounded, with `OptimizationConfig.seed`). A safeguard ensures the optimiser
never returns a result worse than the nominal starting point.

### Product naming / trademark — **decision**

The product name is **FilterDesk** (binary `filterdesk`). It does not use the
ELSIE/Tonne names or marks and is not affiliated with them; ELSIE is referenced
only as a functional comparison. No trademark registration is planned at this
time; if the project is distributed commercially this should be revisited.

### Native acceleration — **not pursued**

The ABCD (NumPy) path is sufficient: 10k Monte-Carlo trials over 512 points run
in ≈5 s. A Rust/C extension is unnecessary; revisit only if profiling shows the
ABCD path is the bottleneck for interactive/optimisation workloads.

## Consequences

- Architecture regressions (GUI importing skrf, domain importing engines, …) fail
  CI instead of silently eroding the layering.
- The authoring format stays inspectable and version-control friendly.
- The optimiser now covers both smooth local (least squares / Nelder–Mead) and
  global (DE / dual annealing) search, and can never worsen the nominal design.
