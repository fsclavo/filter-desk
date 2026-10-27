# ADR-025: Microstrip dispersion in distributed analysis

- **Status:** Accepted
- **Date:** 2026-10-27
- **Relates to:** ADR-018

## Context

The distributed elements stored a single quasi-static `eeff`/`Z0`, so a short
HF line and a millimetre-wave line used the same propagation constant. That is
not acceptable once distributed designs are used beyond a narrow band.

## Decision

- Store substrate `er` and height on `MicrostripLineElement` /
  `MicrostripStubElement` (optional project fields).
- Add `analysis.microstrip_dispersion.dispersion_eeff_z0()` using the
  Kirschning-Jansen closed-form effective-permittivity and impedance dispersion.
- Use the dispersive `eeff(f)`/`Z0(f)` in line ABCD and open/short stub input
  impedance. If geometry is missing, fall back to the stored static values.
- Loss remains the first-order static `loss_db_per_m`; conductor/dielectric loss
  dispersion and discontinuities are not added in this step.
- Distributed synthesis records `er`/height from the chosen substrate.

## Consequences

- Existing distributed designs now get frequency-dependent phase/impedance,
  while old projects without geometry remain backward compatible.
- High-order numerical fits are evaluated with dispersion included; the response
  gate still rejects inadequate designs.
- Discontinuities, radiation, surface roughness beyond the static loss model and
  full EM remain future work.
