# Frequency and impedance transformations

- **Status:** Phase 4 (updated)
- **Decision type:** Theory
- **References:** Matthaei, Young, Jones; Pozar; Williams & Taylor
- **ADRs:** ADR-010 (BP/BS frequencies), ADR-011 (asymmetric Z)

## 1. Low-pass prototype

Prototype elements \(g_k\) are normalized to:

- \(\omega_c' = 1\ \mathrm{rad/s}\)
- \(Z_0' = 1\ \Omega\) (source resistance \(g_0\), load \(g_{n+1}\))

Ladder interpretation (series-first):

| \(k\) odd | series inductance \(L' = g_k\) |
| \(k\) even | shunt capacitance \(C' = g_k\) |

Shunt-first dual swaps L/C roles.

## 2. Frequency transformations (prototype → response)

Let \(s\) be the prototype complex frequency.

| Response | Mapping |
| --- | --- |
| Low-pass | \(s \rightarrow s/\omega_c\) |
| High-pass | \(s \rightarrow \omega_c / s\) |
| Band-pass | \(s \rightarrow (s^2 + \omega_0^2)/(B s)\) |
| Band-stop | \(s \rightarrow B s / (s^2 + \omega_0^2)\) |

Where \(\omega_c = 2\pi f_c\), \(\omega_0 = 2\pi f_0\), \(B = 2\pi\cdot\mathrm{BW}\) (rad/s).  
BP/BS: \(f_0\) and \(\mathrm{BW}\) are the UI fields (ADR-010). Geometric edges satisfy \(f_0=\sqrt{f_1 f_2}\), \(\mathrm{BW}=f_2-f_1\).

### Element replacements

**LP scaled (LP response):**

- Series: \(L_k = g_k Z_0 / \omega_c\)
- Shunt: \(C_k = g_k / (\omega_c Z_0)\)

**LP → HP:**

- Series arm: \(C_k = 1/(\omega_c\, g_k\, Z_0)\)
- Shunt arm: \(L_k = Z_0/(\omega_c\, g_k)\)

**LP → BP** (series-resonator from series \(L'\); shunt parallel from shunt \(C'\)):

- Series resonator: \(L = g_k Z_0 / B\), \(C = B/(\omega_0^2 g_k Z_0)\)
- Shunt parallel tank: \(C = g_k/(B Z_0)\), \(L = B Z_0/(\omega_0^2 g_k)\)
- **Finite-zero shunt series-LC** \((L',C')\): Brune shunt — series resonator (from \(L'\)) in series with parallel tank (from \(C'\))
- **Finite-zero series parallel-LC**: dual Brune in series path — series resonator ‖ parallel tank

**LP → BS:**

- Series arm (parallel tank in series): \(L = g_k Z_0 B/\omega_0^2\), \(C = 1/(g_k Z_0 B)\)
- Shunt arm (series tank to ground): \(L = Z_0/(g_k B)\), \(C = g_k B/(\omega_0^2 Z_0)\)
- Finite-zero arms: same Brune / dual-Brune topology with BS element map (\(L'\rightarrow\) tank, \(C'\rightarrow\) series resonator)

## 3. Impedance scaling

From 1 Ω prototype to \(Z_0\):

\[
L \rightarrow L\cdot Z_0,\qquad C \rightarrow C/Z_0,\qquad R \rightarrow R\cdot Z_0
\]

Combined with frequency scaling as above.

### Asymmetric \(Z_S \neq Z_L\) (ADR-011)

\[
Z_0 = \sqrt{Z_S\, Z_L}
\]

Ports retain \(Z_S\) and \(Z_L\). See ADR-011 for limitations.

## 4. Validation identities

- Scaling \(Z_0\) and \(f_c\) must preserve normalized shape vs \(f/f_c\).
- Dual networks (series-first vs shunt-first) share \|S21\| for matched equal-Z cases; S11 may differ in intermediate Z.
- ABCD cascade of realized arms must match skrf within tight tolerance (equal-Z; Phase 2).
- BP: near \(f_0\), \|S21\| ≈ 0 dB (odd-order Cheby within ripple); far from band, stopband attenuation rises.
- BS: near \(f_0\), deep notch; passbands below/above approach 0 dB.

## 5. Implementation checklist

- [x] `synthesis/realize/ladder.py` LP/HP/BP/BS + exact output transformer (ADR-017)
- [x] Resonator elements `IdealSeriesLC` / `IdealParallelLC`
- [x] Unit / golden tests for BP/BS and asymmetric Z (exact transformer)
- [x] ADR-010 / ADR-011
