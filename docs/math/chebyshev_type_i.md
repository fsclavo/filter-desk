# Chebyshev Type I — mathematical specification

- **Status:** Implemented (odd order: closed-form g-values; even order: modified prototype, equal terminations)
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
\coth^2(\beta/2) & n\ \mathrm{even}
\end{cases}
\]

**Important:** Use \(\gamma = \sinh(\beta/n)\), **not** \(\sinh(\beta/(2n))\). The latter duplicates a common documentation error and fails published tables. For even \(n\), \(g_{n+1}=\coth^2(\beta/2)\) is the load/source ratio \(Z_L/Z_S\) of the *classical* (unequal-termination) prototype; e.g. 1.3554 at \(A_p=0.1\,\)dB for every even order.

### Verification anchors

| \(A_p\) | \(n\) | \(g_1..g_n\) (approx) |
| --- | --- | --- |
| 0.1 dB | 3 | 1.03156, 1.14740, 1.03156 |
| 0.5 dB | 3 | 1.59628, 1.09669, 1.59628 |
| 0.01 dB | 7 | see golden fixture |
| 0.1 dB | 2 | \(g_{n+1}=1.35536\) |

## 5. Even-order modification (equal terminations)

An all-pole LC ladder with **equal** terminations (\(Z_L=Z_S\)) cannot realize the
classical even-order Chebyshev response: the required \(g_{n+1}=\coth^2(\beta/2)\neq1\)
would need a transformer. FilterDesk therefore uses the *modified* even-order
Chebyshev, which relocates the lowest-frequency reflection zero to \(\Omega=0\)
while keeping the equi-ripple passband, so that \(|S_{11}(0)|=0\) and \(|S_{21}(0)|=1\).

Map each classical Chebyshev pole \(P\) (SciPy analog `cheby1` poles, \(\omega_c=1\))
by

\[
P' = \left[\sqrt{\frac{P^2 + \cos^2\!\left(\frac{\pi(n-1)}{2n}\right)}
{1 - \cos^2\!\left(\frac{\pi(n-1)}{2n}\right)}}\right]_{\text{LHP}}
\]

The mapped poles give the equi-ripple transfer function
\(H(s)=k/\prod_m (s-P'_m)\), \(k=\prod_m(-P'_m)\) (unity at DC). The realization
**cannot** use the Cauer element-value formulas; the LC values come from the
continued-fraction expansion of the input impedance

\[
Z_\mathrm{in}(s) = \frac{A(s)+F(s)}{A(s)-F(s)},
\qquad A=\prod_m (s-P'_m),\qquad
F(s)F(-s) = A(s)A(-s) - k^2
\]

with \(R_S=R_L=1\,\Omega\). Since \(F(s)\) is an even polynomial in \(s\) it is
obtained from the (non-positive real) roots of \(A(s)A(-s)-k^2\) in \(u=s^2\).
The alternating series-L / shunt-C ladder is extracted exactly; its element
values are palindromic (\(g_k=g_{n+1-k}\)), reflecting the equal terminations.
Equivalently the network is \(R_S - L_1 - C_2 - \dots - C_n - R_L\) with \(L,C>0\).

At high order the continued fraction is ill-conditioned; FilterDesk falls back
to a symmetric positive-element least-squares fit of the ladder to the mapped
\(|H(j\Omega)|\). The ripple edge is normalized to \(\Omega_c=1\) by construction
(the gain reaches the ripple floor for the last time at \(\Omega=1\)).

## 6. Poles (optional path)


Chebyshev poles lie on an ellipse in the s-plane; ladder synthesis for Phase 1 uses **g-values**, not explicit pole placement. Pole formulas may be added for elliptic/cross-checks later.

## 7. Frequency / impedance transformation

See `transforms.md`. For high-pass at \(\omega_c = 2\pi f_c\) with \(Z_0 = Z_S = Z_L\):

- LP series inductance \(g_k\) → HP series capacitance \(C = 1/(\omega_c g_k Z_0)\)
- LP shunt capacitance \(g_k\) → HP shunt inductance \(L = Z_0/(\omega_c g_k)\)

Odd-order networks use the \(g\)-value path above; even-order networks carry the
already-synthesized LP arms (series-L / shunt-C) and are transformed with the same
per-arm rules.

## 8. Limitations

- Equal-ripple passband; stopband monotonic.
- Even orders use the modified response (section 5): equal terminations are exact,
  but the reflection zero at \(\Omega=0\) means the network is determined numerically
  (continued fraction below \(n\!\approx\!12\), least-squares fit above) rather than
  by closed-form \(g\)-values.
- Unequal ports use the exact output transformer (ADR-017). Even-order Chebyshev I still uses the modified equal-termination network, so its stopband differs from classical tables.
- Do **not** use SciPy digital `cheby1` as a substitute for analog prototype g-values without proving equivalence of normalization.

## 9. Validation strategy

1. Unit test g-values vs table anchors (±1e-5 relative).
2. Golden: `tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/`.
3. Phase 2: \|S21\| within ripple corridor for \(f \ge f_c\); \|S21\|→0 as \(f\to 0\).
4. Even order: \|S21\| ripple = \(A_p\) over \([0,f_c]\), \|S21(0)\|=1, palindromic arms.

## 10. Implementation checklist

- [x] `synthesis/families/chebyshev_i.py`
- [x] Unit tests for ε, β, γ, g-values
- [x] Golden component match
- [x] Even-order modified prototype (equal terminations)
- [ ] Docs stay in sync with code comments (reference this file)
