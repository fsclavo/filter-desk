"""VNA measurement metadata sidecar (calibration/reference-plane provenance)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class VnaMeasurementMetadata:
    """Human/measurement provenance stored next to a Touchstone capture."""

    vna_model: str = ""
    calibration: str = ""
    reference_plane: str = ""
    cables: str = ""
    connectors: str = ""
    terminations: str = ""
    fixture: str = ""
    temperature_c: float | None = None
    measured_at: str = ""
    operator: str = ""
    notes: str = ""

    def summary(self) -> str:
        parts = [
            f"VNA={self.vna_model or '?'}",
            f"cal={self.calibration or '?'}",
            f"ref={self.reference_plane or '?'}",
        ]
        if self.temperature_c is not None:
            parts.append(f"T={self.temperature_c:g} C")
        if self.measured_at:
            parts.append(f"date={self.measured_at}")
        return ", ".join(parts)


def metadata_path_for(touchstone_path: Path | str) -> Path:
    """Return the sidecar path for ``foo.s2p`` -> ``foo.s2p.vna.json``."""
    path = Path(touchstone_path)
    return path.with_name(f"{path.name}.vna.json")


def write_vna_metadata(
    metadata: VnaMeasurementMetadata, touchstone_path: Path | str
) -> Path:
    path = metadata_path_for(touchstone_path)
    path.write_text(
        json.dumps(asdict(metadata), indent=2) + "\n", encoding="utf-8"
    )
    return path


def read_vna_metadata(touchstone_path: Path | str) -> VnaMeasurementMetadata:
    source = Path(touchstone_path)
    path = (
        source
        if source.name.endswith(".vna.json")
        else metadata_path_for(source)
    )
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("VNA metadata must be a JSON object")
    allowed = set(VnaMeasurementMetadata.__dataclass_fields__)
    unknown = set(data).difference(allowed)
    if unknown:
        raise ValueError(f"unknown VNA metadata fields: {sorted(unknown)}")
    temp = data.get("temperature_c")
    return VnaMeasurementMetadata(
        vna_model=str(data.get("vna_model", "")),
        calibration=str(data.get("calibration", "")),
        reference_plane=str(data.get("reference_plane", "")),
        cables=str(data.get("cables", "")),
        connectors=str(data.get("connectors", "")),
        terminations=str(data.get("terminations", "")),
        fixture=str(data.get("fixture", "")),
        temperature_c=None if temp is None else float(temp),
        measured_at=str(data.get("measured_at", "")),
        operator=str(data.get("operator", "")),
        notes=str(data.get("notes", "")),
    )


__all__ = [
    "VnaMeasurementMetadata",
    "metadata_path_for",
    "read_vna_metadata",
    "write_vna_metadata",
]
