# FilterDesk

Open-source desktop application for **passive lumped-element RF/electronic filter
synthesis and analysis**.

> Working name: **FilterDesk**. Independent implementation inspired by the
> *capabilities* of ELSIE and modern LC filter tools — not a clone of any
> proprietary source.

## Status

**Phases 0–7 complete** — synthesis, analysis, desktop GUI, E-series snapping,
Monte-Carlo tolerance analysis, optimization, and redesign-on-change. See:

- [`docs/BACKLOG.md`](docs/BACKLOG.md)
- [`docs/DEVELOPMENT_BLUEPRINT.md`](docs/DEVELOPMENT_BLUEPRINT.md)
- [`docs/phase7/PHASE7_STATUS.md`](docs/phase7/PHASE7_STATUS.md)
- [`docs/adr/`](docs/adr/)

## Features

- Low-pass, high-pass, band-pass, and band-stop LC ladder synthesis.
- Approximation families: Butterworth, Chebyshev Type I/II, elliptic, Bessel,
  Gaussian, Legendre, and constant-*k* / m-derived sections.
- Two analysis backends (`abcd` ladder and `scikit-rf`), S-parameters, VSWR,
  group delay, insertion/return loss.
- Non-ideal components (finite Q, DCR, ESL, ESR, parasitic capacitance).
- E-series component snapping (IEC 60063), Monte-Carlo tolerance/yield, and
  constrained optimization against limit regions.
- Touchstone (`.s1p`/`.s2p`) import/export and Smith-chart export.
- PySide6 desktop GUI and a scriptable command-line interface.

## Requirements

- Python **3.11+**
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- A desktop session for the GUI (Qt/PySide6)

## Installation

Clone and install into a project-local virtual environment with `uv` (uses the
committed `uv.lock` for reproducible builds):

```bash
git clone https://github.com/fsclavo/filter-desk.git
cd filter-desk
uv sync
```

If you prefer `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
```

Verify the install:

```bash
uv run filterdesk --version
uv run filterdesk --help
```

## Usage

### GUI

```bash
uv run filterdesk gui
```

The GUI lets you edit a specification, synthesize, inspect the schematic and
plots (S-parameters, VSWR, group delay, Smith chart), snap values to E-series,
run Monte-Carlo tolerance sweeps, and optimize against limit regions.

### CLI

Run `uv run filterdesk <command> --help` for the full option list. Every
subcommand accepts either a `--spec` JSON file or inline parameters
(`--family`, `--response`, `--order`, `--cutoff`, ...).

**Synthesize** a filter and print components:

```bash
uv run filterdesk synthesize \
  --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json
```

**Analyze** the frequency response and export results:

```bash
uv run filterdesk analyze \
  --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json \
  --backend abcd --export-s2p /tmp/milestone.s2p
```

Snap component values to a preferred number series:

```bash
uv run filterdesk snap --series E24 --strategy independent \
  --family chebyshev_type_i --response high_pass --order 7 \
  --cutoff 140M --ripple 0.01
```

Estimate the minimum order from ripple/attenuation targets:

```bash
uv run filterdesk estimate-order --family chebyshev_type_i --response low_pass \
  --f-pass 1M --f-stop 2M --ap 0.1 --as 40
```

Tolerance Monte-Carlo sweep (optionally with `--limits` for yield):

```bash
uv run filterdesk montecarlo \
  --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json \
  --trials 2000 --tol 2 --distribution uniform --seed 42
```

Optimize component values to satisfy limit regions:

```bash
uv run filterdesk optimize \
  --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json \
  --limits limits.json --bound 0.2
```

Import/compare measured data:

```bash
uv run filterdesk touchstone-info measured.s2p
uv run filterdesk compare /tmp/milestone.s2p measured.s2p
```

Add `--json` to any command for machine-readable output.

### Specification format

A spec is a small JSON object (also written as `.filterdesk.json` project files):

```json
{
  "family": "chebyshev_type_i",
  "response": "high_pass",
  "order": 7,
  "passband_ripple_db": 0.01,
  "cutoff_hz": 140000000.0,
  "cutoff_definition": "ripple_edge",
  "z_source_ohm": 50.0,
  "z_load_ohm": 50.0,
  "topology_id": "ladder_hp_series_c_input"
}
```

## Milestone

```text
7th-order Chebyshev Type I · 0.01 dB ripple · high-pass
140 MHz (ripple-edge cutoff) · 50 Ω / 50 Ω
```

At cutoff, S21 ≈ **−0.01 dB**. Native projects use `.filterdesk.json`.

## Development

```bash
uv run pytest -q            # tests
uv run ruff check src tests # lint
uv run mypy                 # type check
```

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
