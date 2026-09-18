# Issue #4: Add a minimal test connector so the cellpy CLI plugin hook can be exercised

Source: https://github.com/cellpy/cellpy-connectors/issues/4

## Original issue text

## Problem / context

`cellpy-connectors` is still an empty repo (README + license). cellpy now discovers and mounts third-party commands from the `cellpy.cli_plugins` entry-point group (jepegit/cellpy#1042 / #1055 / #1058). This package is the first intended consumer, but #1–#3 are the real BatBase + credential stack.

We need a tiny, installable connector we can use in tests and locally: prove that installing this package adds a command to `cellpy`, without keyring, HTTP, or BatBase.

## Spec

- Bootstrap a minimal installable package (`pyproject.toml`, `cellpy_connectors` importable).
- Ship a small `typer.Typer` app (not Click — matches the cellpy contract).
- Declare it under `[project.entry-points."cellpy.cli_plugins"]` as `connectors = "cellpy_connectors.cli:app"` (mount name is the entry-point name).
- One no-I/O subcommand, e.g. `ping`, that prints a fixed string and exits 0. No credentials, no network, no `ApiClientBase`.
- Tests that do not need BatBase: package imports; entry point is declared; with cellpy installed, `cellpy --help` lists `connectors` and `cellpy connectors ping` succeeds.
- README: how to install editable next to cellpy and run the ping command.

#3 later adds `configure` (and the shared base) to this same Typer app. Do not invent a second top-level mount name.

## Acceptance criteria

- `uv pip install -e .` (or equivalent) from this repo succeeds.
- `cellpy --help` lists `connectors` when this package is installed next to a cellpy that has #1058.
- `cellpy connectors ping` exits 0 and prints the fixed string.
- `import cellpy` still does not import this package.
- No `keyring` / `requests` / BatBase dependency in this issue.

## Out of scope

- #3 credential resolution, `ApiClientBase`, `configure`, keyring.
- #1 `BatBaseClient`, #2 `BatBaseMetadataSource`.
- `cellpy.metadata_sources` entry point (that is #784 / #2).

## Related

- Contract: jepegit/cellpy `cellpy.cli_plugins` (docs: `.issueflows/04-designs-and-guides/cli-plugins.md`).
- Does **not** depend on #1, #2, or #3. #3 should extend this CLI group.
