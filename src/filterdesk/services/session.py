"""Design session — GUI-independent application state."""

from __future__ import annotations

from dataclasses import dataclass, field

from filterdesk import __version__
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
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
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
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
from filterdesk.synthesis import synthesize


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
    title: str = "Milestone Chebyshev HP"
    markers: list[Marker] = field(default_factory=list)
    limits: list[LimitRegion] = field(default_factory=list)

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

    def to_project(self) -> Project:
        assert self.sweep is not None
        extensions: dict[str, object] = {}
        if self.markers:
            extensions["markers"] = markers_to_mapping(self.markers)
        if self.limits:
            extensions["limits"] = limits_to_mapping(self.limits)
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
        self.title = project.metadata.title or "Untitled"
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
        if self.circuit is None:
            self.synthesize()

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
