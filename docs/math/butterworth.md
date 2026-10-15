# Butterworth — mathematical specification

- **Status:** Phase 0 specification (implementation in Phase 1)
- **Decision type:** Theory
- **References:** Pozar; Matthaei et al.; Williams & Taylor

## 1. Definition

Normalized low-pass (\(\omega_c = 1\) at **−3 dB**):

\[
|H(j\Omega)|^2 = \frac{1}{1 + \Omega^{2n}}
\]

## 2. Required inputs

Order \(n\), cutoff \(f_c\) (−3 dB), \(Z_S\), \(Z_L\), topology.

## 3. Order estimation

\[
n \ge \frac{\log_{10}(10^{0.1 A_s}-1)}{2\log_{10}\Omega_s}
\]

## 4. Prototype g-values

\[
g_0 = 1,\quad
g_k = 2\sin\left(\frac{(2k-1)\pi}{2n}\right)\ (k=1..n),\quad
g_{n+1} = 1
\]

### Anchor

\(n=5\): \(g = [1,\ 0.618034,\ 1.618034,\ 2,\ 1.618034,\ 0.618034,\ 1]\)

## 5. Poles

\[
s_k = -sin\theta_k + j\cos\theta_k,\quad
\theta_k = \frac{(2k-1)\pi}{2n}
\]
(with standard left-half-plane placement). Phase 1 may synthesize from g-values only.

## 6. Limitations

- No passband ripple control; return loss near cutoff is modest.
- Maximally flat magnitude; slower roll-off than Chebyshev/elliptic for same \(n\).

## 7. Validation

- g-value unit tests vs closed form.
- Golden LP/HP fixtures in Phase 1 corpus.
