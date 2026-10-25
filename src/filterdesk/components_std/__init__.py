"""Standard-component utilities: E-series tables and value snapping."""

from filterdesk.components_std.air_coil import (
    AirCoilDesign,
    AirCoilError,
    air_coil_inductance_h,
    design_air_coil,
)
from filterdesk.components_std.attenuator import (
    AttenuatorDesign,
    AttenuatorError,
    AttenuatorKind,
    design_attenuator,
)
from filterdesk.components_std.e_series import (
    ESeries,
    base_values,
    e_series_values,
    nearest_e_series,
)
from filterdesk.components_std.matching import (
    MatchingDesign,
    MatchingElement,
    MatchingError,
    MatchingTopology,
    design_matching,
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
from filterdesk.components_std.toroid import (
    CORES,
    ToroidCore,
    ToroidDesign,
    ToroidError,
    WireFit,
    design_toroid,
    find_core,
    list_cores,
    make_custom_core,
    turns_for_inductance,
)

__all__ = [
    "AirCoilDesign",
    "AirCoilError",
    "AttenuatorDesign",
    "AttenuatorError",
    "AttenuatorKind",
    "CORES",
    "ESeries",
    "MatchingDesign",
    "MatchingElement",
    "MatchingError",
    "MatchingTopology",
    "SnapEntry",
    "SnapReport",
    "SnapStrategy",
    "ToroidCore",
    "ToroidDesign",
    "ToroidError",
    "WireFit",
    "air_coil_inductance_h",
    "base_values",
    "design_attenuator",
    "design_air_coil",
    "design_matching",
    "design_toroid",
    "e_series_values",
    "find_core",
    "inductor_resistance_ohm_from_q",
    "list_cores",
    "make_custom_core",
    "make_nonideal_capacitor",
    "make_nonideal_inductor",
    "nearest_e_series",
    "nonidealize_circuit",
    "set_element_parasitics",
    "snap_circuit",
    "turns_for_inductance",
]
