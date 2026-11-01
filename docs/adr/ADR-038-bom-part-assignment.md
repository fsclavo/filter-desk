# ADR-038: Real-part assignment to the BOM

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-035

## Context

The component catalog can list real MPNs, but a design BOM still needs a mapping
from each physical L/C to a selected part. The mapping must not silently change
the analyzed circuit or pretend that catalog data is a full electrical model.

## Decision

- Add `assign_nearest_parts`: for each physical L/C in each branch, choose the
  nearest same-kind library part within a configurable maximum value delta.
  Components outside the threshold are reported as unassigned.
- Add a **PartAssignmentDialog** with:
  - a BOM-component table;
  - a filtered library table sorted by value distance;
  - **Auto-assign**, **Clear**, **Assign selected** and **Load library…**.
- Manual assignment is always allowed; automatic assignment is conservative.
- Store assignments as `branch:ref -> LibraryPart`.
- Include manufacturer, MPN, package and part id in BOM rows, combined CSV,
  Markdown/HTML build sheets and the HTML/PDF system report.
- Assignment is **BOM metadata only** in v1: it does not replace circuit values,
  apply the part's parasitics, or alter the simulation. Users must apply
  E-series/parasitics separately if desired.

## Consequences

- Users can attach real orderable parts to a design without conflating catalog
  data with simulation models.
- BOM/report exports show the selected MPNs.
- Automatic matching can leave many parts unassigned when the library is small;
  this is intentional.
- Full per-part electrical model application remains future work.
