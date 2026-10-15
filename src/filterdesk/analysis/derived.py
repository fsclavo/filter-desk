"""Derived RF metrics from S-parameters."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.types import AnalysisResult


def mag_db(s: NDArray[np.complexfloating]) -> NDArray[np.float64]:
    mag = np.abs(s)
    with np.errstate(divide="ignore"):
        out = 20.0 * np.log10(np.maximum(mag, 1e-30))
    return np.asarray(out, dtype=np.float64)


def insertion_loss_db(result: AnalysisResult) -> NDArray[np.float64]:
    """IL = -20 log10(|S21|)."""
    return np.asarray(-mag_db(result.s21), dtype=np.float64)


def return_loss_db(result: AnalysisResult, port: int = 1) -> NDArray[np.float64]:
    """RL = -20 log10(|Sii|)."""
    s = result.s11 if port == 1 else result.s22
    return np.asarray(-mag_db(s), dtype=np.float64)


def vswr(result: AnalysisResult, port: int = 1) -> NDArray[np.float64]:
    gamma = np.abs(result.s11 if port == 1 else result.s22)
    gamma = np.minimum(gamma, 0.999999999)
    return np.asarray((1.0 + gamma) / (1.0 - gamma), dtype=np.float64)


def phase_deg(s: NDArray[np.complexfloating]) -> NDArray[np.float64]:
    return np.asarray(np.angle(s, deg=True), dtype=np.float64)


def phase_rad(s: NDArray[np.complexfloating]) -> NDArray[np.float64]:
    return np.asarray(np.angle(s, deg=False), dtype=np.float64)


def group_delay_s(
    frequency_hz: NDArray[np.floating],
    s21: NDArray[np.complexfloating],
) -> NDArray[np.float64]:
    """Group delay τ = −(1/2π) d∠S21/df  (seconds)."""
    phase = np.unwrap(np.angle(s21))
    dphase_df = np.gradient(phase, frequency_hz)
    return np.asarray(-dphase_df / (2.0 * np.pi), dtype=np.float64)


def attach_group_delay(result: AnalysisResult) -> NDArray[np.float64]:
    return group_delay_s(result.frequency_hz, result.s21)
