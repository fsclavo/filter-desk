"""N-port scattering-parameter network primitives.

The core stores an S-matrix per frequency for an equal real reference impedance
``z0_ohm``.  It provides the operations needed by the first multiport systems:
port renumbering, termination of one port and parallel combination of grounded
2-port branches at a common input port.

This is deliberately independent of Touchstone and scikit-rf.  Conversions live
in :mod:`filterdesk.io.touchstone`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.types import AnalysisResult


class MultiportError(ValueError):
    """Raised when an N-port network cannot be built or reduced."""


@dataclass(frozen=True, slots=True)
class SParameters:
    """S-parameters on a frequency grid with one real reference impedance."""

    frequency_hz: NDArray[np.float64]
    s: NDArray[np.complex128]
    z0_ohm: float = 50.0
    source: str | None = None

    def __post_init__(self) -> None:
        frequency = np.asarray(self.frequency_hz, dtype=np.float64)
        s = np.asarray(self.s, dtype=np.complex128)
        if frequency.ndim != 1 or frequency.size == 0:
            raise MultiportError("frequency_hz must be a non-empty 1-D array")
        if s.ndim != 3 or s.shape[1] != s.shape[2]:
            raise MultiportError("s must have shape (points, ports, ports)")
        if s.shape[0] != frequency.size:
            raise MultiportError(
                f"s has {s.shape[0]} points but frequency has {frequency.size}"
            )
        if s.shape[1] < 1:
            raise MultiportError("a network needs at least one port")
        if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
            raise MultiportError("frequencies must be finite and > 0")
        if frequency.size > 1 and np.any(np.diff(frequency) <= 0.0):
            raise MultiportError("frequencies must be strictly increasing")
        if not np.all(np.isfinite(s)):
            raise MultiportError("S-parameters must be finite")
        if not np.isfinite(self.z0_ohm) or self.z0_ohm <= 0.0:
            raise MultiportError("z0_ohm must be finite and > 0")
        object.__setattr__(
            self, "frequency_hz", np.ascontiguousarray(frequency)
        )
        object.__setattr__(self, "s", np.ascontiguousarray(s))

    @classmethod
    def from_analysis(cls, result: AnalysisResult) -> SParameters:
        """Build a 2-port network from an ``AnalysisResult``."""
        z0_source = float(result.z0_source_ohm)
        z0_load = float(result.z0_load_ohm)
        if not np.isclose(z0_source, z0_load, rtol=1e-12):
            raise MultiportError(
                "a 2-port AnalysisResult with unequal port impedances cannot be "
                "represented by one scalar z0"
            )
        frequency = np.asarray(result.frequency_hz, dtype=float)
        s11 = np.asarray(result.s11, dtype=np.complex128)
        s21 = np.asarray(result.s21, dtype=np.complex128)
        s12 = np.asarray(result.s12, dtype=np.complex128)
        s22 = np.asarray(result.s22, dtype=np.complex128)
        s = np.empty((frequency.size, 2, 2), dtype=np.complex128)
        s[:, 0, 0] = s11
        s[:, 1, 0] = s21
        s[:, 0, 1] = s12
        s[:, 1, 1] = s22
        return cls(
            frequency_hz=frequency,
            s=s,
            z0_ohm=z0_source,
            source=result.backend or None,
        )

    @property
    def n_ports(self) -> int:
        return int(self.s.shape[1])

    @property
    def n_points(self) -> int:
        return int(self.frequency_hz.size)

    def s_param(self, out_port: int, in_port: int) -> NDArray[np.complex128]:
        """Return ``S[out_port, in_port]`` (1-based) across frequency."""
        self._check_port(out_port)
        self._check_port(in_port)
        return self.s[:, out_port - 1, in_port - 1]

    def port_renumber(self, order: Sequence[int]) -> SParameters:
        """Return a copy whose new port ``k`` is old port ``order[k-1]``."""
        ports = tuple(int(port) for port in order)
        if sorted(ports) != list(range(1, self.n_ports + 1)):
            raise MultiportError(
                f"order must be a permutation of 1..{self.n_ports}: {ports!r}"
            )
        indices = np.asarray([port - 1 for port in ports], dtype=int)
        s = self.s[:, indices, :][:, :, indices]
        return replace(self, s=np.ascontiguousarray(s))

    def terminate(self, port: int, *, z_load_ohm: complex) -> SParameters:
        """Terminate one port and return the reduced network.

        ``port`` is 1-based.  The load is connected between that port and the
        common reference conductor; its reflection coefficient is computed from
        the network reference impedance.
        """
        self._check_port(port)
        if self.n_ports < 2:
            raise MultiportError("cannot terminate the only port of a 1-port")
        index = port - 1
        load = complex(z_load_ohm)
        if np.isinf(load.real) and load.imag == 0.0:
            gamma = 1.0 + 0.0j
        else:
            gamma = (load - self.z0_ohm) / (load + self.z0_ohm)
        if not np.isfinite(gamma):
            raise MultiportError("load reflection coefficient is not finite")
        denominator = 1.0 - self.s[:, index, index] * gamma
        if np.any(np.abs(denominator) < 1e-15):
            raise MultiportError("terminated network is singular")
        factor = gamma / denominator
        correction = (
            self.s[:, :, index][:, :, None]
            * self.s[:, index, :][:, None, :]
            * factor[:, None, None]
        )
        full = self.s + correction
        s = np.delete(np.delete(full, index, axis=1), index, axis=2)
        return replace(self, s=np.ascontiguousarray(s))

    @classmethod
    def parallel_branches(
        cls, branches: Sequence[SParameters]
    ) -> SParameters:
        """Combine grounded 2-port branches at a common input port.

        Each branch must have the same frequency grid and reference impedance.
        The result has port 1 as the shared input, followed by each branch
        output in input order.  Branches are joined through an ideal common
        node (their input voltages are equal and their input currents add); no
        isolation network is inserted.
        """
        items = tuple(branches)
        if len(items) < 2:
            raise MultiportError("parallel combination needs at least two branches")
        first = items[0]
        for branch in items:
            if branch.n_ports != 2:
                raise MultiportError("parallel branches must be 2-ports")
            if not np.array_equal(branch.frequency_hz, first.frequency_hz):
                raise MultiportError("parallel branches must share one frequency grid")
            if not np.isclose(branch.z0_ohm, first.z0_ohm, rtol=1e-12):
                raise MultiportError(
                    "parallel branches must use the same reference impedance"
                )
        total = len(items) + 1
        y = np.zeros(
            (first.n_points, total, total), dtype=np.complex128
        )
        for offset, branch in enumerate(items):
            branch_y = _s_to_y(branch.s, branch.z0_ohm)
            output = offset + 1
            y[:, 0, 0] += branch_y[:, 0, 0]
            y[:, 0, output] = branch_y[:, 0, 1]
            y[:, output, 0] = branch_y[:, 1, 0]
            y[:, output, output] = branch_y[:, 1, 1]
        s = _y_to_s(y, first.z0_ohm)
        return cls(
            frequency_hz=first.frequency_hz,
            s=s,
            z0_ohm=first.z0_ohm,
            source=first.source,
        )

    def summary(self) -> str:
        f = self.frequency_hz
        return (
            f"{self.n_ports}-port, {self.n_points} points, "
            f"{float(f[0]):.6g}–{float(f[-1]):.6g} Hz, "
            f"Z0={self.z0_ohm:g} ohm"
        )

    def _check_port(self, port: int) -> None:
        if not 1 <= port <= self.n_ports:
            raise MultiportError(f"port must be in 1..{self.n_ports}: {port}")


def _s_to_y(s: NDArray[np.complex128], z0_ohm: float) -> NDArray[np.complex128]:
    points, ports, _ = s.shape
    identity = np.eye(ports, dtype=np.complex128)
    try:
        return np.asarray(
            [
                np.linalg.solve(identity + s[index], identity - s[index])
                / z0_ohm
                for index in range(points)
            ],
            dtype=np.complex128,
        )
    except np.linalg.LinAlgError as exc:
        raise MultiportError("S-to-Y conversion is singular") from exc


def _y_to_s(y: NDArray[np.complex128], z0_ohm: float) -> NDArray[np.complex128]:
    points, ports, _ = y.shape
    identity = np.eye(ports, dtype=np.complex128)
    try:
        return np.asarray(
            [
                np.linalg.solve(
                    identity + z0_ohm * y[index], identity - z0_ohm * y[index]
                )
                for index in range(points)
            ],
            dtype=np.complex128,
        )
    except np.linalg.LinAlgError as exc:
        raise MultiportError("Y-to-S conversion is singular") from exc


__all__ = ["MultiportError", "SParameters"]
