# Issue #4 status

- [x] Done

## What's done

- Package bootstrap: `pyproject.toml`, `uv.lock`, `cellpy_connectors` (hatchling, static 0.1.0).
- Typer `app` with group callback + `ping` (`PING_MESSAGE = "cellpy-connectors: ok"`).
- Entry point `connectors = "cellpy_connectors.cli:app"`.
- Tests: 7 passed (`uv run pytest`). Live mount tests skip without cellpy `CellpyCLIGroup`.
- README + `this-project.md` + test-registry rows.

## Remaining work

- None.
