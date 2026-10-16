# FilterDesk User Manual

FilterDesk is an open-source desktop application for the synthesis and analysis
of **passive lumped-element LC filters**. This manual is written for people who
want to *design filters*, not for people reading the source code.

**Contents**

1. [Introduction](#1-introduction)
2. [Installing and launching](#2-installing-and-launching)
3. [Core concepts](#3-core-concepts)
4. [Quick start: your first filter](#4-quick-start-your-first-filter)
5. [The graphical interface](#5-the-graphical-interface)
6. [Design workflows (GUI)](#6-design-workflows-gui)
7. [Markers and limits](#7-markers-and-limits)
8. [Measured data and comparison](#8-measured-data-and-comparison)
9. [Saving, opening, and exporting](#9-saving-opening-and-exporting)
10. [Command-line reference](#10-command-line-reference)
11. [File formats](#11-file-formats)
12. [Approximation families reference](#12-approximation-families-reference)
13. [Units and notation](#13-units-and-notation)
14. [Troubleshooting and FAQ](#14-troubleshooting-and-faq)
15. [Known limitations](#15-known-limitations)
16. [License](#16-license)

---

## 1. Introduction

FilterDesk turns a short list of requirements — response type, cutoff frequency,
impedances, ripple/attenuation targets — into a **ladder of inductors and
capacitors**, then shows you how that ladder actually behaves across frequency.

Typical uses:

- Design an LC filter to a classic approximation (Butterworth, Chebyshev,
  elliptic, Bessel, …).
- See the magnitude, VSWR, group delay, and Smith-chart response.
- Replace ideal values with **standard E-series** parts.
- Study how component **tolerances** and real-world **parasitics** affect the
  response (Monte-Carlo and non-ideal models).
- **Optimize** component values to satisfy a passband/stopband mask.
- Export to **Touchstone**, **CSV**, a **SPICE netlist**, or an image, and compare
  simulation against measured data.

Everything is available both in the **GUI** and from the **command line**, so you
can script designs and regression-test them.

---

## 2. Installing and launching

### Prebuilt bundles

Download the file for your platform from the
[Releases page](https://github.com/fsclavo/filter-desk/releases):

| Platform | File | Notes |
| --- | --- | --- |
| Windows | `FilterDesk-<ver>-windows-x86_64-setup.exe` | installer (Start Menu/Desktop shortcuts) |
| Windows | `FilterDesk-windows-x86_64.zip` | portable bundle |
| Linux | `FilterDesk-x86_64.AppImage` | single-file app, **glibc ≥ 2.35** (Ubuntu 22.04+) |
| Linux | `FilterDesk-linux-x86_64.tar.gz` | portable bundle |

The launcher is **GUI-first**: double-click it, or run it with no arguments, to
open the desktop application. Passing command-line arguments (for example
`FilterDesk --version`) runs the CLI.

### From source

Requires Python **3.11+** and either [`uv`](https://docs.astral.sh/uv/)
(recommended) or `pip`.

```bash
git clone https://github.com/fsclavo/filter-desk.git
cd filter-desk
uv sync
uv run filterdesk --version
```

With `pip`:

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install .
```

### Launching

```bash
uv run filterdesk gui      # desktop application
uv run filterdesk --help   # list of CLI commands
```

On a headless machine (no display), the GUI tests and batch use require an
offscreen Qt backend: set `QT_QPA_PLATFORM=offscreen` in the environment.

---

## 3. Core concepts

**Specification.** A filter is described by a *specification*: the approximation
family, the response (low/high/band-pass/band-stop), the order, the cutoff or
band, the source/load impedances, and family-specific parameters (ripple,
stopband attenuation, m-derived parameter). See
[File formats](#11-file-formats) for the exact fields.

**Synthesis vs. analysis.** *Synthesis* computes the component values (the
circuit) from the specification. *Analysis* computes the frequency response of a
circuit. In the GUI you normally do both at once with **Synthesize + Analyze**.

**Order.** The filter order is the number of reactive elements (L/C) in the
ladder. Higher order gives a steeper transition but more components and loss.

**Cutoff convention.** The meaning of "cutoff" differs by family, and FilterDesk
labels it explicitly:

| Family | Cutoff definition |
| --- | --- |
| Chebyshev Type I, elliptic | **ripple-edge**: the edge of the passband ripple |
| Chebyshev Type II | **stopband-edge**: the edge of the stopband |
| Butterworth, Bessel, Gaussian, Legendre, constant-*k*, m-derived | **half-power (−3 dB)** |

**Band-pass/band-stop frequencies.** BP/BS filters are defined by a **center
frequency** and a **bandwidth**; internally the geometric center is used, so the
low/high edges satisfy `f_low · f_high = f_center²`.

**Impedances.** Source and load impedances may differ. FilterDesk scales the
reactive elements by the geometric mean `√(Zs · Zl)` (see
[Known limitations](#15-known-limitations)).

**Non-ideal parts.** Ideal inductors/capacitors can be converted to *non-ideal*
models that carry DCR/Q, parasitic parallel capacitance, ESR, and ESL.

**Tolerances.** Each component can have a per-part tolerance (±%) used by the
Monte-Carlo engine.

**Snapping.** Ideal values are rarely manufacturable; *snapping* rounds them to a
preferred number series (E6…E96).

---

## 4. Quick start: your first filter

1. **Launch** the app (`uv run filterdesk gui`). It opens with a working example:
   a 7th-order Chebyshev Type I high-pass at 140 MHz, 50 Ω / 50 Ω.
2. **Edit the specification** in the left **Specification** dock. For example,
   set *Response* to `Low-pass`, *Family* to `Butterworth`, and *Passband f /
   cutoff* to `10M`.
3. Press **Synthesize + Analyze** (`Ctrl+Return`) or the toolbar **Synthesize**.
4. Inspect the result:
   - the **Schematic** dock shows the ladder,
   - the **Components** dock lists the computed values,
   - the central **Magnitude / VSWR / Group delay / Smith** tabs show the response.
5. Turn ideal values into real parts: **Design → Snap to E-series…**, choose
   `E24` and `Independent`.
6. Study tolerance spread: **Design → Monte-Carlo tolerances…**, run 1000 trials
   at ±2 %.
7. **Save** your project (**File → Save**, `Ctrl+S`) as a `.filterdesk.json`
   file, and **export** with **File → Export → CSV…** or the Touchstone CLI.

Need a starting order? Press **Estimate N** in the Specification panel (works for
supported low/high-pass families) to compute the minimum order from your
passband/stopband targets.

---

## 5. The graphical interface

### Window layout

The main window has a **central plot area** and five dockable panels. Show or
hide any dock from the **View** menu; drag docks to rearrange them.

| Panel | Default position | Purpose |
| --- | --- | --- |
| **Specification** | left | edit the filter requirements |
| **Schematic** | top | read-only ladder drawing |
| **Components** | right | component values, parasitics, tolerances |
| **Markers** | right | measurement cursors |
| **Limits** | right | pass/fail mask regions |

The central area is a tabbed **plot panel**: **Magnitude**, **VSWR**, **Group
delay**, and **Smith**.

The **toolbar** holds **Synthesize**, **Analyze**, **Tune +** (`Ctrl+]`),
**Tune −** (`Ctrl+[`), and inline sweep controls (**Start Frequency**, **Stop
Frequency**, **N**). The **status bar** at the bottom reports progress, results,
and errors.

The window title shows `FilterDesk — <title>* — <path>`, where `*` marks unsaved
changes.

### Specification panel

| Field | Meaning |
| --- | --- |
| **Family** | approximation family (see [§12](#12-approximation-families-reference)) |
| **Response** | `Low-pass`, `High-pass`, `Band-pass`, `Band-stop` |
| **Order** | filter order (1–21); **Estimate N** button next to it |
| **Passband f / cutoff** | cutoff for LP/HP |
| **Stopband f (est.)** | stopband edge used only by order estimation (LP/HP) |
| **Center** / **Bandwidth** | BP/BS defining frequencies |
| **Ripple / Ap (dB)** | passband ripple (Chebyshev I, elliptic) |
| **Stopband As (dB)** | stopband attenuation (Chebyshev II, elliptic) |
| **m parameter** | m-derived parameter (M-derived only) |
| **Zsource** / **Zload** | port impedances (default 50 Ω) |
| **Topology** | ladder topology; the choices follow the response |

The panel is context-sensitive: fields that do not apply to the selected family
are disabled, and the available **Topology** entries change with the response.
Editing any field only marks the session dirty — it does **not** re-synthesize.
Press **Synthesize + Analyze** to apply changes.

**Estimate N** computes the minimum order from your pass/stop edges and Ap/As and
writes it into the Order field.

### Components panel

A table with columns **Ref**, **Role**, **Type**, **Value**, **Parasitic**,
**Tol**, **Vpk**, **Ipk**. Only the **Value** column is editable (double-click).
Composite elements (series/parallel resonators, Brune arms) are expanded into
sub-rows such as `X1.L`, `X1.C`. Selecting rows highlights the matching element in
the schematic, and vice versa.

**Vpk/Ipk** show the peak voltage/current per part from the **power-stress
estimate**: set the **P (W)** field in the toolbar (0 = off). Stress is evaluated
at the passband landmark (cutoff for LP/HP, center for BP/BS) assuming a matched
`Z0` system, and the worst case is summarised in the status bar. Use it to pick
voltage/current ratings (e.g. capacitor voltage) for transmit filters.

### Schematic panel

A read-only ladder diagram. Series arms are drawn on the signal line, shunt arms
go to ground; resonators, Brune arms, and non-ideal parts are labelled with their
values. **Left-click** an element to select it; **right-click** it to open the
element context menu (the same actions as **Design → Component**).

### Plot panel

Four tabs, all with a logarithmic frequency axis:

- **Magnitude** — |S21| and |S11| in dB (solid = simulated; dashed = measured;
  grey band = Monte-Carlo envelope).
- **VSWR** — input VSWR.
- **Group delay** — in seconds.
- **Smith** — S11 (red) and S22 (blue) loci.

A **cursor readout** below the tabs reports `f`, `S21`, `S11`, `VSWR`, and group
delay at the nearest sweep point, plus Monte-Carlo and marker details when
present.

---

## 6. Design workflows (GUI)

All design-changing actions are **undoable** (`Ctrl+Z` / `Ctrl+Shift+Z`).
Circuit-level edits trigger an automatic re-analysis after a short delay;
specification edits require an explicit **Synthesize**.

| Workflow | How to trigger | Notes |
| --- | --- | --- |
| **Synthesize + Analyze** | `Ctrl+Return`, toolbar **Synthesize**, Design menu | builds circuit from spec + sweep, then analyzes |
| **Band preset** | **Design → Band preset…** | one-click 160 m–6 m LP/HP/BP design (Chebyshev-I, sets sweep) |
| **Analyze** | toolbar **Analyze** | re-analyzes; synthesizes first if needed |
| **Estimate order** | **Estimate N** in the Specification panel | LP/HP classical families |
| **Snap to E-series** | **Design → Snap to E-series…** | picks series (E6–E96) and strategy |
| **Apply parasitics / finite Q** | **Design → Apply parasitics / Q…** | whole-circuit non-ideal conversion |
| **Monte-Carlo tolerances** | **Design → Monte-Carlo tolerances…** | runs in the background; overlays the S21 envelope |
| **Optimize to limits** | **Design → Optimize to limits…** | requires at least one enabled limit |
| **Scale response** | **Design → Scale response…** | scales cutoff (LP/HP) or center+bandwidth (BP/BS) |
| **Tune a part** | **Tune +/−** (`Ctrl+]` / `Ctrl+[`), or the element menu | nudges by the part's relative step (default 2 %) |
| **Set tolerance** | element menu → **Set tolerance…** | per-part ±% for Monte-Carlo |
| **Retune by marker** | bind a marker to a landmark, then drag it | re-synthesizes on release |
| **Edit the circuit** | element menu (Design → Component, or right-click) | edit value, parasitics, convert, insert, delete |

### The element (Component) menu

Opens from **Design → Component** or by right-clicking an element in the
schematic. Depending on the selected element it offers:

- **Edit value…**
- **Tune +N% / Tune −N%**, **Set tune step…**, **Set tolerance…** (L/C/R parts)
- **Edit parasitics…** (L/C parts)
- **Convert to Inductor / Convert to Capacitor**
- **Insert before** / **Insert after** → series/shunt inductor, capacitor, or
  resistor
- **Delete element** (disabled when only one element remains)

### Dialogs

- **Snap to E-series** — *Series* (E6, E12, E24, E48, E96; default E24) and
  *Strategy* (Independent, L only, C only, Preserve LC resonances).
- **Apply parasitics / finite Q** — inductor **Q** (needs a Q reference
  frequency), **DCR**, **Cpar**; capacitor **ESR**, **ESL**. Blank fields leave
  that aspect ideal.
- **Inductor/Capacitor parasitics** (single arm) — Series R (DCR), Parallel C,
  Q, Q reference frequency / ESR and ESL. If Q is given, DCR is derived at the
  reference frequency.
- **Monte-Carlo tolerances** — *Trials* (default 1000), *Tolerance ±%* (default
  1), *Distribution* (`uniform` or `normal`), optional integer *Seed*.
- **Optimize to limits** — *Method* (Least squares, Nelder–Mead, Differential
  evolution, Dual annealing), *Bound ±fraction* (default 0.2), *Max iterations*
  (default 200), optional *Seed*.

---

## 7. Markers and limits

### Markers

The **Markers** dock manages measurement cursors (up to **8**). Columns:
**Id** (auto, read-only), **Frequency** (editable), **Label** (editable), and
**Binds** (a combo of `—`, `cutoff`, `f_center`, `bandwidth`).

- Add with **Ctrl+M**, **Edit → Add marker at cursor**, or the dock's **Add at
  cursor** button (the mouse must be over a plot).
- On the frequency plots a marker is a draggable vertical line; on the Smith chart
  it is a draggable spot on the S11 locus.
- A marker **bound** to a landmark *retunes the specification* when dragged: bind
  to `cutoff` to slide an LP/HP cutoff, or to `f_center`/`bandwidth` for BP/BS.

### Limits

The **Limits** dock defines pass/fail mask regions (up to **10**): columns
**Id**, **Metric**, **f_low**, **f_high**, **y_min**, **y_max**, **On**.

- **Metric** is one of `s21_db`, `s11_db`, `vswr`, `s11_mag`, `s22_mag`.
- **Add limit** offers presets: *Passband |S21| min*, *Stopband |S21| max*,
  *Return loss |S11| max*, *VSWR max*, *Smith |S11| max*, *Smith |S22| max*.
- Enabled limits are drawn as bands on the plots (dashed/dotted circles on the
  Smith chart) and show a **PASS/FAIL** indicator. They also drive **Optimize to
  limits…**.

---

## 8. Measured data and comparison

**File → Import → Touchstone…** loads a measured `.s1p`/`.s2p`/`.sNp` file and
overlays the measured traces (dashed) on the plots; for 2-port files it also
reports a simulation-vs-measurement comparison over the overlapping band. Toggle
the overlay with **View → Show measured overlay**.

---

## 9. Saving, opening, and exporting

| Action | Menu | Shortcut | Format |
| --- | --- | --- | --- |
| Open project | File → Open… | `Ctrl+O` | `.filterdesk.json` |
| Save / Save As | File → Save / Save As… | `Ctrl+S` | `.filterdesk.json` |
| Import measured | File → Import → Touchstone… | — | `.s1p`/`.s2p`/`.sNp` |
| Export Smith chart | File → Export → Smith chart… | — | `.png`/`.svg`/`.pdf` |
| Export CSV | File → Export → CSV… | — | `.csv` |
| Export Touchstone | File → Export → Touchstone (.s2p)… | — | `.s2p` |
| Export SPICE netlist | File → Export → SPICE netlist… | — | `.net`/`.cir` (LTspice) |
| Export LTspice schematic | File → Export → LTspice (.asc)… | — | `.asc` |
| Export Qucs schematic | File → Export → Qucs (.sch)… | — | `.sch` (best-effort) |

The native project file stores the specification, circuit, sweep settings,
markers, limits, and metadata, and is reloadable and editable.

The first **Save** suggests a name derived from the design
(`<family>_<type>_n<order>_<freq>.filterdesk.json`, e.g.
`cheby1_LPF_n7_140MHz.filterdesk.json`); you can change it. The **Help** menu
offers **About FilterDesk** (version/license), **About Qt**, and links to the
GitHub repository and this manual.

---

## 10. Command-line reference

Run `filterdesk` with no command for help, or `filterdesk <command> --help` for a
command's options.

```
filterdesk {synthesize,analyze,gui,bands,snap,montecarlo,optimize,to-csv,
            estimate-order,touchstone-info,compare} ...
```

Global options: `-h/--help`, `--version`.

`--band NAME` (e.g. `40m`) builds a spec from an amateur-band preset and
`--band-kind {lpf,hpf,bpf}` selects the kind; `filterdesk bands` lists them.

### Shared specification options

`synthesize`, `analyze`, `snap`, `montecarlo`, and `optimize` accept either a
`--spec` JSON file **or** inline parameters:

| Option | Meaning |
| --- | --- |
| `--spec PATH` | specification JSON (see [§11](#11-file-formats)) |
| `--family` | approximation family |
| `--response` | `low_pass`, `high_pass`, `band_pass`, `band_stop` |
| `--order INT` | filter order |
| `--cutoff` | cutoff for LP/HP, e.g. `140M` |
| `--f-center`, `--bandwidth` | center/bandwidth for BP/BS |
| `--ripple` | ripple Ap in dB (Chebyshev I / elliptic) |
| `--stopband-att` | stopband attenuation As in dB (Chebyshev II / elliptic) |
| `--m` | m-derived parameter |
| `--zs`, `--zl` | source/load impedance (default `50`) |
| `--topology` | ladder topology id |

Most commands accept `--json` for machine-readable output.

### Commands

- **`gui`** — launch the desktop application.
- **`synthesize`** — synthesize and print the components (or JSON).
  ```bash
  filterdesk synthesize --family chebyshev_type_i --response high_pass \
    --order 7 --cutoff 140M --ripple 0.01
  ```
- **`analyze`** — synthesize (unless already specified) and analyze; export
  results. Options include `--f-start`, `--f-stop`, `--points`, `--spacing`,
  `--backend {abcd,skrf}`, non-ideal flags (`--inductor-q`, `--q-frequency`,
  `--inductor-dcr`, `--inductor-cpar`, `--capacitor-esr`, `--capacitor-esl`),
  power stress (`--power W`), and exporters `--export-s2p`, `--export-smith`,
  `--export-csv`, `--export-spice`, `--export-asc`, `--export-qucs`.
  ```bash
  filterdesk analyze --spec my.spec.json --backend skrf \
    --export-s2p out.s2p --export-csv out.csv
  ```
- **`snap`** — synthesize and round values to an E-series. `--series`
  (E6…E96, default E24), `--strategy` (independent, l_only, c_only,
  preserve_lc_resonances).
- **`montecarlo`** — tolerance sweep. `--trials` (default 1000), `--tol` (default
  1), `--distribution {uniform,normal}`, `--seed`, `--element-tol REF=PCT`
  (repeatable), `--limits FILE` for yield, plus sweep options.
- **`optimize`** — tune values to satisfy limits and/or objectives. Provide
  `--limits FILE` and/or one or more `--objective`:
  - `passband:LO:HI` — minimise passband ripple (`|S21|` variation).
  - `stopband:LO:HI:ATT_DB` — push minimum stopband attenuation up to `ATT_DB`.
  - `returnloss:LO:HI:RL_DB` — push minimum in-band return loss up to `RL_DB`.

  Options: `--method {least_squares,nelder_mead,differential_evolution,dual_annealing}`,
  `--bound` (default 0.2), `--max-iter` (default 200), `--seed` (global methods),
  plus sweep options. Example:
  ```bash
  filterdesk optimize --spec spec.json --objective passband:1M:100M \
      --objective stopband:150M:1G:60 --method nelder_mead --bound 0.3
  ```
- **`to-csv`** — convert a Touchstone file to CSV.
  ```bash
  filterdesk to-csv measured.s2p traces.csv
  ```
  `--columns` selects a comma-separated subset of
  `frequency_hz,s21_db,s11_db,s22_db,s21_mag,s11_mag,vswr,group_delay_s,il_db,rl_db`.
- **`estimate-order`** — minimum order from Ap/As and edges. Requires `--family`
  and `--response`; use `--f-pass/--f-stop` (LP/HP) or `--pass-band/--stop-band`
  (BP/BS), plus `--ap` and `--as`.
  ```bash
  filterdesk estimate-order --family butterworth --response low_pass \
    --f-pass 1M --f-stop 2M --ap 0.1 --as 40
  ```
- **`touchstone-info`** — summarize a Touchstone file.
- **`compare`** — compare two Touchstone results (simulated vs measured).
  ```bash
  filterdesk compare out.s2p measured.s2p
  ```

---

## 11. File formats

### Specification JSON (`.json`, used with `--spec`)

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

| Field | Values / notes |
| --- | --- |
| `family` | `butterworth`, `chebyshev_type_i`, `chebyshev_type_ii`, `bessel`, `gaussian`, `legendre`, `elliptic`, `constant_k`, `m_derived` |
| `response` | `low_pass`, `high_pass`, `band_pass`, `band_stop` |
| `order` | integer |
| `cutoff_hz` | LP/HP cutoff (Hz) |
| `f_center_hz`, `bandwidth_hz` | BP/BS center and bandwidth (Hz) |
| `z_source_ohm`, `z_load_ohm` | port impedances (Ω) |
| `topology_id` | see below; optional (defaults per response) |
| `cutoff_definition` | `half_power_3db`, `ripple_edge`, `stopband_edge`; optional (defaults per family) |
| `passband_ripple_db` | required for Chebyshev I and elliptic |
| `stopband_attenuation_db` | required for Chebyshev II and elliptic |
| `m_parameter` | required for m-derived, in (0, 1) |

Topologies by response:

| Response | `topology_id` values |
| --- | --- |
| Low-pass | `ladder_lp_series_l_input`, `ladder_lp_shunt_c_input` |
| High-pass | `ladder_hp_series_c_input`, `ladder_hp_shunt_l_input` |
| Band-pass | `ladder_bp_series_resonator_input`, `ladder_bp_shunt_resonator_input` |
| Band-stop | `ladder_bs_series_tank_input`, `ladder_bs_shunt_tank_input` |

### Native project (`.filterdesk.json`)

A versioned JSON document (`format_version: 1`) with `metadata`, `specification`,
`circuit`, `analysis.sweep`, and an `extensions` bag that stores `markers` and
`limits`. It is written and read by the GUI and is lossless across a save/open
cycle.

### Limits JSON (used with `--limits`)

A JSON **array** of regions:

```json
[
  {"id": "pb", "metric": "s21_db", "f_low_hz": 1000000.0,
   "f_high_hz": 100000000.0, "y_min": -0.5}
]
```

| Field | Notes |
| --- | --- |
| `metric` | `s21_db`, `s11_db`, `vswr`, `s11_mag`, `s22_mag` |
| `f_low_hz`, `f_high_hz` | band edges (Hz), `f_high > f_low` |
| `y_min`, `y_max` | bounds (at least one required) |
| `enabled` | default `true` |
| `label` | display label |

### Touchstone (`.s1p`/`.s2p`/`.sNp`)

FilterDesk reads Touchstone 1.0 with frequency units `HZ/KHZ/MHZ/GHZ`, formats
`RI/MA/DB`, and the `R <z0>` option line; it imports **S-parameters only**.
Export always writes Hz/RI and (for `.s2p`) requires equal real port impedances.

### CSV and SPICE

CSV columns are `frequency_hz`, `s21_db`, `s11_db`, `s22_db`, `s21_mag`,
`s11_mag`, `vswr`, `group_delay_s`, `il_db`, `rl_db`. The SPICE export is a flat,
LTspice-compatible netlist.

---

## 12. Approximation families reference

| Family | `family` value | Cutoff | Required extras | Order |
| --- | --- | --- | --- | --- |
| Butterworth | `butterworth` | −3 dB | — | ≥ 1 |
| Chebyshev Type I | `chebyshev_type_i` | ripple-edge | `passband_ripple_db` | ≥ 1 |
| Chebyshev Type II | `chebyshev_type_ii` | stopband-edge | `stopband_attenuation_db` | ≥ 1 |
| Elliptic (Cauer) | `elliptic` | ripple-edge | `passband_ripple_db` **and** `stopband_attenuation_db` (As > Ap) | ≥ 2 |
| Bessel | `bessel` | −3 dB | — | 1–10 |
| Gaussian | `gaussian` | −3 dB | — | 1–10 |
| Legendre | `legendre` | −3 dB | — | 2–9 |
| Constant-K | `constant_k` | −3 dB (image) | — | ≥ 1 |
| M-derived | `m_derived` | −3 dB (image) | `m_parameter` (0, 1) | ≥ 1 |

Butterworth/Bessel/Gaussian/Legendre/constant-*k*/m-derived must **not** set
ripple or stopband attenuation; Chebyshev Type I must not set stopband
attenuation; Chebyshev Type II must not set ripple.

---

## 13. Units and notation

Numeric fields accept engineering notation: an SI prefix and an optional unit.

- Examples: `140M`, `4.7p`, `10n`, `50`, `33e-9`, `1.5GHz`, `0.2pF`, `2.2uH`.
- Prefixes: `f, p, n, u (µ), m, k/K, M, G, T`.
- Unit suffixes are optional: `Hz`, `H`, `F`, `Ohm`/`ohm`/`Ω`, `s`, `S`.
- Case matters only for **`M`** (mega, 1e6) versus **`m`** (milli, 1e-3);
  `k`/`K` are both 1e3.
- Plain decimals and scientific notation are always accepted.

Values are displayed in engineering form (e.g. `4.7 pF`, `140 MHz`), and plot
axes use plain-decimal SI-prefixed ticks.

---

## 14. Troubleshooting and FAQ

**Printing shows nothing / "No circuit — click Synthesize".** You have not
synthesized yet. Press **Synthesize + Analyze** (`Ctrl+Return`).

**I changed the Specification but nothing updated.** Specification edits are not
applied automatically — press **Synthesize + Analyze**. (Circuit-level edits like
tuning *are* applied automatically.)

**"Invalid specification" when synthesizing.** A required field for the chosen
family is missing or out of range; check [§12](#12-approximation-families-reference)
(families/orders) and the field rules in [§11](#11-file-formats).

**The GUI will not start on a headless machine.** Set
`QT_QPA_PLATFORM=offscreen`.

**Import says the file has the wrong number of ports.** Only 2-port Touchstone
files map to an analysis result; `.s1p` files can be inspected but not overlaid.

**Optimize says "Add at least one enabled limit region first."** Add a limit in
the **Limits** dock and make sure its **On** flag is enabled.

**The Monte-Carlo run takes long.** Reduce **Trials** or sweep points; the run
happens in the background and reports progress in the status bar.

---

## 15. Known limitations

- **Lumped-element ladders only.** Transmission lines, stubs, impedance
  transformers, and coupled inductors are not implemented.
- **Asymmetric impedances** are handled by geometric-mean scaling
  (`√(Zs·Zl)`), an approximation; strongly unequal ports introduce error.
- **Even-order elliptic/Chebyshev II** synthesis uses an equal-termination fit
  with documented approximations.
- **Order caps** apply to some families (Bessel/Gaussian 1–10, Legendre 2–9).
- **Markers** are limited to 8 and **limits** to 10.
- The GUI analyzes with the `abcd` backend; use the CLI `--backend skrf` for a
  cross-check.

---

## 16. License

FilterDesk is licensed under **Apache-2.0**. See [`../LICENSE`](../LICENSE) and
[`../NOTICE`](../NOTICE). The GUI dynamically links Qt via PySide6 (LGPL-3.0).
