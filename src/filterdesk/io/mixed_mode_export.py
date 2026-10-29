"""CSV/JSON export helpers for 4-port mixed-mode results."""

from __future__ import annotations

import json
import math

from filterdesk.analysis.four_port import FourPortMixedMode

_CSV_HEADER = "frequency_hz,sdd21_db,sdc21_db,scd21_db,scc21_db"


def _db(value: complex) -> float:
    result = 20.0 * math.log10(max(abs(value), 1e-15))
    return 0.0 if abs(result) < 1e-12 else result


def _rows(report: FourPortMixedMode) -> list[tuple[float, float, float, float, float]]:
    rows: list[tuple[float, float, float, float, float]] = []
    for index, freq in enumerate(report.frequency_hz):
        rows.append(
            (
                float(freq),
                _db(complex(report.sdd[index, 1, 0])),
                _db(complex(report.sdc[index, 1, 0])),
                _db(complex(report.scd[index, 1, 0])),
                _db(complex(report.scc[index, 1, 0])),
            )
        )
    return rows


def mixed_mode_csv(report: FourPortMixedMode) -> str:
    """Return a CSV with frequency and the four mixed-mode 21 terms in dB."""
    lines = [_CSV_HEADER]
    for freq, sdd, sdc, scd, scc in _rows(report):
        lines.append(
            f"{freq:.12g},{sdd:.6f},{sdc:.6f},{scd:.6f},{scc:.6f}"
        )
    return "\n".join(lines) + "\n"


def mixed_mode_json(
    report: FourPortMixedMode, *, source: str | None = None
) -> str:
    """Return a JSON document with references and per-frequency metrics."""
    payload: dict[str, object] = {
        "n_ports": 4,
        "n_points": int(report.frequency_hz.size),
        "z0_ohm": report.z0_single_ended_ohm,
        "z0_diff_ohm": report.z0_diff_ohm,
        "z0_common_ohm": report.z0_common_ohm,
        "points": [
            {
                "frequency_hz": freq,
                "sdd21_db": sdd,
                "sdc21_db": sdc,
                "scd21_db": scd,
                "scc21_db": scc,
            }
            for freq, sdd, sdc, scd, scc in _rows(report)
        ],
    }
    if source is not None:
        payload["source"] = source
    return json.dumps(payload, indent=2) + "\n"


__all__ = ["mixed_mode_csv", "mixed_mode_json"]
