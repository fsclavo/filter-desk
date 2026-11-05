# Mutation testing

FilterDesk uses [mutmut](https://github.com/boxed/mutmut) as an optional QA
tool. It is **not** a PR gate: it is slower than the normal suite and is run
manually or from the `mutation` workflow.

## Current scope

The baseline targets:

- `src/filterdesk/components_std/manufacturer_model.py`
- `src/filterdesk/services/coupled_line.py`
- `src/filterdesk/services/circulator.py`
- `src/filterdesk/analysis/multiport.py`
- `src/filterdesk/services/part_application.py`

and runs the matching unit-test files.

The configuration lives in `[tool.mutmut]` in `pyproject.toml`.

## Run

```bash
uv run mutmut run --max-children 2
uv run mutmut results
uv run mutmut export-cicd-stats
```

`mutants/mutmut-cicd-stats.json` contains the machine-readable score.

The Qt test suite normally hard-exits after pytest to avoid a PySide6 teardown
crash. `tests/unit/conftest.py` skips that hard exit when mutmut sets
`MUTMUT_DEPENDENCY_DEPTH`, so mutmut can collect stats and return normally.

## Baseline (2026-11-04)

Initial `manufacturer_model.py` run: 104/199 killed (52.3 %). After targeted
validation and exact error-message tests: **187/199 killed (94.0 %)**; the 12
remaining mutants are equivalent `_interp_log` boundary/strict-zip variants.

First expanded baseline (three modules):

- 705 mutants generated.
- 503 killed.
- 202 survived.
- Mutation score: **71.3 %**.

After targeted `coupled_line`/`circulator` validation, those three modules reached
**568/705 killed (80.6 %)**.

Latest full configured-scope run (2026-11-05):

- 1573 mutants generated.
- 1516 killed.
- 57 survived.
- 0 without associated tests.
- Mutation score: **96.4 %**.

Survivor groups: `multiport` 33, `manufacturer_model` 9, `coupled_line` 8,
`circulator` 4, `part_application` 3. The remaining mutants are equivalent
variants (explicit vs. implicit NumPy dtypes, `zip(strict=True)` on equal-length
sequences, and unreachable numeric-boundary cases). This is a report-only
baseline; no threshold is enforced.

## Weekly report-only workflow

`.github/workflows/mutation.yml` runs every Monday at 04:00 UTC and can also be
started manually. It:

- runs the configured mutation scope;
- uploads `mutants/mutmut-cicd-stats.json` as the `mutation-stats` artifact;
- writes killed/survived/no-tests/total/score to the GitHub job summary;
- does **not** enforce a score threshold yet.

## Next targets

The current five-module scope is effectively saturated: the 57 survivors are
equivalent mutants, so further score gains require either documenting/excluding
them or expanding the scope to new modules one at a time.

Do not mutate GUI/Qt/plotting modules in the batch runner; their native
lifecycle is covered by the GUI-stability job.
