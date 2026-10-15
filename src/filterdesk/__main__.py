"""CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from filterdesk import __version__
from filterdesk.analysis.adapters.abcd_ladder import AnalysisError
from filterdesk.analysis.derived import (
    group_delay_s,
    insertion_loss_db,
    mag_db,
    return_loss_db,
    vswr,
)
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import (
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealSeriesLC,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import (
    FilterSpec,
    SpecValidationError,
    default_cutoff_definition,
    default_topology,
    filter_spec_from_mapping,
    filter_spec_to_mapping,
)
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.io.touchstone import write_touchstone_s2p
from filterdesk.plotting import export_smith_chart
from filterdesk.services.session import default_sweep_for_spec
from filterdesk.synthesis import synthesize
from filterdesk.synthesis.api import SynthesisResult
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
        "--json",
        action="store_true",
        help="Emit JSON summary (checkpoints + arrays truncated)",
    )

    sub.add_parser(
        "gui",
        help="Launch the FilterDesk desktop GUI",
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
        ],
        help="Approximation family",
    )
    est.add_argument(
        "--response",
        required=True,
        choices=[FilterResponse.LOW_PASS.value, FilterResponse.HIGH_PASS.value],
        help="LP or HP",
    )
    est.add_argument(
        "--f-pass",
        required=True,
        help="Passband edge frequency (Hz), e.g. 1M",
    )
    est.add_argument(
        "--f-stop",
        required=True,
        help="Stopband edge frequency (Hz), e.g. 2M",
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
    return parser


def _add_spec_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--spec",
        type=Path,
        help="Path to specification JSON (golden format)",
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
                **(
                    {"value": a.value}
                    if a.value is not None
                    else {"L": a.L, "C": a.C}
                ),
            }
            for a in result.prototype.arms
        ]
    else:
        proto_obj["g_values"] = list(result.prototype.g_values)
    return {
        "spec": filter_spec_to_mapping(result.spec),
        "prototype": proto_obj,
        "components": components,
    }


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "synthesize":
        try:
            spec = _spec_from_cli(args)
            result = synthesize(spec)
        except (SpecValidationError, OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(_synth_to_json(result), indent=2))
        else:
            _print_synth_human(result)
        return 0

    if args.command == "analyze":
        try:
            spec = _spec_from_cli(args)
            synth = synthesize(spec)
            sweep = _default_sweep(spec, args)
            analysis = analyze_circuit(
                synth.circuit, sweep, backend=str(args.backend)
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

        s21 = mag_db(analysis.s21)
        s11 = mag_db(analysis.s11)
        gd = group_delay_s(analysis.frequency_hz, analysis.s21)
        vs = vswr(analysis)
        if args.export_s2p is not None:
            write_touchstone_s2p(
                analysis,
                args.export_s2p,
                comment=f"family={spec.family.value} order={spec.order}",
            )
            print(f"Wrote {args.export_s2p}", file=sys.stderr)

        if args.export_smith is not None:
            export_smith_chart(
                analysis,
                args.export_smith,
                title=(
                    f"Smith — {spec.family.value} "
                    f"n={spec.order} {spec.response.value}"
                ),
            )
            print(f"Wrote {args.export_smith}", file=sys.stderr)

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
        return 0

    if args.command == "gui":
        from filterdesk.gui import run_gui

        return run_gui()

    if args.command == "estimate-order":
        try:
            estimate = estimate_minimum_order(
                ApproximationFamily(args.family),
                FilterResponse(args.response),
                f_pass_hz=parse_si(str(args.f_pass)),
                f_stop_hz=parse_si(str(args.f_stop)),
                passband_attenuation_db=float(args.ap),
                stopband_attenuation_db=float(args.as_db),
            )
        except (OrderEstimateError, SpecValidationError, ValueError) as exc:
            print(f"estimate-order failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(
                json.dumps(
                    {
                        "order": estimate.order,
                        "family": estimate.family.value,
                        "response": estimate.response.value,
                        "f_pass_hz": estimate.f_pass_hz,
                        "f_stop_hz": estimate.f_stop_hz,
                        "passband_attenuation_db": (
                            estimate.passband_attenuation_db
                        ),
                        "stopband_attenuation_db": (
                            estimate.stopband_attenuation_db
                        ),
                        "omega_ratio": estimate.omega_ratio,
                        "natural_freq_hz": estimate.natural_freq_hz,
                        "notes": estimate.notes,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Minimum order: {estimate.order}")
            print(f"Family:        {estimate.family.value}")
            print(f"Response:      {estimate.response.value}")
            print(
                f"f_pass:        {format_engineering(estimate.f_pass_hz, 'Hz')}"
            )
            print(
                f"f_stop:        {format_engineering(estimate.f_stop_hz, 'Hz')}"
            )
            print(f"Ap:            {estimate.passband_attenuation_db:g} dB")
            print(f"As:            {estimate.stopband_attenuation_db:g} dB")
            print(f"Ωs ratio:      {estimate.omega_ratio:.6g}")
            print(
                "Natural f:     "
                f"{format_engineering(estimate.natural_freq_hz, 'Hz')}"
            )
            print(f"Notes:         {estimate.notes}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
