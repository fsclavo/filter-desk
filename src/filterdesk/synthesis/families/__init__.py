"""Approximation family registry helpers."""

from __future__ import annotations

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype
from filterdesk.domain.specs import FilterSpec, SpecValidationError
from filterdesk.synthesis.families.bessel import synthesize_bessel_prototype
from filterdesk.synthesis.families.butterworth import synthesize_butterworth_prototype
from filterdesk.synthesis.families.chebyshev_i import synthesize_chebyshev_i_prototype
from filterdesk.synthesis.families.chebyshev_ii import (
    synthesize_chebyshev_ii_prototype,
)
from filterdesk.synthesis.families.constant_k import synthesize_constant_k_prototype
from filterdesk.synthesis.families.elliptic import synthesize_elliptic_prototype
from filterdesk.synthesis.families.gaussian import synthesize_gaussian_prototype
from filterdesk.synthesis.families.legendre import synthesize_legendre_prototype
from filterdesk.synthesis.families.m_derived import synthesize_m_derived_prototype


def synthesize_prototype(spec: FilterSpec) -> Prototype:
    if spec.family == ApproximationFamily.BUTTERWORTH:
        return synthesize_butterworth_prototype(spec.order)
    if spec.family == ApproximationFamily.CHEBYSHEV_TYPE_I:
        assert spec.passband_ripple_db is not None
        return synthesize_chebyshev_i_prototype(spec.order, spec.passband_ripple_db)
    if spec.family == ApproximationFamily.BESSEL:
        return synthesize_bessel_prototype(spec.order)
    if spec.family == ApproximationFamily.GAUSSIAN:
        return synthesize_gaussian_prototype(spec.order)
    if spec.family == ApproximationFamily.LEGENDRE:
        return synthesize_legendre_prototype(spec.order)
    if spec.family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        assert spec.stopband_attenuation_db is not None
        return synthesize_chebyshev_ii_prototype(
            spec.order, spec.stopband_attenuation_db
        )
    if spec.family == ApproximationFamily.ELLIPTIC:
        assert spec.passband_ripple_db is not None
        assert spec.stopband_attenuation_db is not None
        return synthesize_elliptic_prototype(
            spec.order, spec.passband_ripple_db, spec.stopband_attenuation_db
        )
    if spec.family == ApproximationFamily.CONSTANT_K:
        return synthesize_constant_k_prototype(spec.order)
    if spec.family == ApproximationFamily.M_DERIVED:
        assert spec.m_parameter is not None
        return synthesize_m_derived_prototype(spec.order, spec.m_parameter)
    raise SpecValidationError(f"unsupported family: {spec.family}")
