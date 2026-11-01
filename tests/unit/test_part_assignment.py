"""Real-part assignment to BOM components."""

from __future__ import annotations

from filterdesk.components_std import STARTER_PARTS
from filterdesk.domain.circuit import (
    Circuit,
    IdealCapacitor,
    IdealInductor,
    IdealResistor,
    Port,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.io.build_sheet import (
    build_sheet_rows,
    render_multiplexer_bom_csv,
)
from filterdesk.services.part_assignment import assign_nearest_parts


def _circuit(cap_f: float = 100e-12, ind_h: float = 10e-9) -> Circuit:
    return Circuit(
        [
            IdealCapacitor("C1", cap_f, "in", "out", ElementRole.SERIES),
            IdealInductor("L1", ind_h, "out", "gnd", ElementRole.SHUNT),
            IdealResistor("R1", 50.0, "out", "gnd"),
        ],
        Port("P1", "in", 50.0),
        Port("P2", "out", 50.0),
        ground="gnd",
    )


def test_assigns_nearest_parts_and_ignores_resistors() -> None:
    result = assign_nearest_parts([("Low", _circuit())], STARTER_PARTS)
    assert result.assignments["Low:C1"].mpn == "GRM1885C1H101JA01D"
    assert result.assignments["Low:L1"].mpn == "0603CS-10NXJRW"
    assert "Low:R1" not in result.assignments
    assert not result.unassigned


def test_far_value_is_reported_unassigned() -> None:
    result = assign_nearest_parts([("Low", _circuit(cap_f=5e-12))], STARTER_PARTS)
    assert "Low:C1" not in result.assignments
    assert any(item.ref == "C1" for item in result.unassigned)
    assert "away" in result.unassigned[0].reason


def test_bom_rows_include_assigned_part_metadata() -> None:
    circuit = _circuit()
    cap = next(part for part in STARTER_PARTS if part.mpn == "GRM1885C1H101JA01D")
    ind = next(part for part in STARTER_PARTS if part.mpn == "0603CS-10NXJRW")
    rows = build_sheet_rows(circuit, parts={"C1": cap, "L1": ind})
    by_ref = {row.ref: row for row in rows}
    assert by_ref["C1"].mpn == cap.mpn
    assert by_ref["C1"].manufacturer == "Murata"
    assert by_ref["L1"].package == "0603"
    csv_text = render_multiplexer_bom_csv(
        [("Low", circuit)], parts={"Low:C1": cap, "Low:L1": ind}
    )
    assert "GRM1885C1H101JA01D" in csv_text
    assert "0603CS-10NXJRW" in csv_text
