# Issue #4 plan: minimal test connector

## Goal

Make `cellpy-connectors` an installable package that mounts a tiny Typer
group at `cellpy connectors` with a no-I/O `ping` command, so the
`cellpy.cli_plugins` hook can be exercised without BatBase or credentials.

## Constraints

- Match the cellpy contract
  ([`cli-plugins.md`](https://github.com/jepegit/cellpy/blob/master/.issueflows/04-designs-and-guides/cli-plugins.md),
  [writing a CLI plugin](https://github.com/jepegit/cellpy/blob/master/docs/other/writing_a_cli_plugin.md)):
  group `cellpy.cli_plugins`, mount name = entry-point name `connectors`,
  object is a `typer.Typer`.
- No `keyring` / `requests` / BatBase / `ApiClientBase` / `configure`.
- Do **not** add `cellpy` as a runtime dependency (cellpy loads this package,
  not the reverse). `import cellpy_connectors` must work alone.
- `import cellpy` and `cellpy --help` must not import `cellpy_connectors`
  (cellpy lists stubs without `load()`).
- #3 later adds `configure` to this same `app`. One top-level slot only.
- Toolchain: **uv** (sibling cellpy convention). `requires-python >= 3.13`.
- Static version `0.1.0` in `pyproject.toml` (first release; hatchling).
- No GitHub Actions in this issue (repo has none; issue does not ask).

### Prior art

- cellpy entry-point stanza and mount-name rule: `cellpy.cli_plugins` +
  `connectors = "cellpy_connectors.cli:app"` (docs above).
- cellpy live mount (merged #1059): `CellpyCLIGroup` / `attach_plugin_stubs`
  — `--help` lists the name without importing the plugin module; invoke loads
  it. Tests in `tests/test_cli_plugin_mount.py` use `typer.testing.CliRunner`.
- Toolbox: none (empty `00-tools/` index).
- Graph: no `graphify-out/` in this repo.

## Approach

1. **Package bootstrap.** `pyproject.toml` (hatchling), flat
   `cellpy_connectors/` (same layout as cellpy, not `src/`). Runtime dep:
   `typer` only. Dev group: `pytest`. Lock with `uv lock` / `uv sync`.
2. **CLI.** `cellpy_connectors/cli.py` exports `app = typer.Typer(...)` with
   `no_args_is_help=True` and one command `ping` that prints a module-level
   constant (e.g. `PING_MESSAGE = "cellpy-connectors: ok"`) and exits 0.
   `__init__.py` stays empty of typer/heavy imports so a future
   `import cellpy_connectors` stays cheap. No console-script fallback (that
   was #3's old "predates #1042" idea; the hook is already on cellpy master).
3. **Entry point.** Exactly:
   ```toml
   [project.entry-points."cellpy.cli_plugins"]
   connectors = "cellpy_connectors.cli:app"
   ```
4. **Tests** (no BatBase):
   - Always: package imports; `importlib.metadata` sees the entry point;
     `CliRunner().invoke(app, ["ping"])` prints `PING_MESSAGE`, exit 0.
   - Optional integration (skip if `cellpy` missing or has no
     `CellpyCLIGroup`): after `cli_plugins.clear()`, `CliRunner` on
     `cellpy.cli.cli` — `--help` lists `connectors` and does not put
     `cellpy_connectors` in `sys.modules`; `["connectors", "ping"]` exits 0
     and prints the message. Same skip for `import cellpy` not importing us
     (fresh subprocess or import-order assert).
   - Document sibling install in README:
     `uv sync` here, then `uv pip install -e ../cellpy` (or the reverse)
     so the integration test can run locally. Do not commit
     `[tool.uv.sources]` path overrides (cellpy's Dependabot rule; same
     risk here).
5. **Docs.** README: what the package is, install, `cellpy connectors ping`,
   pointer that #3 will extend this group. Fill
   [this-project.md](../04-designs-and-guides/this-project.md) TODOs
   (uv, pytest, 3.13, static 0.1.0, entry `cellpy_connectors.cli:app`).

## Files to touch

| Path | Change |
| --- | --- |
| `pyproject.toml` | **New.** hatchling, metadata, `typer`, entry point, pytest, uv. |
| `uv.lock` | **New.** From `uv lock`. |
| `cellpy_connectors/__init__.py` | **New.** Empty / version only. |
| `cellpy_connectors/cli.py` | **New.** Typer `app` + `ping` + `PING_MESSAGE`. |
| `tests/test_cli.py` | **New.** Unit + skippable cellpy mount tests. |
| `README.md` | Install + ping recipe. |
| `.issueflows/04-designs-and-guides/this-project.md` | Replace TODOs with the toolchain above. |
| `.issueflows/04-designs-and-guides/test-registry.md` | Rows for the new tests (essential-tests guide exists; no config switch on — still record). |

## Test strategy

```bash
uv sync
uv run pytest
```

Integration cases skip unless a cellpy with #1058/#1059 is importable in the
same env. No conda.

## Open questions

None — scope is one package + one command. (CI workflow = later issue.)
