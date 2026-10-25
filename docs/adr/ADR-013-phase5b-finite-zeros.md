# ADR-013: Phase 5b finite-zero and image-parameter families

- **Status:** Accepted
- **Date:** 2026-10-01
- **Phase:** 5b

## Decision

### Chebyshev Type II (inverse Chebyshev)

| Item | Choice |
| --- | --- |
| Cutoff | `cutoff_hz` = **stopband edge** (first frequency where As is met); `CutoffDefinition.STOPBAND_EDGE` |
| Inputs | order \(n\) (≥1), As (dB), fc |
| Prototype | scipy-compatible zpk → reflection \(S_{11}=s^n/A(s)\) → Cauer zero-shift ladder |
| Responses | LP, HP, BP, BS (equal \(R\); Brune arms for finite zeros) |
| Topology | Series-L or shunt-C input (dual); BP/BS resonator / Brune map |
| Even order | Supported (equal-R Cauer; |S21| fit when needed) |

### Elliptic / Cauer

| Item | Choice |
| --- | --- |
| Cutoff | Passband **ripple edge** (`RIPPLE_EDGE`, ADR-006) |
| Inputs | \(n\ge 2\), Ap, As, fc |
| Prototype | `ellipap` zpk → complementary \(F(s)\) on \(j\omega\) → Cauer extraction |
| Responses | LP, HP, BP, BS |
| Even order | **Rejected** (equal-R needs a transformer/unequal terminations; odd orders only) |

### Constant-K / M-derived

Image-parameter sections (not modern approximation). Constant-K uses classic \(L,C\) vs \(f_c,Z_0\); M-derived adds \(m\in(0,1)\) and a finite attenuation peak. Supported for LP/HP; BP/BS use the same image-parameter maps as textbooks.

## Consequences

- `FilterSpec` gains `stopband_attenuation_db` and optional `m_parameter`.
- `Prototype` may carry Cauer `arms` instead of all-pole `g_values`.
- GUI enables As (and m) per family; ripple for elliptic + Cheby I.
- BP/BS of finite-zero arms use `IdealBruneLC` / `IdealDualBruneLC` (v0.5.5).
