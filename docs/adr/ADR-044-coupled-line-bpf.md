# ADR-044: Coupled-line bandpass filter electrical synthesis

- **Status:** Accepted
- **Date:** 2026-11-01
- **Relates to:** ADR-018, ADR-020, ADR-043

## Context

The distributed workflow could only realize low-pass stepped-impedance
microstrip filters. A first coupled-line capability is needed before hairpin,
interdigital or EM-level layout synthesis.

A full coupled-line design requires coupled microstrip width/gap synthesis,
dispersion, discontinuities, open-end effects and EM validation. Those pieces
are not available in FilterDesk yet.

## Decision

- Add a narrowband parallel-coupled half-wave-resonator BPF synthesis:
  - Butterworth (any order 1–9) and Chebyshev-I (odd order only, equal 50 Ω
    terminations);
  - J-inverter values from the low-pass prototype and fractional bandwidth;
  - even/odd impedances per section from the standard coupled-line inverter
    relations;
  - ideal 2-port response from cascaded J-inverters and shunt resonators.
- Expose the section table (J/Y0, Z0e, Z0o, coupling) in the GUI and CLI.
- Export the ideal response as Touchstone `.s2p`.
- Mark the result **experimental** and state that physical width/gap, layout,
  dispersion, discontinuities and EM coupling are not synthesized.
- Add **Design → Coupled-line BPF…** and `filterdesk coupled-line`.
- Keep hairpin/interdigital/EM layout synthesis out of scope for this ADR.

## Consequences

- Users can size the even/odd impedance targets of a coupled-line BPF and
  compare its ideal response with a VNA/EM simulation.
- The design is not fabrication-ready: a field solver or coupled-microstrip
  calculator is still required for width/gap and layout.
- A future release can build hairpin/interdigital layouts on this electrical
  foundation.
