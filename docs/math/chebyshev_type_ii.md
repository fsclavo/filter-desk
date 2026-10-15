# Chebyshev Type II — Phase 5b

- **Status:** Implemented (Phase 5b)
- **References:** scipy `cheb2ap`; ADR-013; Williams & Taylor

## Definition

Inverse Chebyshev (Type II) low-pass has a **monotonic passband** and **equal-ripple stopband**. Finite \(j\omega\) transmission zeros yield Cauer (zig-zag) arms.

Normalized scipy prototype: stopband edge \(\omega_s=1\), minimum stopband attenuation \(A_s\) (dB).

## Inputs

| Symbol | Meaning |
| --- | --- |
| \(n\) | Order ≥ 1 (odd or even) |
| \(A_s\) | Stopband attenuation (dB) |
| \(f_c\) | Stopband-edge frequency (ADR-013) |

## Algorithm

1. `scipy.signal.cheb2ap(n, As)` → zpk  
2. \(S_{11}(s)=s^n/A(s)\) (odd equal-\(R\))  
3. \(Z_\mathrm{in}=(1+S_{11})/(1-S_{11})\)  
4. Zero-shift Cauer extraction → normalized arms  
5. Scale / dual / LP→HP / LP→BP·BS (Brune arms for finite zeros)

## Tests

`tests/unit/test_phase5b_families.py`
