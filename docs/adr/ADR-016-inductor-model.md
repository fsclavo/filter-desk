# ADR-016 — Real inductor model (Q(f), SRF, DC bias, winding)

## Status

Accepted (Phase 12).

## Context

The original `NonIdealInductor` carried a constant series resistance (DCR / a
finite Q at one frequency) and an optional parallel capacitance. That is enough
for a first loss estimate, but not for a real HF/VHF part:

- Q changes with frequency and the series resistance rises with skin effect.
- Inductance rolls off near self-resonance and drops with DC bias.
- A build sheet wants the physical winding (core, turns, wire gauge).

The project already ships toroid and air-core calculators (`components_std/toroid`,
`components_std/air_coil`) and their CLI/GUI front-ends.

## Decision

Extend `NonIdealInductor` with optional fields (backward compatible defaults):

| Field | Meaning |
| --- | --- |
| `q_ref`, `q_frequency_hz` | unloaded Q at a reference frequency |
| `srf_hz` | self-resonant frequency (overrides `parallel_capacitance_f`) |
| `loss_model` | `"constant"` or `"dc_skin"` |
| `dc_current_a`, `saturation_current_a` | DC-bias derating inputs |
| `winding` (`WindingSpec`) | core/material/turns/wire provenance for reports |

**Series resistance.** `reference_resistance_ohm` is `series_resistance_ohm` when
non-zero, otherwise `2π·f_ref·L/Q`. `loss_model="dc_skin"` scales it by
`max(1, sqrt(f/f_ref))` (monotonic, no decrease below the reference resistance).

**Self-resonance.** When `srf_hz` is set, the effective parallel capacitance is
`1/((2π·srf)²·L)`; otherwise `parallel_capacitance_f` is used.

**DC bias.** The effective inductance is
`L_eff = L / (1 + (I_dc / I_sat)²)`. This is a first-order, core-agnostic roll-off
(not a vendor saturation curve). With no `saturation_current_a` or a zero DC
current the factor is 1.

**Realization.** `services/inductor_realization.py` turns a design from the
toroid/air-core calculators into a `NonIdealInductor`: achieved L, DCR from the
wire length and bare-copper diameter, winding provenance, and (for cores with a
`Bsat`) `I_sat = Bsat·N·Ae/L`. The GUI applies it to the selected inductor through
the normal undoable circuit edit; the build sheet prints the winding columns.

## Consequences

- Old projects and elements without the new fields behave exactly as before.
- The model is documented as approximate: skin effect is a simple `sqrt(f)`
  law, DC derating is not core-specific, and air-core coils do not model SRF/Q
  (the calculators say so). Iron-powder cores have no `Bsat` in the table, so
  no saturation current is derived for them.
- Persistence adds optional keys to `nonideal_inductor`; `FORMAT_VERSION` stays
  at 1 (unknown fields were already preserved by ADR-004).
- The analysis layer stays independent of synthesis/services; ideal helpers live
  in the domain and the LCD (least common denominator) analysis adapter.
