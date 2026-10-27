"""Mixed-mode boundary model for baluns (input + differential/common outputs)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.adapters.abcd_ladder import abcd_to_s, balun_abcd
from filterdesk.domain.circuit import BalunSpec


class MixedModeError(ValueError):
    """Raised when a mixed-mode balun model cannot be built."""


@dataclass(frozen=True, slots=True)
class MixedModeResult:
    """Block-diagonal mixed-mode 3-port model.

    Port 1 is the unbalanced input; ``d`` is the differential output and ``c``
    the output common-mode port. Cross-mode terms are zero for a symmetric
    boundary balun.
    """

    frequency_hz: NDArray[np.float64]
    sdd: NDArray[np.complex128]
    scc: NDArray[np.complex128]
    sdc: NDArray[np.complex128]
    scd: NDArray[np.complex128]
    z0_input_ohm: float
    z0_diff_ohm: float
    z0_common_ohm: float
    model: str = "symmetric block-diagonal mixed-mode boundary"


def _common_mode_impedance(
    balun: BalunSpec, frequencies_hz: NDArray[np.float64]
) -> NDArray[np.complex128]:
    if balun.magnetizing_inductance_h > 0.0:
        return np.asarray(
            1j * 2.0 * math.pi * frequencies_hz * balun.magnetizing_inductance_h,
            dtype=np.complex128,
        )
    if balun.common_mode_impedance_ohm > 0.0:
        return np.full(
            frequencies_hz.size,
            complex(balun.common_mode_impedance_ohm),
            dtype=np.complex128,
        )
    return np.full(frequencies_hz.size, complex(math.inf), dtype=np.complex128)


def mixed_mode_balun(
    balun: BalunSpec,
    frequencies_hz: list[float] | NDArray[np.floating],
    *,
    z0_input_ohm: float | None = None,
    z0_diff_ohm: float | None = None,
    z0_common_ohm: float | None = None,
) -> MixedModeResult:
    """Build ``Sdd``, ``Scc`` and zero cross-mode terms for a boundary balun.

    The differential two-port comes from the existing ABCD balun model. The
    common-mode port uses the choke ``Lm`` (or scalar ``Zcm``) with a reference
    impedance ``z_balanced/2``. This is a symmetric boundary model: it does not
    invent differential/common-mode conversion, and is not a full EM/4-port
    model.
    """
    freq = np.asarray(frequencies_hz, dtype=float)
    if freq.ndim != 1 or freq.size == 0 or np.any(freq <= 0.0):
        raise MixedModeError("frequencies must be a non-empty positive 1-D array")
    z_in = float(balun.z_unbalanced_ohm if z0_input_ohm is None else z0_input_ohm)
    z_diff = float(balun.z_balanced_ohm if z0_diff_ohm is None else z0_diff_ohm)
    z_cm = float(z_diff / 2.0 if z0_common_ohm is None else z0_common_ohm)
    if z_in <= 0.0 or z_diff <= 0.0 or z_cm <= 0.0:
        raise MixedModeError("mixed-mode reference impedances must be > 0")

    abcd = balun_abcd(balun, freq)
    s11, s21, s12, s22 = abcd_to_s(abcd, z_in, z_diff)
    sdd = np.zeros((freq.size, 2, 2), dtype=np.complex128)
    sdd[:, 0, 0] = s11
    sdd[:, 1, 0] = s21
    sdd[:, 0, 1] = s12
    sdd[:, 1, 1] = s22

    zcm = _common_mode_impedance(balun, freq)
    scc = np.ones(freq.size, dtype=np.complex128)
    finite = np.isfinite(zcm.real) & np.isfinite(zcm.imag)
    scc[finite] = (zcm[finite] - z_cm) / (zcm[finite] + z_cm)
    sdc = np.zeros((freq.size, 2), dtype=np.complex128)
    scd = np.zeros((freq.size, 2), dtype=np.complex128)
    return MixedModeResult(
        frequency_hz=freq,
        sdd=sdd,
        scc=scc,
        sdc=sdc,
        scd=scd,
        z0_input_ohm=z_in,
        z0_diff_ohm=z_diff,
        z0_common_ohm=z_cm,
    )


__all__ = ["MixedModeError", "MixedModeResult", "mixed_mode_balun"]
