"""Touchstone v1 reader (.s1p / .s2p), inverse of :mod:`writer`.

Supports frequency units HZ/KHZ/MHZ/GHZ, data formats RI/MA/DB, the ``R z0``
option, ``!`` comments and multi-line (wrapped) records. Only scattering
parameters (``S``) are accepted; ``Y``/``Z``/``G``/``H`` raise
:class:`TouchstoneError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from math import isqrt
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.types import AnalysisResult

_FREQ_UNITS: dict[str, float] = {
    "HZ": 1.0,
    "KHZ": 1e3,
    "MHZ": 1e6,
    "GHZ": 1e9,
}
_DATA_FORMATS = ("RI", "MA", "DB")
_PORT_RE = re.compile(r"\.s(\d+)p$", re.IGNORECASE)

# Touchstone 1.0 defaults when no option line is present.
_DEFAULT_FREQ_UNIT = "GHZ"
_DEFAULT_FORMAT = "MA"


class TouchstoneError(ValueError):
    """Raised when a Touchstone file cannot be parsed."""


@dataclass(slots=True)
class TouchstoneData:
    """Parsed frequency-domain network data (S-parameters on an f-grid)."""

    frequency_hz: NDArray[np.float64]
    s: NDArray[np.complex128]
    z0_ohm: float = 50.0
    freq_unit: str = "HZ"
    data_format: str = "RI"
    param_type: str = "S"
    comments: list[str] = field(default_factory=list)
    source: str | None = None

    @property
    def n_ports(self) -> int:
        return int(self.s.shape[1])

    @property
    def n_points(self) -> int:
        return int(self.frequency_hz.shape[0])

    def s_param(
        self, out_port: int, in_port: int
    ) -> NDArray[np.complex128]:
        """Return ``S[out_port, in_port]`` (1-based) across frequency."""
        return self.s[:, out_port - 1, in_port - 1]

    def to_analysis_result(self) -> AnalysisResult:
        """Map a 2-port file to :class:`AnalysisResult` for compare/overlay."""
        if self.n_ports != 2:
            raise TouchstoneError(
                f"only 2-port data maps to an analysis result (got {self.n_ports})"
            )
        s = self.s
        s11 = s[:, 0, 0]
        s21 = s[:, 1, 0]
        s12 = s[:, 0, 1]
        s22 = s[:, 1, 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            zin = self.z0_ohm * (1.0 + s11) / (1.0 - s11)
            zout = self.z0_ohm * (1.0 + s22) / (1.0 - s22)
        return AnalysisResult(
            frequency_hz=self.frequency_hz,
            s11=s11,
            s21=s21,
            s12=s12,
            s22=s22,
            zin_ohm=zin,
            zout_ohm=zout,
            z0_source_ohm=self.z0_ohm,
            z0_load_ohm=self.z0_ohm,
            backend="touchstone",
        )

    def summary(self) -> str:
        f = self.frequency_hz
        fmin = float(f.min()) if f.size else 0.0
        fmax = float(f.max()) if f.size else 0.0
        return (
            f"{self.n_ports}-port, {self.n_points} points, "
            f"{fmin:.6g}–{fmax:.6g} Hz, format={self.data_format}, "
            f"Z0={self.z0_ohm:g} ohm"
        )


def ports_from_filename(path: Path | str) -> int | None:
    """Infer port count from a ``.s2p`` style extension (else ``None``)."""
    match = _PORT_RE.search(Path(path).name)
    return int(match.group(1)) if match else None


def read_touchstone(path: Path | str) -> TouchstoneData:
    """Read and parse a Touchstone file from disk."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise TouchstoneError(f"cannot read {p}: {exc}") from exc
    return parse_touchstone(
        text, source=str(p), n_ports=ports_from_filename(p)
    )


