"""CLI entry point."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from filterdesk import __version__
from filterdesk.analysis.adapters.abcd_ladder import AnalysisError
from filterdesk.analysis.compliance import (
    ComplianceResult,
    check_spec_compliance,
)
from filterdesk.analysis.derived import (
    group_delay_s,
    insertion_loss_db,
    mag_db,
    return_loss_db,
    vswr,
)
from filterdesk.analysis.harmonics import (
    HarmonicError,
    HarmonicReport,
    compute_harmonics,
)
from filterdesk.analysis.sensitivity import SensitivityReport, sensitivity
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.stress import StressError, StressReport, compute_stress
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import (
    AirCoilError,
    AttenuatorError,
    AttenuatorKind,
    BalunError,
    BalunKind,
    ESeries,
    MatchingError,
    MatchingTopology,
    MicrostripError,
    SnapReport,
    SnapStrategy,
    StubKind,
    Substrate,
    ToroidError,
    TransformerTopology,
    design_air_coil,
    design_attenuator,
    design_balun,
    design_balun_options,
    design_matching,
    design_microstrip,
    design_quarter_wave_transformer,
    design_stub,
    design_toroid,
    find_core,
    find_substrate,
    list_cores,
    make_custom_core,
    nonidealize_circuit,
    snap_circuit,
)
from filterdesk.domain.circuit import (
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealSeriesLC,
    MicrostripLineElement,
    MicrostripStubElement,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.overlays import LimitRegion, limits_from_mapping
from filterdesk.domain.specs import (
    FilterSpec,
    SpecValidationError,
    default_cutoff_definition,
    default_topology,
    filter_spec_from_mapping,
    filter_spec_to_mapping,
)
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.io.build_sheet import write_build_sheet
from filterdesk.io.csv_export import (
    COLUMNS,
    CsvExportError,
    analysis_from_touchstone,
    export_csv,
)
from filterdesk.io.qucs import write_qucs_schematic
from filterdesk.io.spice import write_ltspice_asc, write_spice_netlist
from filterdesk.io.touchstone import (
    TouchstoneError,
    read_touchstone,
    write_touchstone_s2p,
)
from filterdesk.montecarlo import (
    ElementTolerance,
    MonteCarloConfig,
    MonteCarloResult,
    ToleranceDistribution,
    run_monte_carlo,
    wilson_interval,
)
from filterdesk.optimization import (
    Objective,
    OptimizationConfig,
    OptimizationResult,
    OptimizeMethod,
    PassbandRipple,
    ReturnLoss,
    StopbandAttenuation,
    optimize_circuit,
)
from filterdesk.plotting import get_plot_backend
from filterdesk.services.bands import (
    ALL_PRESETS,
    BandKind,
    band_preset_spec,
    find_band,
)
from filterdesk.services.compare import CompareError, compare_results
from filterdesk.services.design_sweep import (
    DesignSweepConfig,
    DesignSweepRow,
    SweepAxis,
    parse_values,
    run_design_sweep,
)
from filterdesk.services.session import default_sweep_for_spec
from filterdesk.services.vna_measurement import (
    metadata_path_for,
    read_vna_metadata,
)
from filterdesk.services.vna_tuning import (
    VnaBoundMode,
    VnaTuningConfig,
    VnaTuningError,
    fit_circuit_to_measurement,
)
from filterdesk.synthesis import synthesis_note, synthesize
from filterdesk.synthesis.api import SynthesisResult
from filterdesk.synthesis.distributed import (
    DistributedSynthesisError,
    design_distributed_lowpass,
)
from filterdesk.synthesis.order_estimate import (
    OrderEstimateError,
    estimate_minimum_order,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filterdesk",
        description=(
            "FilterDesk: passive lumped-element RF filter synthesis and analysis."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"filterdesk {__version__}",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    sub = parser.add_subparsers(dest="command")

    syn = sub.add_parser(
        "synthesize",
        help="Synthesize a filter from a JSON spec or CLI parameters",
    )
    _add_spec_args(syn)
    syn.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (spec + prototype + components)",
    )
    syn.add_argument(
        "--check",
        action="store_true",
        help="Analyze the result and check it meets the requested specification",
    )

    ana = sub.add_parser(
        "analyze",
        help="Synthesize (unless circuit-only later) and analyze frequency response",
    )
    _add_spec_args(ana)
    ana.add_argument("--f-start", default=None, help="Sweep start (Hz), e.g. 10M")
    ana.add_argument("--f-stop", default=None, help="Sweep stop (Hz), e.g. 1G")
    ana.add_argument("--points", type=int, default=2048, help="Number of points")
    ana.add_argument(
        "--spacing",
        choices=[s.value for s in SweepSpacing],
        default=SweepSpacing.LOGARITHMIC.value,
        help="Frequency spacing",
    )
    ana.add_argument(
        "--backend",
        choices=["abcd", "skrf"],
        default="abcd",
        help="Analysis backend",
    )
    ana.add_argument(
        "--inductor-q",
        type=float,
        default=None,
        help="Apply finite unloaded Q to inductors (needs --q-frequency)",
    )
    ana.add_argument(
        "--q-frequency",
        default=None,
        help="Reference frequency for --inductor-q, e.g. 100M",
    )
    ana.add_argument(
        "--inductor-dcr",
        default=None,
        help="Add series resistance to inductors, e.g. 0.5 (ohm)",
    )
    ana.add_argument(
        "--inductor-cpar",
        default=None,
        help="Inductor parasitic parallel capacitance, e.g. 0.2p",
    )
    ana.add_argument(
        "--capacitor-esr",
        default=None,
        help="Capacitor equivalent series resistance, e.g. 0.05",
    )
    ana.add_argument(
        "--capacitor-esl",
        default=None,
        help="Capacitor equivalent series inductance, e.g. 0.5n",
    )
    ana.add_argument(
        "--inductor-srf",
        default=None,
        help="Inductor self-resonant frequency, e.g. 500M",
    )
    ana.add_argument(
        "--inductor-loss-model",
        choices=["constant", "dc_skin"],
        default=None,
        help="Inductor resistance model (constant or rising with sqrt(f))",
    )
    ana.add_argument(
        "--inductor-dc-current",
        default=None,
        help="DC bias current for inductance derating, e.g. 5",
    )
    ana.add_argument(
        "--inductor-i-sat",
        default=None,
        help="Inductor saturation current, e.g. 8",
    )
    ana.add_argument(
        "--export-s2p",
        type=Path,
        default=None,
        help="Write Touchstone .s2p to this path",
    )
    ana.add_argument(
        "--export-smith",
        type=Path,
        default=None,
        help="Write Smith chart image (.png/.svg/.pdf) to this path",
    )
    ana.add_argument(
        "--export-csv",
        type=Path,
        default=None,
        help="Write trace CSV (frequency, S21/S11 dB, VSWR, …) to this path",
    )
    ana.add_argument(
        "--export-spice",
        type=Path,
        default=None,
        help="Write an LTspice-compatible SPICE netlist to this path",
    )
    ana.add_argument(
        "--export-asc",
        type=Path,
        default=None,
        help="Write an LTspice .asc schematic to this path",
    )
    ana.add_argument(
        "--export-qucs",
        type=Path,
        default=None,
        help="Write a Qucs .sch schematic to this path (best-effort)",
    )
    ana.add_argument(
        "--export-build-sheet",
        type=Path,
        default=None,
        help="Write a BOM/build sheet to this path (.csv, .md or .html)",
    )
    ana.add_argument(
        "--bom-series",
        choices=[s.value for s in ESeries],
        default=None,
        help="Snap L/C to this E-series in the build sheet",
    )
    ana.add_argument(
        "--bom-group",
        action="store_true",
        help="Group identical parts (combined refs + quantity) in the build sheet",
    )
    ana.add_argument(
        "--bom-columns",
        default=None,
        help="Comma-separated BOM columns for .csv (default: full set)",
    )
    ana.add_argument(
        "--power",
        type=float,
        default=0.0,
        help="Source available power (W) for the per-element nodal stress analysis",
    )
    ana.add_argument(
        "--harmonics",
        action="store_true",
        help="Print |S21| and suppression at harmonics of the band landmark",
    )
    ana.add_argument(
        "--harmonics-f0",
        default=None,
        help="Fundamental frequency (Hz) for the harmonic readout, e.g. 7.1M",
    )
    ana.add_argument(
        "--check",
        action="store_true",
        help="Check the analyzed response against the requested specification",
    )
    ana.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON summary (checkpoints + arrays truncated)",
    )

    sub.add_parser(
        "gui",
        help="Launch the FilterDesk desktop GUI",
    )

    sub.add_parser(
        "bands",
        help="List amateur band presets (160 m–6 m)",
    )

    atten = sub.add_parser(
        "attenuator",
        help="Design a symmetric T or Pi resistive attenuator",
    )
    atten.add_argument("--db", required=True, type=float, help="Attenuation (dB)")
    atten.add_argument("--z0", default="50", help="System impedance (ohm)")
    atten.add_argument(
        "--kind",
        choices=[k.value for k in AttenuatorKind],
        default=AttenuatorKind.TEE.value,
        help="Pad topology",
    )
    atten.add_argument("--json", action="store_true", help="Emit JSON")

    match = sub.add_parser(
        "match",
        help="Design an L/Pi/T matching network to a complex load",
    )
    match.add_argument("--z0", default="50", help="Source impedance (ohm)")
    match.add_argument("--rl", required=True, help="Load resistance (ohm)")
    match.add_argument("--xl", default="0", help="Load reactance (ohm, +ind/-cap)")
    match.add_argument("--f", required=True, help="Design frequency, e.g. 7.1M")
    match.add_argument(
        "--topology",
        choices=[t.value for t in MatchingTopology],
        default=MatchingTopology.L.value,
        help="Network topology",
    )
    match.add_argument(
        "--q",
        type=float,
        default=None,
        help="Loaded Q (Pi/T only; defaults above the minimum)",
    )
    match.add_argument("--json", action="store_true", help="Emit JSON")

    tor = sub.add_parser(
        "toroid",
        help="Toroid turns / wire / saturation calculator",
    )
    tor.add_argument(
        "--core",
        default=None,
        help="Built-in core name (e.g. T50-2); use --list to see the table",
    )
    tor.add_argument("--al", default=None, help="Custom core AL in nH/N^2")
    tor.add_argument("--od", default=None, help="Custom core outer diameter (mm)")
    tor.add_argument("--id", default=None, help="Custom core inner diameter (mm)")
    tor.add_argument("--height", default=None, help="Custom core height (mm)")
    tor.add_argument("--bsat", type=float, default=None, help="Custom core Bsat (T)")
    tor.add_argument("--inductance", default=None, help="Target inductance, e.g. 1u")
    tor.add_argument(
        "--turns", type=int, default=None, help="Turn count (instead of a target L)"
    )
    tor.add_argument(
        "--current",
        type=float,
        default=0.0,
        help="Peak current (A) for the flux-density estimate",
    )
    tor.add_argument("--list", action="store_true", help="List built-in cores")
    tor.add_argument("--json", action="store_true", help="Emit JSON")

    air = sub.add_parser(
        "air-coil",
        help="Single-layer air-core solenoid calculator",
    )
    air.add_argument("--inductance", default=None, help="Target inductance, e.g. 1u")
    air.add_argument(
        "--turns", type=int, default=None, help="Turn count (instead of a target L)"
    )
    air.add_argument("--diameter", required=True, help="Coil diameter (mm)")
    wire = air.add_mutually_exclusive_group()
    wire.add_argument("--awg", type=int, default=None, help="Wire gauge (AWG 8-40)")
    wire.add_argument(
        "--wire-mm", type=float, default=None, help="Bare wire diameter (mm)"
    )
    enamel = air.add_mutually_exclusive_group()
    enamel.add_argument(
        "--bare-wire", action="store_true", help="Assume bare copper (no enamel)"
    )
    enamel.add_argument(
        "--enamel-mm",
        type=float,
        default=None,
        help="Enamel build (mm); default: typical grade-1 enamelled wire",
    )
    air.add_argument("--json", action="store_true", help="Emit JSON")

    tr = sub.add_parser(
        "transformer",
        help="Design a transformer, unun or balun (model + BOM)",
    )
    tr.add_argument(
        "--kind",
        choices=[k.value for k in BalunKind],
        default=BalunKind.UNUN.value,
        help="Device kind",
    )
    tr.add_argument(
        "--topology",
        choices=[t.value for t in TransformerTopology],
        default=TransformerTopology.AUTOTRANSFORMER.value,
        help="Autotransformer (tapped) or isolated two-winding",
    )
    tr.add_argument(
        "--z-low",
        "--z-unbalanced",
        dest="z_low",
        required=True,
        help="Low-side / unbalanced impedance (ohm)",
    )
    tr.add_argument(
        "--z-high",
        "--z-balanced",
        dest="z_high",
        required=True,
        help="High-side / balanced impedance (ohm)",
    )
    tr.add_argument("--core", required=True, help="Built-in core name, e.g. FT50-43")
    tr.add_argument(
        "--frequency",
        "--f-min",
        dest="frequency",
        default="1M",
        help="Lowest frequency, e.g. 1M",
    )
    tr.add_argument(
        "--f-max",
        default=None,
        help="Highest frequency; default: 10 x f_min",
    )
    tr.add_argument("--power", type=float, default=10.0, help="Power (W)")
    tr.add_argument("--coupling", type=float, default=0.98, help="Winding coupling k")
    tr.add_argument("--tan-delta", type=float, default=0.02, help="Core loss tangent")
    tr.add_argument(
        "--winding-c", type=float, default=0.0, help="Winding capacitance (F)"
    )
    tr.add_argument("--line-z0", type=float, default=None, help="TLT line Z0 (ohm)")
    tr.add_argument("--line-length", type=float, default=None, help="TLT length (m)")
    tr.add_argument("--vf", type=float, default=0.7, help="TLT velocity factor")
    tr.add_argument("--line-loss", type=float, default=0.0, help="TLT loss (dB/m)")
    tr.add_argument(
        "--reactance-factor",
        type=float,
        default=4.0,
        help="Minimum magnetizing reactance / Z_low (default 4)",
    )
    tr.add_argument(
        "--current-density",
        type=float,
        default=4.0,
        help="Wire current density (A/mm^2, default 4)",
    )
    tr.add_argument(
        "--show-options",
        action="store_true",
        help="Include compact/recommended/robust turns options",
    )
    tr.add_argument("--json", action="store_true", help="Emit JSON")

    ms = sub.add_parser("microstrip", help="Microstrip line calculator")
    ms.add_argument("--z0", required=True, help="Target characteristic impedance")
    ms.add_argument("--frequency", default="1G", help="Design frequency")
    ms.add_argument("--length", default="0", help="Physical line length (m)")
    _add_microstrip_substrate(ms)
    ms.add_argument("--json", action="store_true", help="Emit JSON")

    qwt = sub.add_parser("qwt", help="Microstrip quarter-wave transformer calculator")
    qwt.add_argument("--z-low", required=True, help="Low impedance")
    qwt.add_argument("--z-high", required=True, help="High impedance")
    qwt.add_argument("--frequency", default="1G", help="Center frequency")
    _add_microstrip_substrate(qwt)
    qwt.add_argument("--json", action="store_true", help="Emit JSON")

    stub = sub.add_parser("stub", help="Microstrip open/short stub calculator")
    stub.add_argument("--z0", required=True, help="Stub characteristic impedance")
    stub.add_argument(
        "--angle", type=float, default=90.0, help="Electrical angle (deg)"
    )
    stub.add_argument("--kind", choices=["open", "short"], default="open")
    stub.add_argument("--frequency", default="1G", help="Design frequency")
    _add_microstrip_substrate(stub)
    stub.add_argument("--json", action="store_true", help="Emit JSON")

    dist = sub.add_parser(
        "distributed",
        help="Microstrip stepped-impedance low-pass realization (experimental)",
    )
    _add_spec_args(dist)
    _add_microstrip_substrate(dist)
    dist.add_argument(
        "--angle",
        type=float,
        default=30.0,
        help="Electrical length at cutoff (degrees; auto-adjusted to fit Z0)",
    )
    dist.add_argument("--z0-min", type=float, default=10.0, help="Minimum line Z0")
    dist.add_argument("--z0-max", type=float, default=120.0, help="Maximum line Z0")
    dist.add_argument(
        "--export-s2p",
        type=Path,
        default=None,
        help="Write the distributed response as Touchstone .s2p",
    )
    dist.add_argument(
        "--export-build-sheet",
        type=Path,
        default=None,
        help="Write a distributed BOM/build sheet (.csv/.md/.html)",
    )
    dist.add_argument("--json", action="store_true", help="Emit JSON")

    snap = sub.add_parser(
        "snap",
        help="Synthesize a filter and snap component values to an E-series",
    )
    _add_spec_args(snap)
    snap.add_argument(
        "--series",
        choices=[s.value for s in ESeries],
        default=ESeries.E24.value,
        help="Preferred number series (IEC 60063)",
    )
    snap.add_argument(
        "--strategy",
        choices=[s.value for s in SnapStrategy],
        default=SnapStrategy.INDEPENDENT.value,
        help="Snap strategy for L/C (and resonators)",
    )
    snap.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (snap report + snapped components)",
    )

    mc = sub.add_parser(
        "montecarlo",
        help="Tolerance Monte-Carlo sweep over a synthesized filter",
    )
    _add_spec_args(mc)
    mc.add_argument("--f-start", default=None, help="Sweep start (Hz), e.g. 10M")
    mc.add_argument("--f-stop", default=None, help="Sweep stop (Hz), e.g. 1G")
    mc.add_argument("--points", type=int, default=512, help="Number of points")
    mc.add_argument(
        "--spacing",
        choices=[s.value for s in SweepSpacing],
        default=SweepSpacing.LOGARITHMIC.value,
        help="Frequency spacing",
    )
    mc.add_argument(
        "--trials", type=int, default=1000, help="Number of Monte-Carlo trials"
    )
    mc.add_argument(
        "--tol", type=float, default=1.0, help="Relative tolerance in percent"
    )
    mc.add_argument(
        "--distribution",
        choices=[d.value for d in ToleranceDistribution],
        default=ToleranceDistribution.UNIFORM.value,
        help="Tolerance distribution",
    )
    mc.add_argument("--seed", type=int, default=None, help="RNG seed")
    mc.add_argument(
        "--element-tol",
        action="append",
        default=[],
        metavar="REF=PCT",
        help="Per-component tolerance override (repeatable), e.g. L1=2 C2=5",
    )
    mc.add_argument(
        "--limits",
        type=Path,
        default=None,
        help="JSON file with a list of limit regions (for yield)",
    )
    mc.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (envelope summary + yield)",
    )

    opt = sub.add_parser(
        "optimize",
        help="Tune component values to satisfy limit regions (FR-P4)",
    )
    _add_spec_args(opt)
    opt.add_argument("--f-start", default=None, help="Sweep start (Hz), e.g. 10M")
    opt.add_argument("--f-stop", default=None, help="Sweep stop (Hz), e.g. 1G")
    opt.add_argument("--points", type=int, default=512, help="Number of points")
    opt.add_argument(
        "--spacing",
        choices=[s.value for s in SweepSpacing],
        default=SweepSpacing.LOGARITHMIC.value,
        help="Frequency spacing",
    )
    opt.add_argument(
        "--limits",
        type=Path,
        default=None,
        help="JSON file with a list of limit regions",
    )
    opt.add_argument(
        "--objective",
        action="append",
        default=[],
        metavar="TYPE:LO:HI[:TARGET]",
        help=(
            "Composable objective (repeatable): "
            "passband:LO:HI, stopband:LO:HI:ATT, returnloss:LO:HI:RL"
        ),
    )
    opt.add_argument(
        "--method",
        choices=[m.value for m in OptimizeMethod],
        default=OptimizeMethod.LEAST_SQUARES.value,
        help="Optimization method",
    )
    opt.add_argument(
        "--bound",
        type=float,
        default=0.2,
        help="Per-component relative bound (fraction, e.g. 0.2 = ±20%%)",
    )
    opt.add_argument(
        "--max-iter", type=int, default=200, help="Maximum solver iterations"
    )
    opt.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for the global methods (DE / dual annealing)",
    )
    opt.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (costs + tuned values)",
    )

    sens = sub.add_parser(
        "sensitivity",
        help="Rank component values by their effect on |S21| / limit margins",
    )
    _add_spec_args(sens)
    sens.add_argument("--f-start", default=None, help="Sweep start (Hz), e.g. 10M")
    sens.add_argument("--f-stop", default=None, help="Sweep stop (Hz), e.g. 1G")
    sens.add_argument("--points", type=int, default=512, help="Number of points")
    sens.add_argument(
        "--spacing",
        choices=[s.value for s in SweepSpacing],
        default=SweepSpacing.LOGARITHMIC.value,
        help="Frequency spacing",
    )
    sens.add_argument(
        "--backend",
        choices=["abcd", "skrf"],
        default="abcd",
        help="Analysis backend",
    )
    sens.add_argument(
        "--limits",
        type=Path,
        default=None,
        help="JSON file with a list of limit regions (enables tuning guidance)",
    )
    sens.add_argument(
        "--objective",
        action="append",
        default=[],
        metavar="TYPE:LO:HI[:TARGET]",
        help=(
            "Composable objective (repeatable): "
            "passband:LO:HI, stopband:LO:HI:ATT, returnloss:LO:HI:RL"
        ),
    )
    sens.add_argument(
        "--relative-step",
        type=float,
        default=1.0,
        help="Finite-difference step in percent (default 1)",
    )
    sens.add_argument(
        "--band-range",
        nargs=2,
        metavar=("LOW", "HIGH"),
        default=None,
        help="Restrict statistics to a frequency interval, e.g. --band-range 130M 150M",
    )
    sens.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    sweep = sub.add_parser(
        "sweep",
        help="Sweep a design parameter into a comparison table",
    )
    _add_spec_args(sweep)
    sweep.add_argument(
        "--axis",
        required=True,
        choices=[axis.value for axis in SweepAxis],
        help="Parameter to sweep",
    )
    sweep.add_argument(
        "--values",
        required=True,
        help="Comma-separated values, e.g. 3,5,7,9 or butterworth,chebyshev_type_i",
    )
    sweep.add_argument("--points", type=int, default=512, help="Sweep points")
    sweep.add_argument(
        "--pass-band",
        nargs=2,
        metavar=("LOW", "HIGH"),
        default=None,
        help="Passband for the metrics (default: derived from the spec)",
    )
    sweep.add_argument(
        "--stop-band",
        nargs=2,
        metavar=("LOW", "HIGH"),
        default=None,
        help="Stopband for the metrics (default: derived from the spec)",
    )
    sweep.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Write the comparison table to this CSV path",
    )
    sweep.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    tocsv = sub.add_parser(
        "to-csv",
        help="Convert a Touchstone file (.s2p) to trace CSV",
    )
    tocsv.add_argument("input", type=Path, help="Input Touchstone file")
    tocsv.add_argument("output", type=Path, help="Output CSV path")
    tocsv.add_argument(
        "--columns",
        default=",".join(COLUMNS),
        help="Comma-separated column names (default: standard set)",
    )

    est = sub.add_parser(
        "estimate-order",
        help="Estimate minimum order from Ap/As and pass/stop frequencies",
    )
    est.add_argument(
        "--family",
        required=True,
        choices=[
            ApproximationFamily.BUTTERWORTH.value,
            ApproximationFamily.CHEBYSHEV_TYPE_I.value,
            ApproximationFamily.CHEBYSHEV_TYPE_II.value,
            ApproximationFamily.ELLIPTIC.value,
            ApproximationFamily.BESSEL.value,
            ApproximationFamily.GAUSSIAN.value,
            ApproximationFamily.LEGENDRE.value,
        ],
        help="Approximation family",
    )
    est.add_argument(
        "--response",
        required=True,
        choices=[r.value for r in FilterResponse],
        help="LP, HP, BP, or BS",
    )
    est.add_argument(
        "--f-pass",
        default=None,
        help="Passband edge (Hz, LP/HP), e.g. 1M",
    )
    est.add_argument(
        "--f-stop",
        default=None,
        help="Stopband edge (Hz, LP/HP), e.g. 2M",
    )
    est.add_argument(
        "--pass-band",
        nargs=2,
        metavar=("LOW", "HIGH"),
        default=None,
        help="Passband edges (Hz, BP/BS), e.g. --pass-band 0.9M 1.1M",
    )
    est.add_argument(
        "--stop-band",
        nargs=2,
        metavar=("LOW", "HIGH"),
        default=None,
        help="Stopband edges (Hz, BP/BS), e.g. --stop-band 0.7M 1.4M",
    )
    est.add_argument(
        "--ap",
        type=float,
        required=True,
        help="Passband attenuation / ripple Ap (dB)",
    )
    est.add_argument(
        "--as",
        dest="as_db",
        type=float,
        required=True,
        help="Stopband attenuation As (dB)",
    )
    est.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    tsinfo = sub.add_parser(
        "touchstone-info",
        help="Inspect a Touchstone file (.s1p / .s2p)",
    )
    tsinfo.add_argument("path", type=Path, help="Touchstone file path")
    tsinfo.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    cmpp = sub.add_parser(
        "compare",
        help="Compare two Touchstone results (simulated vs measured)",
    )
    cmpp.add_argument("simulated", type=Path, help="Simulated .s2p")
    cmpp.add_argument("measured", type=Path, help="Measured .s2p")
    cmpp.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    tune = sub.add_parser(
        "tune-vna",
        help="Synthesize a design and trim L/C values to a measured .s2p",
    )
    tune.add_argument("measured", type=Path, help="Measured Touchstone .s2p")
    tune.add_argument(
        "--holdout",
        type=Path,
        default=None,
        help="Optional second capture evaluated only after fitting",
    )
    tune.add_argument(
        "--metadata",
        type=Path,
        default=None,
        help="VNA metadata JSON (default: <measured>.vna.json if present)",
    )
    _add_spec_args(tune)
    tune.add_argument(
        "--bound", type=float, default=0.2, help="Local trim bound (default 0.2)"
    )
    tune.add_argument(
        "--bound-mode",
        choices=[m.value for m in VnaBoundMode],
        default=VnaBoundMode.LOCAL.value,
        help="Component search box: local, wide or multi-start global",
    )
    tune.add_argument(
        "--global-starts",
        type=int,
        default=6,
        help="Multi-start count for --bound-mode global",
    )
    tune.add_argument(
        "--max-points", type=int, default=401, help="Measured points used in fit"
    )
    tune.add_argument(
        "--max-nfev", type=int, default=200, help="Maximum function evaluations"
    )
    tune.add_argument(
        "--f-min", default=None, help="Fit band start (default: measured start)"
    )
    tune.add_argument(
        "--f-max", default=None, help="Fit band stop (default: measured stop)"
    )
    tune.add_argument("--no-s11", action="store_true", help="Do not fit S11")
    tune.add_argument("--no-s21", action="store_true", help="Do not fit S21")
    tune.add_argument(
        "--fit-phase",
        action="store_true",
        help="Fit phase too (adds delay and phase offsets)",
    )
    tune.add_argument(
        "--phase-weight", type=float, default=1.0, help="Phase residual weight"
    )
    tune.add_argument(
        "--phase-min-db",
        type=float,
        default=-40.0,
        help="Only fit phase where measured magnitude is above this",
    )
    tune.add_argument(
        "--max-delay-ns",
        type=float,
        default=1000.0,
        help="Maximum absolute reference-plane delay for phase fitting (ns)",
    )
    tune.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def _add_spec_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--spec",
        type=Path,
        help="Path to specification JSON (golden format)",
    )
    p.add_argument(
        "--band",
        help="Amateur band preset, e.g. 40m (overrides family/response/order)",
    )
    p.add_argument(
        "--band-kind",
        choices=[k.value for k in BandKind],
        default=BandKind.LPF.value,
        help="Band preset filter kind (with --band)",
    )
    p.add_argument(
        "--family",
        choices=[f.value for f in ApproximationFamily],
        help="Approximation family",
    )
    p.add_argument(
        "--response",
        choices=[r.value for r in FilterResponse],
        help="Filter response type",
    )
    p.add_argument("--order", type=int, help="Filter order")
    p.add_argument(
        "--cutoff",
        help="Cutoff frequency (Hz) for LP/HP, e.g. 140M",
    )
    p.add_argument(
        "--f-center",
        help="Center frequency (Hz) for BP/BS, e.g. 100M",
    )
    p.add_argument(
        "--bandwidth",
        help="Bandwidth (Hz) for BP/BS, e.g. 20M",
    )
    p.add_argument(
        "--ripple",
        type=float,
        help="Passband ripple Ap dB (Cheby I / elliptic)",
    )
    p.add_argument(
        "--stopband-att",
        type=float,
        help="Stopband attenuation As dB (Cheby II / elliptic)",
    )
    p.add_argument(
        "--m",
        type=float,
        help="M-derived parameter m in (0,1)",
    )
    p.add_argument("--zs", default="50", help="Source impedance (ohm)")
    p.add_argument("--zl", default="50", help="Load impedance (ohm)")
    p.add_argument(
        "--topology",
        choices=[t.value for t in TopologyId],
        help="Ladder topology id",
    )


def _spec_from_cli(args: argparse.Namespace) -> FilterSpec:
    if args.spec is not None:
        data = json.loads(args.spec.read_text(encoding="utf-8"))
        return filter_spec_from_mapping(data)

    band = getattr(args, "band", None)
    if band:
        try:
            return band_preset_spec(
                find_band(band), BandKind(getattr(args, "band_kind", "lpf"))
            )
        except KeyError as exc:
            raise SpecValidationError(str(exc)) from exc

    missing = [
        name
        for name, val in (
            ("--family", args.family),
            ("--response", args.response),
            ("--order", args.order),
        )
        if val is None
    ]
    if missing:
        raise SpecValidationError("provide --spec or all of: " + ", ".join(missing))

    family = ApproximationFamily(args.family)
    response = FilterResponse(args.response)
    topology = (
        TopologyId(args.topology) if args.topology else default_topology(response)
    )
    mapping: dict[str, object] = {
        "family": family.value,
        "response": response.value,
        "order": int(args.order),
        "z_source_ohm": parse_si(str(args.zs)),
        "z_load_ohm": parse_si(str(args.zl)),
        "topology_id": topology.value,
        "cutoff_definition": default_cutoff_definition(family).value,
    }
    if response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        if args.f_center is None or args.bandwidth is None:
            raise SpecValidationError(
                "BP/BS requires --f-center and --bandwidth (or --spec)"
            )
        mapping["f_center_hz"] = parse_si(str(args.f_center))
        mapping["bandwidth_hz"] = parse_si(str(args.bandwidth))
    else:
        if args.cutoff is None:
            raise SpecValidationError("LP/HP requires --cutoff (or --spec)")
        mapping["cutoff_hz"] = parse_si(str(args.cutoff))
    if args.ripple is not None:
        mapping["passband_ripple_db"] = float(args.ripple)
    if getattr(args, "stopband_att", None) is not None:
        mapping["stopband_attenuation_db"] = float(args.stopband_att)
    if getattr(args, "m", None) is not None:
        mapping["m_parameter"] = float(args.m)
    return filter_spec_from_mapping(mapping)


def _emit_synthesis_note(spec: FilterSpec) -> None:
    note = synthesis_note(spec)
    if note:
        print(f"Note: {note}", file=sys.stderr)


def _print_synth_human(result: SynthesisResult) -> None:
    print("Specification:")
    for key, value in filter_spec_to_mapping(result.spec).items():
        print(f"  {key}: {value}")
    proto = result.prototype
    if proto.arms is not None:
        print("Prototype arms (normalized):")
        for i, arm in enumerate(proto.arms, start=1):
            if arm.value is not None:
                print(f"  [{i}] {arm.kind} = {arm.value:.12g}")
            else:
                print(f"  [{i}] {arm.kind} L={arm.L:.12g} C={arm.C:.12g}")
    else:
        print("Prototype g-values:")
        print("  " + ", ".join(f"{g:.12g}" for g in proto.g_values))
    print("Components:")
    for el in result.circuit.elements:
        g_txt = f"{el.g:.12g}" if el.g is not None else "—"
        if isinstance(el, IdealCapacitor):
            eng = format_engineering(el.value_f, "F")
            print(f"  {el.id:4s}  {el.role.value:6s}  {eng}  (g={g_txt})")
        elif isinstance(el, IdealInductor):
            eng = format_engineering(el.value_h, "H")
            print(f"  {el.id:4s}  {el.role.value:6s}  {eng}  (g={g_txt})")
        elif isinstance(el, NonIdealInductor):
            print(
                f"  {el.id:4s}  {el.role.value:6s}  "
                f"L={format_engineering(el.value_h, 'H')} "
                f"R={format_engineering(el.series_resistance_ohm, 'Ohm')} "
                f"Cp={format_engineering(el.parallel_capacitance_f, 'F')}  (g={g_txt})"
            )
        elif isinstance(el, NonIdealCapacitor):
            print(
                f"  {el.id:4s}  {el.role.value:6s}  "
                f"C={format_engineering(el.value_f, 'F')} "
                f"ESR={format_engineering(el.esr_ohm, 'Ohm')} "
                f"ESL={format_engineering(el.esl_h, 'H')}  (g={g_txt})"
            )
        elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            join = "+" if isinstance(el, IdealSeriesLC) else "||"
            print(
                f"  {el.id:4s}  {el.role.value:6s}  "
                f"{format_engineering(el.value_h, 'H')} {join} "
                f"{format_engineering(el.value_f, 'F')}  (g={g_txt})"
            )
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            kind = "Brune+" if isinstance(el, IdealBruneLC) else "Brune||"
            print(
                f"  {el.id:4s}  {el.role.value:6s}  {kind}  "
                f"Ls={format_engineering(el.series_l_h, 'H')} "
                f"Cs={format_engineering(el.series_c_f, 'F')} "
                f"Lp={format_engineering(el.parallel_l_h, 'H')} "
                f"Cp={format_engineering(el.parallel_c_f, 'F')}"
            )


def _print_compliance(report: ComplianceResult) -> None:
    print(f"Spec compliance: {'PASS' if report.ok else 'FAIL'}")
    if report.passband_ripple_db is not None:
        print(f"  passband ripple: {report.passband_ripple_db:.3f} dB")
    if report.stopband_attenuation_db is not None:
        print(f"  stopband attenuation: {report.stopband_attenuation_db:.2f} dB")
    if report.edge_loss_db:
        print(
            "  edge loss: "
            + ", ".join(f"{value:.2f} dB" for value in report.edge_loss_db)
        )
    for issue in report.issues:
        print(f"  issue: {issue}")
    for note in report.notes:
        print(f"  note: {note}")


def _synth_to_json(result: SynthesisResult) -> dict[str, object]:
    components: list[dict[str, object]] = []
    for el in result.circuit.elements:
        row: dict[str, object] = {
            "ref": el.id,
            "role": el.role.value,
            "type": el.element_type.value,
            "g": el.g,
            "node_a": el.node_a,
            "node_b": el.node_b,
        }
        if isinstance(el, IdealCapacitor):
            row["value_F"] = el.value_f
        elif isinstance(el, IdealInductor):
            row["value_H"] = el.value_h
        elif isinstance(el, NonIdealInductor):
            row["value_H"] = el.value_h
            row["series_R_Ohm"] = el.series_resistance_ohm
            row["parallel_C_F"] = el.parallel_capacitance_f
        elif isinstance(el, NonIdealCapacitor):
            row["value_F"] = el.value_f
            row["esr_Ohm"] = el.esr_ohm
            row["esl_H"] = el.esl_h
        elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            row["value_H"] = el.value_h
            row["value_F"] = el.value_f
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            row["series_L_H"] = el.series_l_h
            row["series_C_F"] = el.series_c_f
            row["parallel_L_H"] = el.parallel_l_h
            row["parallel_C_F"] = el.parallel_c_f
        components.append(row)
    proto_obj: dict[str, object] = {
        "family": result.prototype.family.value,
        "epsilon": result.prototype.epsilon,
        "passband_ripple_db": result.prototype.passband_ripple_db,
        "stopband_attenuation_db": result.prototype.stopband_attenuation_db,
        "m_parameter": result.prototype.m_parameter,
    }
    if result.prototype.arms is not None:
        proto_obj["arms"] = [
            {
                "kind": a.kind,
                **({"value": a.value} if a.value is not None else {"L": a.L, "C": a.C}),
            }
            for a in result.prototype.arms
        ]
    else:
        proto_obj["g_values"] = list(result.prototype.g_values)
    note = synthesis_note(result.spec)
    payload: dict[str, object] = {
        "spec": filter_spec_to_mapping(result.spec),
        "prototype": proto_obj,
        "components": components,
    }
    if note is not None:
        payload["note"] = note
    return payload


def _print_snap_report(report: SnapReport) -> None:
    print(
        f"Snap to {report.series.value} ({report.strategy.value}); "
        f"max change {report.max_delta_pct:.2f}%"
    )
    for entry in report.entries:
        print(
            f"  {entry.element_id:6s} {entry.part:2s}  "
            f"{entry.original:.6g} -> {entry.snapped:.6g}  "
            f"({entry.delta_pct:+.2f}%)"
        )


def _snap_to_json(result: SynthesisResult, report: SnapReport) -> dict[str, object]:
    payload = _synth_to_json(result)
    payload["snap"] = {
        "series": report.series.value,
        "strategy": report.strategy.value,
        "max_delta_pct": report.max_delta_pct,
        "entries": [
            {
                "ref": e.element_id,
                "part": e.part,
                "original": e.original,
                "snapped": e.snapped,
                "delta_pct": e.delta_pct,
            }
            for e in report.entries
        ],
    }
    return payload


def _default_sweep(spec: FilterSpec, args: argparse.Namespace) -> SweepConfig:
    base = default_sweep_for_spec(spec, n_points=int(args.points))
    f_start = parse_si(args.f_start) if args.f_start else base.f_start_hz
    f_stop = parse_si(args.f_stop) if args.f_stop else base.f_stop_hz
    return SweepConfig(
        f_start_hz=f_start,
        f_stop_hz=f_stop,
        n_points=int(args.points),
        spacing=SweepSpacing(args.spacing),
    )


def _print_analysis_human(
    synth: SynthesisResult,
    backend: str,
    result_freq_count: int,
    s21_db: list[float],
    s11_db: list[float],
    freqs: list[float],
    gd_ns: list[float],
    vswr_in: list[float],
) -> None:
    _print_synth_human(synth)
    print(f"Analysis backend: {backend}  points: {result_freq_count}")
    print("Sample points (first / mid / last):")
    idxs = [0, result_freq_count // 2, result_freq_count - 1]
    for i in idxs:
        print(
            f"  f={format_engineering(freqs[i], 'Hz')}  "
            f"S21={s21_db[i]:.3f} dB  S11={s11_db[i]:.3f} dB  "
            f"VSWR={vswr_in[i]:.3f}  GD={gd_ns[i]:.3f} ns"
        )
    print(
        f"|S21| range: {min(s21_db):.3f} … {max(s21_db):.3f} dB  "
        f"|S11| range: {min(s11_db):.3f} … {max(s11_db):.3f} dB"
    )


def _stress_frequency(spec: FilterSpec) -> float | None:
    if spec.response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        return spec.f_center_hz
    return spec.cutoff_hz if spec.cutoff_hz > 0.0 else None


def _print_stress(report: StressReport) -> None:
    print(
        f"Power stress @ {format_engineering(report.frequency_hz, 'Hz', digits=6)} "
        f"(P={report.power_w:g} W, Z0={report.z0_ohm:g} Ohm):"
    )
    for entry in report.entries:
        print(
            f"  {entry.ref:6s} {entry.role.value:6s} "
            f"Z={abs(entry.impedance_ohm):.4g} Ohm  "
            f"Vpk={entry.v_peak_v:.4g} V  Ipk={entry.i_peak_a:.4g} A"
        )
    print(
        f"  worst: V={report.worst_voltage_ref} ({report.max_v_peak_v:.4g} V), "
        f"I={report.worst_current_ref} ({report.max_i_peak_a:.4g} A)"
    )


def _stress_to_json(report: StressReport) -> dict[str, object]:
    return {
        "power_w": report.power_w,
        "z0_ohm": report.z0_ohm,
        "frequency_hz": report.frequency_hz,
        "max_v_peak_v": report.max_v_peak_v,
        "max_i_peak_a": report.max_i_peak_a,
        "elements": [
            {
                "ref": e.ref,
                "role": e.role.value,
                "impedance_ohm": abs(e.impedance_ohm),
                "v_peak_v": e.v_peak_v,
                "i_peak_a": e.i_peak_a,
            }
            for e in report.entries
        ],
    }


def _print_harmonics(report: HarmonicReport) -> None:
    print(
        f"Harmonics (f0 = "
        f"{format_engineering(report.fundamental_hz, 'Hz', digits=6)}, "
        f"|S21|(f0)={report.fundamental_s21_db:.3f} dB):"
    )
    for h in report.harmonics:
        print(
            f"  {h.order}f = {format_engineering(h.frequency_hz, 'Hz', digits=6)}  "
            f"|S21|={h.s21_db:.2f} dB  suppression={h.suppression_db:.2f} dB"
        )


def _harmonics_to_json(report: HarmonicReport) -> dict[str, object]:
    return {
        "fundamental_hz": report.fundamental_hz,
        "fundamental_s21_db": report.fundamental_s21_db,
        "min_suppression_db": report.min_suppression_db,
        "harmonics": [
            {
                "order": h.order,
                "frequency_hz": h.frequency_hz,
                "s21_db": h.s21_db,
                "suppression_db": h.suppression_db,
            }
            for h in report.harmonics
        ],
    }


def _print_mc_human(spec: FilterSpec, result: MonteCarloResult) -> None:
    cfg = result.config
    print(
        f"Monte-Carlo: {result.n_trials} trials  tol=±{cfg.tolerance_pct:g}%  "
        f"({cfg.distribution.value})  seed={cfg.seed}"
    )
    f = result.frequency_hz
    idxs = [0, f.shape[0] // 2, f.shape[0] - 1]
    print("S21 envelope (min … max dB) at sample points:")
    for i in idxs:
        print(
            f"  f={format_engineering(float(f[i]), 'Hz')}  "
            f"{result.s21_db_min[i]:.3f} … {result.s21_db_max[i]:.3f} dB  "
            f"(p05..p95 {result.s21_db_p05[i]:.3f} … "
            f"{result.s21_db_p95[i]:.3f})"
        )
    print(f"Worst-case spread: {result.max_spread_db:.3f} dB")
    if result.yield_fraction is not None:
        lo, hi = wilson_interval(result.passes, result.n_trials)
        print(
            f"Yield: {100.0 * result.yield_fraction:.2f}% "
            f"({result.passes}/{result.n_trials}; 95% CI "
            f"{100.0 * lo:.1f}–{100.0 * hi:.1f}%)"
        )


def _mc_to_json(spec: FilterSpec, result: MonteCarloResult) -> dict[str, object]:
    cfg = result.config
    payload: dict[str, object] = {
        "spec": filter_spec_to_mapping(spec),
        "trials": result.n_trials,
        "tolerance_pct": cfg.tolerance_pct,
        "distribution": cfg.distribution.value,
        "seed": cfg.seed,
        "max_spread_db": result.max_spread_db,
    }
    if cfg.overrides:
        payload["element_tolerances"] = {
            ref: tol.tolerance_pct for ref, tol in cfg.overrides.items()
        }
    if result.yield_fraction is not None:
        lo, hi = wilson_interval(result.passes, result.n_trials)
        payload["yield"] = {
            "fraction": result.yield_fraction,
            "passes": result.passes,
            "ci95": [lo, hi],
        }
    return payload


def _print_optimize_human(result: OptimizationResult) -> None:
    print(
        f"Optimize ({result.method.value}): cost {result.initial_cost:.5f} -> "
        f"{result.final_cost:.5f} (evals {result.n_evaluations})"
    )
    for ref, x0, x1 in zip(
        result.refs, result.initial_values, result.final_values, strict=True
    ):
        pct = 0.0 if x0 == 0 else 100.0 * (x1 - x0) / x0
        print(f"  {ref:6s} {x0:.6g} -> {x1:.6g} ({pct:+.2f}%)")


def _optimize_to_json(result: OptimizationResult) -> dict[str, object]:
    return {
        "method": result.method.value,
        "success": result.success,
        "message": result.message,
        "initial_cost": result.initial_cost,
        "final_cost": result.final_cost,
        "n_evaluations": result.n_evaluations,
        "components": [
            {"ref": ref, "initial": float(x0), "final": float(x1)}
            for ref, x0, x1 in zip(
                result.refs, result.initial_values, result.final_values, strict=True
            )
        ],
    }


def _print_sensitivity_human(report: SensitivityReport) -> None:
    print(f"Component sensitivity (+1% step, backend {report.backend}):")
    print(
        f"  {'Ref':8s} {'Value':>12s} {'d|S21|dB/%':>12s} {'RMS':>9s} "
        f"{'Worst f':>11s}  Dir"
    )
    for row in report.rows:
        value = (
            format_engineering(row.value, row.unit, digits=6)
            if row.unit
            else f"{row.value:.6g}"
        )
        worst = format_engineering(row.worst_frequency_hz, "Hz", digits=6)
        direction = "+" if row.direction > 0 else "-" if row.direction < 0 else "—"
        print(
            f"  {row.ref:8s} {value:>12s} {row.max_abs_db_per_pct:12.4f} "
            f"{row.rms_db_per_pct:9.4f} {worst:>11s}  {direction}"
        )
    if report.rows and report.rows[0].limit_margin_delta is None:
        print("  (no limits/objectives supplied: tuning direction not estimated)")


def _sensitivity_to_json(report: SensitivityReport) -> dict[str, object]:
    return {
        "backend": report.backend,
        "relative_step_pct": report.relative_step_pct,
        "band_hz": list(report.band) if report.band is not None else None,
        "components": [
            {
                "ref": row.ref,
                "element_id": row.element_id,
                "field": row.field,
                "value": row.value,
                "unit": row.unit,
                "max_abs_db_per_pct": row.max_abs_db_per_pct,
                "rms_db_per_pct": row.rms_db_per_pct,
                "worst_frequency_hz": row.worst_frequency_hz,
                "limit_margin_delta": row.limit_margin_delta,
                "direction": row.direction,
            }
            for row in report.rows
        ],
    }


def _fmt_metric(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


def _sweep_row_json(row: DesignSweepRow) -> dict[str, object]:
    metrics = row.metrics
    return {
        "value": row.value,
        "ok": row.ok,
        "error": row.error,
        "n_components": row.n_components,
        "passband_ripple_db": metrics.passband_ripple_db if metrics else None,
        "stopband_attenuation_db": (
            metrics.stopband_attenuation_db if metrics else None
        ),
        "min_return_loss_db": metrics.min_return_loss_db if metrics else None,
        "group_delay_ripple_s": (metrics.group_delay_ripple_s if metrics else None),
        "note": row.note,
    }


def _print_sweep_human(axis: SweepAxis, rows: list[DesignSweepRow]) -> None:
    print(f"Design sweep — {axis.value}")
    print(
        f"  {'Value':>12s}  {'OK':3s} {'N':>3s} {'Ripple dB':>10s} "
        f"{'Stop dB':>9s} {'RL dB':>7s} {'GD ps':>8s}  Note"
    )
    for row in rows:
        if not row.ok:
            print(f"  {str(row.value):>12s}  no   —  {row.error}")
            continue
        metrics = row.metrics
        ripple = (
            ""
            if metrics is None or metrics.passband_ripple_db is None
            else f"{metrics.passband_ripple_db:.3f}"
        )
        stop = (
            ""
            if metrics is None or metrics.stopband_attenuation_db is None
            else f"{metrics.stopband_attenuation_db:.1f}"
        )
        rl = (
            ""
            if metrics is None or metrics.min_return_loss_db is None
            else f"{metrics.min_return_loss_db:.1f}"
        )
        gd = (
            ""
            if metrics is None or metrics.group_delay_ripple_s is None
            else f"{metrics.group_delay_ripple_s * 1e12:.1f}"
        )
        print(
            f"  {str(row.value):>12s}  yes {row.n_components:3d} "
            f"{ripple:>10s} {stop:>9s} {rl:>7s} {gd:>8s}  {row.note or ''}"
        )


def _write_sweep_csv(rows: list[DesignSweepRow], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "value",
                "ok",
                "error",
                "n_components",
                "passband_ripple_db",
                "stopband_attenuation_db",
                "min_return_loss_db",
                "group_delay_ripple_s",
                "note",
            ]
        )
        for row in rows:
            metrics = row.metrics
            writer.writerow(
                [
                    row.value,
                    row.ok,
                    row.error or "",
                    row.n_components,
                    _fmt_metric(
                        None if metrics is None else metrics.passband_ripple_db
                    ),
                    _fmt_metric(
                        None if metrics is None else metrics.stopband_attenuation_db
                    ),
                    _fmt_metric(
                        None if metrics is None else metrics.min_return_loss_db
                    ),
                    _fmt_metric(
                        None if metrics is None else metrics.group_delay_ripple_s
                    ),
                    row.note or "",
                ]
            )


def _objectives_from_cli(entries: list[str]) -> list[Objective]:
    out: list[Objective] = []
    for entry in entries:
        parts = entry.split(":")
        kind = parts[0].strip().lower()
        try:
            if kind == "passband" and len(parts) == 3:
                out.append(PassbandRipple(parse_si(parts[1]), parse_si(parts[2])))
            elif kind == "stopband" and len(parts) == 4:
                out.append(
                    StopbandAttenuation(
                        parse_si(parts[1]), parse_si(parts[2]), float(parts[3])
                    )
                )
            elif kind == "returnloss" and len(parts) == 4:
                out.append(
                    ReturnLoss(parse_si(parts[1]), parse_si(parts[2]), float(parts[3]))
                )
            else:
                raise SpecValidationError(f"invalid --objective {entry!r}")
        except (ValueError, IndexError) as exc:
            raise SpecValidationError(f"invalid --objective {entry!r}: {exc}") from exc
    return out


def _element_tolerances_from_cli(entries: list[str]) -> dict[str, ElementTolerance]:
    out: dict[str, ElementTolerance] = {}
    for entry in entries:
        ref, sep, pct = entry.partition("=")
        if not sep or not ref.strip() or not pct.strip():
            raise SpecValidationError(f"invalid --element-tol {entry!r} (use REF=PCT)")
        out[ref.strip()] = ElementTolerance(float(pct))
    return out


def _nonideal_kwargs(args: argparse.Namespace) -> dict[str, float]:
    """Collect non-ideal analysis flags; returns {} when none are given."""
    kwargs: dict[str, float] = {}
    if getattr(args, "inductor_q", None) is not None:
        kwargs["inductor_q"] = float(args.inductor_q)
        if args.q_frequency is None:
            raise SpecValidationError("--inductor-q requires --q-frequency")
        kwargs["q_frequency_hz"] = parse_si(str(args.q_frequency))
    if getattr(args, "inductor_dcr", None) is not None:
        kwargs["inductor_dcr_ohm"] = parse_si(str(args.inductor_dcr))
    if getattr(args, "inductor_cpar", None) is not None:
        kwargs["inductor_parallel_capacitance_f"] = parse_si(str(args.inductor_cpar))
    if getattr(args, "capacitor_esr", None) is not None:
        kwargs["capacitor_esr_ohm"] = parse_si(str(args.capacitor_esr))
    if getattr(args, "capacitor_esl", None) is not None:
        kwargs["capacitor_esl_h"] = parse_si(str(args.capacitor_esl))
    if getattr(args, "inductor_srf", None) is not None:
        kwargs["inductor_srf_hz"] = parse_si(str(args.inductor_srf))
    if getattr(args, "inductor_dc_current", None) is not None:
        kwargs["inductor_dc_current_a"] = parse_si(str(args.inductor_dc_current))
    if getattr(args, "inductor_i_sat", None) is not None:
        kwargs["inductor_i_sat_a"] = parse_si(str(args.inductor_i_sat))
    return kwargs


def _add_microstrip_substrate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--substrate", default="FR4", help="Built-in substrate")
    parser.add_argument("--er", type=float, default=None, help="Override er")
    parser.add_argument("--h", type=float, default=None, help="Substrate height (mm)")
    parser.add_argument(
        "--tan-delta", type=float, default=None, help="Override loss tangent"
    )
    parser.add_argument("--t", type=float, default=None, help="Copper thickness (mm)")
    parser.add_argument(
        "--roughness", type=float, default=None, help="Copper roughness (um rms)"
    )


def _microstrip_substrate(args: argparse.Namespace) -> Substrate:
    base = find_substrate(str(args.substrate))
    if all(
        value is None
        for value in (args.er, args.h, args.tan_delta, args.t, args.roughness)
    ):
        return base
    return Substrate(
        name=base.name,
        er=base.er if args.er is None else float(args.er),
        h_mm=base.h_mm if args.h is None else float(args.h),
        tan_delta=base.tan_delta if args.tan_delta is None else float(args.tan_delta),
        t_mm=base.t_mm if args.t is None else float(args.t),
        roughness_um=base.roughness_um
        if args.roughness is None
        else float(args.roughness),
    )


def main(argv: list[str] | None = None) -> int:
    explicit = argv is not None
    arg_list = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(arg_list)

    if args.self_test:
        from filterdesk.package_self_test import run_package_self_test

        return run_package_self_test()

    if args.command == "synthesize":
        try:
            spec = _spec_from_cli(args)
            result = synthesize(spec)
            _emit_synthesis_note(spec)
        except (SpecValidationError, OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        compliance = check_spec_compliance(spec, result.circuit) if args.check else None
        if args.json:
            payload = _synth_to_json(result)
            if compliance is not None:
                payload["compliance"] = compliance.to_mapping()
            print(json.dumps(payload, indent=2))
        else:
            _print_synth_human(result)
            if compliance is not None:
                _print_compliance(compliance)
        return 0

    if args.command == "distributed":
        try:
            spec = _spec_from_cli(args)
            dist_substrate = _microstrip_substrate(args)
            dist_design = design_distributed_lowpass(
                spec,
                dist_substrate,
                electrical_length_deg=float(args.angle),
                z0_min_ohm=float(args.z0_min),
                z0_max_ohm=float(args.z0_max),
            )
            dist_sweep = default_sweep_for_spec(spec)
            dist_result = analyze_circuit(
                dist_design.circuit, dist_sweep, backend="abcd"
            )
            if args.export_s2p is not None:
                write_touchstone_s2p(
                    dist_result,
                    args.export_s2p,
                    comment="FilterDesk distributed microstrip realization",
                )
                print(f"Wrote {args.export_s2p}", file=sys.stderr)
            if args.export_build_sheet is not None:
                write_build_sheet(
                    dist_design.circuit,
                    args.export_build_sheet,
                    spec=spec,
                    title="Distributed microstrip realization",
                )
                print(f"Wrote {args.export_build_sheet}", file=sys.stderr)
        except (
            DistributedSynthesisError,
            SpecValidationError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        dist_line_rows = [
            {
                "ref": el.id,
                "z0_ohm": el.z0_ohm,
                "width_mm": el.width_mm,
                "length_mm": el.length_m * 1e3,
                "angle_deg": el.angle_deg,
                "substrate": el.substrate,
            }
            for el in dist_design.circuit.elements
            if isinstance(el, (MicrostripLineElement, MicrostripStubElement))
        ]
        if args.json:
            print(
                json.dumps(
                    {
                        "spec": filter_spec_to_mapping(spec),
                        "substrate": dist_design.substrate.name,
                        "electrical_length_deg": dist_design.electrical_length_deg,
                        "warnings": list(dist_design.warnings),
                        "lines": dist_line_rows,
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"Distributed LP: {spec.family.value}, order {spec.order}, "
                f"{dist_design.substrate.name}, "
                f"theta={dist_design.electrical_length_deg:g} deg"
            )
            for dist_line in dist_line_rows:
                print(
                    f"  {dist_line['ref']}: Z0={dist_line['z0_ohm']:.4g} ohm, "
                    f"W={dist_line['width_mm']:.3g} mm, "
                    f"L={dist_line['length_mm']:.4g} mm"
                )
            for dist_warning in dist_design.warnings:
                print(f"  warning: {dist_warning}", file=sys.stderr)
        return 0

    if args.command == "snap":
        try:
            spec = _spec_from_cli(args)
            result = synthesize(spec)
            _emit_synthesis_note(spec)
            snapped_circuit, report = snap_circuit(
                result.circuit, ESeries(args.series), SnapStrategy(args.strategy)
            )
            snapped_result = SynthesisResult(
                spec=result.spec,
                prototype=result.prototype,
                circuit=snapped_circuit,
            )
        except (SpecValidationError, OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(_snap_to_json(snapped_result, report), indent=2))
        else:
            _print_snap_report(report)
            _print_synth_human(snapped_result)
        return 0

    if args.command == "montecarlo":
        try:
            spec = _spec_from_cli(args)
            synth = synthesize(spec)
            _emit_synthesis_note(spec)
            sweep = _default_sweep(spec, args)
            limits = None
            if args.limits is not None:
                data = json.loads(args.limits.read_text(encoding="utf-8"))
                limits = limits_from_mapping(data)
            config = MonteCarloConfig(
                n_trials=int(args.trials),
                tolerance_pct=float(args.tol),
                distribution=ToleranceDistribution(args.distribution),
                seed=args.seed,
                overrides=_element_tolerances_from_cli(args.element_tol),
            )
            mc_result = run_monte_carlo(synth.circuit, sweep, config, limits=limits)
        except (
            SpecValidationError,
            AnalysisError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(_mc_to_json(spec, mc_result), indent=2))
        else:
            _print_mc_human(spec, mc_result)
        return 0

    if args.command == "optimize":
        try:
            spec = _spec_from_cli(args)
            synth = synthesize(spec)
            _emit_synthesis_note(spec)
            sweep = _default_sweep(spec, args)
            opt_limits: list[LimitRegion] = []
            if args.limits is not None:
                data = json.loads(args.limits.read_text(encoding="utf-8"))
                opt_limits = limits_from_mapping(data)
            objectives = _objectives_from_cli(args.objective)
            if not opt_limits and not objectives:
                raise SpecValidationError(
                    "provide --limits and/or at least one --objective"
                )
            opt_config = OptimizationConfig(
                method=OptimizeMethod(args.method),
                bound_pct=float(args.bound),
                max_iter=int(args.max_iter),
                seed=args.seed,
                objectives=tuple(objectives),
            )
            opt_result = optimize_circuit(synth.circuit, sweep, opt_limits, opt_config)
        except (
            SpecValidationError,
            AnalysisError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(_optimize_to_json(opt_result), indent=2))
        else:
            _print_optimize_human(opt_result)
        return 0

    if args.command == "sensitivity":
        try:
            spec = _spec_from_cli(args)
            synth = synthesize(spec)
            _emit_synthesis_note(spec)
            sweep = _default_sweep(spec, args)
            sens_limits: list[LimitRegion] = []
            if args.limits is not None:
                data = json.loads(args.limits.read_text(encoding="utf-8"))
                sens_limits = limits_from_mapping(data)
            sens_objectives = _objectives_from_cli(args.objective)
            sens_band: tuple[float, float] | None = None
            if args.band_range is not None:
                sens_band = (
                    parse_si(str(args.band_range[0])),
                    parse_si(str(args.band_range[1])),
                )
            sens_report = sensitivity(
                synth.circuit,
                sweep,
                limits=sens_limits,
                objectives=sens_objectives,
                relative_step_pct=float(args.relative_step),
                backend=str(args.backend),
                band=sens_band,
            )
        except (
            SpecValidationError,
            AnalysisError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(_sensitivity_to_json(sens_report), indent=2))
        else:
            _print_sensitivity_human(sens_report)
        return 0

    if args.command == "sweep":
        try:
            base = _spec_from_cli(args)
            axis = SweepAxis(args.axis)
            values = parse_values(axis, args.values)
            passband = (
                (
                    parse_si(str(args.pass_band[0])),
                    parse_si(str(args.pass_band[1])),
                )
                if args.pass_band is not None
                else None
            )
            stopband = (
                (
                    parse_si(str(args.stop_band[0])),
                    parse_si(str(args.stop_band[1])),
                )
                if args.stop_band is not None
                else None
            )
            sweep_config = DesignSweepConfig(
                base_spec=base,
                axis=axis,
                values=values,
                points=int(args.points),
                passband=passband,
                stopband=stopband,
            )
            sweep_rows = run_design_sweep(sweep_config)
        except (
            SpecValidationError,
            AnalysisError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.csv is not None:
            _write_sweep_csv(sweep_rows, args.csv)
            print(f"Wrote {args.csv}", file=sys.stderr)
        if args.json:
            print(
                json.dumps(
                    {
                        "axis": axis.value,
                        "values": list(values),
                        "rows": [_sweep_row_json(row) for row in sweep_rows],
                    },
                    indent=2,
                )
            )
        else:
            _print_sweep_human(axis, sweep_rows)
        return 0

    if args.command == "analyze":
        try:
            spec = _spec_from_cli(args)
            synth = synthesize(spec)
            _emit_synthesis_note(spec)
            nonideal = _nonideal_kwargs(args)
            loss_model = getattr(args, "inductor_loss_model", None)
            if nonideal or loss_model is not None:
                synth = SynthesisResult(
                    spec=synth.spec,
                    prototype=synth.prototype,
                    circuit=nonidealize_circuit(
                        synth.circuit,
                        **nonideal,
                        inductor_loss_model=loss_model or "constant",
                    ),
                )
            sweep = _default_sweep(spec, args)
            analysis = analyze_circuit(synth.circuit, sweep, backend=str(args.backend))
        except (
            SpecValidationError,
            AnalysisError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        s21 = mag_db(analysis.s21)
        s11 = mag_db(analysis.s11)
        gd = group_delay_s(analysis.frequency_hz, analysis.s21)
        vs = vswr(analysis)

        stress: StressReport | None = None
        if args.power > 0.0:
            stress_freq = _stress_frequency(spec)
            if stress_freq is not None:
                try:
                    stress = compute_stress(
                        synth.circuit, power_w=args.power, frequency_hz=stress_freq
                    )
                except StressError:
                    stress = None

        harmonics: HarmonicReport | None = None
        if args.harmonics or args.harmonics_f0 is not None:
            f0 = (
                parse_si(str(args.harmonics_f0))
                if args.harmonics_f0
                else _stress_frequency(spec)
            )
            if f0 is not None and f0 > 0.0:
                try:
                    harmonics = compute_harmonics(analysis, f0)
                except HarmonicError:
                    harmonics = None
        if args.export_s2p is not None:
            write_touchstone_s2p(
                analysis,
                args.export_s2p,
                comment=f"family={spec.family.value} order={spec.order}",
            )
            print(f"Wrote {args.export_s2p}", file=sys.stderr)

        if args.export_smith is not None:
            get_plot_backend().save_smith_chart(
                analysis,
                args.export_smith,
                title=(
                    f"Smith — {spec.family.value} n={spec.order} {spec.response.value}"
                ),
            )
            print(f"Wrote {args.export_smith}", file=sys.stderr)

        if args.export_csv is not None:
            export_csv(
                analysis,
                args.export_csv,
                comment=(
                    f"family={spec.family.value} order={spec.order} "
                    f"{spec.response.value} backend={analysis.backend}"
                ),
            )
            print(f"Wrote {args.export_csv}", file=sys.stderr)

        if args.export_spice is not None:
            write_spice_netlist(
                synth.circuit,
                args.export_spice,
                title=(f"{spec.family.value} n={spec.order} {spec.response.value}"),
                ac=sweep,
            )
            print(f"Wrote {args.export_spice}", file=sys.stderr)

        if args.export_asc is not None:
            write_ltspice_asc(
                synth.circuit,
                args.export_asc,
                title=f"{spec.family.value} n={spec.order} {spec.response.value}",
                ac=sweep,
            )
            print(f"Wrote {args.export_asc}", file=sys.stderr)

        if args.export_qucs is not None:
            write_qucs_schematic(
                synth.circuit,
                args.export_qucs,
                title=f"{spec.family.value} n={spec.order} {spec.response.value}",
            )
            print(f"Wrote {args.export_qucs}", file=sys.stderr)

        if args.export_build_sheet is not None:
            bom_series = ESeries(args.bom_series) if args.bom_series else None
            bom_columns = (
                tuple(
                    column.strip()
                    for column in args.bom_columns.split(",")
                    if column.strip()
                )
                if args.bom_columns
                else None
            )
            write_build_sheet(
                synth.circuit,
                args.export_build_sheet,
                spec=spec,
                stress=stress,
                power_w=args.power,
                title=f"{spec.family.value} n={spec.order} {spec.response.value}",
                series=bom_series,
                group=bool(args.bom_group),
                columns=bom_columns,
            )
            print(f"Wrote {args.export_build_sheet}", file=sys.stderr)

        compliance = check_spec_compliance(spec, synth.circuit) if args.check else None

        if args.json:
            n = analysis.frequency_hz.shape[0]
            idxs = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})
            samples = []
            for i in idxs:
                samples.append(
                    {
                        "frequency_hz": float(analysis.frequency_hz[i]),
                        "s21_db": float(s21[i]),
                        "s11_db": float(s11[i]),
                        "vswr": float(vs[i]),
                        "group_delay_s": float(gd[i]),
                        "il_db": float(insertion_loss_db(analysis)[i]),
                        "rl_db": float(return_loss_db(analysis)[i]),
                    }
                )
            payload = {
                "spec": filter_spec_to_mapping(spec),
                "backend": analysis.backend,
                "n_points": n,
                "samples": samples,
            }
            note = synthesis_note(spec)
            if note is not None:
                payload["note"] = note
            if compliance is not None:
                payload["compliance"] = compliance.to_mapping()
            if nonideal:
                payload["nonideal"] = nonideal
            if stress is not None:
                payload["stress"] = _stress_to_json(stress)
            if harmonics is not None:
                payload["harmonics"] = _harmonics_to_json(harmonics)
            print(json.dumps(payload, indent=2))
        else:
            _print_analysis_human(
                synth,
                analysis.backend,
                analysis.frequency_hz.shape[0],
                [float(x) for x in s21],
                [float(x) for x in s11],
                [float(x) for x in analysis.frequency_hz],
                [float(x) * 1e9 for x in gd],
                [float(x) for x in vs],
            )
            if stress is not None:
                _print_stress(stress)
            if harmonics is not None:
                _print_harmonics(harmonics)
            if compliance is not None:
                _print_compliance(compliance)
        return 0

    if args.command == "gui":
        from filterdesk.gui import run_gui

        return run_gui()

    if args.command == "bands":
        for preset in ALL_PRESETS:
            print(
                f"  {preset.name:14s} "
                f"{format_engineering(preset.low_hz, 'Hz', digits=4)} – "
                f"{format_engineering(preset.high_hz, 'Hz', digits=4)}  "
                f"(center {format_engineering(preset.center_hz, 'Hz', digits=4)})"
            )
        return 0

    if args.command == "toroid":
        if args.list:
            for core in list_cores():
                print(
                    f"  {core.name:9s} {core.kind:11s} mix {core.material:>2s}  "
                    f"AL={core.al_nh:6.1f} nH/N^2  "
                    f"{core.od_mm:6.2f} x {core.id_mm:6.2f} x "
                    f"{core.height_mm:5.2f} mm"
                )
            return 0
        try:
            if args.core is not None:
                core = find_core(str(args.core))
            elif args.al is not None:
                core = make_custom_core(
                    "custom",
                    float(args.al),
                    od_mm=float(args.od or 0.0),
                    id_mm=float(args.id or 0.0),
                    height_mm=float(args.height or 0.0),
                    bsat_t=args.bsat,
                )
            else:
                print(
                    "error: supply --core NAME or --al AL (or --list)",
                    file=sys.stderr,
                )
                return 2
            toroid = design_toroid(
                core,
                inductance_h=(
                    parse_si(str(args.inductance))
                    if args.inductance is not None
                    else None
                ),
                turns=args.turns,
                current_a=float(args.current),
            )
        except (ToroidError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(
                json.dumps(
                    {
                        "core": {
                            "name": core.name,
                            "kind": core.kind,
                            "material": core.material,
                            "color": core.color,
                            "al_nh": core.al_nh,
                            "od_mm": core.od_mm,
                            "id_mm": core.id_mm,
                            "height_mm": core.height_mm,
                            "ae_mm2": core.ae_mm2,
                            "bsat_t": core.bsat_t,
                        },
                        "turns_exact": toroid.turns_exact,
                        "turns": toroid.turns,
                        "inductance_h": toroid.inductance_h,
                        "target_inductance_h": toroid.target_inductance_h,
                        "wire": {
                            "fits": toroid.wire.fits,
                            "awg": toroid.wire.awg,
                            "diameter_mm": toroid.wire.diameter_mm,
                            "max_diameter_mm": toroid.wire.max_diameter_mm,
                            "fill_ratio": toroid.wire.fill_ratio,
                        },
                        "wire_length_m": toroid.wire_length_m,
                        "flux_density_t": toroid.flux_density_t,
                        "saturation_ratio": toroid.saturation_ratio,
                        "saturated": toroid.saturated,
                    },
                    indent=2,
                )
            )
            return 0

        print(
            f"{core.name}  ({core.kind}, mix {core.material}, AL={core.al_nh:g} nH/N^2)"
        )
        if toroid.target_inductance_h is not None:
            print(
                "  Target L = "
                f"{format_engineering(toroid.target_inductance_h, 'H', digits=4)}"
            )
        print(f"  Turns: {toroid.turns_exact:.2f} -> {toroid.turns}")
        print(f"  L = {format_engineering(toroid.inductance_h, 'H', digits=6)}")
        if toroid.wire.fits:
            print(
                f"  Wire: AWG {toroid.wire.awg} "
                f"({toroid.wire.diameter_mm:.3f} mm), "
                f"max {toroid.wire.max_diameter_mm:.3f} mm, "
                f"fill {(toroid.wire.fill_ratio or 0.0) * 100:.0f}%"
            )
        else:
            print(
                "  Wire: does not fit in one layer "
                f"(max {toroid.wire.max_diameter_mm:.3f} mm)"
            )
        if toroid.wire_length_m > 0.0:
            print(f"  Wire length ~ {toroid.wire_length_m:.3f} m")
        if toroid.flux_density_t is not None:
            print(f"  Bpk = {toroid.flux_density_t * 1000.0:.1f} mT")
            if toroid.saturation_ratio is not None:
                flag = "  SATURATED" if toroid.saturated else ""
                print(f"  B/Bsat = {toroid.saturation_ratio:.2f}{flag}")
        return 0

    if args.command == "air-coil":
        try:
            awg = args.awg
            wire_mm = args.wire_mm
            if awg is None and wire_mm is None:
                awg = 24
            enamel_mm = 0.0 if args.bare_wire else args.enamel_mm
            air_design = design_air_coil(
                diameter_mm=float(args.diameter),
                awg=awg,
                wire_diameter_mm=wire_mm,
                enamel_build_mm=enamel_mm,
                inductance_h=(
                    parse_si(str(args.inductance))
                    if args.inductance is not None
                    else None
                ),
                turns=args.turns,
            )
        except (AirCoilError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(
                json.dumps(
                    {
                        "diameter_mm": air_design.diameter_mm,
                        "awg": air_design.awg,
                        "wire_diameter_mm": air_design.wire_diameter_mm,
                        "enamel_build_mm": air_design.enamel_build_mm,
                        "overall_diameter_mm": air_design.overall_diameter_mm,
                        "turns_exact": air_design.turns_exact,
                        "turns": air_design.turns,
                        "turns_below": air_design.turns_below,
                        "inductance_h": air_design.inductance_h,
                        "inductance_below_h": air_design.inductance_below_h,
                        "target_inductance_h": air_design.target_inductance_h,
                        "length_mm": air_design.length_mm,
                        "length_to_diameter": air_design.length_to_diameter,
                        "wire_length_m": air_design.wire_length_m,
                        "resistance_ohm": air_design.resistance_ohm,
                        "short_coil": air_design.short_coil,
                    },
                    indent=2,
                )
            )
            return 0
        print(
            f"Air-core solenoid D = {air_design.diameter_mm:g} mm, "
            f"wire {air_design.wire_diameter_mm:.3f} mm bare / "
            f"{air_design.overall_diameter_mm:.3f} mm over enamel "
            f"(AWG {air_design.awg} eq.)"
        )
        if air_design.target_inductance_h is not None:
            print(
                "  Target L = "
                f"{format_engineering(air_design.target_inductance_h, 'H', digits=4)}"
            )
        print(f"  Turns: {air_design.turns_exact:.2f} -> {air_design.turns}")
        if air_design.turns_below < air_design.turns:
            print(
                f"  Closest below: {air_design.turns_below} -> "
                f"{format_engineering(air_design.inductance_below_h, 'H', digits=6)}"
            )
        print(f"  L = {format_engineering(air_design.inductance_h, 'H', digits=6)}")
        short = " (short coil: formula less accurate)" if air_design.short_coil else ""
        print(
            f"  Coil length = {air_design.length_mm:.2f} mm "
            f"(L/D = {air_design.length_to_diameter:.2f}){short}"
        )
        print(f"  Wire length ~ {air_design.wire_length_m:.3f} m")
        print(f"  R_DC = {air_design.resistance_ohm:.4f} Ohm")
        print("  note: SRF/Q not modelled (single close-wound layer)")
        return 0

    if args.command == "transformer":
        try:
            core = find_core(str(args.core))
            f_min = parse_si(str(args.frequency))
            f_max = parse_si(str(args.f_max)) if args.f_max else f_min * 10.0
            tr_design = design_balun(
                core,
                kind=BalunKind(str(args.kind)),
                z_unbalanced_ohm=parse_si(str(args.z_low)),
                z_balanced_ohm=parse_si(str(args.z_high)),
                f_min_hz=f_min,
                f_max_hz=f_max,
                power_w=float(args.power),
                topology=TransformerTopology(str(args.topology)),
                coupling=float(args.coupling),
                tan_delta=float(args.tan_delta),
                winding_capacitance_f=float(args.winding_c),
                line_z0_ohm=args.line_z0,
                line_length_m=args.line_length,
                velocity_factor=float(args.vf),
                line_loss_db_per_m=float(args.line_loss),
                reactance_factor=float(args.reactance_factor),
                current_density_a_mm2=float(args.current_density),
            )
        except (BalunError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        options = (
            design_balun_options(
                core,
                kind=BalunKind(str(args.kind)),
                z_unbalanced_ohm=parse_si(str(args.z_low)),
                z_balanced_ohm=parse_si(str(args.z_high)),
                f_min_hz=f_min,
                f_max_hz=f_max,
                power_w=float(args.power),
                topology=TransformerTopology(str(args.topology)),
                coupling=float(args.coupling),
                tan_delta=float(args.tan_delta),
                winding_capacitance_f=float(args.winding_c),
                line_z0_ohm=args.line_z0,
                line_length_m=args.line_length,
                velocity_factor=float(args.vf),
                line_loss_db_per_m=float(args.line_loss),
                reactance_factor=float(args.reactance_factor),
                current_density_a_mm2=float(args.current_density),
            )
            if args.show_options
            else []
        )
        if args.json:
            payload = {
                "kind": tr_design.kind.value,
                "topology": tr_design.topology.value,
                "core": tr_design.core.name,
                "z_low_ohm": tr_design.z_unbalanced_ohm,
                "z_high_ohm": tr_design.z_balanced_ohm,
                "z_unbalanced_ohm": tr_design.z_unbalanced_ohm,
                "z_balanced_ohm": tr_design.z_balanced_ohm,
                "impedance_ratio": tr_design.impedance_ratio,
                "ratio_text": tr_design.ratio_text,
                "turns_ratio": tr_design.actual_turns_ratio,
                "n_low": tr_design.n_primary,
                "n_high": tr_design.n_secondary,
                "n_primary": tr_design.n_primary,
                "n_secondary": tr_design.n_secondary,
                "total_turns": tr_design.total_turns,
                "reactance_ratio": tr_design.reactance_ratio,
                "hf_caution": tr_design.hf_caution,
                "thermal_caution": tr_design.thermal_caution,
                "thermal_text": tr_design.thermal_text,
                "core_loss_w": tr_design.core_loss_w,
                "copper_loss_w": tr_design.copper_loss_w,
                "total_loss_w": tr_design.total_loss_w,
                "temperature_rise_c": tr_design.temperature_rise_c,
                "hot_temperature_c": tr_design.hot_temperature_c,
                "bsat_margin_hot": tr_design.bsat_margin_hot,
                "power_density_w_cm3": tr_design.power_density_w_cm3,
                "warnings": list(tr_design.warnings),
                "status": tr_design.status_text,
                "magnetizing_inductance_h": tr_design.magnetizing_inductance_h,
                "leakage_inductance_h": tr_design.leakage_inductance_h,
                "core_loss_ohm": tr_design.core_loss_ohm,
                "common_mode_impedance_ohm": tr_design.common_mode_impedance_ohm,
                "z0_line_ohm": tr_design.z0_line_ohm,
                "length_m": tr_design.length_m,
                "v_low_rms": tr_design.v_unbalanced_rms,
                "v_high_rms": tr_design.v_balanced_rms,
                "i_low_rms_a": tr_design.i_unbalanced_rms_a,
                "i_high_rms_a": tr_design.i_balanced_rms_a,
                "b_peak_t": tr_design.b_peak_t,
                "bsat_margin": tr_design.bsat_margin,
                "saturated": tr_design.saturated,
                "awg_low": tr_design.awg_primary,
                "awg_high": tr_design.awg_secondary,
                "awg_primary": tr_design.awg_primary,
                "awg_secondary": tr_design.awg_secondary,
                "fit_awg": tr_design.fit.awg,
                "fit_diameter_mm": tr_design.fit.diameter_mm,
                "notes": list(tr_design.notes),
                "options": [
                    {
                        "n_low": d.n_primary,
                        "n_high": d.n_secondary,
                        "n_primary": d.n_primary,
                        "n_secondary": d.n_secondary,
                        "total_turns": d.total_turns,
                        "magnetizing_inductance_h": d.magnetizing_inductance_h,
                        "leakage_inductance_h": d.leakage_inductance_h,
                        "reactance_ratio": d.reactance_ratio,
                        "b_peak_t": d.b_peak_t,
                        "bsat_margin": d.bsat_margin,
                        "fit_awg": d.fit.awg,
                        "hf_caution": d.hf_caution,
                        "thermal_caution": d.thermal_caution,
                        "thermal_text": d.thermal_text,
                        "total_loss_w": d.total_loss_w,
                        "status": d.status_text,
                    }
                    for d in options
                ]
                if args.show_options
                else [],
            }
            print(json.dumps(payload, indent=2))
            return 0
        print(
            f"{tr_design.kind.value}: {tr_design.z_unbalanced_ohm:g} -> "
            f"{tr_design.z_balanced_ohm:g} Ohm on {tr_design.core.name}"
        )
        print(
            f"  Topology: {tr_design.topology.value}, "
            f"total turns {tr_design.total_turns}"
        )
        print(
            f"  Turns: low={tr_design.n_primary}, high={tr_design.n_secondary} "
            f"({tr_design.ratio_text}, X_Lm/Z {tr_design.reactance_ratio:.2f})"
        )
        print(
            "  Lm (low side) = "
            f"{format_engineering(tr_design.magnetizing_inductance_h, 'H', digits=4)}"
        )
        if tr_design.core_loss_ohm is not None:
            lk = format_engineering(tr_design.leakage_inductance_h, "H", digits=4)
            print(f"  Lk = {lk}, Rp = {tr_design.core_loss_ohm:.4g} Ohm")
        print(
            f"  V low/high = {tr_design.v_unbalanced_rms:.3g} / "
            f"{tr_design.v_balanced_rms:.3g} Vrms"
        )
        print(
            f"  I low/high = {tr_design.i_unbalanced_rms_a:.3g} / "
            f"{tr_design.i_balanced_rms_a:.3g} Arms"
        )
        if tr_design.b_peak_t is not None:
            b_txt = f"{tr_design.b_peak_t * 1000.0:.1f} mT"
            if tr_design.bsat_margin is not None:
                b_txt += f" (Bsat/B={tr_design.bsat_margin:.2f})"
            print(f"  Bpk = {b_txt}")
        print(
            f"  Wire: low AWG {tr_design.awg_primary}, high AWG "
            f"{tr_design.awg_secondary}; single-layer fit AWG "
            f"{tr_design.fit.awg}"
        )
        if tr_design.total_loss_w is not None:
            print(
                f"  Loss: core {tr_design.core_loss_w:.2f} W, copper "
                f"{tr_design.copper_loss_w:.3f} W, total "
                f"{tr_design.total_loss_w:.2f} W; hot {tr_design.thermal_text}"
            )
        print(f"  status: {tr_design.status_text}")
        for note in tr_design.notes:
            print(f"  note: {note}")
        return 0

    if args.command in {"microstrip", "qwt", "stub"}:
        try:
            substrate = _microstrip_substrate(args)
            frequency = parse_si(str(args.frequency))
            if args.command == "microstrip":
                line = design_microstrip(
                    parse_si(str(args.z0)),
                    substrate,
                    frequency,
                    length_m=parse_si(str(args.length)),
                )
                payload = {
                    "kind": "microstrip",
                    "substrate": substrate.name,
                    "er": substrate.er,
                    "h_mm": substrate.h_mm,
                    "tan_delta": substrate.tan_delta,
                    "z0_ohm": line.z0_ohm,
                    "width_mm": line.width_mm,
                    "eeff": line.eeff,
                    "wavelength_m": line.wavelength_m,
                    "quarter_wave_m": line.quarter_wave_m,
                    "length_m": line.length_m,
                    "length_deg": line.electrical_length_deg(),
                    "conductor_loss_db_per_m": line.conductor_loss_db_per_m,
                    "dielectric_loss_db_per_m": line.dielectric_loss_db_per_m,
                    "loss_db_per_m": line.loss_db_per_m,
                    "loss_db": line.loss_db(),
                }
                if args.json:
                    print(json.dumps(payload, indent=2))
                    return 0
                print(
                    f"Microstrip on {substrate.name} "
                    f"(er={substrate.er:g}, h={substrate.h_mm:g} mm)"
                )
                print(
                    f"  Z0 = {line.z0_ohm:.2f} Ohm -> W = {line.width_mm:.3f} mm, "
                    f"eeff = {line.eeff:.3f}"
                )
                print(
                    f"  lambda_g = {line.wavelength_m * 1000.0:.2f} mm, "
                    f"lambda_g/4 = {line.quarter_wave_m * 1000.0:.2f} mm"
                )
                print(
                    f"  Loss = {line.loss_db_per_m:.3f} dB/m "
                    f"(conductor {line.conductor_loss_db_per_m:.3f} + "
                    f"dielectric {line.dielectric_loss_db_per_m:.3f})"
                )
                if line.length_m:
                    print(
                        f"  Length {line.length_m * 1000.0:.2f} mm = "
                        f"{line.electrical_length_deg():.1f} deg, "
                        f"loss {line.loss_db():.4f} dB"
                    )
                return 0
            if args.command == "qwt":
                qwt_design = design_quarter_wave_transformer(
                    parse_si(str(args.z_low)),
                    parse_si(str(args.z_high)),
                    substrate,
                    frequency,
                )
                payload = {
                    "kind": "quarter_wave_transformer",
                    "substrate": substrate.name,
                    "z_low_ohm": qwt_design.z_low_ohm,
                    "z_high_ohm": qwt_design.z_high_ohm,
                    "z0_ohm": qwt_design.z0_ohm,
                    "width_mm": qwt_design.line.width_mm,
                    "length_m": qwt_design.line.length_m,
                    "eeff": qwt_design.line.eeff,
                    "loss_db": qwt_design.line.loss_db(),
                }
                if args.json:
                    print(json.dumps(payload, indent=2))
                    return 0
                print(
                    f"Quarter-wave transformer {qwt_design.z_low_ohm:g} -> "
                    f"{qwt_design.z_high_ohm:g} Ohm on {substrate.name}"
                )
                print(
                    f"  Z0 = {qwt_design.z0_ohm:.2f} Ohm -> "
                    f"W = {qwt_design.line.width_mm:.3f} mm, "
                    f"length = {qwt_design.line.length_m * 1000.0:.2f} mm"
                )
                print(f"  Loss = {qwt_design.line.loss_db():.4f} dB")
                return 0
            stub_design = design_stub(
                parse_si(str(args.z0)),
                float(args.angle),
                substrate,
                frequency,
                kind=StubKind(str(args.kind)),
            )
            zin = stub_design.input_impedance_ohm()
            payload = {
                "kind": "stub",
                "stub_kind": stub_design.kind.value,
                "substrate": substrate.name,
                "z0_ohm": stub_design.line.z0_ohm,
                "angle_deg": stub_design.angle_deg,
                "width_mm": stub_design.line.width_mm,
                "length_m": stub_design.line.length_m,
                "eeff": stub_design.line.eeff,
                "zin_real_ohm": zin.real,
                "zin_imag_ohm": zin.imag,
                "loss_db": stub_design.line.loss_db(),
            }
            if args.json:
                print(json.dumps(payload, indent=2))
                return 0
            print(
                f"{stub_design.kind.value.capitalize()} stub "
                f"{stub_design.angle_deg:g} deg, Z0 = {stub_design.line.z0_ohm:.2f} "
                f"Ohm on {substrate.name}"
            )
            print(
                f"  W = {stub_design.line.width_mm:.3f} mm, "
                f"length = {stub_design.line.length_m * 1000.0:.2f} mm"
            )
            print(
                f"  Zin = {zin.real:.3f} "
                f"{zin.imag:+.3f}j Ohm, loss = {stub_design.line.loss_db():.4f} dB"
            )
            return 0
        except (MicrostripError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.command == "attenuator":
        try:
            design = design_attenuator(
                float(args.db), parse_si(str(args.z0)), AttenuatorKind(args.kind)
            )
        except (AttenuatorError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(
                json.dumps(
                    {
                        "kind": design.kind.value,
                        "attenuation_db": design.attenuation_db,
                        "z0_ohm": design.z0_ohm,
                        "r_series_ohm": design.r_series_ohm,
                        "r_shunt_ohm": design.r_shunt_ohm,
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"{design.kind.value.upper()} pad {design.attenuation_db:g} dB @ "
                f"{design.z0_ohm:g} Ohm:"
            )
            print(
                f"  series R = "
                f"{format_engineering(design.r_series_ohm, 'Ohm', digits=4)}"
            )
            print(
                f"  shunt  R = "
                f"{format_engineering(design.r_shunt_ohm, 'Ohm', digits=4)}"
            )
        return 0

    if args.command == "match":
        try:
            match_design = design_matching(
                parse_si(str(args.z0)),
                parse_si(str(args.rl)),
                parse_si(str(args.xl)),
                parse_si(str(args.f)),
                MatchingTopology(args.topology),
                args.q,
            )
        except (MatchingError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(
                json.dumps(
                    {
                        "topology": match_design.topology.value,
                        "frequency_hz": match_design.frequency_hz,
                        "source_ohm": match_design.source_ohm,
                        "load_r_ohm": match_design.load_r_ohm,
                        "load_x_ohm": match_design.load_x_ohm,
                        "q": match_design.q,
                        "input_impedance_ohm": [
                            match_design.input_impedance_ohm.real,
                            match_design.input_impedance_ohm.imag,
                        ],
                        "elements": [
                            {"role": e.role.value, "kind": e.kind, "value": e.value}
                            for e in match_design.elements
                        ],
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"{match_design.topology.value.upper()} match "
                f"{match_design.source_ohm:g} -> {match_design.load_r_ohm:g}"
                f"{match_design.load_x_ohm:+g}j @ "
                f"{format_engineering(match_design.frequency_hz, 'Hz', digits=4)}:"
            )
            for e in match_design.elements:
                unit = "H" if e.kind == "L" else "F"
                print(
                    f"  {e.role.value:6s} {e.kind} = "
                    f"{format_engineering(e.value, unit, digits=4)}"
                )
            print(
                f"  Zin = {match_design.input_impedance_ohm.real:.4g}"
                f"{match_design.input_impedance_ohm.imag:+g}j Ohm"
            )
        return 0

    if args.command == "estimate-order":
        response = FilterResponse(args.response)
        band = response in (
            FilterResponse.BAND_PASS,
            FilterResponse.BAND_STOP,
        )
        band_kwargs: dict[str, float] = {}
        try:
            if band:
                if args.pass_band is None or args.stop_band is None:
                    raise OrderEstimateError(
                        "band-pass/band-stop require --pass-band and --stop-band"
                    )
                band_kwargs = {
                    "f_pass_low_hz": parse_si(str(args.pass_band[0])),
                    "f_pass_high_hz": parse_si(str(args.pass_band[1])),
                    "f_stop_low_hz": parse_si(str(args.stop_band[0])),
                    "f_stop_high_hz": parse_si(str(args.stop_band[1])),
                }
                scalar_kwargs: dict[str, float] = {}
            else:
                if args.f_pass is None or args.f_stop is None:
                    raise OrderEstimateError(
                        "low-pass/high-pass require --f-pass and --f-stop"
                    )
                scalar_kwargs = {
                    "f_pass_hz": parse_si(str(args.f_pass)),
                    "f_stop_hz": parse_si(str(args.f_stop)),
                }
            estimate = estimate_minimum_order(
                ApproximationFamily(args.family),
                response,
                passband_attenuation_db=float(args.ap),
                stopband_attenuation_db=float(args.as_db),
                **scalar_kwargs,
                **band_kwargs,
            )
        except (OrderEstimateError, SpecValidationError, ValueError) as exc:
            print(f"estimate-order failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            estimate_payload: dict[str, object] = {
                "order": estimate.order,
                "family": estimate.family.value,
                "response": estimate.response.value,
                "passband_attenuation_db": estimate.passband_attenuation_db,
                "stopband_attenuation_db": estimate.stopband_attenuation_db,
                "omega_ratio": estimate.omega_ratio,
                "natural_freq_hz": estimate.natural_freq_hz,
                "notes": estimate.notes,
            }
            if band:
                estimate_payload.update(
                    {
                        "f_pass_low_hz": estimate.f_pass_low_hz,
                        "f_pass_high_hz": estimate.f_pass_high_hz,
                        "f_stop_low_hz": estimate.f_stop_low_hz,
                        "f_stop_high_hz": estimate.f_stop_high_hz,
                        "natural_freq_low_hz": estimate.natural_freq_low_hz,
                        "natural_freq_high_hz": estimate.natural_freq_high_hz,
                    }
                )
            else:
                estimate_payload.update(
                    {
                        "f_pass_hz": estimate.f_pass_hz,
                        "f_stop_hz": estimate.f_stop_hz,
                    }
                )
            print(json.dumps(estimate_payload, indent=2))
        else:
            print(f"Minimum order: {estimate.order}")
            print(f"Family:        {estimate.family.value}")
            print(f"Response:      {estimate.response.value}")
            if band:
                print(
                    "Passband:      "
                    f"{format_engineering(estimate.f_pass_low_hz or 0.0, 'Hz')}"
                    " – "
                    f"{format_engineering(estimate.f_pass_high_hz or 0.0, 'Hz')}"
                )
                print(
                    "Stopband:      "
                    f"{format_engineering(estimate.f_stop_low_hz or 0.0, 'Hz')}"
                    " – "
                    f"{format_engineering(estimate.f_stop_high_hz or 0.0, 'Hz')}"
                )
            else:
                print(f"f_pass:        {format_engineering(estimate.f_pass_hz, 'Hz')}")
                print(f"f_stop:        {format_engineering(estimate.f_stop_hz, 'Hz')}")
            print(f"Ap:            {estimate.passband_attenuation_db:g} dB")
            print(f"As:            {estimate.stopband_attenuation_db:g} dB")
            print(f"Ωs ratio:      {estimate.omega_ratio:.6g}")
            print(
                f"Natural f:     {format_engineering(estimate.natural_freq_hz, 'Hz')}"
            )
            print(f"Notes:         {estimate.notes}")
        return 0

    if args.command == "touchstone-info":
        try:
            data = read_touchstone(args.path)
        except (TouchstoneError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            f = data.frequency_hz
            print(
                json.dumps(
                    {
                        "source": data.source,
                        "n_ports": data.n_ports,
                        "n_points": data.n_points,
                        "f_min_hz": float(f.min()),
                        "f_max_hz": float(f.max()),
                        "z0_ohm": data.z0_ohm,
                        "freq_unit": data.freq_unit,
                        "data_format": data.data_format,
                        "comments": data.comments,
                    },
                    indent=2,
                )
            )
        else:
            print(data.summary())
            if data.source:
                print(f"source: {data.source}")
        return 0

    if args.command == "tune-vna":
        try:
            spec = _spec_from_cli(args)
            data = read_touchstone(args.measured)
            measured = data.to_analysis_result()
            holdout = None
            if args.holdout is not None:
                holdout = read_touchstone(args.holdout).to_analysis_result()
            meta_path = args.metadata
            if meta_path is None:
                candidate = metadata_path_for(args.measured)
                meta_path = candidate if candidate.exists() else None
            metadata = None if meta_path is None else read_vna_metadata(meta_path)
            nominal = synthesize(spec)
            cfg = VnaTuningConfig(
                bound_pct=float(args.bound),
                bound_mode=VnaBoundMode(str(args.bound_mode)),
                max_points=int(args.max_points),
                max_nfev=int(args.max_nfev),
                global_starts=int(args.global_starts),
                fit_s11=not args.no_s11,
                fit_s21=not args.no_s21,
                fit_phase=bool(args.fit_phase),
                phase_weight=float(args.phase_weight),
                phase_min_db=float(args.phase_min_db),
                max_delay_ns=float(args.max_delay_ns),
                f_min_hz=parse_si(str(args.f_min)) if args.f_min else None,
                f_max_hz=parse_si(str(args.f_max)) if args.f_max else None,
            )
            tuned = fit_circuit_to_measurement(
                nominal.circuit, measured, cfg, holdout=holdout
            )
        except (VnaTuningError, TouchstoneError, OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(
                json.dumps(
                    {
                        "initial_rms_db": tuned.initial_rms_db,
                        "final_rms_db": tuned.final_rms_db,
                        "improvement_db": tuned.improvement_db,
                        "initial_rms_s11_db": tuned.initial_rms_s11_db,
                        "final_rms_s11_db": tuned.final_rms_s11_db,
                        "initial_rms_s21_db": tuned.initial_rms_s21_db,
                        "final_rms_s21_db": tuned.final_rms_s21_db,
                        "success": tuned.success,
                        "message": tuned.message,
                        "n_evaluations": tuned.n_evaluations,
                        "n_points": int(tuned.frequency_hz.size),
                        "holdout_rms_db": tuned.holdout_rms_db,
                        "holdout_rms_s11_db": tuned.holdout_rms_s11_db,
                        "holdout_rms_s21_db": tuned.holdout_rms_s21_db,
                        "holdout_points": tuned.holdout_points,
                        "quality_notes": list(tuned.quality_notes),
                        "metadata": (
                            None
                            if metadata is None
                            else {
                                "vna_model": metadata.vna_model,
                                "calibration": metadata.calibration,
                                "reference_plane": metadata.reference_plane,
                                "cables": metadata.cables,
                                "connectors": metadata.connectors,
                                "terminations": metadata.terminations,
                                "fixture": metadata.fixture,
                                "temperature_c": metadata.temperature_c,
                                "measured_at": metadata.measured_at,
                                "operator": metadata.operator,
                                "notes": metadata.notes,
                            }
                        ),
                        "bound_mode": tuned.bound_mode.value,
                        "n_starts": tuned.n_starts,
                        "delay_s": tuned.delay_s,
                        "phase_s11_deg": tuned.phase_s11_deg,
                        "phase_s21_deg": tuned.phase_s21_deg,
                        "components": [
                            {"ref": ref, "initial": float(a), "final": float(b)}
                            for ref, a, b in zip(
                                tuned.refs,
                                tuned.initial_values,
                                tuned.final_values,
                                strict=True,
                            )
                        ],
                    },
                    indent=2,
                )
            )
            return 0
        print(
            f"VNA fit: {tuned.initial_rms_db:.3f} -> {tuned.final_rms_db:.3f} dB RMS "
            f"({tuned.improvement_db:+.3f} dB, {tuned.n_evaluations} evaluations, "
            f"{tuned.frequency_hz.size} points)"
        )
        print(
            f"  S21 {tuned.initial_rms_s21_db:.3f} -> {tuned.final_rms_s21_db:.3f} dB, "
            f"S11 {tuned.initial_rms_s11_db:.3f} -> {tuned.final_rms_s11_db:.3f} dB"
        )
        if tuned.delay_s is not None:
            print(
                f"  Phase model: delay {tuned.delay_s * 1e9:.3f} ns, "
                f"S21 {tuned.phase_s21_deg or 0.0:+.2f} deg, "
                f"S11 {tuned.phase_s11_deg or 0.0:+.2f} deg"
            )
        if tuned.holdout_rms_db is not None:
            print(
                f"  Holdout: {tuned.holdout_rms_db:.3f} dB RMS "
                f"({tuned.holdout_points} points)"
            )
        if tuned.quality_notes:
            print(f"  quality: {'; '.join(tuned.quality_notes)}")
        if metadata is not None:
            print(f"  metadata: {metadata.summary()}")
        for ref, initial, final in zip(
            tuned.refs, tuned.initial_values, tuned.final_values, strict=True
        ):
            pct = (final / initial - 1.0) * 100.0
            print(f"  {ref}: {initial:.6g} -> {final:.6g} ({pct:+.2f}%)")
        return 0

    if args.command == "to-csv":
        columns = tuple(
            name.strip() for name in str(args.columns).split(",") if name.strip()
        )
        try:
            data = read_touchstone(args.input)
            analysis_result = analysis_from_touchstone(data)
            export_csv(
                analysis_result,
                args.output,
                columns=columns,
                comment=f"source={args.input}",
            )
        except (
            TouchstoneError,
            CsvExportError,
            OSError,
            ValueError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote {args.output}", file=sys.stderr)
        return 0

    if args.command == "compare":
        try:
            sim = read_touchstone(args.simulated).to_analysis_result()
            mea = read_touchstone(args.measured).to_analysis_result()
        except (TouchstoneError, OSError) as exc:
            print(f"compare failed: {exc}", file=sys.stderr)
            return 2
        try:
            cmp = compare_results(sim, mea)
        except CompareError as exc:
            print(f"compare failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(
                json.dumps(
                    {
                        "n_points": cmp.n_points,
                        "f_min_hz": cmp.f_min_hz,
                        "f_max_hz": cmp.f_max_hz,
                        "s21_db_rms_error": cmp.s21_db_rms_error,
                        "s21_db_max_error": cmp.s21_db_max_error,
                        "s11_db_rms_error": cmp.s11_db_rms_error,
                        "s11_db_max_error": cmp.s11_db_max_error,
                    },
                    indent=2,
                )
            )
        else:
            print(cmp.summary())
        return 0

    if not explicit and not arg_list:
        # Launched with no arguments (e.g. double-clicked): open the GUI.
        from filterdesk.gui import run_gui

        return run_gui()

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
