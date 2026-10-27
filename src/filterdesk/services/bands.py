"""Amateur-band presets (Phase 12).

Quick design recipes for the common HF/VHF bands: a :class:`Band` carries the
approximate allocation, and :func:`band_preset_spec` turns a band + a filter kind
into a ready-to-synthesize :class:`FilterSpec` (Chebyshev Type I, 0.1 dB ripple).
Frequencies are approximate and meant as starting points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
)
from filterdesk.domain.specs import FilterSpec, default_topology


class BandKind(StrEnum):
    LPF = "lpf"
    HPF = "hpf"
    BPF = "bpf"
    BSF = "bsf"


@dataclass(frozen=True, slots=True)
class Band:
    name: str
    low_hz: float
    high_hz: float

    @property
    def center_hz(self) -> float:
        return math.sqrt(self.low_hz * self.high_hz)


#: Approximate amateur allocations (Hz), IARU region-agnostic common ranges.
BANDS: tuple[Band, ...] = (
    Band("160 m", 1.8e6, 2.0e6),
    Band("80 m", 3.5e6, 4.0e6),
    Band("60 m", 5.3e6, 5.4e6),
    Band("40 m", 7.0e6, 7.3e6),
    Band("30 m", 10.1e6, 10.15e6),
    Band("20 m", 14.0e6, 14.35e6),
    Band("17 m", 18.068e6, 18.168e6),
    Band("15 m", 21.0e6, 21.45e6),
    Band("12 m", 24.89e6, 24.99e6),
    Band("10 m", 28.0e6, 29.7e6),
    Band("6 m", 50.0e6, 54.0e6),
)

#: Broadcast bands commonly notched out (band-stop presets).
REJECTION_PRESETS: tuple[Band, ...] = (
    Band("AM broadcast", 530e3, 1710e3),
    Band("FM broadcast", 88e6, 108e6),
)

#: Every preset offered in the GUI/CLI band selector.
ALL_PRESETS: tuple[Band, ...] = BANDS + REJECTION_PRESETS

_BAND_ALIASES: dict[str, str] = {
    "am": "AM broadcast",
    "am broadcast": "AM broadcast",
    "mw": "AM broadcast",
    "fm": "FM broadcast",
    "fm broadcast": "FM broadcast",
}


def find_band(name: str) -> Band:
    """Look up a band; accepts ``40``, ``40m``, ``am``, ``fm``, ``AM broadcast``…"""
    raw = name.strip()
    alias = _BAND_ALIASES.get(raw.lower().replace("  ", " "))
    if alias is not None:
        for band in REJECTION_PRESETS:
            if band.name == alias:
                return band
    key = raw.lower().replace(" ", "")
    if key.endswith("m"):
        key = key[:-1]
    for band in ALL_PRESETS:
        if band.name.lower().replace(" ", "").rstrip("m") == key:
            return band
    raise KeyError(f"unknown band preset: {name!r}")


def band_preset_spec(band: Band, kind: BandKind = BandKind.LPF) -> FilterSpec:
    """Build a Chebyshev-I spec for ``band`` as an LPF/HPF/BPF preset."""
    response_map = {
        BandKind.LPF: FilterResponse.LOW_PASS,
        BandKind.HPF: FilterResponse.HIGH_PASS,
        BandKind.BPF: FilterResponse.BAND_PASS,
        BandKind.BSF: FilterResponse.BAND_STOP,
    }
    response = response_map[kind]
    common: dict[str, object] = {
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "response": response,
        "z_source_ohm": 50.0,
        "z_load_ohm": 50.0,
        "topology_id": default_topology(response),
        "cutoff_definition": CutoffDefinition.RIPPLE_EDGE,
        "passband_ripple_db": 0.1,
    }
    if kind == BandKind.LPF:
        common["order"] = 5
        common["cutoff_hz"] = band.high_hz * 1.1
    elif kind == BandKind.HPF:
        common["order"] = 5
        common["cutoff_hz"] = band.low_hz * 0.9
    else:
        # Odd order keeps both terminations equal (50 Ω); even-order
        # Chebyshev-I would require the ideal output transformer T1.
        common["order"] = 5
        common["f_center_hz"] = band.center_hz
        common["bandwidth_hz"] = (band.high_hz - band.low_hz) * 1.5
    return FilterSpec(**common)  # type: ignore[arg-type]


def band_sweep(band: Band) -> SweepConfig:
    """A sweep that covers the band and its 3rd harmonic (for TX LPFs)."""
    return SweepConfig(
        f_start_hz=band.low_hz * 0.5,
        f_stop_hz=band.high_hz * 5.0,
        n_points=1024,
        spacing=SweepSpacing.LOGARITHMIC,
    )


__all__ = [
    "ALL_PRESETS",
    "BANDS",
    "REJECTION_PRESETS",
    "Band",
    "BandKind",
    "band_preset_spec",
    "band_sweep",
    "find_band",
]