def _parse_option(
    tokens: list[str],
) -> tuple[str, str, str, float]:
    freq_unit = _DEFAULT_FREQ_UNIT
    data_format = _DEFAULT_FORMAT
    param_type = "S"
    z0 = 50.0
    # Option line order: "# <freq_unit> <param_type> <data_format> R <z0>".
    upper = [t.upper() for t in tokens]
    if upper:
        freq_unit = upper[0]
    if len(upper) > 1:
        param_type = upper[1]
    if len(upper) > 2:
        data_format = upper[2]
    if "R" in upper:
        ri = upper.index("R")
        if ri + 1 < len(upper):
            try:
                z0 = float(upper[ri + 1])
            except ValueError as exc:
                raise TouchstoneError(
                    f"invalid reference impedance in option line: {tokens!r}"
                ) from exc
    if freq_unit not in _FREQ_UNITS:
        raise TouchstoneError(f"unsupported frequency unit: {freq_unit!r}")
    if data_format not in _DATA_FORMATS:
        raise TouchstoneError(f"unsupported data format: {data_format!r}")
    if param_type != "S":
        raise TouchstoneError(
            f"unsupported parameter type: {param_type!r} (only S is supported)"
        )
    return freq_unit, data_format, param_type, z0


def _infer_ports(first_values: int, total_values: int) -> int:
    """Infer the port count.

    Prefer the first data line (a complete record in unwrapped files), then
    fall back to the total number of values so wrapped records still parse.
    """
    if first_values > 0 and first_values % 2 == 0:
        n = isqrt(first_values // 2)
        if n >= 1 and n * n * 2 == first_values:
            return n
    n_max = isqrt(max(total_values - 1, 1) // 2)
    for n in range(n_max, 0, -1):
        per_freq = 2 * n * n + 1
        if per_freq <= total_values and total_values % per_freq == 0:
            return n
    raise TouchstoneError(
        "cannot infer port count; use a .sNp filename extension"
    )


def parse_touchstone(
    text: str,
    *,
    source: str | None = None,
    n_ports: int | None = None,
) -> TouchstoneData:
    """Parse Touchstone text (see module docstring for supported features)."""
    comments: list[str] = []
    option_tokens: list[str] | None = None
    data_lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!"):
            comments.append(line[1:].strip())
            continue
        if line.startswith("#"):
            if option_tokens is None:
                option_tokens = line[1:].split()
            continue
        if "!" in line:  # inline comment after data
            line = line.split("!", 1)[0].strip()
        if line:
            data_lines.append(line)

    if not data_lines:
        raise TouchstoneError("no data found in Touchstone file")

    freq_unit, data_format, param_type, z0 = _parse_option(option_tokens or [])
    freq_scale = _FREQ_UNITS[freq_unit]

    values: list[float] = []
    for line in data_lines:
        for token in line.split():
            try:
                values.append(float(token))
            except ValueError as exc:
                raise TouchstoneError(
                    f"invalid numeric token {token!r}"
                ) from exc

    total = len(values)
    if n_ports is not None:
        ports = n_ports
    else:
        ports = _infer_ports(len(data_lines[0].split()) - 1, total)
    if ports < 1:
        raise TouchstoneError(f"invalid port count: {ports}")

    per_freq = 1 + 2 * ports * ports
    if total % per_freq != 0:
        raise TouchstoneError(
            f"data length {total} is not a multiple of {per_freq} "
            f"(1 + 2*{ports}^2) — wrong port count?"
        )
    n_points = total // per_freq
    if n_points < 1:
        raise TouchstoneError("no complete frequency records found")

    matrix = np.array(values, dtype=np.float64).reshape(n_points, per_freq)
    frequency_hz = matrix[:, 0] * freq_scale
    pairs = matrix[:, 1:].reshape(n_points, ports * ports, 2)
    first = pairs[:, :, 0]
    second = pairs[:, :, 1]
    if data_format == "RI":
        cplx = first + 1j * second
    elif data_format == "MA":
        cplx = first * np.exp(1j * np.deg2rad(second))
    else:  # DB
        cplx = np.power(10.0, first / 20.0) * np.exp(1j * np.deg2rad(second))

    # Touchstone column order is S11 S21 S31 ... (column-major): index k maps
    # to S[i, j] with i = k % n, j = k // n.
    s = cplx.reshape(n_points, ports, ports).transpose(0, 2, 1)
    return TouchstoneData(
        frequency_hz=frequency_hz,
        s=np.ascontiguousarray(s, dtype=np.complex128),
        z0_ohm=z0,
        freq_unit=freq_unit,
        data_format=data_format,
        param_type=param_type,
        comments=comments,
        source=source,
    )
