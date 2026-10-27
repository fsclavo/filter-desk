# ADR-023: Winding DCR estimate and persisted option

- **Status:** Accepted
- **Date:** 2026-10-27
- **Relates to:** ADR-016, ADR-021

## Context

The transformer/balun designer already reports Lm, leakage, wire gauge and a
single-layer fit, but not the DC resistance of each winding. It also did not
persist an explicit option label, although the selected turns were stored.

## Decision

- Estimate DC copper resistance at 20 °C from:
  - the core mean turn length (`ToroidCore.mean_turn_mm`);
  - the selected AWG diameter;
  - `R = rho_Cu * length / area`.
- Store per-winding `dcr_primary_ohm`/`dcr_secondary_ohm` in `BalunSpec` and the
  native project (optional, backward compatible).
- Store an explicit `winding_option` label (`n_primary:n_secondary`) in
  `BalunSpec` and the BOM.
- Show DCR and leakage in the dialog options table, the selected-design summary,
  CLI text/JSON and BOM.
- For the BAL1 BOM row, `dcr_ohm` is the sum of both winding estimates and the
  parasitic text shows the low/high split.

## Consequences

- Users can compare winding options by copper loss/resistance, not just turns.
- DCR is a 20 °C copper estimate; skin/proximity effects, lead length, solder
  joints and temperature rise are not included.
- The existing copper-loss thermal estimate remains the source for hot
  temperature; DCR is informational for loss/voltage-drop checks.
