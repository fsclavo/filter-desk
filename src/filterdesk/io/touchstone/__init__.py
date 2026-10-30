"""Touchstone I/O."""

from pathlib import Path

from filterdesk.analysis.multiport import SParameters
from filterdesk.io.touchstone.reader import (
    TouchstoneData,
    TouchstoneError,
    parse_touchstone,
    ports_from_filename,
    read_touchstone,
)
from filterdesk.io.touchstone.writer import (
    write_touchstone_s1p,
    write_touchstone_s2p,
    write_touchstone_snp,
)


def read_sparameters(path: Path | str) -> SParameters:
    """Read any ``.sNp`` file into the analysis-layer N-port container."""
    data = read_touchstone(path)
    return SParameters(
        frequency_hz=data.frequency_hz,
        s=data.s,
        z0_ohm=data.z0_ohm,
        source=data.source,
    )


def write_sparameters(
    network: SParameters,
    path: Path | str,
    *,
    comment: str | None = None,
) -> None:
    """Write an N-port network as Touchstone 1.0 RI/Hz."""
    write_touchstone_snp(network, path, comment=comment)


__all__ = [
    "TouchstoneData",
    "TouchstoneError",
    "parse_touchstone",
    "ports_from_filename",
    "read_sparameters",
    "read_touchstone",
    "write_sparameters",
    "write_touchstone_s1p",
    "write_touchstone_s2p",
    "write_touchstone_snp",
]
