# ADR-004: Native project format is versioned JSON

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

Need a human-readable, extensible, native project file. Candidates: JSON, YAML, TOML, SQLite, binary.

## Decision

- Native format: **JSON** (UTF-8), extension **`.filterdesk.json`** (also accept `.fdsk.json`).
- Required top-level field: `format_version` (integer, currently `2`; v1 files
  remain readable after the ADR-018 distributed-element addition).
- Unknown fields preserved under `extensions` where practical for forward compatibility.
- Heavy sweep arrays are **not** stored by default; optional cache later.
- `.lct` is an interchange format only — never the internal model.

## Consequences

- Simple schema evolution and golden fixtures in-repo.
- YAML rejected to avoid subtle type/anchor issues; TOML poor for nested numeric arrays.
