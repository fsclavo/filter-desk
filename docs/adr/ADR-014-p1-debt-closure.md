# ADR-014: P1 backlog debt closure

- **Status:** Accepted
- **Date:** 2026-10-15
- **Phase:** post-Phase 7

## Context

The P1 backlog (deferred items from completed phases) had six open entries:
B1.2 (true asymmetric synthesis), B1.5 (order estimation for more families),
B1.6 (exact even-order elliptic), B1.7 (order caps by tables), B2.1 (scikit-rf
unequal-Z), B4.3 (`PlotBackend` abstraction). We decided to implement the
tractable ones and record explicit decisions for the research-level ones.

## Decisions

### B2.1 — scikit-rf unequal-Z: **implemented**

`ScikitRFAnalyzer` now cascades every element at a single reference impedance
\(z_0=\sqrt{Z_S Z_L}\) and renormalizes the resulting two-port to
\([Z_S, Z_L]\) (`Network.renormalize`). It matches the ABCD backend to
\(<10^{-9}\) for unequal ports (50 Ω / 75 Ω).

### B4.3 — plotting backend abstraction: **implemented (minimal)**

The interactive GUI keeps using PyQtGraph directly. The *static export* path is
now behind `plotting/protocol.py::PlotBackend`, implemented by
`MatplotlibBackend` and obtained via `plotting.get_plot_backend()`. CLI and GUI
export route through the protocol so a future backend (e.g. SVG/vector) can be
swapped without touching callers.

### B1.5 — order estimation for monotonic families: **implemented (LP/HP)**

Bessel / Gaussian / Legendre have no classical closed-form order formula. A
numeric search over each family's prototype table (bisection for the pass edge
where attenuation = Ap, then check attenuation ≥ As at `ratio · ω_pass`) returns
the smallest order whose realized filter meets the spec. BP/BS remain
unsupported for these families (the band mapping needs a different formulation).

### B1.7 — order caps (Bessel/Gaussian 1–10, Legendre 2–9): **decided (keep caps)**

Prototypes are verified g-value **tables**; extending beyond them requires
prototype-generation research (pole fitting) per family and is out of scope.
The caps are enforced with clear errors, and B1.5's numeric estimator is bounded
by them. Revisit if a user needs higher orders.

### B1.2 — true asymmetric \(Z_S \neq Z_L\): **decided (accepted approximation)**

Kept the geometric-mean reactive scaling of ADR-011. A full Norton /
minimum-inductance redesign (ratio tables, transformer insertion) is a research
task with limited near-term payoff; documented as an accepted limitation.

### B1.6 — exact even-order elliptic: **decided (rejected)**

Equal-R even-order Cauer requires a transformer or unequal terminations. The
previous transformer-free `|S21|` fit could violate the requested passband
ripple (audit 2026-10-25: ~0.97 dB with Ap=0.5 dB) and order 2 could fail
outright, so even orders are now rejected with a clear validation error. Odd
orders (3, 5, 7, …) remain exact against `scipy.signal.ellipap`.

## Consequences

- Both analyzers support unequal terminations; ADR-011's skrf limitation is
  lifted.
- `filterdesk estimate-order` accepts Bessel/Gaussian/Legendre for LP/HP.
- B1.2/B1.6/B1.7 are documented limitations, not silent gaps.
