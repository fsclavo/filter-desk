# ADR-010: Band-pass / band-stop frequency definition

- **Status:** Accepted
- **Date:** 2026-09-30
- **Phase:** 4

## Context

LP/HP use a single cutoff. BP/BS need a center frequency and a bandwidth. Edge-only specs (\(f_1\), \(f_2\)) must map uniquely to synthesis parameters \(\omega_0\) and \(B\).

## Decision

1. **Primary UI/API fields:** `f_center_hz` (\(f_0\)) and `bandwidth_hz` (\(\mathrm{BW} = f_2 - f_1 > 0\)).
2. **Center definition:** geometric — \(f_0 = \sqrt{f_1 f_2}\) when edges are given; synthesis uses \(\omega_0 = 2\pi f_0\), \(B = 2\pi\cdot\mathrm{BW}\).
3. **Edge meaning** follows the family cutoff convention (ADR-006):
   - Butterworth: \(-3\,\mathrm{dB}\) edges
   - Chebyshev Type I: ripple-edge edges
4. **Transforms** use the classic LP→BP / LP→BS element replacements (see `docs/math/transforms.md`).

## Consequences

- Spec JSON for BP/BS omits `cutoff_hz` (or ignores it).
- Default analysis sweep spans roughly \(f_0/20\) … \(20 f_0\) (same spirit as LP/HP).
