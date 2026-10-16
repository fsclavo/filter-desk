# ADR-002: Project license Apache-2.0; Qt via LGPL PySide6

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

The project must remain open-source and dependency-friendly. NanoVNASaver is GPL-3.0 (inspiration only). PySide6/Qt are LGPL-3.0. scikit-rf is BSD-3-Clause.

## Decision

1. **FilterDesk original source:** Apache-2.0.
2. **GUI binding:** PySide6 (LGPL-3.0), not PyQt6 (GPL/commercial).
3. Ship `LICENSE`, `NOTICE`, and third-party license texts with distributions.
4. **Never copy** proprietary or GPL third-party application code into this tree.

## Consequences

- Downstream projects can relicense more easily than under GPL.
- AppImage/ZIP must preserve LGPL redistribution obligations (dynamic Qt libs, source offer for Qt/PySide6).
- Legal checklist is part of Phase 11 packaging acceptance.
