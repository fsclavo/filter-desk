# Mutation testing

FilterDesk uses [mutmut](https://github.com/boxed/mutmut) as an optional QA
tool. It is **not** a PR gate: it is slower than the normal suite and is run
manually or from the `mutation` workflow.

## Current scope

The first baseline targets:

`src/filterdesk/components_std/manufacturer_model.py`

and runs only:

`tests/unit/test_manufacturer_model.py`

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

Initial run: 104/199 killed (52.3 %). After targeted validation, exact error
message and interpolation tests:

- 199 mutants generated.
- 187 killed.
- 12 survived.
- Mutation score: **94.0 %**.

The remaining survivors are all in `_interp_log`: mostly equivalent boundary
(`<=` vs `<` at an exact endpoint) or `zip(strict=...)` variants. They are not
behaviorally distinguishable by the public interpolation contract.

## Next targets

After improving the baseline, add small service modules one at a time:

- `services/coupled_line.py`
- `services/circulator.py`
- `services/part_application.py`
- `analysis/multiport.py`

Do not mutate GUI/Qt/plotting modules in the batch runner; their native
lifecycle is covered by the GUI-stability job.
