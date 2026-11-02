# ADR-047: DXF layout export for external EM

- **Status:** Accepted
- **Date:** 2026-11-01
- **Relates to:** ADR-046

## Context

FilterDesk has no field solver. A routed/EM-validated layout cannot be claimed
from the internal circuit model, but users need a portable geometry to run
their own EM or PCB tool.

## Decision

- Export the conceptual coupled-line sketch as minimal ASCII DXF (AC1009, mm):
  - `TOP_COPPER` layer with filled trace solids;
  - `BOARD_OUTLINE` layer with the board rectangle.
- Keep SVG as the visual preview; infer SVG/DXF from the output suffix in the
  GUI and CLI.
- State explicitly that the DXF is a geometry handoff, not a routed fabrication
  layout and not an EM-validated design.
- Do not add Gerber, copper thickness, bends, vias or discontinuity compensation
  in this step.

## Consequences

- Users can import the sketch into a field solver or CAD tool for further work.
- The DXF is suitable for early EM exploration, not for direct fabrication.
- A future layout engine must add routed connections and validation before a
  manufacturing claim.
