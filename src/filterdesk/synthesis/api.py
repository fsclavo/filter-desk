"""Public synthesis API."""

from __future__ import annotations

from dataclasses import dataclass

from filterdesk.domain.circuit import Circuit
from filterdesk.domain.prototype import Prototype
from filterdesk.domain.specs import FilterSpec, validate_spec
from filterdesk.synthesis.families import synthesize_prototype
from filterdesk.synthesis.realize import realize_ladder


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    spec: FilterSpec
    prototype: Prototype
    circuit: Circuit


def synthesize(spec: FilterSpec) -> SynthesisResult:
    """Synthesize a passive ladder filter from a validated specification."""
    validate_spec(spec)
    prototype = synthesize_prototype(spec)
    circuit = realize_ladder(spec, prototype)
    return SynthesisResult(spec=spec, prototype=prototype, circuit=circuit)
