# ADR-034: Versioned system project (`.fdsys.json`)

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-032, ADR-033

## Context

The system designer was ephemeral: closing it discarded the band plan, order,
sweep, E-series and parasitic settings. Exporting S-parameters or a BOM did not
allow reopening and continuing the design.

## Decision

- Add a versioned JSON document with `format: filterdesk.system` and
  `version: 1`.
- Store only **inputs/configuration**:
  - system kind;
  - band labels/centers/bandwidths;
  - LP/HP cutoffs or duplexer TX/RX fields;
  - order, family, ripple/stopband and Z0;
  - sweep;
  - selected E-series;
  - parasitic assumptions.
- Do **not** store derived S-matrices, circuits or metrics; reopen rebuilds
  them deterministically.
- Expose **Open system…** and **Save system…** in the designer. Opening applies
  the controls and immediately redesigns.
- Reject unknown formats/versions, unsupported kinds and incomplete
  kind-specific fields with `SystemProjectError`.

## Consequences

- System designs can be saved, reopened and reproduced without retyping.
- Files stay small and human-readable.
- Changing the model or synthesis code can change the rebuilt result; the file
  records the inputs, not a frozen numerical result.
- This is separate from the single-filter native project format.
