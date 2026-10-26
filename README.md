<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-wordmark-dark.png">
    <img src="assets/logo-wordmark.png" alt="FilterDesk" width="420">
  </picture>
</p>

[![test](https://github.com/fsclavo/filter-desk/actions/workflows/test.yml/badge.svg)](https://github.com/fsclavo/filter-desk/actions/workflows/test.yml)
[![release](https://img.shields.io/github/v/release/fsclavo/filter-desk)](https://github.com/fsclavo/filter-desk/releases)

Open-source desktop application for **passive lumped-element RF/electronic filter
synthesis and analysis**. FilterDesk designs low-pass, high-pass, band-pass, and
band-stop LC filters, shows you how they actually behave, accounts for real-world
tolerances and parasitics, and exports the result to Touchstone, CSV, SPICE, or an
image.

> An independent implementation of classical network-synthesis theory and
> practical LC filter design.

## Features

- **Synthesis** of low-pass, high-pass, band-pass, and band-stop LC ladders.
- **Approximation families**: Butterworth, Chebyshev Type I/II, elliptic (Cauer),
  Bessel, Gaussian, Legendre, and constant-*k* / m-derived sections.
- **Analysis** with magnitude, S12/S22, phase, VSWR, group delay, impedance, and
  Smith-chart views, using a fast ladder backend (`abcd`) or a `scikit-rf`
  cross-check.
- **Real-world effects**: finite inductor Q, DCR, self-resonance, DC-bias
  derating, capacitor ESL/ESR, and parasitic capacitance.
- **Transformer / unun / balun calculator**: turns, Lm, flux/saturation and wire
  gauges on the built-in toroid table.
- **Balun / unun designer**: ideal, Guanella/Ruthroff and choke models with
  core/wire, complex-permeability core loss, thermal-rise estimate and
  output-boundary BOM insertion.
- **Microstrip / distributed calculators**: line width, `eeff`, quarter-wave
  transformer, open/short stubs, substrate presets and first-order loss.
- **VNA-guided tuning**: import a measured `.s2p` and trim L/C/R values to the
  measured S11/S21 magnitude with bounded least squares.
- **Toroid / air-core realization**: turn a synthesized inductor into a physical
  winding (turns, wire gauge, DCR) from the built-in coil calculators.
- **Light/dark/system theme** with remembered window layout.
- **English/Spanish GUI** (applies on restart).
- **E-series snapping** (IEC 60063 E6–E96) to turn ideal values into real parts.
- **Tolerance analysis**: per-component tolerances and a Monte-Carlo envelope
  with yield estimates.
- **Optimization** against limit regions (passband/stopband masks).
- **Component sensitivity** analysis that ranks parts by their effect and
  suggests a tuning direction.
- **Design parameter sweeps** (order, family, frequency, ripple…) into a
  comparison table, with one-click load of a chosen variant.
- **Interactive tuning**: tune components, retune by dragging markers, and scale
  the whole response.
- **Interoperability**: import/export Touchstone (`.s1p`/`.s2p`), export CSV,
  LTspice-compatible SPICE netlists, and Smith-chart images.
- Both a **desktop GUI** (PySide6) and a scriptable **command-line interface**.

## Download and install

### Prebuilt bundles

Prebuilt packages for Windows and Linux are published on the
[Releases](https://github.com/fsclavo/filter-desk/releases) page:

| Platform | File | Notes |
| --- | --- | --- |
| Windows | `FilterDesk-<ver>-windows-x86_64-setup.exe` | installer with Start Menu/Desktop shortcuts |
| Windows | `FilterDesk-windows-x86_64.zip` | portable bundle |
| Linux | `FilterDesk-x86_64.AppImage` | single-file app (needs **glibc ≥ 2.35**, i.e. Ubuntu 22.04+) |
| Linux | `FilterDesk-linux-x86_64.tar.gz` | portable bundle |

The launcher is GUI-first: double-click it to open the desktop app. Passing CLI
arguments (for example `FilterDesk --version`) uses the command-line interface.

### From source

Requires Python **3.11+** and either [`uv`](https://docs.astral.sh/uv/)
(recommended) or `pip`.

```bash
git clone https://github.com/fsclavo/filter-desk.git
cd filter-desk
uv sync
```

With `pip` instead:

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install .
```

Verify the install:

```bash
uv run filterdesk --version
```

## Quick start

Launch the desktop application:

```bash
uv run filterdesk gui
```

The app opens with a ready-made example (a 7th-order Chebyshev Type I high-pass,
140 MHz cutoff). Edit the fields in the **Specification** panel and press
**Synthesize + Analyze** (`Ctrl+Return`) to see the schematic, component table,
and response plots update.

Prefer the command line? Synthesize and analyze the same filter:

```bash
uv run filterdesk synthesize \
  --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json

uv run filterdesk analyze \
  --spec tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm/spec.json \
  --export-s2p milestone.s2p --export-csv traces.csv
```

## Documentation

- **[User Manual](docs/user-manual.md)** — installing, concepts, the GUI,
  workflows, the full CLI reference, and file formats. Start here.
- [Development blueprint](docs/DEVELOPMENT_BLUEPRINT.md) and
  [backlog](docs/BACKLOG.md) — architecture and roadmap (for contributors).
- [packaging.md](docs/packaging.md) — how the release bundles are built.
- [`docs/adr/`](docs/adr/) — architecture decision records and
  [`docs/math/`](docs/math/) — the synthesis math.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
