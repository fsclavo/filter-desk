# ADR-032: E-series snap with system reanalysis

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-027, ADR-028, ADR-029, ADR-030, ADR-031

## Context

The system designers initially analyzed ideal branch values while the BOM could
be snapped independently to an E-series. That made the exported component list
inconsistent with the response, isolation and crossover metrics.

## Decision

- Add `snap_system_design`: snap every branch with the existing
  `snap_circuit` logic, reanalyze all branches on the stored sweep, rebuild the
  combined N-port and recompute the system metrics.
- Use `SnapStrategy.PRESERVE_LC_RESONANCES` by default so resonant arms keep
  their L·C product as close as possible.
- Store the sweep in each system design so reanalysis uses the same grid.
- Expose an **E-series snap** selector (None/E24/E48/E96) in the designer. The
  displayed curves, metrics, schematic and BOM all use the snapped circuits.
- In the system CLI, `--bom-series` now means **snap and reanalyze**, not
  BOM-only snapping. The BOM notes the applied series and maximum delta.
- If snapping makes a duplexer miss its isolation target, the normal
  `meets_target` flag reports that; it is not hidden.

## Consequences

- BOM values, schematics and simulated metrics refer to the same circuit.
- Snapping can degrade insertion loss, rejection, return loss or isolation; the
  user sees the recomputed result rather than an ideal-only response.
- The designer no longer offers a second independent E-series choice at BOM
  export time; grouping remains optional.
- This is still an ideal LC model; E-series snap does not add parasitics,
  thermal or power validation.
