"""Persistent measurement history records."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from filterdesk.analysis.types import AnalysisResult
from filterdesk.services.vna_measurement import VnaMeasurementMetadata


@dataclass(slots=True)
class MeasurementRecord:
    """A stored measured 2-port capture with provenance."""

    name: str
    source: str = ""
    z0_ohm: float = 50.0
    frequency_hz: tuple[float, ...] = ()
    s11: tuple[complex, ...] = ()
    s21: tuple[complex, ...] = ()
    s12: tuple[complex, ...] = ()
    s22: tuple[complex, ...] = ()
    metadata: VnaMeasurementMetadata = field(
        default_factory=VnaMeasurementMetadata
    )

    @classmethod
    def from_arrays(
        cls,
        *,
        name: str,
        frequency_hz: Iterable[float],
        s11: Iterable[complex],
        s21: Iterable[complex],
        s12: Iterable[complex],
        s22: Iterable[complex],
        z0_ohm: float = 50.0,
        source: str = "",
        metadata: VnaMeasurementMetadata | None = None,
    ) -> MeasurementRecord:
        frequency = tuple(float(value) for value in frequency_hz)
        arrays = [
            tuple(complex(value) for value in values)
            for values in (s11, s21, s12, s22)
        ]
        if not frequency or any(len(values) != len(frequency) for values in arrays):
            raise ValueError("measurement arrays must be non-empty and aligned")
        return cls(
            name=name,
            source=source,
            z0_ohm=float(z0_ohm),
            frequency_hz=frequency,
            s11=arrays[0],
            s21=arrays[1],
            s12=arrays[2],
            s22=arrays[3],
            metadata=metadata or VnaMeasurementMetadata(),
        )

    def to_analysis_result(self) -> AnalysisResult:
        s11 = np.asarray(self.s11, dtype=np.complex128)
        s21 = np.asarray(self.s21, dtype=np.complex128)
        s12 = np.asarray(self.s12, dtype=np.complex128)
        s22 = np.asarray(self.s22, dtype=np.complex128)
        with np.errstate(divide="ignore", invalid="ignore"):
            zin = self.z0_ohm * (1.0 + s11) / (1.0 - s11)
            zout = self.z0_ohm * (1.0 + s22) / (1.0 - s22)
        return AnalysisResult(
            frequency_hz=np.asarray(self.frequency_hz, dtype=np.float64),
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

    def to_mapping(self) -> dict[str, object]:
        def pairs(values: tuple[complex, ...]) -> list[list[float]]:
            return [[float(value.real), float(value.imag)] for value in values]

        return {
            "name": self.name,
            "source": self.source,
            "z0_ohm": self.z0_ohm,
            "frequency_hz": list(self.frequency_hz),
            "s11": pairs(self.s11),
            "s21": pairs(self.s21),
            "s12": pairs(self.s12),
            "s22": pairs(self.s22),
            "metadata": asdict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> MeasurementRecord:
        def pairs(key: str) -> tuple[complex, ...]:
            raw = data.get(key)
            if not isinstance(raw, list):
                raise ValueError(f"measurement.{key} must be a list")
            return tuple(complex(float(pair[0]), float(pair[1])) for pair in raw)

        frequency = data.get("frequency_hz")
        if not isinstance(frequency, list):
            raise ValueError("measurement.frequency_hz must be a list")
        metadata_raw = data.get("metadata")
        metadata = VnaMeasurementMetadata()
        if isinstance(metadata_raw, dict):
            allowed = set(VnaMeasurementMetadata.__dataclass_fields__)
            values = {
                key: value
                for key, value in metadata_raw.items()
                if key in allowed
            }
            try:
                metadata = VnaMeasurementMetadata(**values)
            except TypeError:
                metadata = VnaMeasurementMetadata()
        result = cls(
            name=str(data.get("name", "measurement")),
            source=str(data.get("source", "")),
            z0_ohm=float(data.get("z0_ohm", 50.0)),
            frequency_hz=tuple(float(value) for value in frequency),
            s11=pairs("s11"),
            s21=pairs("s21"),
            s12=pairs("s12"),
            s22=pairs("s22"),
            metadata=metadata,
        )
        if not result.frequency_hz or any(
            len(values) != len(result.frequency_hz)
            for values in (result.s11, result.s21, result.s12, result.s22)
        ):
            raise ValueError("measurement arrays must be non-empty and aligned")
        return result


__all__ = ["MeasurementRecord"]
