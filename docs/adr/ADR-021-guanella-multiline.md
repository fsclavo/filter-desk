# ADR-021: Explicit multi-line Guanella model

- **Status:** Accepted
- **Date:** 2026-10-27
- **Relates to:** ADR-018

## Context

The boundary `BAL1` model used a single ideal transformer plus one TEM line for
Guanella and Ruthroff TLTs. That is a useful first-order approximation, but it
does not capture the parallel-input/series-output structure of a Guanella
transformer. For integer 1:N² ratios the network can be represented exactly with
N identical transmission lines.

## Decision

- For `kind="guanella"` with an integer line count, build the network explicitly:
  - all N lines have the same `Z0`, length, velocity factor and loss;
  - inputs are in parallel, outputs in series;
  - the resulting ABCD is
    `[[A/N, B], [C, N·D]]` for a step-up ratio, and its inverse for step-down.
- The line count is derived from `turns_ratio`; non-integer or non-Guanella
  ratios keep the previous transformer + TEM-line model.
- Leakage, shunt core loss and winding capacitance remain boundary elements.
- Ruthroff remains first-order (transformer + one TEM line). Common-mode
  impedance is reported as a design quantity but is not represented in the
  differential 2-port.

## Consequences

- 1:4, 1:9, 1:16, … Guanella designs now show the correct transmission-line
  frequency dependence, not just a fixed transformer ratio.
- 1:1 Guanella with zero line length reduces exactly to the ideal transformer.
- The model still has no full common-mode/EM or hardware validation.
