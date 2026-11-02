# ADR-042: Direct NanoVNA serial sweep import

- **Status:** Accepted
- **Date:** 2026-11-01
- **Relates to:** ADR-005, ADR-007, ADR-040

## Context

FilterDesk could compare and tune against Touchstone captures, but users had to
use another program to read a NanoVNA. Direct support should avoid a manual file
round-trip while keeping provenance and measurement limitations explicit.

NanoVNA-Saver is a useful reference but is licensed **GPL-3.0**; FilterDesk is
Apache-2.0. Copying its implementation would change FilterDesk's licensing
obligations.

## Decision

- Implement an independent minimal client for the NanoVNA console protocol:
  `version`, `help`, `sweep`, `frequencies`, `data 0`, `data 1`, with a
  `scan` mask fallback for firmware that supports it.
- Use `pyserial` (BSD-3-Clause) for serial access and port discovery.
- Add **File → Import → NanoVNA sweep…** with port, baud, start/stop and points.
- Read S11/S21 only. S12/S22 are stored as zero because a NanoVNA 2-port sweep
  does not measure them.
- Use the device's active calibration; do not write calibration data or perform
  in-application calibration.
- Store the sweep in the existing measurement history with model, firmware,
  port, method, timestamp and an explicit "calibration not independently
  verified" note.
- Do not copy NanoVNA-Saver code. Use only the publicly documented command
  protocol and independently written parsers.

## Consequences

- Users can compare or tune directly against a NanoVNA without exporting a
  file first.
- Classic 101-point sweeps use `sweep`; larger or newer devices can fall back to
  `scan` when the firmware advertises it.
- S12/S22, true N-port measurements, calibration writing and vendor-specific
  V2/LiteVNA command variants remain unsupported.
- Hardware validation on real NanoVNA models is still required before claiming
  production confidence.
