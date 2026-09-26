# cellpy-connectors

## What this project is

Plugin package that adds connector commands under the `cellpy` CLI (entry-point
group `cellpy.cli_plugins`). Ships `ping`, a credential resolver, `ApiClientBase`,
`cellpy connectors configure <name>`, and the BatBase connector
(`cellpy_connectors.batbase.BatBaseClient`, `cellpy connectors batbase check|get`).

## Stack / runtime

- Python >= 3.13
- Package manager: **uv** (`uv sync`, `uv run`, `uv lock`)
- Build: hatchling; static version in `pyproject.toml`
- CLI: Typer (`cellpy_connectors.cli:app`)
- No conda for day-to-day work

## How to run / test

```bash
uv sync
uv run pytest
```

Live `cellpy connectors …` tests skip unless a cellpy with `CellpyCLIGroup`
(#1058 / #1059) is importable in the same env. Install sibling cellpy with
`uv pip install -e ../cellpy` after `uv sync`. Do not commit
`[tool.uv.sources]` path overrides.

## Conventions

- Issue branches: `<N>-<short-slug>`
- Conventional Commits; squash-merge on GitHub
- `cellpy` is not a runtime dependency of this package
- One top-level CLI slot: entry-point name `connectors`. `ping`,
  `configure` and the `batbase` sub-app share the Typer `app` in
  `cellpy_connectors.cli`
- Shipped connectors register their `ConnectorSpec` on import;
  `cli._load_builtin_connectors()` imports them before `configure` looks up
  a name. Add new connectors there.
- Live smoke tests against BatBase are manual (local dev server on
  `http://localhost:8000` with `--anonymous`); the pytest suite is offline.

## Release & version bump

- **Static version (uv):** `[project] version` lives in `pyproject.toml`
  (currently `0.1.0`). Bump with `uv version --bump <level>` before the
  release commit.

## Entry points

- Package: `cellpy_connectors`
- CLI: `cellpy_connectors.cli:app`
- Plugin declaration: `[project.entry-points."cellpy.cli_plugins"]`
  `connectors = "cellpy_connectors.cli:app"`

## Non-goals / known limitations

- BatBase is read-only in practice: `BatBaseClient` exposes `get`/`get_all`
  (#1); no push helpers. `write` scope can be requested but nothing uses it.
- No `cellpy.metadata_sources` entry point (cellpy #784 / this repo #2)
- Credential precedence and the HTTP base: [connector-base.md](connector-base.md);
  BatBase specifics: [batbase-client.md](batbase-client.md)
- No GitHub Actions yet
