# ADR-046: Conceptual coupled-line layout sketches

- **Status:** Accepted
- **Date:** 2026-11-01
- **Relates to:** ADR-044, ADR-045

## Context

The coupled-line BPF now produces electrical targets and first-pass width/gap,
but there was no visual check of the physical arrangement. A routed fabrication
layout needs bend/discontinuity models, a real connection topology and EM
validation, none of which are available yet.

## Decision

- Add **conceptual** to-scale SVG sketches for:
  - straight edge-coupled sections;
  - folded hairpin resonators;
  - interdigital resonators.
- Use the synthesized section width, gap and quarter-wave length.
- For hairpin/interdigital sketches use uniform average width/gap and idealized
  bends; label the result clearly as conceptual.
- Export SVG from the GUI and `filterdesk coupled-line --layout …`.
- Do not claim routing, fabrication readiness, discontinuity compensation or
  EM validation.
- Keep a true routed hairpin/interdigital layout and EM engine out of scope.

## Consequences

- Users can inspect approximate proportions and export a sketch for discussion.
- The sketch is not a fabrication drawing; copper thickness, bends, open-end
  effects, dispersion and coupling discontinuities are absent.
- A future layout engine must add routed geometry and field-solver/VNA checks
  before any fabrication claim.
