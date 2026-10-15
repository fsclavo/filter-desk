"""Domain enumerations for filter specifications and topologies."""

from __future__ import annotations

from enum import StrEnum


class ApproximationFamily(StrEnum):
    BUTTERWORTH = "butterworth"
    CHEBYSHEV_TYPE_I = "chebyshev_type_i"
    BESSEL = "bessel"
    GAUSSIAN = "gaussian"
    LEGENDRE = "legendre"
    CHEBYSHEV_TYPE_II = "chebyshev_type_ii"
    ELLIPTIC = "elliptic"
    CONSTANT_K = "constant_k"
    M_DERIVED = "m_derived"


class FilterResponse(StrEnum):
    LOW_PASS = "low_pass"
    HIGH_PASS = "high_pass"
    BAND_PASS = "band_pass"
    BAND_STOP = "band_stop"


class CutoffDefinition(StrEnum):
    """See ADR-006 / ADR-013."""

    HALF_POWER_3DB = "half_power_3db"
    RIPPLE_EDGE = "ripple_edge"
    STOPBAND_EDGE = "stopband_edge"


class TopologyId(StrEnum):
    """Ladder topologies (LP/HP/BP/BS)."""

    LADDER_LP_SERIES_L_INPUT = "ladder_lp_series_l_input"
    LADDER_LP_SHUNT_C_INPUT = "ladder_lp_shunt_c_input"
    LADDER_HP_SERIES_C_INPUT = "ladder_hp_series_c_input"
    LADDER_HP_SHUNT_L_INPUT = "ladder_hp_shunt_l_input"
    LADDER_BP_SERIES_RES_INPUT = "ladder_bp_series_resonator_input"
    LADDER_BP_SHUNT_RES_INPUT = "ladder_bp_shunt_resonator_input"
    LADDER_BS_SERIES_TANK_INPUT = "ladder_bs_series_tank_input"
    LADDER_BS_SHUNT_TANK_INPUT = "ladder_bs_shunt_tank_input"


class ElementRole(StrEnum):
    SERIES = "series"
    SHUNT = "shunt"


class ElementType(StrEnum):
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    INDUCTOR = "inductor"
    SERIES_LC = "series_lc"
    PARALLEL_LC = "parallel_lc"
    # Series of (series-LC) + (parallel-LC) — Brune finite-zero BP/BS arm
    BRUNE_LC = "brune_lc"
    # Parallel of (series-LC) || (parallel-LC)
    DUAL_BRUNE_LC = "dual_brune_lc"
