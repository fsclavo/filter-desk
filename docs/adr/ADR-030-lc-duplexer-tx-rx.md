# ADR-030: LC TX/RX duplexer with isolation target

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-027, ADR-028, ADR-029

## Context

A diplexer separates bands; a TX/RX duplexer additionally needs a quantified
isolation between the transmitter and receiver paths when they share an antenna.
The isolation requirement, not just the branch insertion loss, drives the filter
order and the guard band.

## Decision

- Add `DuplexerConfig` with independent TX/RX center frequencies and bandwidths,
  a minimum isolation target, a maximum insertion loss and an order search range.
- Build two band-pass branches and combine them through the N-port common-input
  model. Ports are fixed: **1 = antenna**, **2 = TX**, **3 = RX**, regardless of
  which band is higher in frequency.
- Compute:
  - TX and RX insertion loss,
  - TX and RX input return loss at the antenna port,
  - isolation in the TX band and in the RX band, using `|S32|`,
  - worst isolation across both bands.
- If no explicit order is supplied, search `min_order…max_order` and select the
  lowest order that meets the isolation and insertion-loss targets. If none
  meets them, return the best attempt and set `meets_target = false`; do not
  silently claim success.
- Expose `filterdesk duplexer` and a **Duplexer TX/RX** mode in the GUI.

## Consequences

- Users can see whether the requested isolation is actually met by the combined
  3-port network instead of inferring it from two separate filters.
- Narrow guard bands require higher orders and may still miss the target; the
  tool reports that result explicitly.
- This is still an ideal LC model. It does not include antenna impedance,
  cavity/EM effects, circulators, isolation networks, component parasitics
  beyond the selected models, thermal behavior or high-power validation. It is
  not a repeater duplexer design without those checks.
