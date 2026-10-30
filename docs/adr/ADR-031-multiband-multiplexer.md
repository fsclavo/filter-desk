# ADR-031: Multi-band BPF multiplexer / triplexer

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-027, ADR-028, ADR-029

## Context

After two-branch diplexers, three or more passbands need the same common-input
model without duplicating analysis code for every band count.

## Decision

- Add a general `MultiplexerConfig` containing a tuple of labelled bands
  (`center_hz`, `bandwidth_hz`), plus the shared filter family/order/ripple
  rules and reference impedance.
- Sort branches by center frequency and expose ports as **1 = common**, then
  each output in ascending frequency order. For the three-band GUI/CLI this is
  **1 = common, 2 = low, 3 = mid, 4 = high**.
- Build each branch with `make_bandpass_spec`, analyze all branches on one sweep
  and combine them with `SParameters.parallel_branches`.
- Report per-band insertion loss, worst out-of-band transmission to any other
  output and input return loss, plus adjacent-band crossovers.
- Validate unique labels, non-overlapping adjacent passbands and sweep coverage.
- Expose `filterdesk triplexer` and a **Triplexer (3 bands)** mode in the GUI.

## Consequences

- The N-port engine now handles 3+ branches without a triplexer-specific
  analyzer.
- The GUI currently exposes the three-band convenience mode; arbitrary N-band
  entry remains a service/CLI extension point.
- The same ideal common-node LC limits as the diplexers apply: no antenna,
  cavity, circulator, isolation network, EM, thermal or high-power validation.
