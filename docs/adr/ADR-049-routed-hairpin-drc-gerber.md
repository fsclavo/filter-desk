# ADR-049: Routed hairpin geometry, DRC and Gerber handoff

- **Status:** Accepted
- **Date:** 2026-11-06
- **Relates to:** ADR-044, ADR-045, ADR-046, ADR-047

## Context

The coupled-line BPF dialog already produces to-scale sketches. The edge and
interdigital modes remain conceptual: edge sections are drawn separately and
interdigital lines would need shorting vias. The hairpin mode is different:
each resonator is a continuous U-shaped trace with an idealized bend, so it can
serve as a first routed geometry handoff.

FilterDesk still has no field solver. Geometry can be checked for manufacturing
rules and exported, but the electrical response of the routed board is not
validated by the internal narrowband model.

## Decision

- Treat **Hairpin** as the routed mode. Its resonators are connected traces; the
  UI label is **Hairpin (routed)**.
- Add a DRC pass before Gerber export:
  - minimum trace width;
  - minimum gap between different nets, including parallel and crossing traces;
  - board-edge margin;
  - zero-length/zero-width segments;
  - reject non-routed edge/interdigital modes for Gerber output.
- Export RS-274X copper and board-outline Gerbers plus an Excellon drill file.
  The default drill file has no holes; an API accepts optional mounting/via
  holes.
- Keep the DXF/SVG sketch path. Do not claim EM validation, impedance control,
  discontinuity compensation, copper thickness or via modeling.
- State the limits in the GUI, CLI JSON and documentation.

## Consequences

- Users get a manufacturable starting geometry for a hairpin filter, with
  explicit DRC failures instead of silent bad geometry.
- The electrical design still requires a field solver or VNA validation.
- Edge-coupled and interdigital modes remain sketches until a real routing/via
  model is implemented.
