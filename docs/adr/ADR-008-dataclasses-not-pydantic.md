# ADR-008: Spec validation with dataclasses + explicit validators (not Pydantic)

- **Status:** Accepted
- **Date:** 2026-03-29
- **Phase:** 0

## Context

Blueprint left open: Pydantic v2 vs dataclasses for `FilterSpec` / project documents.

## Decision

Use **`dataclasses`** (stdlib) plus small explicit validation functions / discriminated unions via `Literal` + factory helpers.

Revisit Pydantic only if JSON schema export or complex validation pain appears.

## Rationale

- Fewer dependencies in the math/domain core.
- Adequate for versioned JSON via `dataclasses.asdict` + manual loaders.
- Keeps domain importable without pydantic in constrained environments.

## Consequences

- Slightly more hand-written validation code.
- Native JSON schema may be documented in Markdown rather than auto-generated.
