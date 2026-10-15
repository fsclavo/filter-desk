"""Standard-component utilities: E-series tables and value snapping."""

from filterdesk.components_std.e_series import (
    ESeries,
    base_values,
    e_series_values,
    nearest_e_series,
)
from filterdesk.components_std.nonideal import (
    inductor_resistance_ohm_from_q,
    make_nonideal_capacitor,
    make_nonideal_inductor,
    nonidealize_circuit,
    set_element_parasitics,
)
from filterdesk.components_std.snap import (
    SnapEntry,
    SnapReport,
    SnapStrategy,
    snap_circuit,
)

__all__ = [
    "ESeries",
    "SnapEntry",
    "SnapReport",
    "SnapStrategy",
    "base_values",
    "e_series_values",
    "inductor_resistance_ohm_from_q",
    "make_nonideal_capacitor",
    "make_nonideal_inductor",
    "nearest_e_series",
    "nonidealize_circuit",
    "set_element_parasitics",
    "snap_circuit",
]
