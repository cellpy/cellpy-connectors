# cellpy-connectors

## What this project is

Plugin package that adds connector commands under the `cellpy` CLI (entry-point
group `cellpy.cli_plugins`). Ships `ping`, a credential resolver, `ApiClientBase`,
and `cellpy connectors configure <name>`. BatBase is a later issue.

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
- One top-level CLI slot: entry-point name `connectors`. `ping` and
  `configure` share the Typer `app` in `cellpy_connectors.cli`

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

- No BatBase client yet (#1 / #2). `configure` has nothing to register until then.
- No `cellpy.metadata_sources` entry point (cellpy #784 / this repo #2)
- Credential precedence and the HTTP base: [connector-base.md](connector-base.md)
- No GitHub Actions yet
