# ADR-039: Apply assigned real parts to the analysis

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-035, ADR-038

## Context

ADR-038 kept part assignment as BOM metadata only. That leaves the BOM and the
simulation referring to different values. The next step is to apply the selected
part value and the available datasheet parasitics to the circuit.

## Decision

- Add `apply_assigned_parts`: for each assigned simple L/C, replace the value
  with the library part value and apply DCR/SRF (inductor) or ESR/ESL
  (capacitor) when available. Rebuild the system and recompute all metrics.
- For composite LC/Brune sub-parts (BPF branches), replace the sub-part value
  but do **not** apply a parasitic model yet; report a warning. The composite
  element does not carry separate per-subpart loss fields.
- Manual assignment is applied if the user requests it; the tool does not
  silently rewrite the circuit when parts are assigned.
- Add **Apply assigned parts** to the designer. BOM/report notes record how many
  models were applied and any composite warnings.
- This remains a catalog-level model: missing ESR/ESL/Q data stays unset; it is
  not a vendor model or a thermal/power/EM simulation.

## Consequences

- Simple L/C systems (LPF/HPF diplexers, etc.) can be reanalyzed with real part
  values and available parasitics.
- BPF composite branches receive real values but still need a future
  per-subpart non-ideal composite model.
- Applying a far-away manual part can materially degrade the response; the
  recomputed metrics expose it.
