# FilterDesk

Open-source desktop application for **passive lumped-element RF/electronic filter
synthesis and analysis**.

> Working name: **FilterDesk**. Independent implementation inspired by the
> *capabilities* of ELSIE and modern LC filter tools — not a clone of any
> proprietary source.

## Status

**Phases 0–3 complete** — synthesis, analysis, and a minimal desktop GUI.  
**Phase 4 next** — BP/BS and additional topologies.

See:

- [`docs/BACKLOG.md`](docs/BACKLOG.md)
- [`docs/DEVELOPMENT_BLUEPRINT.md`](docs/DEVELOPMENT_BLUEPRINT.md)
- [`docs/phase3/PHASE3_STATUS.md`](docs/phase3/PHASE3_STATUS.md)
- [`docs/adr/`](docs/adr/)

## Quick start

```bash
uv sync
uv run filterdesk gui
```

CLI (no GUI):

```bash
uv run filterdesk synthesize --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json
uv run filterdesk analyze --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json \
  --backend abcd --export-s2p /tmp/milestone.s2p
uv run pytest -q
```

## Milestone

```text
7th-order Chebyshev Type I · 0.01 dB ripple · high-pass
140 MHz (ripple-edge cutoff) · 50 Ω / 50 Ω
```

At cutoff, S21 ≈ **−0.01 dB**. Native projects use `.filterdesk.json`.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
