# ADR-040: System measurement comparison with a 2-port VNA

- **Status:** Accepted
- **Date:** 2026-10-30
- **Relates to:** ADR-027, ADR-028, ADR-029, ADR-030, ADR-031

## Context

Most radio amateurs have a 2-port VNA, not an N-port analyzer. A diplexer or
duplexer can still be characterized as several 2-port paths by terminating the
unused ports in 50 Ω.

## Decision

- Compare measured 2-port captures against simulated system paths:
  - common → each output;
  - adjacent output ↔ output isolation paths when applicable.
- Each capture is a `.s2p` file from the first port to the second; all other
  system ports are terminated in 50 Ω.
- For each path, build a simulated `AnalysisResult` from the combined network:
  - S21 = S[to, from];
  - S11 = S[from, from].
- Reuse `compare_results` for frequency alignment and S21/S11 RMS/max error.
- Expose **Compare measurements…** in the system designer. The dialog lists
  paths, file pickers and per-path errors.
- This is not a true N-port VNA measurement and does not measure simultaneous
  matching/isolation under arbitrary loads.

## Consequences

- Users can validate a real diplexer/duplexer with an ordinary 2-port VNA.
- Missing paths can be left unassigned; available paths are compared.
- The method assumes the unused ports are terminated in the reference impedance.
- Full N-port measurement and calibration remain future work.
