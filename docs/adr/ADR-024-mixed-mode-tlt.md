# ADR-024: Mixed-mode 3-port boundary model and TLT SPICE export

- **Status:** Accepted
- **Date:** 2026-10-27
- **Relates to:** ADR-019, ADR-021

## Context

A balun is not fully described by a differential 2-port. The differential
response can be cross-checked as before, but common-mode behavior needs a
separate port. The boundary model must stay explicit about what is and is not
represented.

## Decision

- Add a **3-port mixed-mode boundary model** with ports:
  - input (unbalanced),
  - differential output,
  - common-mode output.
- Build `Sdd` from the existing ABCD balun model and `Scc` from the choke
  `Lm`/scalar `Zcm`. Cross-mode terms are exactly zero for a symmetric model.
  This is a **block-diagonal** boundary model, not a full asymmetric 4-port.
- Reference impedances: `Z0_input`, `Z0_diff = z_balanced`,
  `Z0_common = z_balanced/2`.
- Show five-point mixed-mode tables in the transformer Model tab and include a
  five-point array in the CLI JSON.
- Add `tlt_spice_netlist()` for integer-ratio **Guanella**:
  N `T` lines parallel at input, series at output, center-node `Lcm`/core-loss
  shunt, and a differential load. Validate the differential response against
  `Sdd21` with ngspice.
- Add a Ruthroff **1:4 step-up** bootstrap netlist: one TEM line with port 1
  across the source and port 2 from ground to the floating output; validate the
  low-frequency voltage/load match with ngspice.
- Non-integer Guanella, other Ruthroff ratios and reverse Ruthroff orientation
  keep the existing differential model; their SPICE export remains unsupported.

## Consequences

- Users can see differential and common-mode behavior separately instead of
  pretending the 2-port captures both.
- The common-mode result is a choke/center-tap estimate, not a full EM or
  asymmetric 4-port model.
- Guanella SPICE export is lossless and differential-port validated; the
  Ruthroff export is a step-up bootstrap test netlist. Common-mode fixture/EM
  validation remains future work.
