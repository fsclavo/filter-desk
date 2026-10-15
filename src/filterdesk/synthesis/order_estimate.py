"""Minimum-order estimation from pass/stop edges and Ap/As (scipy *ord)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
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
    """Result of a classical analog order estimate.

    For LP/HP the scalar ``f_pass_hz``/``f_stop_hz`` and ``natural_freq_hz``
    carry the edges. For BP/BS the ``*_low_hz``/``*_high_hz`` pairs are set,
    ``f_pass_hz``/``f_stop_hz`` hold the lower pass/stop edges, and
    ``natural_freq_hz`` is the geometric mean of the two prototype corners.
    """

    order: int
    family: ApproximationFamily
    response: FilterResponse
    f_pass_hz: float
    f_stop_hz: float
    passband_attenuation_db: float
    stopband_attenuation_db: float
    omega_ratio: float
    """Selectivity: edge ratio (LP/HP) or stop/pass bandwidth ratio (BP/BS)."""
    natural_freq_hz: float
    """Natural frequency from scipy (Hz); meaning depends on family."""
    notes: str
    f_pass_low_hz: float | None = None
    f_pass_high_hz: float | None = None
    f_stop_low_hz: float | None = None
    f_stop_high_hz: float | None = None
    natural_freq_low_hz: float | None = None
    natural_freq_high_hz: float | None = None


def supports_order_estimation(family: ApproximationFamily) -> bool:
    return family in _SUPPORTED


def _validate_ap_as(
    passband_attenuation_db: float, stopband_attenuation_db: float
) -> None:
    if passband_attenuation_db <= 0.0:
        raise OrderEstimateError("passband_attenuation_db (Ap) must be > 0")
    if stopband_attenuation_db <= 0.0:
        raise OrderEstimateError("stopband_attenuation_db (As) must be > 0")
    if stopband_attenuation_db <= passband_attenuation_db:
        raise OrderEstimateError("As must be greater than Ap")


def estimate_minimum_order(
    family: ApproximationFamily,
    response: FilterResponse,
    *,
    f_pass_hz: float = 0.0,
    f_stop_hz: float = 0.0,
    passband_attenuation_db: float,
    stopband_attenuation_db: float,
    f_pass_low_hz: float | None = None,
    f_pass_high_hz: float | None = None,
    f_stop_low_hz: float | None = None,
    f_stop_high_hz: float | None = None,
) -> OrderEstimateResult:
    """Return the minimum order meeting Ap @ passband and As @ stopband.

    LP/HP use the scalar ``f_pass_hz``/``f_stop_hz`` (Hz). BP/BS use the four
    band-edge arguments ``f_pass_low_hz``, ``f_pass_high_hz``,
    ``f_stop_low_hz``, ``f_stop_high_hz``.
    """
    if family not in _SUPPORTED:
        raise OrderEstimateError(
            f"order estimation not supported for {family.value}; "
            "use Butterworth, Chebyshev I/II, or Elliptic"
        )
    _validate_ap_as(passband_attenuation_db, stopband_attenuation_db)
    gpass = float(passband_attenuation_db)
    gstop = float(stopband_attenuation_db)

    pass_low: float | None = None
    pass_high: float | None = None
    stop_low: float | None = None
    stop_high: float | None = None

    if response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        if f_pass_hz <= 0.0 or f_stop_hz <= 0.0:
            raise OrderEstimateError("frequencies must be > 0")
        if response == FilterResponse.LOW_PASS:
            if f_stop_hz <= f_pass_hz:
                raise OrderEstimateError("low-pass requires f_stop > f_pass")
            omega_ratio = f_stop_hz / f_pass_hz
        else:
            if f_stop_hz >= f_pass_hz:
                raise OrderEstimateError("high-pass requires f_stop < f_pass")
            omega_ratio = f_pass_hz / f_stop_hz
        wp: float | np.ndarray = 2.0 * math.pi * f_pass_hz
        ws: float | np.ndarray = 2.0 * math.pi * f_stop_hz
        is_band = False
        res_f_pass, res_f_stop = f_pass_hz, f_stop_hz
    elif response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        edges = (f_pass_low_hz, f_pass_high_hz, f_stop_low_hz, f_stop_high_hz)
        if any(e is None for e in edges):
            raise OrderEstimateError(
                "band filters require f_pass_low/high and f_stop_low/high"
            )
        pass_low = float(f_pass_low_hz)  # type: ignore[arg-type]
        pass_high = float(f_pass_high_hz)  # type: ignore[arg-type]
        stop_low = float(f_stop_low_hz)  # type: ignore[arg-type]
        stop_high = float(f_stop_high_hz)  # type: ignore[arg-type]
        if min(pass_low, pass_high, stop_low, stop_high) <= 0.0:
            raise OrderEstimateError("frequencies must be > 0")
        if response == FilterResponse.BAND_PASS:
            if not (stop_low < pass_low < pass_high < stop_high):
                raise OrderEstimateError(
                    "band-pass requires "
                    "f_stop_low < f_pass_low < f_pass_high < f_stop_high"
                )
            omega_ratio = (stop_high - stop_low) / (pass_high - pass_low)
        else:
            if not (pass_low < stop_low < stop_high < pass_high):
                raise OrderEstimateError(
                    "band-stop requires "
                    "f_pass_low < f_stop_low < f_stop_high < f_pass_high"
                )
            omega_ratio = (pass_high - pass_low) / (stop_high - stop_low)
        wp = 2.0 * math.pi * np.array([pass_low, pass_high])
        ws = 2.0 * math.pi * np.array([stop_low, stop_high])
        is_band = True
        res_f_pass, res_f_stop = pass_low, stop_low
    else:
        raise OrderEstimateError(
            "order estimation supports low-pass, high-pass, band-pass, "
            "and band-stop"
        )

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

    wn_arr = np.atleast_1d(np.asarray(wn, dtype=float)) / (2.0 * math.pi)
    nat_low: float | None = None
    nat_high: float | None = None
    if is_band:
        nat_low = float(wn_arr[0])
        nat_high = float(wn_arr[-1])
        natural_freq_hz = math.sqrt(nat_low * nat_high)
        notes += "; band edges are the lowpass prototype corners"
    else:
        natural_freq_hz = float(wn_arr[0])

    return OrderEstimateResult(
        order=order,
        family=family,
        response=response,
        f_pass_hz=res_f_pass,
        f_stop_hz=res_f_stop,
        passband_attenuation_db=gpass,
        stopband_attenuation_db=gstop,
        omega_ratio=float(omega_ratio),
        natural_freq_hz=natural_freq_hz,
        notes=notes,
        f_pass_low_hz=pass_low,
        f_pass_high_hz=pass_high,
        f_stop_low_hz=stop_low,
        f_stop_high_hz=stop_high,
        natural_freq_low_hz=nat_low,
        natural_freq_high_hz=nat_high,
    )
