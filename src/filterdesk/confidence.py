"""Model-confidence registry and build-sheet assumptions.

The registry makes the difference between validated, cross-checked, estimated,
experimental and not-evaluated behaviour explicit. It is intentionally central:
the GUI, manual and build sheets should not invent their own confidence labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from filterdesk.domain.circuit import (
    Circuit,
    MicrostripLineElement,
    MicrostripStubElement,
    NonIdealCapacitor,
    NonIdealInductor,
)


class ConfidenceLevel(StrEnum):
    IDEAL = "ideal"
    VALIDATED = "validated"
    CROSS_CHECKED = "cross-checked"
    ESTIMATED = "estimated"
    EXPERIMENTAL = "experimental"
    NOT_EVALUATED = "not evaluated"


@dataclass(frozen=True, slots=True)
class ConfidenceItem:
    key: str
    area: str
    level: ConfidenceLevel
    evidence: str
    limits: str


ITEMS: tuple[ConfidenceItem, ...] = (
    ConfidenceItem(
        "filter_synthesis",
        "Filter synthesis",
        ConfidenceLevel.VALIDATED,
        "Golden component/metric cases and classical prototype checks.",
        "Even-order elliptic is rejected; order caps apply to some families.",
    ),
    ConfidenceItem(
        "filter_analysis",
        "Filter analysis",
        ConfidenceLevel.CROSS_CHECKED,
        "ABCD ladder cross-checked against scikit-rf and analytic circuits.",
        "Ideal ladders unless parasitics are applied; no distributed elements.",
    ),
    ConfidenceItem(
        "filter_components",
        "Filter components",
        ConfidenceLevel.IDEAL,
        "Ideal R/L/C values in the working circuit.",
        "Apply parasitics/Q/tolerances for an estimated real-component model.",
    ),
    ConfidenceItem(
        "synthesis",
        "Lumped LC synthesis",
        ConfidenceLevel.VALIDATED,
        "Golden component/metric cases and classical prototype checks.",
        "Even-order elliptic is rejected; order caps apply to some families.",
    ),
    ConfidenceItem(
        "abcd",
        "ABCD ladder analysis",
        ConfidenceLevel.CROSS_CHECKED,
        "Cross-checked against scikit-rf and analytic circuits.",
        "Ideal ladders unless parasitics are applied; no distributed elements.",
    ),
    ConfidenceItem(
        "skrf",
        "scikit-rf backend",
        ConfidenceLevel.CROSS_CHECKED,
        "Differential tests against the ABCD backend.",
        "Adapter backend, not the canonical domain model.",
    ),
    ConfidenceItem(
        "t1",
        "Output transformer T1",
        ConfidenceLevel.VALIDATED,
        "SPICE netlist validated with an independent MNA solver.",
        "LTspice/Qucs exports have not been verified in those tools.",
    ),
    ConfidenceItem(
        "chebyshev_even",
        "Even-order Chebyshev I",
        ConfidenceLevel.VALIDATED,
        "Classical g-values and output-transformer golden case.",
        "Uses an ideal output transformer; not a general unequal-R synthesis.",
    ),
    ConfidenceItem(
        "compliance",
        "Spec compliance",
        ConfidenceLevel.CROSS_CHECKED,
        "Exact band-edge evaluation and independent validation tests.",
        "Approximation notes are reported for non-classical cases.",
    ),
    ConfidenceItem(
        "optimization",
        "Limits optimization",
        ConfidenceLevel.ESTIMATED,
        "Deterministic/global solvers with bounded component values.",
        "Solution quality depends on limits, bounds and topology.",
    ),
    ConfidenceItem(
        "montecarlo",
        "Monte-Carlo tolerances",
        ConfidenceLevel.ESTIMATED,
        "Random tolerance trials with a reported envelope.",
        "Component distributions and parasitics must be supplied.",
    ),
    ConfidenceItem(
        "vna",
        "VNA-guided tuning",
        ConfidenceLevel.EXPERIMENTAL,
        "Synthetic phase/delay regressions; real captures are holdout only.",
        "Magnitude alone may not identify all components; calibration and "
        "reference plane matter.",
    ),
    ConfidenceItem(
        "thermal",
        "Ferrite core loss / temperature",
        ConfidenceLevel.ESTIMATED,
        "Fair-Rite complex-permeability data plus copper loss and natural convection.",
        "Low-flux μ'' data, matched sine assumption, no high-flux curves or "
        "thermal simulation.",
    ),
    ConfidenceItem(
        "balun_tlt",
        "Guanella/Ruthroff TLT",
        ConfidenceLevel.EXPERIMENTAL,
        "Integer 1:N² Guanella ratios use an explicit N-line network; 1:4 "
        "Ruthroff uses a bootstrap ABCD; mixed-mode is a block-diagonal 3-port "
        "boundary model.",
        "Cross-mode terms are zero by symmetry. Common-mode is a choke/center-tap "
        "estimate, not a full asymmetric 4-port/EM model; Ruthroff SPICE export "
        "is not implemented.",
    ),
    ConfidenceItem(
        "microstrip",
        "Microstrip/stub calculators",
        ConfidenceLevel.ESTIMATED,
        "Hammerstad-Jensen quasi-static synthesis and first-order loss.",
        "No thickness in Z0, discontinuities, radiation, dispersion or field solver.",
    ),
    ConfidenceItem(
        "toroid",
        "Toroid/air-coil calculators",
        ConfidenceLevel.ESTIMATED,
        "Catalog AL/dimensions, wire-fit and flux checks.",
        "AL batch spread, core loss and thermal derating require verification.",
    ),
    ConfidenceItem(
        "touchstone",
        "Touchstone import/export",
        ConfidenceLevel.CROSS_CHECKED,
        "Parser/writer round-trip and compare tests.",
        "Reference-plane and calibration metadata are not inferred.",
    ),
    ConfidenceItem(
        "spice_export",
        "SPICE/LTspice/Qucs export",
        ConfidenceLevel.CROSS_CHECKED,
        "SPICE/MNA validation and syntax tests, including lossless distributed "
        "line/stub T-elements.",
        "LTspice/Qucs graphical exports require a manual external check; "
        "distributed loss and dispersion are not exported.",
    ),
    ConfidenceItem(
        "distributed",
        "Distributed microstrip synthesis",
        ConfidenceLevel.EXPERIMENTAL,
        "Stepped-impedance LP conversion with ABCD/skrf cross-checks; orders "
        "4–5 add a bounded numerical fit against the lumped prototype.",
        "Low-pass, Butterworth/Chebyshev-I, order <= 5. Orders 4–5 are accepted "
        "only if the response gate passes and may require wide Z0 ranges. "
        "Kirschning-Jansen dispersion is included when substrate geometry is "
        "available; discontinuities, radiation, coupling and fabrication "
        "tolerances are not modeled. Verify the board with Touchstone/VNA.",
    ),
)

_BY_KEY = {item.key: item for item in ITEMS}


def confidence_for(key: str) -> ConfidenceItem:
    try:
        return _BY_KEY[key]
    except KeyError:
        raise KeyError(f"unknown confidence key: {key}") from None


def assumptions_for_circuit(circuit: Circuit) -> tuple[str, ...]:
    """User-facing assumptions for a build sheet/project export."""
    assumptions = [
        "ABCD analysis assumes ideal R/L/C elements unless parasitics are applied.",
        "The BOM value is the current project value; the nearest E-series value "
        "is a snap suggestion, not a purchasing commitment.",
    ]
    if circuit.output_transformer_ratio != 1.0:
        assumptions.append(
            "T1 is an ideal output transformer; its SPICE model is validated by MNA."
        )
    if circuit.output_balun is not None:
        balun = circuit.output_balun
        lines = balun.guanella_line_count
        model = (
            f"{lines}-line Guanella network"
            if lines is not None
            else "transformer + TEM-line"
        )
        assumptions.append(
            f"BAL1 is a {balun.kind} model ({balun.topology}, {model}); "
            "Ruthroff/common-mode behaviour is approximate."
        )
    if any(
        isinstance(el, (NonIdealInductor, NonIdealCapacitor)) for el in circuit.elements
    ):
        assumptions.append(
            "Parasitic values are user/model estimates unless measured data is "
            "supplied."
        )
    if any(
        isinstance(el, (MicrostripLineElement, MicrostripStubElement))
        for el in circuit.elements
    ):
        assumptions.append(
            "Distributed elements use an ideal TEM microstrip model; verify "
            "dispersion, discontinuities, radiation and fabrication tolerances "
            "on the physical board."
        )
    return tuple(assumptions)


def filter_confidence_items(circuit: Circuit) -> tuple[ConfidenceItem, ...]:
    """Contextual badges for the filter result strip."""
    items = [
        confidence_for("filter_synthesis"),
        confidence_for("filter_analysis"),
    ]
    nonideal = any(
        isinstance(el, (NonIdealInductor, NonIdealCapacitor)) for el in circuit.elements
    )
    if nonideal:
        items.append(
            ConfidenceItem(
                "filter_components",
                "Filter components",
                ConfidenceLevel.ESTIMATED,
                "Non-ideal/parasitic component model.",
                "Parasitic values are estimates unless measured data is supplied.",
            )
        )
    else:
        items.append(confidence_for("filter_components"))
    if circuit.output_transformer_ratio != 1.0:
        items.append(confidence_for("t1"))
    if circuit.output_balun is not None:
        items.append(confidence_for("balun_tlt"))
    if any(
        isinstance(el, (MicrostripLineElement, MicrostripStubElement))
        for el in circuit.elements
    ):
        items.append(confidence_for("distributed"))
    return tuple(items)


__all__ = [
    "ConfidenceItem",
    "ConfidenceLevel",
    "ITEMS",
    "assumptions_for_circuit",
    "confidence_for",
    "filter_confidence_items",
]
