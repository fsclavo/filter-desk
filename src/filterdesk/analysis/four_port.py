"""Mixed-mode analysis of a general 4-port single-ended S-matrix.

Ports are grouped as two differential pairs: (1, 2) and (3, 4). The transform
produces the canonical mixed-mode order ``d1, d2, c1, c2`` and exposes the
differential, common-mode and cross-mode blocks. It is a pure S-parameter
transform; it does not create an electromagnetic device model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


class FourPortError(ValueError):
    """Raised for invalid 4-port S-parameter data or reference impedances."""


@dataclass(frozen=True, slots=True)
class FourPortMixedMode:
    """Mixed-mode S data for a 4-port network.

    ``sdd``/``scc`` are 2x2 differential/common blocks in mixed-port order
    ``[d1, d2]`` and ``[c1, c2]``. ``sdc`` is differential output vs common
    input; ``scd`` is common output vs differential input.
    """

    frequency_hz: NDArray[np.float64]
    s_mm: NDArray[np.complex128]
    sdd: NDArray[np.complex128]
    sdc: NDArray[np.complex128]
    scd: NDArray[np.complex128]
    scc: NDArray[np.complex128]
    z0_single_ended_ohm: float
    z0_diff_ohm: float
    z0_common_ohm: float
    model: str = "4-port mixed-mode S transform"


def mixed_mode_4port(
    s: NDArray[np.complexfloating],
    frequency_hz: NDArray[np.floating] | list[float],
    *,
    z0_ohm: float = 50.0,
) -> FourPortMixedMode:
    """Transform 4-port single-ended S data to the mixed-mode basis."""
    freq = np.asarray(frequency_hz, dtype=float)
    matrix = np.asarray(s, dtype=np.complex128)
    if freq.ndim != 1 or freq.size == 0 or np.any(freq <= 0.0):
        raise FourPortError("frequency_hz must be a non-empty positive 1-D array")
    if matrix.shape != (freq.size, 4, 4):
        raise FourPortError("s must have shape (n_points, 4, 4)")
    if not math.isfinite(z0_ohm) or z0_ohm <= 0.0:
        raise FourPortError("z0_ohm must be finite and > 0")

    root = 1.0 / math.sqrt(2.0)
    transform = np.array(
        [
            [root, -root, 0.0, 0.0],
            [0.0, 0.0, root, -root],
            [root, root, 0.0, 0.0],
            [0.0, 0.0, root, root],
        ],
        dtype=np.float64,
    )
    s_mm = np.einsum(
        "ij,njk,lk->nil", transform, matrix, transform, optimize=True
    )
    return FourPortMixedMode(
        frequency_hz=freq,
        s_mm=s_mm,
        sdd=s_mm[:, :2, :2],
        sdc=s_mm[:, :2, 2:],
        scd=s_mm[:, 2:, :2],
        scc=s_mm[:, 2:, 2:],
        z0_single_ended_ohm=float(z0_ohm),
        z0_diff_ohm=2.0 * float(z0_ohm),
        z0_common_ohm=0.5 * float(z0_ohm),
    )


__all__ = ["FourPortError", "FourPortMixedMode", "mixed_mode_4port"]
