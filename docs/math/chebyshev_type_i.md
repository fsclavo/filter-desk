# Chebyshev Type I — mathematical specification

- **Status:** Phase 0 specification (implementation in Phase 1)
- **Decision type:** Theory (formulas) + Recommendation (conventions per ADR-006)
- **References:** Williams & Taylor, *Electronic Filter Design Handbook*; Matthaei, Young, Jones; standard prototype tables

## 1. Definition

Low-pass magnitude-squared response (normalized ωc = 1 at **ripple edge**):

\[
|H(j\Omega)|^2 = \frac{1}{1 + \varepsilon^2\, T_n^2(\Omega)}
\]

where \(T_n\) is the Chebyshev polynomial of the first kind, order \(n\).

Passband ripple \(A_p\) (dB) relates to \(\varepsilon\) by:

\[
\varepsilon = \sqrt{10^{A_p/10} - 1}
\]

## 2. Required inputs

| Symbol | Meaning | Milestone |
| --- | --- | --- |
| \(n\) | Order | 7 |
| \(A_p\) | Passband ripple (dB) | 0.01 |
| \(f_c\) | Cutoff (Hz), ripple-edge | 140×10⁶ |
| \(Z_S, Z_L\) | Port resistances (Ω) | 50, 50 |
| Topology | Ladder realization | `ladder_hp_series_c_input` |

## 3. Order estimation (optional UI helper)

For stopband attenuation \(A_s\) at \(\Omega_s > 1\):

\[
n \ge \frac{\mathrm{acosh}\sqrt{(10^{0.1 A_s}-1)/\varepsilon^2}}{\mathrm{acosh}\,\Omega_s}
\]

Milestone uses **explicit order**, not estimation.

## 4. Prototype g-values (equal terminations)

Let

\[
\beta = \mathrm{asinh}(1/\varepsilon), \qquad
\gamma = \sinh(\beta / n)
\]

\[
a_k = \sin\left(\frac{(2k-1)\pi}{2n}\right), \quad
b_k = \gamma^2 + \sin^2\left(\frac{k\pi}{n}\right)
\]

\[
g_0 = 1,\quad
g_1 = \frac{2 a_1}{\gamma},\quad
g_k = \frac{4 a_{k-1} a_k}{b_{k-1}\, g_{k-1}}\ (k=2..n)
\]

\[
g_{n+1} =
\begin{cases}
1 & n\ \mathrm{odd}\\
\coth^2(\beta/4) & n\ \mathrm{even}
\end{cases}
\]

**Important:** Use \(\gamma = \sinh(\beta/n)\), **not** \(\sinh(\beta/(2n))\). The latter duplicates a common documentation error and fails published tables.

### Verification anchors

| \(A_p\) | \(n\) | \(g_1..g_n\) (approx) |
| --- | --- | --- |
| 0.1 dB | 3 | 1.03156, 1.14740, 1.03156 |
| 0.5 dB | 3 | 1.59628, 1.09669, 1.59628 |
| 0.01 dB | 7 | see golden fixture |

## 5. Poles (optional path)

Chebyshev poles lie on an ellipse in the s-plane; ladder synthesis for Phase 1 uses **g-values**, not explicit pole placement. Pole formulas may be added for elliptic/cross-checks later.

## 6. Frequency / impedance transformation

See `transforms.md`. For high-pass at \(\omega_c = 2\pi f_c\) with \(Z_0 = Z_S = Z_L\):

- LP series inductance \(g_k\) → HP series capacitance \(C = 1/(\omega_c g_k Z_0)\)
- LP shunt capacitance \(g_k\) → HP shunt inductance \(L = Z_0/(\omega_c g_k)\)

## 7. Limitations

- Equal-ripple passband; stopband monotonic.
- Even-order equal-ripple with \(g_{n+1}\neq 1\) needs careful asymmetric termination handling.
- Do **not** use SciPy digital `cheby1` as a substitute for analog prototype g-values without proving equivalence of normalization.

## 8. Validation strategy

1. Unit test g-values vs table anchors (±1e-5 relative).
2. Golden: `tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/`.
3. Phase 2: \|S21\| within ripple corridor for \(f \ge f_c\); \|S21\|→0 as \(f\to 0\).

## 9. Implementation checklist

- [ ] `synthesis/families/chebyshev_i.py`
- [ ] Unit tests for ε, β, γ, g-values
- [ ] Golden component match
- [ ] Docs stay in sync with code comments (reference this file)
