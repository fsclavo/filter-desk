"""Apply assigned library-part values/parasitics to system circuits."""

from __future__ import annotations

from dataclasses import dataclass, replace

from filterdesk.components_std import (
    LibraryPart,
    inductor_resistance_ohm_from_q,
    set_element_parasitics,
)
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
    physical_components,
)
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign
from filterdesk.services.system_rebuild import SystemDesign, rebuild_system_design


class PartApplicationError(ValueError):
    """Raised when assigned parts cannot be applied."""


@dataclass(frozen=True, slots=True)
class PartApplicationResult:
    design: SystemDesign
    applied: tuple[str, ...]
    warnings: tuple[str, ...]


def apply_assigned_parts(
    design: SystemDesign,
    assignments: dict[str, LibraryPart],
) -> PartApplicationResult:
    """Apply assigned part values and available parasitics, then reanalyze.

    Simple L/C elements and series/parallel LC resonators receive value +
    DCR/SRF or ESR/ESL when available. Brune/dual-Brune arms receive the
    sub-part value but no parasitic model yet; that limitation is reported in
    ``warnings``.
    """
    if not assignments:
        raise PartApplicationError("no assigned parts to apply")
    branches = _branches(design)
    by_label = {label: circuit for label, circuit in branches}
    applied: list[str] = []
    warnings: list[str] = []
    changed: dict[str, Circuit] = {}
    for key, part in assignments.items():
        if ":" not in key:
            warnings.append(f"{key}: invalid assignment key")
            continue
        label, ref = key.split(":", 1)
        circuit = changed.get(label, by_label.get(label))
        if circuit is None:
            warnings.append(f"{key}: unknown branch")
            continue
        try:
            new_circuit, notes = _apply_part(circuit, ref, part)
        except (KeyError, ValueError) as exc:
            warnings.append(f"{key}: {exc}")
            continue
        changed[label] = new_circuit
        applied.append(key)
        warnings.extend(notes)
    if not applied:
        raise PartApplicationError("no assigned parts could be applied")
    circuits = tuple(changed.get(label, circuit) for label, circuit in branches)
    return PartApplicationResult(
        design=rebuild_system_design(design, circuits),
        applied=tuple(applied),
        warnings=tuple(warnings),
    )


def _apply_part(
    circuit: Circuit, ref: str, part: LibraryPart
) -> tuple[Circuit, list[str]]:
    target = next(
        (item for item in physical_components(circuit) if item.ref == ref), None
    )
    if target is None:
        raise KeyError(f"unknown component {ref}")
    if target.kind != part.kind:
        raise ValueError(
            f"part kind {part.kind!r} does not match component kind {target.kind!r}"
        )
    element_id = target.element_id
    suffix = ref[len(element_id) :]
    new_elements: list[Element] = list(circuit.elements)
    warnings: list[str] = []
    for index, element in enumerate(new_elements):
        if element.id != element_id:
            continue
        if suffix:
            new_elements[index] = _replace_composite_value(element, suffix, part)
            if not isinstance(element, (IdealSeriesLC, IdealParallelLC)):
                warnings.append(
                    f"{ref}: composite parasitic model not applied (value only)"
                )
            elif part.model is not None and part.model.has_curve:
                warnings.append(
                    f"{ref}: manufacturer Q/ESR curve not applied to a composite "
                    "resonator; constant DCR/ESR used"
                )
        elif isinstance(element, (IdealInductor, NonIdealInductor)):
            new_elements[index] = replace(element, value_h=part.value_si)
        elif isinstance(element, (IdealCapacitor, NonIdealCapacitor)):
            new_elements[index] = replace(element, value_f=part.value_si)
        else:
            raise ValueError(f"{ref} is not an L/C component")
        break
    else:
        raise KeyError(f"unknown element {element_id}")
    updated = replace(circuit, elements=new_elements)
    if suffix:
        return updated, warnings
    if part.kind == "inductor":
        dcr = part.dcr_ohm
        q_ref = part.q_min if dcr is None else None
        q_frequency = 250e6 if q_ref is not None else None
        q_curve = (
            ()
            if part.model is None
            else tuple(
                (point.frequency_hz, point.value)
                for point in part.model.q_points
            )
        )
        if (
            dcr is not None
            or part.srf_hz is not None
            or q_ref is not None
            or q_curve
        ):
            updated = set_element_parasitics(
                updated,
                element_id,
                series_resistance_ohm=dcr,
                q_ref=q_ref,
                q_frequency_hz=q_frequency,
                srf_hz=part.srf_hz,
                q_curve=q_curve or None,
            )
    elif part.kind == "capacitor":
        esr_curve = (
            ()
            if part.model is None
            else tuple(
                (point.frequency_hz, point.value)
                for point in part.model.esr_points
            )
        )
        if part.esr_ohm is not None or part.esl_h is not None or esr_curve:
            updated = set_element_parasitics(
                updated,
                element_id,
                esr_ohm=part.esr_ohm,
                esl_h=part.esl_h,
                esr_curve=esr_curve or None,
            )
    return updated, warnings


def _replace_composite_value(
    element: Element, suffix: str, part: LibraryPart
) -> Element:
    if isinstance(element, (IdealSeriesLC, IdealParallelLC)):
        if suffix == ".L" and part.kind == "inductor":
            resistance = part.dcr_ohm or 0.0
            if resistance == 0.0 and part.q_min is not None:
                resistance = inductor_resistance_ohm_from_q(
                    part.value_si, part.q_min, 250e6
                )
            return replace(
                element,
                value_h=part.value_si,
                l_series_resistance_ohm=resistance,
                l_srf_hz=part.srf_hz,
            )
        if suffix == ".C" and part.kind == "capacitor":
            return replace(
                element,
                value_f=part.value_si,
                c_esr_ohm=part.esr_ohm or 0.0,
                c_esl_h=part.esl_h or 0.0,
            )
    if isinstance(element, (IdealBruneLC, IdealDualBruneLC)):
        if suffix == ".Ls" and part.kind == "inductor":
            return replace(element, series_l_h=part.value_si)
        if suffix == ".Cs" and part.kind == "capacitor":
            return replace(element, series_c_f=part.value_si)
        if suffix == ".Lp" and part.kind == "inductor":
            return replace(element, parallel_l_h=part.value_si)
        if suffix == ".Cp" and part.kind == "capacitor":
            return replace(element, parallel_c_f=part.value_si)
    raise ValueError(f"unsupported composite part {suffix}")


def _branches(design: SystemDesign) -> list[tuple[str, Circuit]]:
    if isinstance(design, MultiplexerDesign):
        return [
            (band.label.capitalize(), circuit)
            for band, circuit in zip(design.bands, design.circuits, strict=True)
        ]
    if isinstance(design, DuplexerDesign):
        return [("TX", design.tx_circuit), ("RX", design.rx_circuit)]
    return [("Low", design.low_circuit), ("High", design.high_circuit)]


__all__ = [
    "PartApplicationError",
    "PartApplicationResult",
    "apply_assigned_parts",
]
