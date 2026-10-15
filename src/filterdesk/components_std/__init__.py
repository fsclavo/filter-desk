"""Standard-component utilities: E-series tables and value snapping."""

from filterdesk.components_std.e_series import (
    ESeries,
    base_values,
    e_series_values,
    nearest_e_series,
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
    "nearest_e_series",
    "snap_circuit",
]
