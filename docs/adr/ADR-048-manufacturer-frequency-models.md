# ADR-048: Manufacturer frequency-dependent Q/ESR models

- **Status:** Accepted
- **Date:** 2026-11-01
- **Relates to:** ADR-035, ADR-039, ADR-041

## Context

The component catalog stored single datasheet points (`Qmin`, `SRF`, DCR, ESR,
ESL) but not frequency-dependent manufacturer data. Redistributing vendor SPICE
models is not acceptable without a clear license, and the native project format
had no place for curves.

## Decision

- Add an optional `ManufacturerModel` block to catalog parts:
  - model id, source, confidence and notes;
  - sorted `Q(f)` points for inductors;
  - sorted `ESR(f)` points for capacitors.
- Interpolate in log-frequency/log-value between points and clamp outside the
  measured range.
- Persist the curves on simple `NonIdealInductor`/`NonIdealCapacitor` elements
  and in native project JSON.
- Apply curves in the ABCD analyzer:
  - inductor `R(f)=ωL/Q(f)` with DCR as a lower bound;
  - capacitor `ESR(f)` in the series R-L-C model.
- Apply catalog curves in **Apply assigned parts** for simple L/C arms.
- For series/parallel LC resonators, keep the existing constant DCR/ESR and
  report a warning that the curve is not applied.
- Do not bundle vendor SPICE decks. Users import their own datasheet/measured
  points via the component-library JSON.

## Consequences

- Manufacturer data can drive frequency-dependent loss without changing the
  circuit topology.
- The model remains a two-terminal first-order equivalent; temperature, DC
  bias, mounting and vendor simulation decks are not included.
- Composite resonators still need a future sub-part curve extension.
