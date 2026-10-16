"""Default file names derived from a filter specification (UX helper).

Builds a compact, filesystem-safe stem from family / response type / order /
frequency so the first save (and export defaults) suggest a meaningful name such
as ``cheby1_lpf_n7_140MHz.filterdesk.json``.
"""

from __future__ import annotations

import re

from filterdesk.domain.enums import ApproximationFamily, FilterResponse
from filterdesk.domain.specs import FilterSpec
from filterdesk.domain.units import format_engineering

_FAMILY_SHORT: dict[ApproximationFamily, str] = {
    ApproximationFamily.BUTTERWORTH: "butterworth",
    ApproximationFamily.CHEBYSHEV_TYPE_I: "cheby1",
    ApproximationFamily.CHEBYSHEV_TYPE_II: "cheby2",
    ApproximationFamily.ELLIPTIC: "elliptic",
    ApproximationFamily.BESSEL: "bessel",
    ApproximationFamily.GAUSSIAN: "gaussian",
    ApproximationFamily.LEGENDRE: "legendre",
    ApproximationFamily.CONSTANT_K: "constk",
    ApproximationFamily.M_DERIVED: "mderived",
}

_RESPONSE_TAG: dict[FilterResponse, str] = {
    FilterResponse.LOW_PASS: "LPF",
    FilterResponse.HIGH_PASS: "HPF",
    FilterResponse.BAND_PASS: "BPF",
    FilterResponse.BAND_STOP: "BSF",
}

_UNSAFE = re.compile(r"[^A-Za-z0-9_.+-]+")


def _hz(value: float | None) -> str:
    if not value or value <= 0.0:
        return ""
    return format_engineering(float(value), "Hz", digits=6).replace(" ", "")


def default_stem(spec: FilterSpec) -> str:
    """Compact filename stem: ``<family>_<type>_n<order>_<freq>[_bw<bw>]``."""
    parts: list[str] = [
        _FAMILY_SHORT.get(spec.family, spec.family.value),
        _RESPONSE_TAG.get(spec.response, spec.response.value.upper()),
        f"n{spec.order}",
    ]
    if spec.response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        center = _hz(spec.f_center_hz)
        if center:
            parts.append(center)
        bandwidth = _hz(spec.bandwidth_hz)
        if bandwidth:
            parts.append(f"bw{bandwidth}")
    else:
        cutoff = _hz(spec.cutoff_hz)
        if cutoff:
            parts.append(cutoff)
    return _UNSAFE.sub("_", "_".join(part for part in parts if part))


def default_filename(spec: FilterSpec, *, suffix: str = ".filterdesk.json") -> str:
    """Default file name (stem + suffix) for the given specification."""
    return f"{default_stem(spec)}{suffix}"
