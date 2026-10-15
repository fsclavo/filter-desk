# Constant-K / M-derived — Phase 5b

- **Status:** Implemented (Phase 5b)
- **References:** classic image-parameter texts (Terman, ITT); ADR-013

## Constant-K

Mid-series cascade of T-sections at \(Z_0'=1\), image \(\omega_c'=1\):

- End series \(L=1\), internal series \(L=2\)
- Shunt \(C=2\)

`order` = number of T-sections. LP/HP/BP/BS via standard reactance maps (pure L/C arms).

## M-derived

Shunt m-derived sections (\(0<m<1\)):

- Series \(L=m\)
- Shunt series-LC with \(L=(1-m^2)/m\), \(C=m\) → \(\omega_\infty=1/\sqrt{1-m^2}\)

`order` = number of L-sections. LP/HP only in Phase 5b.

## Tests

`tests/unit/test_phase5b_families.py`
