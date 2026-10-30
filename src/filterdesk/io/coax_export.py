"""CSV export for the coaxial-stub notch response."""

from __future__ import annotations

from filterdesk.components_std.coax import CoaxStubDesign, CoaxStubResponse


def coax_notch_csv(
    design: CoaxStubDesign, response: CoaxStubResponse
) -> str:
    """Return a CSV with metadata comments and S21/S11 versus frequency."""
    if len(response.frequency_hz) != len(response.s21_db) or len(
        response.frequency_hz
    ) != len(response.s11_db):
        raise ValueError("response arrays must have the same length")
    lines = [
        f"# cable={design.cable.name if design.cable else 'custom'}",
        f"# z0_ohm={design.z0_ohm:g}",
        f"# velocity_factor={design.velocity_factor:g}",
        f"# kind={design.kind.value}",
        f"# length_m={design.length_m:.12g}",
        f"# line_z0_ohm={response.line_z0_ohm:g}",
        "frequency_hz,s21_db,s11_db",
    ]
    lines.extend(
        f"{frequency:.12g},{s21:.6f},{s11:.6f}"
        for frequency, s21, s11 in zip(
            response.frequency_hz, response.s21_db, response.s11_db, strict=True
        )
    )
    return "\n".join(lines) + "\n"


__all__ = ["coax_notch_csv"]
