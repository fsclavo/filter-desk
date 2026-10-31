# ADR-033: System-level finite-Q / parasitic reanalysis

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-016, ADR-032

## Context

E-series snapping made the BOM and ideal LC response consistent, but real
inductors and capacitors still need finite Q, DCR, parasitic capacitance,
self-resonance, ESR and ESL. Applying those only to the BOM would repeat the
ideal-vs-BOM mismatch.

## Decision

- Add `SystemParasiticsConfig` and `apply_system_parasitics`: convert every
  branch with the existing `nonidealize_circuit`, reanalyze on the stored sweep,
  rebuild the combined N-port and recompute the system metrics.
- Use each branch's center (BPF) or cutoff (LP/HP) as the Q reference frequency.
- Expose a **Parasitics…** dialog in the system designer for inductor Q, DCR,
  Cp, SRF, capacitor ESR and ESL. The model is global across branches.
- Store the applied model in the report/BOM notes so the exported values and
  assumptions travel together.
- Keep the model first-order: constant Q at one reference frequency, optional
  DC/skin loss model, and no thermal, saturation or EM validation.

## Consequences

- Metrics, curves, schematics and BOM refer to the same non-ideal circuits.
- A finite Q or ESR can materially degrade insertion loss, rejection,
  return loss and duplexer isolation; the normal metrics expose that.
- This is not a full vendor component model or a thermal/high-power simulation.
