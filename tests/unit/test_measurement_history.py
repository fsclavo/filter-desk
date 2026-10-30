"""Persistent measurement history."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.services.measurements import MeasurementRecord
from filterdesk.services.session import DesignSession
from filterdesk.services.vna_measurement import VnaMeasurementMetadata


def _record(name: str, offset: float = 0.0) -> MeasurementRecord:
    freq = (100e6 + offset, 110e6 + offset, 120e6 + offset)
    return MeasurementRecord.from_arrays(
        name=name,
        frequency_hz=freq,
        s11=(0.1 + 0j, 0.2 + 0j, 0.3 + 0j),
        s21=(0.9 + 0j, 0.8 + 0j, 0.7 + 0j),
        s12=(0.9 + 0j, 0.8 + 0j, 0.7 + 0j),
        s22=(0.1 + 0j, 0.2 + 0j, 0.3 + 0j),
    )


def test_add_activate_remove_measurements() -> None:
    session = DesignSession()
    first = session.add_measurement(_record("first.s2p"))
    second = session.add_measurement(_record("second.s2p"))
    assert first == 0 and second == 1
    assert session.active_measurement == 1
    assert session.measured_name == "second.s2p"
    assert session.measured is not None
    assert session.measured.frequency_hz[0] == pytest.approx(100e6)

    session.activate_measurement(0)
    assert session.measured_name == "first.s2p"
    session.remove_measurement(0)
    assert len(session.measurements) == 1
    assert session.measured_name == "second.s2p"
    session.clear_measurements()
    assert session.measurements == []
    assert session.measured is None


def test_duplicate_measurement_names_are_made_unique() -> None:
    session = DesignSession()
    session.add_measurement(_record("same.s2p"))
    session.add_measurement(_record("same.s2p", 10e6))
    assert [item.name for item in session.measurements] == [
        "same.s2p",
        "same.s2p (2)",
    ]


def test_measurement_history_project_roundtrip() -> None:
    session = DesignSession()
    session.synthesize()
    session.add_measurement(_record("one.s2p"))
    session.add_measurement(_record("two.s2p", 10e6))
    session.activate_measurement(0)

    project = session.to_project()
    restored = DesignSession()
    restored.load_project(project)
    assert [item.name for item in restored.measurements] == [
        "one.s2p",
        "two.s2p",
    ]
    assert restored.active_measurement == 0
    assert restored.measured_name == "one.s2p"
    assert restored.measured is not None


def test_legacy_project_without_measurements_is_clean() -> None:
    session = DesignSession()
    session.synthesize()
    project = session.to_project()
    project.extensions.pop("measurements", None)
    restored = DesignSession()
    restored.load_project(project)
    assert restored.measurements == []
    assert restored.measured is None
    assert restored.active_measurement is None


def test_measurement_mapping_roundtrip() -> None:
    record = _record("capture.s2p")
    restored = MeasurementRecord.from_mapping(record.to_mapping())
    assert restored.name == record.name
    assert restored.frequency_hz == record.frequency_hz
    assert restored.s21 == record.s21
    assert np.allclose(
        restored.to_analysis_result().s11,
        record.to_analysis_result().s11,
    )


def test_measurement_metadata_roundtrip() -> None:
    record = _record("capture.s2p")
    record.metadata = VnaMeasurementMetadata(
        vna_model="NanoVNA",
        calibration="SOLT",
        reference_plane="connector",
        cables="RG-58",
        operator="Tester",
    )
    restored = MeasurementRecord.from_mapping(record.to_mapping())
    assert restored.metadata.vna_model == "NanoVNA"
    assert restored.metadata.calibration == "SOLT"
    assert restored.metadata.reference_plane == "connector"
    assert restored.metadata.cables == "RG-58"
    assert restored.metadata.operator == "Tester"
