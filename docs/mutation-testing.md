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

## First baseline (2026-11-04)

- 199 mutants generated.
- 104 killed.
- 95 survived.
- Mutation score: **52.3 %**.

The largest survivor groups are `ManufacturerModel.from_mapping` (44),
`_interp_log` (21) and `ManufacturerModel.__post_init__` (13). This is a useful
target list for stronger validation tests.

## Next targets

After improving the baseline, add small service modules one at a time:

- `services/coupled_line.py`
- `services/circulator.py`
- `services/part_application.py`
- `analysis/multiport.py`

Do not mutate GUI/Qt/plotting modules in the batch runner; their native
lifecycle is covered by the GUI-stability job.
