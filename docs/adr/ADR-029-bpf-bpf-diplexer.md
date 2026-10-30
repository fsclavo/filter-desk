# ADR-029: BPF+BPF diplexer extension

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-027, ADR-028

## Context

The LPF+HPF diplexer covers split-band systems, but preselector banks and
separate low/high operating bands need two band-pass branches with independent
centers and bandwidths.

## Decision

- Add `BandDiplexerConfig` with `low_center_hz`, `low_bandwidth_hz`,
  `high_center_hz` and `high_bandwidth_hz`.
- Build two `band_pass` specifications with the shared family, order,
  ripple/stopband rules and reference impedance.
- Compute each passband with the same BPF edge convention used elsewhere
  (`band_edges`). Reject overlapping passbands and require the analysis sweep to
  cover both passbands.
- Keep the fixed port order: **1 = common**, **2 = low band**, **3 = high
  band**.
- Reuse `evaluate_diplexer_bands` for insertion loss, out-of-band transmission,
  input return loss and crossover.
- Expose the design as `filterdesk band-diplexer` and as the **BPF + BPF** mode
  in **Tools → Diplexer designer…**.

## Consequences

- LPF+HPF and BPF+BPF share the same N-port combination and metric definitions.
- BPF branches are ideal LC ladders; passband edges follow the ripple/stopband
  convention of the selected family, so the reported band may differ slightly
  from the entered nominal bandwidth.
- The same limits as ADR-028 apply: no antenna, cavity, isolation network,
  thermal or high-power validation.
