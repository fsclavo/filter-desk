# Chebyshev Type I — mathematical specification

- **Status:** Implemented (closed-form g-values for odd and even orders; even orders use an ideal output transformer)
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

## 5. Even-order realization (classical + output transformer)

An even-order all-pole LC ladder has an unequal classical termination ratio
\(g_{n+1}=\coth^2(\beta/2)\neq1\). FilterDesk uses the **classical**
g-values and places an ideal output transformer (ADR-017):

\[
n=\frac{N_p}{N_s}=\sqrt{\frac{Z_S}{Z_L}},\qquad Z_{in,primary}=n^2 Z_L=Z_S
\]

The response and element values therefore match the textbook even-order
Chebyshev tables. The earlier modified equal-termination prototype was retired.
For \(Z_S=Z_L=50\,\Omega\), the transformer ratio is
\(\sqrt{g_{n+1}}\) (e.g. 1.164 for \(A_p=0.1\,\)dB).

## 6. Poles (optional path)


Chebyshev poles lie on an ellipse in the s-plane; ladder synthesis for Phase 1 uses **g-values**, not explicit pole placement. Pole formulas may be added for elliptic/cross-checks later.

## 7. Frequency / impedance transformation

See `transforms.md`. For high-pass at \(\omega_c = 2\pi f_c\) with \(Z_0 = Z_S = Z_L\):

- LP series inductance \(g_k\) → HP series capacitance \(C = 1/(\omega_c g_k Z_0)\)
- LP shunt capacitance \(g_k\) → HP shunt inductance \(L = Z_0/(\omega_c g_k)\)

Odd- and even-order networks use the \(g\)-value path above; the output
transformer handles the even-order classical load ratio and any unequal ports.

## 8. Limitations

- Equal-ripple passband; stopband monotonic.
- Even orders use the classical g-values and an ideal output transformer
  (section 5); response/values match the textbook tables.
- Unequal ports also use the exact output transformer (ADR-017).
- Do **not** use SciPy digital `cheby1` as a substitute for analog prototype g-values without proving equivalence of normalization.

## 9. Validation strategy

1. Unit test g-values vs table anchors (±1e-5 relative).
2. Golden: `tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/`.
3. Phase 2: \|S21\| within ripple corridor for \(f \ge f_c\); \|S21\|→0 as \(f\to 0\).
4. Even order: response matches `scipy.signal.cheb1ap` (within 0.15 dB) with the output transformer; ripple = \(A_p\) and \(|S21(f_c)|=A_p\).

## 10. Implementation checklist

- [x] `synthesis/families/chebyshev_i.py`
- [x] Unit tests for ε, β, γ, g-values
- [x] Golden component match
- [x] Classical even-order g-values + output transformer
- [ ] Docs stay in sync with code comments (reference this file)
