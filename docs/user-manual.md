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
15. [Model confidence and limitations](#15-model-confidence-and-limitations)
16. [Known limitations](#16-known-limitations)
17. [License](#17-license)

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

### Who this manual is for

This manual assumes you want to design, build or measure a real filter. It does
not assume a mathematics background. Each workflow starts from a practical
requirement (band, rejection, impedance, power) and explains the result,
including its model confidence and limitations.

### If you are a radio amateur

FilterDesk is aimed at **ham radio homebrew, repair, antenna and station
projects**. A good first path is:

| What you want | Where to start |
| --- | --- |
| Receive band-pass for 160–10 m | **Design → HF band filter wizard…** |
| Transmit low-pass for an HF/VHF rig | **Design → Band preset… → Transmit LPF** |
| Reject AM or FM broadcast | **Design → Band preset… → Band-stop**, or enter an HPF/BSF spec |
| 1:1 choke, 1:4 balun, 1:49 unun | **Tools → Transformer / balun / unun…** |
| Toroid or air-core coil | **Tools → Coil calculator…** |
| PCB microstrip/stub/quarter-wave | **Tools → Microstrip line…** |
| Low-pass filter as microstrip lines | **Design → Distributed microstrip realization…** |
| Compare a built filter with a VNA | **File → Import → Touchstone…**, then **Design → Tune to VNA measurement…** |
| Produce a BOM/build sheet | **File → Export → build sheet / BOM…** |

You do not need to know the synthesis theory to begin: choose the band, use the
wizard or preset, press **Synthesize + Analyze**, then inspect the response and
the model status. The **Help → Model confidence** window explains what is
validated, estimated or experimental.

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
| Debian/Ubuntu | `FilterDesk-<ver>-amd64.deb` | system package; `sudo apt install ./FilterDesk-<ver>-amd64.deb` |

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

**Impedances.** Source and load impedances may differ. The ladder is designed
for `Zs` and an **ideal output transformer** `T1` (`n = √(Zs/Zl)`) matches the
load, so the response is the exact equal-termination prototype response. See
[Known limitations](#15-known-limitations) for exports and even-order elliptic.

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
   - the central **Magnitude / S12 / S22 / Phase / VSWR / Group delay /
     Impedance / Smith** tabs show the response.
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
| **Harmonics** | right | `|S21|`/suppression at 2f, 3f, … of a fundamental |

The central area is a tabbed **plot panel**: **Magnitude**, **S12 / S22**,
**Phase**, **VSWR**, **Group delay**, **Impedance**, and **Smith**.

The **toolbar** holds **Synthesize**, **Analyze**, **Tune +** (`Ctrl+]`),
**Tune −** (`Ctrl+[`), and inline sweep controls (**Start Frequency**, **Stop
Frequency**, **N**). The **status bar** at the bottom reports progress, results,
and errors.

The window title shows `FilterDesk — <name>`, where `*` marks unsaved changes.
The name is the project title (see **File → Rename project…**) or, until you
name it, the saved file name or `Untitled`.

### Language

**View → Language** switches the GUI between **English** and **Español**. The
choice is saved with the other preferences and **applies on the next start**
(FilterDesk asks you to restart). The command-line interface and exported files
(netlists, CSV, Touchstone) stay in English so scripts and EDA tools keep
working. Domain/technical error text may also remain in English.

**View → Theme** switches between **System**, **Light** and **Dark**. The choice
is remembered across sessions, and the window size and dock layout are restored
on the next launch. The theme and language are stored in the platform's user settings
(QSettings), not inside the project file, so opening a project does not change
your appearance.

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

**Vpk/Ipk** show the peak voltage/current per part from the **nodal
power-stress analysis**: set the **TX Power** field in the toolbar (0 = off). The
circuit is solved at the passband landmark (cutoff for LP/HP, center for BP/BS)
with the actual source/load impedances and the boundary T1/BAL1, so resonances
and mismatch are included. `TX Power` is the source **available** power; a
matched 50 Ω load receives that power, while a mismatched load receives less.
The worst case is summarised in the status bar. Use it to pick voltage/current
ratings (e.g. capacitor voltage) for transmit filters. This is a linear
frequency-domain result, not a thermal or nonlinear stress simulation.

### Schematic panel

A read-only ladder diagram. Series arms are drawn on the signal line, shunt arms
go to ground; resonators, Brune arms, and non-ideal parts are labelled with their
values. **Left-click** an element to select it; **right-click** it to open the
element context menu (the same actions as **Design → Component**).

### Plot panel

Six tabs, all with a logarithmic frequency axis:

- **Magnitude** — |S21| and |S11| in dB (solid = simulated; dashed = measured;
  grey band = Monte-Carlo envelope).
- **S12 / S22** — reverse transmission |S12| (isolation) and output match |S22|.
- **Phase** — ∠S21 and ∠S11 in degrees.
- **VSWR** — input VSWR.
- **Group delay** — in seconds.
- **Impedance** — input impedance (|Zin|, Re(Zin), Im(Zin)) and |Zout| in ohms.
- **Smith** — S11 (red) and S22 (blue) loci. Measured loci and the
  `S11 meas` / `S22 meas` legend entries appear only after a Touchstone file is
  loaded.

A **cursor readout** below the tabs reports `f`, `S21`, `S11`, `S22`, `S12`,
`VSWR`, group delay, ∠S21, and |Zin| at the nearest sweep point, plus
Monte-Carlo and marker details when present. When a measured Touchstone overlay
is visible, it also appends the measured `S21`, `S11`, `VSWR`, ∠S21 and their
deltas (`sim − meas`) at the cursor frequency; frequencies outside the measured
band show `—`.

---

## 6. Design workflows (GUI)

All design-changing actions are **undoable** (`Ctrl+Z` / `Ctrl+Shift+Z`).
Circuit-level edits trigger an automatic re-analysis after a short delay;
specification edits require an explicit **Synthesize**.

| Workflow | How to trigger | Notes |
| --- | --- | --- |
| **Synthesize + Analyze** | `Ctrl+Return`, toolbar **Synthesize**, Design menu | builds circuit from spec + sweep, then analyzes |
| **Band preset** | **Design → Band preset…** | one-click LP/HP/BP/BS design for 160 m–6 m and AM/FM broadcast notches (Chebyshev-I, order 5, sets sweep) |
| **HF band filter wizard** | **Design → HF band filter wizard…** | receive-band BPF workflow: band + max IL/rejection → order search → apply, optional E24 snap |
| **Update spec from circuit** | **Design → Update spec from circuit…** | derive cutoff/center and bandwidth from the current analyzed response; family, order and topology are kept, and the circuit is not changed |
| **Harmonic readout** | **Harmonics** dock | table of `|S21|` and suppression at 2f, 3f, … of the fundamental |
| **Attenuator pad** | **Tools → Attenuator pad…** | designs a symmetric T/Pi pad and inserts it at the input |
| **Matching network** | **Tools → Matching network…** | L/Pi/T match from Z0 to a complex load; optionally models the load |
| **Coil calculator** | **Tools → Coil calculator…** | tabs: **Toroid** (turns, wire gauge, flux/saturation) and **Air-core** solenoid (turns, length, R_DC, enamelled wire by default) |
| **Transformer / balun / unun** | **Tools → Transformer / balun / unun…** | topology and winding options, core/turns/wire, leakage/core loss, TLT models, output-boundary insertion and BOM |
| **Microstrip line** | **Tools → Microstrip line…** | Hammerstad-Jensen synthesis: width, effective er, guided wavelength, quarter-wave length and first-order conductor/dielectric loss |
| **Tune to VNA** | **Design → Tune to VNA measurement…** | least-squares trim of L/C/R values to an imported measured S11/S21 magnitude response |
| **Analyze** | toolbar **Analyze** | re-analyzes; synthesizes first if needed |
| **Estimate order** | **Estimate N** in the Specification panel | LP/HP classical families |
| **Snap to E-series** | **Design → Snap to E-series…** | picks series (E6–E96) and strategy |
| **Apply parasitics / finite Q** | **Design → Apply parasitics / Q…** | whole-circuit non-ideal conversion |
| **Monte-Carlo tolerances** | **Design → Monte-Carlo tolerances…** | runs in the background; overlays the S21 envelope |
| **Optimize to limits** | **Design → Optimize to limits…** | requires at least one enabled limit |
| **Component sensitivity** | **Design → Component sensitivity…** | ranks parts by their effect on the response; suggests a tune direction when limits are set |
| **Parameter sweep** | **Design → Parameter sweep…** | synthesizes a series of variants (order, family, frequency, ripple…) and compares metrics; a row can be loaded into the design |
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
the overlay with **View → Show measured overlay**. The measured legend entries
are hidden until a file is loaded and while the overlay is disabled.

---

## 9. Saving, opening, and exporting

| Action | Menu | Shortcut | Format |
| --- | --- | --- | --- |
| New project | File → New | `Ctrl+N` | — |
| Open project | File → Open… | `Ctrl+O` | `.filterdesk.json` |
| Recent projects | File → Recent projects | — | `.filterdesk.json` |
| Save / Save As | File → Save / Save As… | `Ctrl+S` | `.filterdesk.json` |
| Rename project | File → Rename project… | — | — |
| Import measured | File → Import → Touchstone… | — | `.s1p`/`.s2p`/`.sNp` |
| Export Smith chart | File → Export → Smith chart… | — | `.png`/`.svg`/`.pdf` |
| Export CSV | File → Export → CSV… | — | `.csv` |
| Export Touchstone | File → Export → Touchstone (.s2p)… | — | `.s2p` |
| Export SPICE netlist | File → Export → SPICE netlist… | — | `.net`/`.cir` (LTspice) |
| Export LTspice schematic | File → Export → LTspice (.asc)… | — | `.asc` |
| Export Qucs schematic | File → Export → Qucs (.sch)… | — | `.sch` (best-effort) |
| Export build sheet / BOM | File → Export → build sheet / BOM… | — | `.md`, `.csv`, `.html` |

The native project file stores the specification, circuit, sweep settings,
markers, limits, per-component tolerances and tune steps, the TX Power setting,
the harmonic-readout fundamental, and metadata; it is reloadable and editable.

**File → Recent projects** lists the last ten projects opened or saved, most
recent first. Missing files are removed automatically; **Clear recent projects**
empties the list. The list is stored in the application settings, not in the
project file.

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
filterdesk {synthesize,analyze,gui,bands,attenuator,match,snap,montecarlo,
            optimize,to-csv,estimate-order,touchstone-info,compare} ...
```

Global options: `-h/--help`, `--version`.

`--band NAME` (e.g. `40m`, `am`, `fm`) builds a spec from a preset and
`--band-kind {lpf,hpf,bpf,bsf}` selects the kind; `filterdesk bands` lists them.

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
  `--inductor-dcr`, `--inductor-cpar`, `--inductor-srf`,
  `--inductor-loss-model {constant,dc_skin}`, `--inductor-dc-current`,
  `--inductor-i-sat`, `--capacitor-esr`, `--capacitor-esl`),
  power stress (`--power W`), the harmonic readout (`--harmonics`,
  `--harmonics-f0 F`), and exporters `--export-s2p`, `--export-smith`,
  `--export-csv`, `--export-spice`, `--export-asc`, `--export-qucs`,
  `--export-build-sheet`. Build-sheet options: `--bom-series {E6,E12,E24,E48,E96}`,
  `--bom-group`, and `--bom-columns` (comma-separated CSV columns).
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
- **`sweep`** — synthesize a series of variants along one axis and compare them.
  `--axis {order,family,cutoff,center,bandwidth,ripple,stopband_att,m_factor}`,
  `--values` (comma-separated; SI units for frequency axes), optional
  `--pass-band`/`--stop-band` for the metrics, `--points`, `--csv FILE` and
  `--json`. Invalid combinations (e.g. even-order elliptic) are reported per
  row without aborting the sweep. Example:
  ```bash
  filterdesk sweep --axis order --values 3,5,7,9 \
      --family chebyshev_type_i --response low_pass --order 5 \
      --cutoff 100M --ripple 0.1
  ```
- **`sensitivity`** — rank tunable components by their effect on the response.
  `--relative-step` (default 1 %), optional `--band-range LOW HIGH`, and
  `--limits FILE` / `--objective …` to obtain a tuning direction. Sweep and
  `--backend` options mirror `analyze`. Example:
  ```bash
  filterdesk sensitivity --spec spec.json --limits limits.json \
      --band-range 130M 150M
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
- **`bands`** — list the amateur/broadcast band presets.
- **`attenuator`** — symmetric T/Pi pad (`--db`, `--z0`, `--kind`, `--json`).
- **`match`** — L/Pi/T match to a complex load (`--z0`, `--rl`, `--xl`, `--f`,
  `--topology`, `--q`, `--json`).
- **`toroid`** — toroid turns/wire/saturation. Use `--core NAME` (or `--al AL`
  plus optional `--od/--id/--height/--bsat`) with either `--inductance` or
  `--turns`; add `--current A` for flux density, `--list` to show the cores, and
  `--json` for machine output.
  ```bash
  filterdesk toroid --core T50-2 --inductance 1u --current 1
  filterdesk toroid --core FT50-43 --turns 5 --current 0.5 --json
  ```
- **`transformer`** — unified transformer / unun / balun designer on a built-in
  toroid core: `filterdesk transformer --kind guanella --z-low 50 --z-high 200
  --core FT240-43 --frequency 3.5M --f-max 30M --power 100`. It reports
  topology/options, turns, Lm/Lk/Rp, V/I, flux versus Bsat, wire gauges and
  single-layer fit; use `--show-options` for 2:14/3:21/4:28-style alternatives.
- **`microstrip` / `qwt` / `stub`** — microstrip line, quarter-wave transformer,
  and open/short stub on a built-in substrate (`--substrate FR4` or overrides
  `--er`, `--h`, `--tan-delta`, `--t`, `--roughness`). Example:
  `filterdesk microstrip --z0 50 --substrate FR4 --frequency 1G --length 50m`.
- **`distributed`** — experimental microstrip stepped-impedance low-pass
  realization (Butterworth/Chebyshev-I, order ≤ 3):
  `filterdesk distributed --family butterworth --response low_pass --order 3
  --cutoff 100M --substrate FR4 --export-s2p out.s2p --export-build-sheet bom.csv`.
  Use `--angle`, `--z0-min` and `--z0-max` to control the line geometry.
- **`tune-vna`** — synthesize from a spec, then trim component values to a
  measured `.s2p`: `filterdesk tune-vna measured.s2p --family chebyshev_type_i
  --response low_pass --order 4 --cutoff 100M --ripple 0.1 --bound 0.2`.
  Add `--holdout holdout.s2p` for post-fit evaluation and `--fit-phase` for
  phase/delay; metadata is read from `<measured>.s2p.vna.json` or `--metadata`.
- **`air-coil`** — single-layer close-wound air-core solenoid (Wheeler). Requires
  `--diameter mm` and either `--awg` or `--wire-mm`; use `--inductance` or
  `--turns`. Wire is enamelled grade 1 by default (`--bare-wire` or
  `--enamel-mm` to override); `--json` for machine output.
  ```bash
  filterdesk air-coil --diameter 10 --awg 24 --inductance 1u
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

A versioned JSON document (`format_version: 2`; v1 still loads) with
`metadata`, `specification`,
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

### Build sheet / BOM

**File → Export → build sheet / BOM…** (or `analyze --export-build-sheet PATH`)
writes one row per physical part, expanding compound elements (`X1.L`/`X1.C`,
Brune `Ls/Cs/Lp/Cp`). Before choosing the file, the GUI offers an optional
**E-series** snap and a **group identical parts** checkbox.

The format follows the extension:

- `.csv` — machine-readable BOM. Default columns: `ref`, `qty`, `role`, `type`,
  `value`, `value_si`, `unit`, `series`, `nearest_value`, `delta_pct`,
  `tolerance_pct`, `parasitic`, `dcr_ohm`, `srf_hz`, `core`, `turns`,
  `wire_awg`, `v_peak_v`, `i_peak_a`. Use `--bom-columns` to pick a subset.
- `.md` / `.html` — printable build sheet with the specification summary, the
  BOM table (values, tolerance, parasitics, DCR/SRF, winding, peak V/I) and
  optional notes. HTML has no external assets, so it prints or exports to PDF
  from a browser.

Options: `--bom-series E24` snaps L/C to a preferred series (showing the nearest
value and the relative change), and `--bom-group` merges identical parts into one
row with a combined reference list and a quantity.

Per-part tolerances (GUI) and the power-stress columns (when **TX Power** is set)
are included automatically.

### HF receive-band filter wizard

**Design → HF band filter wizard…** builds a Chebyshev-I receive-band BPF from
practical requirements, not from a fully specified prototype:

- choose the amateur band and source/load impedance;
- enter maximum passband insertion loss and minimum stopband attenuation;
- choose how far outside the allocation the rejection is required
  (`Stopband guard` as a percentage of the band span; default 50 %);
- the wizard searches orders 2…N and shows passband/rejection for every
  candidate, selecting the lowest order that meets both;
- **Apply to project** synthesizes the selected design and sets a band sweep;
  optionally **Snap to E24 after apply** converts the values to commercial
  series values before analysis.

After applying, use **File → Export → build sheet / BOM…** and the normal VNA
measurement compare/overlay. The wizard is a starting design: verify the final
values, parasitics and rejection with the normal analysis and measurement
workflow.

### Updating the target spec from the circuit

If you edit component values manually, the project can intentionally have a
target specification that no longer matches the actual response. **Design →
Update spec from circuit…** derives a new target cutoff (or center/bandwidth
for BP/BS) from the current analyzed response. It uses the family's criterion:
ripple edge for Chebyshev I/elliptic, stopband edge for Chebyshev II, otherwise
−3 dB. Family, order, topology, ripple and stopband parameters are retained;
the circuit is not re-synthesized. The action is undoable. This changes the
**target**, not the circuit: pressing Synthesize afterwards creates a new ideal
circuit from the updated target.

### Coil calculator

**Tools → Coil calculator…** has two tabs; both are also available from the CLI.

**Toroid** (`filterdesk toroid`) computes windings from `L = AL * N^2`, with AL in
nH/N². The built-in table covers common Amidon/Fair-Rite iron-powder cores
(mixes 2, 6, 10) and ferrite mixes 31/43/52/61, including the HF power sizes
FT37/FT50/FT82/FT114/FT140/FT240/FT290; `--al`/`--od`/`--id`/`--height` accept a
custom core. With a
target inductance the turn count is rounded **up**, so the achieved L is at least
the requested value. It also reports:

- the thickest **AWG** that fits a single layer through the inner diameter
  (85 % fill), with the estimated wire length;
- peak flux density `B = L*I / (N*Ae)` and `B/Bsat` for ferrite cores
  (Bsat is the room-temperature typical value; derate it with temperature).

AL spread is typically ±20–25 % (vendor test conditions differ); ferrite AL
entries are typical μi/dimension-derived values, not individually measured. `Ae` is derived
geometrically from the catalog dimensions (coating ignored), and iron-powder
cores do not show a Bsat check. Mix 31 is intended for low-HF common-mode
chokes, 43 for general HF power, 52 for wideband/high-power, and 61 for the
higher HF bands.
Treat the result as a starting point and verify against the core datasheet.

**Air-core** (`filterdesk air-coil`) designs a single-layer, close-wound
solenoid using Wheeler's formula `L[uH] = a^2 N^2 / (9a + 10b)`, with `a` the
radius and `b = N * pitch` the winding length (inches internally). Inputs are the
target L (or fixed turns), coil diameter and the wire size — **AWG** or its
**bare diameter in mm**. By default the wire is **grade-1 enamelled**: the bare
copper sets the DC resistance, while a typical enamel build (interpolated from
IEC 60317-0-1) sets the pitch and length. Use a build of `0` for bare copper or
enter a custom build in mm. Outputs are turns, coil length, length/diameter,
bare/overall wire size, wire length and DC resistance; the best turn count below
the target is also shown, because air-core turn steps are coarse.

### Transformer / balun / unun

**Tools → Transformer / balun / unun…** is the single designer for
transformer-type ununs, baluns and power transformers. It combines the turns
calculator, the electrical model and the output-boundary insertion that were
previously split across two tools.

- **Design:** core, kind (`ideal`, `unun`, `guanella`, `ruthroff`, `choke`),
  topology, low/high impedance, lowest/highest frequency and power. The
  winding-options table shows compact / recommended / robust candidates for the
  same ratio. For 50 -> 2500 Ω these are typically **2:14**, **3:21** and
  **4:28**; all give 49:1, but they are not equivalent.
- **Topology:** the default is an **autotransformer** (one tapped winding:
  input across `Np`, output across `Ns`, total `Ns`, no galvanic isolation).
  Select **isolated** for two separate windings (total `Np + Ns`).
- **Model:** coupling/leakage, core `tan delta` (shunt `Rp`), winding
  capacitance and, for TLT kinds, line `Z0`, length, velocity factor and loss.
  Integer 1:N² Guanella ratios use an explicit **N-line parallel/series**
  network; 1:4/4:1 Ruthroff uses an equal-delay bootstrap network. Non-integer
  Guanella and other Ruthroff ratios use the first-order transformer + TEM-line
  model. The Model tab shows a five-point **mixed-mode** table (`Sdd21` and
  `|Scc|`) and, for chokes, a five-point common-mode sweep. The CLI JSON includes
  `mixed_mode` and `common_mode_sweep`. These are block-diagonal boundary
  estimates: cross-mode terms are zero, and they are not a full asymmetric
  4-port/EM model.
  Core loss uses Fair-Rite complex-permeability data for mixes 31/43/52/61;
  copper loss and a natural-convection thermal resistance give an estimated hot
  temperature. This is a sizing estimate, not a high-flux or thermal simulation.
- **Apply:** inserts the result as `BAL1` at the circuit output. It appears in
  the project, component table and BOM with core, turns, AWG, the selected
  winding option and the low/high DCR estimate. The DCR is a 20 °C copper
  estimate from mean turn length and AWG; skin/proximity, leads and temperature
  are not included. The dialog has only **Design** and **Model** tabs; winding
  diagrams were removed because they were not reliable enough.

The displayed ratio is explicit: for 50 → 2500 Ω with 3:21 it shows
**`1:7 turns / 1:49 Z`**, not an ambiguous `0.1429:1`. The options table uses
**`Bsat/B`** (safety margin), not `B/Bsat`. More turns increase `Lm` and lower
peak flux, but also add leakage and winding capacitance. At high HF (for example
28 MHz), prefer fewer turns: 4:28 is flagged as `HF 28T` when the highest
frequency is ≥20 MHz.

The **Flags** column is intentionally stricter and explicit: `LF X/Z ...`,
`SAT ...` (Bsat/B below 3), `FIT no`, `HF ...`, and `THERMAL ...`. The table
wraps the flags, stretches that column, and shows a full tooltip; a legend below
the table explains every code.
The thermal estimate uses vendor complex-permeability data (μ' and μ'') for
power-rated mix 61, evaluates core loss over the band, adds an approximate
copper loss, and applies a natural-convection thermal resistance for the core.
It reports the estimated hot temperature and flags `THERMAL` above 100 °C; above
the material's Curie point it reports `>Tc`. Mixes 31/43/52 are suppression
materials without public high-flux power-loss curves, so their thermal rise is
reported as **not evaluated** instead of extrapolating low-flux μ''. The model
assumes a matched sinusoidal load; mismatch, DC bias, duty cycle, mounting and
ambient temperature can make the real rise worse. Measure the actual rise for
power designs.

Ferrite material data for mixes 31/43/52/61 includes initial permeability,
saturation flux, Curie temperature and Fair-Rite complex-permeability points
(μ'/μ''). Core loss is calculated from those points; the project does not claim
fitted Steinmetz coefficients, because the complex-permeability model is used
instead. Ferrite AL entries are typical values derived from Fair-Rite μi and
nominal dimensions; confirm the actual core batch.

The model is **first-order and behavioral**: the TLT section is a single TEM
line, not a full multi-line Guanella/Ruthoff derivation or an EM simulation;
the differential two-port cannot represent a choke's common-mode stopband.
Verify the real winding, common-mode impedance, core loss and
temperature/DC-bias derating on hardware. SPICE/LTspice/Qucs exports represent
the ideal transformer part; SPICE adds the scalar leakage/core-loss terms, but
the TLT line section is not exported.

### Microstrip / distributed calculators

**Tools → Microstrip line…** (`filterdesk microstrip`) synthesizes a
microstrip width from a target `Z0`, substrate (`FR4`, `RO4350B`, `RO4003C`,
`PTFE`, `Alumina`, `Air`) and frequency, using the Hammerstad-Jensen
quasi-static model. It reports `eeff`, guided wavelength, quarter-wave length,
and first-order conductor/dielectric loss (`dB/m` and for an optional length).
`filterdesk qwt` sizes a quarter-wave transformer
(`Z0 = sqrt(Z_low*Z_high)`), and `filterdesk stub` gives the width, length and
input reactance of an open or short stub at a chosen electrical angle.

Limitations: strip thickness is not included in `Z0`; conductor loss uses a
surface-resistance/skin-depth approximation and dielectric loss the standard
quasi-static formula. The distributed **analysis** applies Kirschning-Jansen
dispersion when substrate geometry is stored, but the standalone calculators
report quasi-static values. Discontinuities, radiation and finite-ground-plane
effects are not modelled. Verify the layout with a 2-D/3-D field solver or VNA.

### Distributed microstrip realization (experimental)

**Design → Distributed microstrip realization…** converts the current
low-pass specification into a cascade of microstrip lines. It is intended for
PCB low-pass filters, not for arbitrary distributed networks.

- Supported: **Butterworth** and **Chebyshev-I low-pass**, order **1–5**.
- Orders **1–3** use the analytical stepped-impedance formulas. Orders **4–5**
  use a bounded numerical fit and are accepted only if passband/stopband gates
  pass; otherwise the tool returns an explicit error instead of a questionable
  design.
- Choose substrate, requested electrical length and a `Z0` range (default
  **10–250 Ω**). The tool starts at the requested angle and adjusts it (up to
  80°) to keep every line inside the range; warnings report the adjustment and
  any very narrow/wide traces. High-order fits may sit near the impedance limits.
- Series inductors become high-impedance lines and shunt capacitors become
  low-impedance lines. The preview lists `Z0`, trace width, length and angle.
- Apply creates a normal circuit: it appears in the schematic, component table,
  project, BOM and Touchstone export. The action is undoable.
- The model is **experimental**: lines use Kirschning-Jansen dispersion and
  open stubs include the Hammerstad open-end fringing correction when substrate
  `er`/height/width are available. Step discontinuities, radiation, coupling and
  fabrication tolerances are not modeled. It is not a hardware-validated
  engine. Verify the board with Touchstone/VNA.
- **SPICE netlist** export now represents series lines and shunt stubs with
  ideal lossless `T` elements (open/short stub terminated). Integer-ratio
  Guanella TLTs export as parallel/series `T` lines with an optional center-node
  `Lcm`; Ruthroff 1:4 step-up exports as one bootstrap `T` line with a floating
  balanced load. The Transformer / balun / unun dialog exposes **Export TLT
  SPICE…** for these supported kinds. Both are validated with ngspice. LTspice
  `.asc`, Qucs `.sch`
  and reverse/other Ruthroff ratios remain unsupported. Loss, dispersion,
  discontinuities and radiation are not in the exported model.

On the command line:

```bash
filterdesk distributed --family butterworth --response low_pass --order 3 \
  --cutoff 100M --substrate FR4 --json
filterdesk distributed --family chebyshev_type_i --ripple 0.1 --response low_pass \
  --order 5 --cutoff 100M --export-s2p out.s2p --export-build-sheet bom.csv
```

Manual line and stub elements are also part of the canonical netlist and both
ABCD/skrf backends. Stubs are not produced by the v1 low-pass synthesis; series
stubs, Kuroda transforms, coupled lines and higher-order synthesis remain future
work.

### VNA-guided tuning

The full measurement protocol is in [VNA measurement protocol](vna-measurement-protocol.md).

Import a measured 2-port Touchstone file (**File → Import → Touchstone…**),
synthesize/analyze the nominal design, then use **Design → Tune to VNA
measurement…** (`filterdesk tune-vna`). The dialog fits the circuit's L/C/R
values to the measured **magnitude** of S21 and/or S11 over the overlap band.
The fit is a bounded local trim (`±20 %` by default) around the current values;
it reports initial/final RMS error in dB, the per-component changes, and can
apply the tuned circuit as one undoable edit.

Phase fitting is optional (`--fit-phase`): it adds a shared delay and per-signal
phase offsets, and is only meaningful with a known calibration/reference plane.
Deep stopband points are floored at −80 dB to avoid fitting noise. Bounds can be
local, wide or multi-start global; the fit can be restricted to selected refs in
the API. The CLI accepts a second `--holdout` capture and reads a
`<capture>.vna.json` metadata sidecar; the holdout is evaluated only after the
fit. Quality notes flag high RMS, values at bounds, delay at a bound and a
holdout much worse than the fit. Use a calibrated measurement and verify against
component tolerances before committing to hardware.

It does **not** model self-capacitance/SRF, AC resistance or Q, and accuracy
drops for very short coils (`length/diameter < 0.2`, flagged in the result).

When opened with an inductor selected in the schematic/table, the calculator
shows an **Apply to selected inductor** button: it turns the ideal value into the
physical winding (achieved L, DCR from the wire, core/turns/gauge provenance) and
installs it in the circuit as an undoable edit. Applying a toroid also derives a
saturation current (`I_sat = Bsat·N·Ae/L`) so the analysis can derate the
inductance for a DC bias. The model is described in
[ADR-016](adr/ADR-016-inductor-model.md): Q may be entered at a reference
frequency, `srf_hz` sets the parallel resonance, and the optional `dc_skin` loss
model makes the resistance rise with `sqrt(f)`.

---

## 12. Approximation families reference

| Family | `family` value | Cutoff | Required extras | Order |
| --- | --- | --- | --- | --- |
| Butterworth | `butterworth` | −3 dB | — | ≥ 1 |
| Chebyshev Type I | `chebyshev_type_i` | ripple-edge | `passband_ripple_db` | ≥ 1 |
| Chebyshev Type II | `chebyshev_type_ii` | stopband-edge | `stopband_attenuation_db` | ≥ 1 |
| Elliptic (Cauer) | `elliptic` | ripple-edge | `passband_ripple_db` **and** `stopband_attenuation_db` (As > Ap) | odd ≥ 3 |
| Bessel | `bessel` | −3 dB | — | 1–10 |
| Gaussian | `gaussian` | −3 dB | — | 1–10 |
| Legendre | `legendre` | −3 dB | — | 2–9 |
| Constant-K | `constant_k` | −3 dB (image) | — | ≥ 1 |
| M-derived | `m_derived` | −3 dB (image) | `m_parameter` (0, 1) | ≥ 1 |

Butterworth/Bessel/Gaussian/Legendre/constant-*k*/m-derived must **not** set
ripple or stopband attenuation; Chebyshev Type I must not set stopband
attenuation; Chebyshev Type II must not set ripple. Even-order elliptic needs a
transformer or unequal terminations and is **rejected** (use an odd order).
Even-order Chebyshev I uses the classical equal-ripple prototype plus an
ideal output transformer, so its response and element values match the textbook
tables.

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

### Glossary for newcomers

- **Passband / stopband** — frequencies the filter should pass / reject.
- **Cutoff / corner** — the transition frequency; the UI states whether it is
  the −3 dB point, ripple edge or stopband edge.
- **S11 / S21** — input reflection and forward transmission; dB values are
  relative to the incident wave.
- **VSWR / return loss** — measures of impedance match.
- **E-series** — standard commercial component values (E6, E12, E24, …).
- **Toroid** — a ring-shaped magnetic core for inductors and transformers.
- **Unun / balun** — unbalanced-to-unbalanced / balanced-to-unbalanced
  transformer.
- **VNA** — vector network analyzer; measures S-parameters of a real circuit.
- **Model confidence** — whether a result is validated, cross-checked,
  estimated, experimental or not evaluated.

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

## 15. Model confidence and limitations

The filter response panel shows a compact **Model status** strip: synthesis
(e.g. `validated`), analysis (`cross-checked`) and components (`ideal`, or
`estimated` after parasitics). If the project has a T1/BAL1, their model status
is shown too. **Help → Model confidence…** shows the full inventory. The
statuses are:

| Status | Meaning |
| --- | --- |
| **validated** | Reference/golden cases or an independent solver agree. |
| **cross-checked** | Compared against a second backend or import/export round-trip. |
| **estimated** | First-order/approximate model; assumptions are documented. |
| **experimental** | Useful workflow, but not yet validated on hardware. |
| **not evaluated** | Calculator or interface exists, but it is not a validated model. |

Important examples: LC synthesis and T1 are validated; ABCD↔scikit-rf and
Touchstone I/O are cross-checked; ideal filter components are a separate
`ideal` state (upgraded to `estimated` when parasitics are applied); ferrite
loss/temperature, microstrip and toroid calculators are estimated; VNA tuning,
Guanella/Ruthroff TLT and distributed microstrip synthesis are experimental. The
build sheet includes an **Assumptions** section with the same model limits. The
detailed test cases and tolerances are in
[Validation matrix](validation-matrix.md).

## 16. Known limitations

- **Lumped-element ladders only.** Distributed line/stub calculators exist, but
  transmission lines, stubs and coupled inductors are not ladder elements.
  Unequal ports use an ideal **output** transformer or a boundary `BAL1`;
  mid-ladder transformers are not implemented. The balun/TLT model is
  behavioral, not a full Guanella/Ruthroff or EM simulation.
- **Transformer exports**: the ideal `T1` is included in analysis, compliance,
  project files and the BOM. SPICE uses an exact E/F controlled-source model;
  LTspice `.asc` embeds the same directives; Qucs `.sch` uses a best-effort
  `Tr` component (verify the ratio orientation in Qucs).
- **Even-order elliptic** is rejected (it needs an unequal-R Cauer synthesis);
  **even-order Chebyshev I** uses the classical prototype + output transformer
  and matches textbook values (see §12).
- **Order caps** apply to some families (Bessel/Gaussian 1–10, Legendre 2–9).
- **Real-inductor model is approximate**: `dc_skin` is a simple `sqrt(f)` law, DC
  bias uses a core-agnostic `1/(1+(I/Isat)²)` derating, and air-core coils do not
  model SRF/Q (see [ADR-016](adr/ADR-016-inductor-model.md)).
- **Ferrite loss/thermal model**: thermal loss is evaluated only for power-rated
  mix 61 using low-flux complex-permeability data; 31/43/52 are marked not
  evaluated because public high-flux curves are unavailable. It is not a
  high-flux thermal simulation; validate power designs with the core datasheet or
  measurement. Ferrite AL values are typical μi/dimension-derived values; confirm
  the exact batch.
- **Markers** are limited to 8 and **limits** to 10.
- The GUI analyzes with the `abcd` backend; use the CLI `--backend skrf` for a
  cross-check.

---

## 17. License

FilterDesk is licensed under **Apache-2.0**. See [`../LICENSE`](../LICENSE) and
[`../NOTICE`](../NOTICE). The GUI dynamically links Qt via PySide6 (LGPL-3.0).
