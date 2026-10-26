# ADR-017 — Exact unequal terminations via an ideal output transformer

- **Status:** Accepted (2026-10-26)
- **Supersedes:** ADR-011 (geometric-mean scaling) for realization
- **Related:** ADR-003 (analyzers), ADR-016 (real inductors)

## Context

ADR-011 scaled reactive elements by \(Z_0=\sqrt{Z_S Z_L}\) and terminated the
ladder directly with \(Z_S/Z_L\). That kept the port impedances but did not give
the equal-termination prototype response for \(Z_S\neq Z_L\).

## Decision

Design the ladder for the **source** impedance and place an **ideal output
transformer** between the ladder and the load:

\[
n=\frac{N_p}{N_s}=\sqrt{\frac{Z_S}{Z_L}},\qquad
Z_{in,primary}=n^2 Z_L=Z_S
\]

`Circuit.output_transformer_ratio` stores \(n\) (1.0 = no transformer). Both
analyzers apply the ABCD matrix
\(\begin{bmatrix}n&0\\0&1/n\end{bmatrix}\) at the output, so the achieved
response equals the equal-\(Z_S\) prototype **exactly**. The GUI component
table, project file and build sheet/BOM show a `T1` entry.

Even-order Chebyshev I now uses its **classical** equal-ripple prototype and
the output transformer (even for 50/50 ports), so its response and element
values match textbook tables. Even-order elliptic remains rejected: its exact
equal-R realization needs an unequal-R Cauer synthesis, which is a separate
task.

## Consequences

- Exact unequal-port response for all equal-R prototypes (Butterworth, odd
  Chebyshev I, Chebyshev II, odd elliptic, Bessel, Gaussian, Legendre,
  constant-K, m-derived).
- No change for \(Z_S=Z_L\) (ratio 1.0).
- Project JSON is backward compatible (missing field defaults to 1.0).
- The SPICE netlist exports the transformer exactly with a VCVS/CCCS pair and a
  0 V current-sense source. LTspice `.asc` embeds the same directives; Qucs
  `.sch` uses a best-effort `Tr` component (ratio orientation should be checked
  in Qucs).
