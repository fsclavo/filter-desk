# Elliptic / Cauer — Phase 5b

- **Status:** Implemented (Phase 5b)
- **References:** scipy `ellipap`; ADR-006; ADR-013

## Definition

Equiripple passband and stopband; finite transmission zeros. Highest selectivity per order among classical responses.

Normalized scipy prototype: passband edge \(\omega_p=1\), ripple \(A_p\), minimum stopband \(A_s\).

## Inputs

| Symbol | Meaning |
| --- | --- |
| \(n\) | Order **odd ≥ 3** (even order needs a transformer / unequal terminations and is rejected) |
| \(A_p\) | Passband ripple (dB) |
| \(A_s\) | Stopband attenuation (dB) |
| \(f_c\) | Passband ripple-edge frequency |

## Algorithm

1. `scipy.signal.ellipap(n, Ap, As)` → zpk  
2. Complementary \(F(s)\) from \(1-|H|^2\) (reflection zeros on \(j\omega\))  
3. \(S_{11}=F/A\), Cauer zero-shift extraction  
4. Scale / dual / LP→HP / LP→BP·BS (Brune arms for finite zeros)

## Tests

`tests/unit/test_phase5b_families.py`
