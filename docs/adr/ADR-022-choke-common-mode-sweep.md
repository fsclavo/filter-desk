# ADR-022: Common-mode sweep for choke baluns

- **Status:** Accepted
- **Date:** 2026-10-27
- **Relates to:** ADR-021

## Context

The differential 2-port cannot represent a choke's common-mode stopband. The
previous model only reported a scalar `Zcm`/attenuation at the lowest frequency,
which hides the frequency dependence that matters for a common-mode choke.

## Decision

- Persist the choke magnetizing inductance in `BalunSpec` (optional project
  field, backward compatible).
- Add `analysis.common_mode.common_mode_sweep()`:
  - `Zcm(f) = j·2πf·Lm` when `Lm` is available;
  - fall back to the scalar `common_mode_impedance_ohm`;
  - series-choke attenuation `|S21| = 2Z0 / (2Z0 + Zcm)` with
    `Z0 = z_unbalanced_ohm`.
- The sweep is **separate** from the differential filter 2-port. It does not
  change S11/S21 of the filter and is not a full 3-port/4-port mixed-mode model.
- Show a five-point table in the transformer dialog and emit a five-point
  `common_mode_sweep` array in the CLI JSON. Keep the scalar `Zcm`/attenuation.

## Consequences

- Choke users can see how common-mode rejection rises with frequency.
- The model remains a first-order series-choke estimate; leakage, winding
  capacitance, core loss and fixture asymmetry are not included.
- Full common-mode/EM validation remains future work.
