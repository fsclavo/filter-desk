"""Minimum-order estimation from pass/stop edges and Ap/As (scipy *ord)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy import signal

from filterdesk.domain.enums import ApproximationFamily, FilterResponse


class OrderEstimateError(ValueError):
    """Order cannot be estimated for the given family or parameters."""


_SUPPORTED = frozenset(
    {
        ApproximationFamily.BUTTERWORTH,
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        ApproximationFamily.CHEBYSHEV_TYPE_II,
        ApproximationFamily.ELLIPTIC,
    }
)


@dataclass(frozen=True, slots=True)
class OrderEstimateResult:
    """Result of a classical analog order estimate."""

    order: int
    family: ApproximationFamily
    response: FilterResponse
    f_pass_hz: float
    f_stop_hz: float
    passband_attenuation_db: float
    stopband_attenuation_db: float
    omega_ratio: float
    """Natural frequency from scipy (Hz); meaning depends on family."""
    natural_freq_hz: float
    notes: str


def supports_order_estimation(family: ApproximationFamily) -> bool:
    return family in _SUPPORTED


def estimate_minimum_order(
    family: ApproximationFamily,
    response: FilterResponse,
    *,
    f_pass_hz: float,
    f_stop_hz: float,
    passband_attenuation_db: float,
    stopband_attenuation_db: float,
) -> OrderEstimateResult:
    """Return the minimum order meeting Ap @ f_pass and As @ f_stop.

    Frequencies are in Hz. For LP: ``f_stop > f_pass``. For HP: ``f_stop < f_pass``.
    Band-pass / band-stop are not supported here (use LP prototype edges).
    """
    if family not in _SUPPORTED:
        raise OrderEstimateError(
            f"order estimation not supported for {family.value}; "
            "use Butterworth, Chebyshev I/II, or Elliptic"
        )
    if response not in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        raise OrderEstimateError(
            "order estimation currently supports low-pass and high-pass only"
        )
    if f_pass_hz <= 0.0 or f_stop_hz <= 0.0:
        raise OrderEstimateError("frequencies must be > 0")
    if passband_attenuation_db <= 0.0:
        raise OrderEstimateError("passband_attenuation_db (Ap) must be > 0")
    if stopband_attenuation_db <= 0.0:
        raise OrderEstimateError("stopband_attenuation_db (As) must be > 0")
    if stopband_attenuation_db <= passband_attenuation_db:
        raise OrderEstimateError("As must be greater than Ap")

    if response == FilterResponse.LOW_PASS:
        if f_stop_hz <= f_pass_hz:
            raise OrderEstimateError("low-pass requires f_stop > f_pass")
        omega_ratio = f_stop_hz / f_pass_hz
    else:
        if f_stop_hz >= f_pass_hz:
            raise OrderEstimateError("high-pass requires f_stop < f_pass")
        omega_ratio = f_pass_hz / f_stop_hz

    wp = 2.0 * math.pi * f_pass_hz
    ws = 2.0 * math.pi * f_stop_hz
    gpass = float(passband_attenuation_db)
    gstop = float(stopband_attenuation_db)

    if family == ApproximationFamily.BUTTERWORTH:
        n, wn = signal.buttord(wp, ws, gpass, gstop, analog=True)
        notes = "Butterworth: Ap at passband edge, As at stopband edge"
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_I:
        n, wn = signal.cheb1ord(wp, ws, gpass, gstop, analog=True)
        notes = "Chebyshev I: Ap = passband ripple, As at stopband edge"
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        n, wn = signal.cheb2ord(wp, ws, gpass, gstop, analog=True)
        notes = (
            "Chebyshev II: Ap = max passband loss, As at stopband edge; "
            "FilterDesk cutoff is the stopband edge"
        )
    else:
        n, wn = signal.ellipord(wp, ws, gpass, gstop, analog=True)
        notes = "Elliptic: Ap = passband ripple, As at stopband edge"

    order = int(n)
    if order < 1:
        raise OrderEstimateError("estimated order < 1")
    wn_hz = float(wn) / (2.0 * math.pi)
    return OrderEstimateResult(
        order=order,
        family=family,
        response=response,
        f_pass_hz=f_pass_hz,
        f_stop_hz=f_stop_hz,
        passband_attenuation_db=gpass,
        stopband_attenuation_db=gstop,
        omega_ratio=float(omega_ratio),
        natural_freq_hz=wn_hz,
        notes=notes,
    )
