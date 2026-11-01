"""Structural validation for LTspice/Qucs schematic exporters.

This does not replace opening the files in the vendor tools. It checks the
generated text for the invariants that the exporters promise: headers, symbol
blocks, instance/value attributes, ports, wires and net flags.
"""

from __future__ import annotations

from dataclasses import dataclass

from filterdesk.domain.circuit import Circuit
from filterdesk.io.qucs import qucs_schematic
from filterdesk.io.spice import ltspice_asc, spice_netlist


@dataclass(frozen=True, slots=True)
class ExportValidationReport:
    ok: bool
    checks: tuple[str, ...]
    issues: tuple[str, ...]

    def summary(self) -> str:
        if self.ok:
            return f"OK ({len(self.checks)} checks)"
        return "; ".join(self.issues)


def validate_ltspice_asc(
    text: str, circuit: Circuit | None = None
) -> ExportValidationReport:
    """Validate the structural contract of an LTspice ``.asc`` export."""
    checks: list[str] = []
    issues: list[str] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != "Version 4":
        issues.append("missing 'Version 4' header")
    else:
        checks.append("header")
    if not any(line.startswith("SHEET ") for line in lines):
        issues.append("missing SHEET")
    else:
        checks.append("sheet")

    symbols: list[str] = []
    attrs: dict[str, set[str]] = {}
    flags = 0
    ac = False
    for line in lines:
        if line.startswith("SYMBOL "):
            parts = line.split()
            if len(parts) < 4:
                issues.append(f"malformed SYMBOL: {line}")
                continue
            symbols.append(parts[1])
        elif line.startswith("SYMATTR InstName "):
            name = line.removeprefix("SYMATTR InstName ").strip()
            attrs.setdefault(name, set()).add("name")
        elif line.startswith("SYMATTR Value "):
            value = line.removeprefix("SYMATTR Value ").strip()
            if not value:
                issues.append("empty SYMATTR Value")
        elif line.startswith("FLAG "):
            flags += 1
        elif line.startswith("TEXT ") and "!.ac " in line:
            ac = True

    if not symbols:
        issues.append("no SYMBOL entries")
    else:
        checks.append("symbols")
    if flags < 2:
        issues.append("fewer than two FLAG net labels")
    else:
        checks.append("flags")
    if not ac:
        issues.append("missing .ac directive")
    else:
        checks.append("ac")
    if any("name" not in values for values in attrs.values()):
        issues.append("symbol without InstName")
    if circuit is not None:
        expected = {element.id for element in circuit.elements}
        missing = sorted(
            ref
            for ref in expected
            if ref not in attrs
            and f"{ref}L" not in attrs
            and f"{ref}C" not in attrs
        )
        if missing:
            issues.append(f"missing component refs: {', '.join(missing)}")
        else:
            checks.append("component refs")
    return ExportValidationReport(
        ok=not issues, checks=tuple(checks), issues=tuple(issues)
    )


def validate_qucs_schematic(
    text: str, circuit: Circuit | None = None
) -> ExportValidationReport:
    """Validate the structural contract of a Qucs ``.sch`` export."""
    checks: list[str] = []
    issues: list[str] = []
    if not text.startswith("<Qucs Schematic "):
        issues.append("missing Qucs Schematic header")
    else:
        checks.append("header")
    for tag in ("<Components>", "</Components>", "<Wires>", "</Wires>"):
        if tag not in text:
            issues.append(f"missing {tag}")
    if not issues:
        checks.append("sections")
    if '<Port P1 ' not in text or '<Port P2 ' not in text:
        issues.append("missing P1/P2 ports")
    else:
        checks.append("ports")
    if circuit is not None:
        expected = {element.id for element in circuit.elements}
        exported: set[str] = set()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("<") or stripped.startswith("</"):
                continue
            parts = stripped[1:].split()
            if len(parts) >= 2 and parts[0] not in {"Port", "GND"}:
                name = parts[1]
                exported.add(name)
                for element in circuit.elements:
                    if name in {element.id, f"{element.id}L", f"{element.id}C"}:
                        exported.add(element.id)
        missing = sorted(ref for ref in expected if ref not in exported)
        if missing:
            issues.append(f"missing component refs: {', '.join(missing)}")
        else:
            checks.append("component refs")
    return ExportValidationReport(
        ok=not issues, checks=tuple(checks), issues=tuple(issues)
    )


def validate_exports(circuit: Circuit) -> ExportValidationReport:
    """Generate and structurally validate LTspice, Qucs and SPICE exports."""
    checks: list[str] = []
    issues: list[str] = []
    for label, report in (
        ("ltspice", validate_ltspice_asc(ltspice_asc(circuit), circuit)),
        ("qucs", validate_qucs_schematic(qucs_schematic(circuit), circuit)),
    ):
        checks.extend(f"{label}:{check}" for check in report.checks)
        issues.extend(f"{label}: {issue}" for issue in report.issues)
    netlist = spice_netlist(circuit)
    if not netlist.strip():
        issues.append("spice: empty netlist")
    else:
        checks.append("spice:netlist")
    return ExportValidationReport(
        ok=not issues, checks=tuple(checks), issues=tuple(issues)
    )


__all__ = [
    "ExportValidationReport",
    "validate_exports",
    "validate_ltspice_asc",
    "validate_qucs_schematic",
]
