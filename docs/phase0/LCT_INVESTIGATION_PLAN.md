# ELSIE `.lct` investigation plan

- **Status:** Phase 0 plan (execution in Phase 9; sample collection may start anytime)
- **Decision type:** Open investigation — no public authoritative schema found (2026-03-29 research)

## Goal

Determine whether FilterDesk can provide **semantic** `.lct` import/export without making `.lct` the domain model.

## Known facts

- `.lct` is ELSIE’s native design file (Tonne Software).
- Manual describes Save/Get design, LASTSESSION, limits, stepsizes, analysis settings — **behaviorally**, not as a byte schema.
- Separate ELSIE writers exist for DAT/TXT, Touchstone, LTspice (not `.lct`).
- No public formal grammar was located during blueprint research.

## Legal / ethical constraints

- Do **not** decompile ELSIE or copy proprietary code.
- Only use `.lct` files the project is entitled to use (user-created designs, redistributable demos if any).
- Do **not** commit ELSIE installers or Registration keys.
- Document interoperability limitations honestly.

## Sample corpus targets

Collect ≥10 diverse files covering:

| Dimension | Variants |
| --- | --- |
| Family | Butterworth, Cheby, Cauer, Bessel if available |
| Response | LP, HP, BP, BS |
| Order | 3, 5, 7 |
| Topology | C-input / L-input / BP variants |
| Extras | with limits, with part stepsizes, after manual edit |

Store under `tests/lct_roundtrip/corpus/` with a README listing provenance (owner, ELSIE version, redistributable? yes/no).

## Investigation procedure

1. **Classify:** text vs binary (`file`, hexdump first 256 bytes).
2. **Versioning:** find repeating headers / version strings across files.
3. **Differential analysis:** change one capacitor in ELSIE, save, binary/text diff.
4. **Map fields** to internal `LctDocument` DTO (not domain).
5. **Mapper** `LctDocument` ↔ FilterDesk domain with `CompatibilityReport`.
6. **Round-trip:** import → export → semantic compare (components, zs/zl, sweep).
7. **Manual ELSIE open test** of exported file (Windows; not CI).

## Go / no-go criteria

| Outcome | Action |
| --- | --- |
| Stable mapping for R/L/C ladders + zs/zl + sweep | Ship import/export best-effort |
| Partial mapping | Import with warnings; export subset |
| Opaque / unstable across versions | Defer `.lct`; prioritize Touchstone + native JSON |

## Deliverables (Phase 9)

- `src/filterdesk/io/lct/{parser,exporter,model_mapper}.py`
- `docs/lct_compatibility.md` coverage table
- Round-trip tests on redistributable corpus only

## Interim workaround (Phases 2–8)

Use Touchstone + native `.filterdesk.json` + SPICE for interchange with other tools.
