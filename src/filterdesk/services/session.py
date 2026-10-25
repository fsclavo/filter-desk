"""Design session — GUI-independent application state."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from filterdesk import __version__
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.harmonics import (
    HarmonicError,
    HarmonicReport,
    compute_harmonics,
)
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.stress import StressError, StressReport, compute_stress
from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
from filterdesk.components_std import (
    ESeries,
    SnapReport,
    SnapStrategy,
    nonidealize_circuit,
    snap_circuit,
)
from filterdesk.domain import circuit_edit
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    ElementRole,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.overlays import (
    MAX_LIMITS,
    MAX_MARKERS,
    LimitRegion,
    Marker,
    limits_from_mapping,
    limits_to_mapping,
    markers_from_mapping,
    markers_to_mapping,
)
from filterdesk.domain.project import Project, ProjectMetadata
from filterdesk.domain.prototype import Prototype
from filterdesk.domain.specs import FilterSpec, validate_spec
from filterdesk.montecarlo import (
    ElementTolerance,
    MonteCarloConfig,
    MonteCarloResult,
    ToleranceDistribution,
    run_monte_carlo,
)
from filterdesk.optimization import (
    OptimizationConfig,
    OptimizationResult,
    optimize_circuit,
)
from filterdesk.services.retune import (
    RetuneRequest,
    nudge_value,
    retune_spec,
)
from filterdesk.services.retune import (
    scale_response as _scale_spec_response,
)
from filterdesk.synthesis import synthesize

#: Neutral project title used until the user names/saves the document.
DEFAULT_TITLE = "Untitled"

#: Old hard-coded default; normalised to :data:`DEFAULT_TITLE` on load.
_LEGACY_TITLES = frozenset({"Milestone Chebyshev HP"})


def _base_element_id(ref: str) -> str:
    for suffix in (".Ls", ".Cs", ".Lp", ".Cp", ".L", ".C"):
        if ref.endswith(suffix):
            return ref[: -len(suffix)]
    return ref


def _element_value_si(circuit: Circuit, element_id: str) -> float:
    target_id = element_id
    part: str | None = None
    for suffix in (".Ls", ".Cs", ".Lp", ".Cp", ".L", ".C"):
        if element_id.endswith(suffix):
            target_id = element_id[: -len(suffix)]
            part = suffix[1:]
            break
    for el in circuit.elements:
        if el.id != target_id:
            continue
        if isinstance(el, IdealCapacitor):
            return float(el.value_f)
        if isinstance(el, IdealInductor):
            return float(el.value_h)
        if isinstance(el, NonIdealCapacitor):
            return float(el.value_f)
        if isinstance(el, NonIdealInductor):
            return float(el.value_h)
        if isinstance(el, IdealResistor):
            return float(el.value_ohm)
        if isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            if part == "L":
                return float(el.value_h)
            if part == "C":
                return float(el.value_f)
            raise ValueError("edit resonator as Xn.L or Xn.C")
        if isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            if part == "Ls":
                return float(el.series_l_h)
            if part == "Cs":
                return float(el.series_c_f)
            if part == "Lp":
                return float(el.parallel_l_h)
            if part == "Cp":
                return float(el.parallel_c_f)
            raise ValueError("edit Brune arm as Xn.Ls / .Cs / .Lp / .Cp")
    raise KeyError(element_id)


def default_milestone_spec() -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.HIGH_PASS,
        order=7,
        cutoff_hz=140e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_HP_SERIES_C_INPUT,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.01,
    )


def default_sweep_for_spec(spec: FilterSpec, n_points: int = 1024) -> SweepConfig:
    if spec.response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        assert spec.f_center_hz is not None
        fc = spec.f_center_hz
    else:
        fc = spec.cutoff_hz
    return SweepConfig(
        f_start_hz=fc / 20.0,
        f_stop_hz=fc * 20.0,
        n_points=n_points,
        spacing=SweepSpacing.LOGARITHMIC,
    )


@dataclass(slots=True)
class DesignSession:
    """Mutable session state used by the GUI and CLI."""

    spec: FilterSpec = field(default_factory=default_milestone_spec)
    sweep: SweepConfig | None = None
    prototype: Prototype | None = None
    circuit: Circuit | None = None
    analysis: AnalysisResult | None = None
    backend: str = "abcd"
    dirty: bool = False
    path: str | None = None
    title: str = DEFAULT_TITLE
    markers: list[Marker] = field(default_factory=list)
    limits: list[LimitRegion] = field(default_factory=list)
    measured: AnalysisResult | None = None
    measured_name: str | None = None
    element_steps: dict[str, float] = field(default_factory=dict)
    element_tolerances: dict[str, ElementTolerance] = field(default_factory=dict)
    power_w: float = 0.0
    harmonics_f0_hz: float | None = None

    DEFAULT_TUNE_STEP = 0.02

    def __post_init__(self) -> None:
        if self.sweep is None:
            self.sweep = default_sweep_for_spec(self.spec)

    def set_spec(self, spec: FilterSpec) -> None:
        validate_spec(spec)
        self.spec = spec
        self.dirty = True

    def synthesize(self) -> None:
        result = synthesize(self.spec)
        self.prototype = result.prototype
        self.circuit = result.circuit
        self.analysis = None
        self.dirty = True

    def analyze(self) -> AnalysisResult:
        if self.circuit is None:
            self.synthesize()
        assert self.circuit is not None
        assert self.sweep is not None
        self.analysis = analyze_circuit(
            self.circuit, self.sweep, backend=self.backend
        )
        return self.analysis

    def synthesize_and_analyze(self) -> AnalysisResult:
        self.synthesize()
        return self.analyze()

    def retune(self, request: RetuneRequest) -> None:
        """Redesign the current spec with overridden fields and re-synthesize."""
        self.set_spec(retune_spec(self.spec, request))
        self.synthesize()

    def scale_response(self, factor: float) -> None:
        """Scale all frequency landmarks by ``factor`` and re-synthesize."""
        self.set_spec(_scale_spec_response(self.spec, factor))
        self.synthesize()

    def optimize(
        self, config: OptimizationConfig | None = None
    ) -> OptimizationResult:
        """Tune component values to minimise limit violations (no mutation)."""
        if self.circuit is None or self.sweep is None:
            raise ValueError("no circuit/sweep")
        return optimize_circuit(self.circuit, self.sweep, self.limits, config)

    def step_fraction(self, element_id: str) -> float:
        """Per-part relative tune step (falls back to ``DEFAULT_TUNE_STEP``)."""
        default = self.DEFAULT_TUNE_STEP
        return self.element_steps.get(_base_element_id(element_id), default)

    def set_element_step(self, element_id: str, fraction: float) -> None:
        if fraction <= 0.0:
            raise ValueError("tune step must be > 0")
        self.element_steps[_base_element_id(element_id)] = float(fraction)
        self.dirty = True

    def nudged_value(self, element_id: str, direction: int) -> float:
        """Value after one multiplicative tune step (no mutation)."""
        value = self.lookup_element_value(element_id)
        return nudge_value(value, self.step_fraction(element_id), direction)

    def nudge_element(self, element_id: str, direction: int) -> float:
        """Apply one tune step in place and return the new value."""
        new_value = self.nudged_value(element_id, direction)
        self.update_element_value(element_id, new_value)
        return new_value

    def update_element_value(self, element_id: str, value_si: float) -> None:
        if self.circuit is None:
            raise ValueError("no circuit")
        if value_si <= 0.0:
            raise ValueError("component value must be > 0")
        # Resonator / Brune parts: X1.L, X1.C, X1.Ls, …
        target_id = element_id
        part: str | None = None
        for suffix in (".Ls", ".Cs", ".Lp", ".Cp", ".L", ".C"):
            if element_id.endswith(suffix):
                target_id = element_id[: -len(suffix)]
                part = suffix[1:]
                break

        new_elements: list[Element] = []
        found = False
        for el in self.circuit.elements:
            if el.id != target_id:
                new_elements.append(el)
                continue
            found = True
            if isinstance(el, IdealCapacitor):
                new_elements.append(
                    IdealCapacitor(
                        id=el.id,
                        value_f=value_si,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                    )
                )
            elif isinstance(el, IdealInductor):
                new_elements.append(
                    IdealInductor(
                        id=el.id,
                        value_h=value_si,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                    )
                )
            elif isinstance(el, IdealSeriesLC):
                l_h = value_si if part == "L" else el.value_h
                c_f = value_si if part == "C" else el.value_f
                if part is None:
                    raise ValueError("edit resonator as Xn.L or Xn.C")
                new_elements.append(
                    IdealSeriesLC(
                        id=el.id,
                        value_h=l_h,
                        value_f=c_f,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                    )
                )
            elif isinstance(el, IdealParallelLC):
                l_h = value_si if part == "L" else el.value_h
                c_f = value_si if part == "C" else el.value_f
                if part is None:
                    raise ValueError("edit resonator as Xn.L or Xn.C")
                new_elements.append(
                    IdealParallelLC(
                        id=el.id,
                        value_h=l_h,
                        value_f=c_f,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                    )
                )
            elif isinstance(el, NonIdealCapacitor):
                new_elements.append(
                    NonIdealCapacitor(
                        id=el.id,
                        value_f=value_si,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        esr_ohm=el.esr_ohm,
                        esl_h=el.esl_h,
                        g=el.g,
                    )
                )
            elif isinstance(el, NonIdealInductor):
                new_elements.append(
                    NonIdealInductor(
                        id=el.id,
                        value_h=value_si,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        series_resistance_ohm=el.series_resistance_ohm,
                        parallel_capacitance_f=el.parallel_capacitance_f,
                        g=el.g,
                    )
                )
            elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
                if part not in {"Ls", "Cs", "Lp", "Cp"}:
                    raise ValueError("edit Brune arm as Xn.Ls / .Cs / .Lp / .Cp")
                kwargs = {
                    "series_l_h": el.series_l_h,
                    "series_c_f": el.series_c_f,
                    "parallel_l_h": el.parallel_l_h,
                    "parallel_c_f": el.parallel_c_f,
                }
                key = {
                    "Ls": "series_l_h",
                    "Cs": "series_c_f",
                    "Lp": "parallel_l_h",
                    "Cp": "parallel_c_f",
                }[part]
                kwargs[key] = value_si
                cls = IdealBruneLC if isinstance(el, IdealBruneLC) else IdealDualBruneLC
                new_elements.append(
                    cls(
                        id=el.id,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                        **kwargs,
                    )
                )
            else:
                new_elements.append(
                    IdealResistor(
                        id=el.id,
                        value_ohm=value_si,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                    )
                )
        if not found:
            raise KeyError(element_id)
        self.circuit.elements = new_elements
        self.analysis = None
        self.dirty = True

    def lookup_element_value(self, element_id: str) -> float:
        if self.circuit is None:
            raise ValueError("no circuit")
        return _element_value_si(self.circuit, element_id)

    def replace_circuit(self, circuit: Circuit) -> None:
        """Swap in a topologically edited circuit and invalidate analysis."""
        self.circuit = circuit
        self.analysis = None
        self.dirty = True

    def snap_components(
        self,
        series: ESeries | str = ESeries.E24,
        strategy: SnapStrategy | str = SnapStrategy.INDEPENDENT,
    ) -> SnapReport:
        """Snap the current circuit's values to an E-series and invalidate analysis."""
        if self.circuit is None:
            raise ValueError("no circuit")
        snapped, report = snap_circuit(self.circuit, series, strategy)
        self.replace_circuit(snapped)
        return report

    def apply_nonideal(
        self,
        *,
        inductor_q: float | None = None,
        q_frequency_hz: float | None = None,
        inductor_dcr_ohm: float = 0.0,
        inductor_parallel_capacitance_f: float = 0.0,
        capacitor_esr_ohm: float = 0.0,
        capacitor_esl_h: float = 0.0,
    ) -> Circuit:
        """Replace inductors/capacitors with lossy/parasitic models; re-invalidate."""
        if self.circuit is None:
            raise ValueError("no circuit")
        lossy = nonidealize_circuit(
            self.circuit,
            inductor_q=inductor_q,
            q_frequency_hz=q_frequency_hz,
            inductor_dcr_ohm=inductor_dcr_ohm,
            inductor_parallel_capacitance_f=inductor_parallel_capacitance_f,
            capacitor_esr_ohm=capacitor_esr_ohm,
            capacitor_esl_h=capacitor_esl_h,
        )
        self.replace_circuit(lossy)
        return lossy

    def monte_carlo(
        self,
        config: MonteCarloConfig,
        *,
        limits: list[LimitRegion] | None = None,
    ) -> MonteCarloResult:
        """Tolerance-sweep the current circuit/sweep (defaults to session limits)."""
        if self.circuit is None or self.sweep is None:
            raise ValueError("no circuit/sweep")
        merged = {**self.element_tolerances, **config.overrides}
        return run_monte_carlo(
            self.circuit,
            self.sweep,
            replace(config, overrides=merged),
            limits=self.limits if limits is None else limits,
        )

    def element_tolerance(self, ref: str) -> ElementTolerance | None:
        """Per-component tolerance override, if any."""
        return self.element_tolerances.get(ref)

    def set_element_tolerance(
        self,
        ref: str,
        tolerance_pct: float,
        distribution: ToleranceDistribution | None = None,
    ) -> None:
        self.element_tolerances[ref] = ElementTolerance(tolerance_pct, distribution)
        self.dirty = True

    def clear_element_tolerance(self, ref: str) -> None:
        if ref in self.element_tolerances:
            del self.element_tolerances[ref]
            self.dirty = True

    def stress_frequency_hz(self) -> float | None:
        """Reference frequency for the power-stress estimate (band landmark)."""
        if self.spec.response in (
            FilterResponse.BAND_PASS,
            FilterResponse.BAND_STOP,
        ):
            return self.spec.f_center_hz
        cutoff = self.spec.cutoff_hz
        return cutoff if cutoff > 0.0 else None

    def compute_stress(self) -> StressReport | None:
        """Per-element peak V/I at the reference frequency, or ``None`` (power off)."""
        if self.power_w <= 0.0 or self.circuit is None:
            return None
        frequency = self.stress_frequency_hz()
        if frequency is None or frequency <= 0.0:
            return None
        try:
            return compute_stress(
                self.circuit, power_w=self.power_w, frequency_hz=frequency
            )
        except StressError:
            return None

    def harmonics_reference_hz(self) -> float | None:
        """Fundamental for the harmonic readout (explicit, else band landmark)."""
        if self.harmonics_f0_hz is not None and self.harmonics_f0_hz > 0.0:
            return self.harmonics_f0_hz
        return self.stress_frequency_hz()

    def compute_harmonics(self) -> HarmonicReport | None:
        """Harmonic |S21|/suppression from the current analysis, or ``None``."""
        if self.analysis is None:
            return None
        fundamental = self.harmonics_reference_hz()
        if fundamental is None or fundamental <= 0.0:
            return None
        try:
            return compute_harmonics(self.analysis, fundamental)
        except HarmonicError:
            return None

    def insert_arm(
        self,
        *,
        role: ElementRole,
        kind: str,
        value_si: float,
        before_id: str | None = None,
    ) -> None:
        if self.circuit is None:
            raise ValueError("no circuit")
        self.replace_circuit(
            circuit_edit.insert_simple_arm(
                self.circuit,
                role=role,
                kind=kind,
                value_si=value_si,
                before_id=before_id,
            )
        )

    def delete_arm(self, element_id: str) -> None:
        if self.circuit is None:
            raise ValueError("no circuit")
        self.replace_circuit(circuit_edit.delete_arm(self.circuit, element_id))

    def change_arm_type(self, element_id: str, target_kind: str) -> None:
        if self.circuit is None:
            raise ValueError("no circuit")
        reference_hz = circuit_edit.reference_frequency_hz(self.circuit)
        if reference_hz is None:
            raise ValueError("circuit has no reference frequency for conversion")
        self.replace_circuit(
            circuit_edit.convert_simple_arm(
                self.circuit, element_id, target_kind, reference_hz
            )
        )

    def set_markers(self, markers: list[Marker]) -> None:
        if len(markers) > MAX_MARKERS:
            raise ValueError(f"at most {MAX_MARKERS} markers")
        self.markers = list(markers)
        self.dirty = True

    def set_limits(self, limits: list[LimitRegion]) -> None:
        if len(limits) > MAX_LIMITS:
            raise ValueError(f"at most {MAX_LIMITS} limits")
        self.limits = list(limits)
        self.dirty = True

    def set_measured(self, result: AnalysisResult | None, name: str = "") -> None:
        """Store imported measured data (Touchstone) for compare/overlay."""
        self.measured = result
        self.measured_name = (name or None) if result is not None else None

    def to_project(self) -> Project:
        assert self.sweep is not None
        extensions: dict[str, object] = {}
        if self.markers:
            extensions["markers"] = markers_to_mapping(self.markers)
        if self.limits:
            extensions["limits"] = limits_to_mapping(self.limits)
        if self.element_steps:
            extensions["element_steps"] = dict(self.element_steps)
        if self.element_tolerances:
            extensions["element_tolerances"] = {
                ref: {
                    "tolerance_pct": tol.tolerance_pct,
                    "distribution": (
                        tol.distribution.value if tol.distribution is not None else None
                    ),
                }
                for ref, tol in self.element_tolerances.items()
            }
        if self.power_w > 0.0:
            extensions["power_w"] = float(self.power_w)
        if self.harmonics_f0_hz is not None:
            extensions["harmonics_f0_hz"] = float(self.harmonics_f0_hz)
        return Project(
            specification=self.spec,
            circuit=self.circuit,
            sweep=self.sweep,
            metadata=ProjectMetadata(
                title=self.title,
                app_version=__version__,
            ),
            extensions=extensions,
        )

    def load_project(self, project: Project, path: str | None = None) -> None:
        if project.specification is None:
            raise ValueError("project has no specification")
        self.spec = project.specification
        self.circuit = project.circuit
        self.prototype = None
        self.analysis = None
        self.sweep = project.sweep or default_sweep_for_spec(self.spec)
        self.title = project.metadata.title or DEFAULT_TITLE
        if self.title in _LEGACY_TITLES:
            self.title = DEFAULT_TITLE
        self.path = path
        self.dirty = False
        ext = project.extensions or {}
        raw_m = ext.get("markers")
        raw_l = ext.get("limits")
        self.markers = (
            markers_from_mapping(list(raw_m)) if isinstance(raw_m, list) else []
        )
        self.limits = (
            limits_from_mapping(list(raw_l)) if isinstance(raw_l, list) else []
        )
        self.element_steps = self._steps_from_ext(ext.get("element_steps"))
        self.element_tolerances = self._tolerances_from_ext(
            ext.get("element_tolerances")
        )
        raw_power = ext.get("power_w")
        self.power_w = (
            float(raw_power) if isinstance(raw_power, (int, float)) else 0.0
        )
        raw_f0 = ext.get("harmonics_f0_hz")
        self.harmonics_f0_hz = (
            float(raw_f0) if isinstance(raw_f0, (int, float)) else None
        )
        if self.circuit is None:
            self.synthesize()

    @staticmethod
    def _steps_from_ext(raw: object) -> dict[str, float]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for ref, value in raw.items():
            if isinstance(value, (int, float)):
                out[str(ref)] = float(value)
        return out

    @staticmethod
    def _tolerances_from_ext(raw: object) -> dict[str, ElementTolerance]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, ElementTolerance] = {}
        for ref, value in raw.items():
            if not isinstance(value, dict):
                continue
            dist_raw = value.get("distribution")
            try:
                out[str(ref)] = ElementTolerance(
                    float(value.get("tolerance_pct", 0.0)),
                    ToleranceDistribution(str(dist_raw)) if dist_raw else None,
                )
            except (ValueError, TypeError):
                continue
        return out

    def summary_metrics(self) -> dict[str, float]:
        if self.analysis is None:
            raise ValueError("no analysis")
        s21 = mag_db(self.analysis.s21)
        s11 = mag_db(self.analysis.s11)
        return {
            "s21_db_min": float(s21.min()),
            "s21_db_max": float(s21.max()),
            "s11_db_min": float(s11.min()),
            "s11_db_max": float(s11.max()),
        }
