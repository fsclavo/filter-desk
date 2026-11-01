# ADR-035: Curated component catalog v1

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-016, ADR-032, ADR-033

## Context

The design flow can synthesize, snap to E-series and apply first-order
parasitics, but it does not expose real manufacturer part numbers. A full vendor
model database is large and has data/licensing constraints, so the first step is
a small catalog with provenance and no invented model data.

## Decision

- Add a versioned `filterdesk.components` JSON format with catalog fields:
  manufacturer, MPN, kind, value, package, tolerance, voltage/current, DCR, SRF,
  Q min, optional ESR/ESL, source URL and notes.
- Ship a small starter catalog of real Murata C0G 0603 capacitors and Coilcraft
  0603CS inductors. Only values that can be stated from public datasheet tables
  are populated; model-level fields remain unset when not directly available.
- Provide search/filter by kind, MPN, value, package and notes.
- Provide JSON import/export so users can maintain their own library without
  redistributing vendor data.
- Expose the catalog through **Tools → Component library…** and the
  `filterdesk components` CLI.
- This v1 is **catalog-only**: it does not automatically replace circuit values,
  apply vendor models or assign parts to BOM rows yet.

## Consequences

- Users can find real MPNs and copy them into a BOM/order.
- The project does not claim that catalog-level values are complete models.
- Automatic nearest-part matching and BOM assignment are future increments.
- Manufacturer data must be verified against the current datasheet before
  ordering; source links and notes are stored with each part.
