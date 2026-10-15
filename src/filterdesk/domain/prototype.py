"""Normalized prototype: all-pole g-values and/or Cauer ladder arms."""

from __future__ import annotations

from dataclasses import dataclass

from filterdesk.domain.circuit import ArmKind
from filterdesk.domain.enums import ApproximationFamily


@dataclass(frozen=True, slots=True)
class NormalizedArm:
    """One ladder arm at ω'=1 rad/s, Z'=1 Ω."""

    kind: ArmKind
    value: float | None = None
    L: float | None = None
    C: float | None = None

    def __post_init__(self) -> None:
        single = ("series_L", "series_C", "shunt_L", "shunt_C")
        tank = (
            "series_series_LC",
            "shunt_parallel_LC",
            "series_parallel_LC",
            "shunt_series_LC",
        )
        if self.kind in single:
            if self.value is None or self.value == 0.0:
                raise ValueError(f"{self.kind} requires nonzero value")
        elif self.kind in tank:
            if self.L is None or self.C is None or self.L == 0.0 or self.C == 0.0:
                raise ValueError(f"{self.kind} requires nonzero L and C")
        else:
            raise ValueError(f"unknown arm kind: {self.kind}")

    @property
    def is_positive(self) -> bool:
        if self.value is not None and self.value <= 0.0:
            return False
        if self.L is not None and self.L <= 0.0:
            return False
        if self.C is not None and self.C <= 0.0:
            return False
        return True


@dataclass(frozen=True, slots=True)
class Prototype:
    """Low-pass prototype normalized to ωc'=1, Z0'=1 Ω.

    All-pole families use ``g_values`` = g0..g(n+1).
    Finite-zero / image-parameter families use ``arms`` (Cauer / K-m ladder).
    """

    family: ApproximationFamily
    order: int
    g_values: tuple[float, ...] = ()
    arms: tuple[NormalizedArm, ...] | None = None
    epsilon: float | None = None
    passband_ripple_db: float | None = None
    stopband_attenuation_db: float | None = None
    m_parameter: float | None = None
    notes: str = "omega_c=1 rad/s; Z0'=1 ohm"

    def __post_init__(self) -> None:
        if self.arms is not None:
            if self.order < 1:
                raise ValueError("order must be >= 1")
            return
        expected = self.order + 2
        if len(self.g_values) != expected:
            raise ValueError(
                f"expected {expected} g-values for order {self.order}, "
                f"got {len(self.g_values)}"
            )

    @property
    def is_cauer(self) -> bool:
        return self.arms is not None

    @property
    def section_g(self) -> tuple[float, ...]:
        """g1..gn (ladder arms only)."""
        if self.arms is not None:
            raise ValueError("Cauer prototype has no g-values; use arms")
        return self.g_values[1:-1]
