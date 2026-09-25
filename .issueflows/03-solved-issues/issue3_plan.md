# Issue #3 plan: shared connector base

## Goal

Give every future connector one credential resolver, one HTTP base, and one
`cellpy connectors configure <name>` command, so #1 (`BatBaseClient`) only
adds BatBase's token and endpoints.

## Constraints

- Toolchain: **uv** (`uv sync`, `uv run pytest`). Python >= 3.13. `cellpy` is
  not a runtime dependency. `import cellpy` must not import this package
  ([this-project.md](../04-designs-and-guides/this-project.md)).
- One CLI slot. `configure` is a command on the existing Typer `app` in
  [`cellpy_connectors/cli.py`](../../cellpy_connectors/cli.py)
  (`connectors = "cellpy_connectors.cli:app"`). The issue text says Click;
  #4 and cellpy's `cli-plugins.md` already chose Typer. Do not add a second
  mount name.
- No fallback console script. #4 recorded that the "predates #1042" script is
  obsolete: the plugin hook is on cellpy master.
- Do **not** declare `cellpy.metadata_sources`. There is no adapter yet; that
  entry point is #2. The CLI entry point already exists from #4.
- No BatBase client, OAuth, or `/o/token/` (#1). No `MetadataSource` (#2).
- Secrets: precedence is explicit argument → environment variable → OS keyring.
  No config-file or URL storage
  ([metadata design](https://github.com/jepegit/cellpy-design-and-development/blob/master/active/cellpy2-metadata-source-integration.md)
  §3.5 and rejected alternatives). Hold values as pydantic `SecretStr` (same
  type cellpy uses; this package must not import cellpy to get it).
- `requests` and `keyring` are dependencies of this package only.
- Keep `cellpy_connectors/__init__.py` free of those imports so a plain import
  stays cheap. `ping` behaviour stays as it is.

### Prior art

- `ping` + Typer `app`: [`cellpy_connectors/cli.py`](../../cellpy_connectors/cli.py)
  — **extend** (add `configure`); do not replace the group.
- Entry point and mount tests: [`tests/test_cli.py`](../../tests/test_cli.py)
  — **coexist**; new tests sit beside them. Keep the "help does not import
  `cellpy_connectors`" and `import cellpy` assertions.
- cellpy `SecretStr` + env resolution: `cellpy/config/credentials.py` — **mirror
  the idea** (one resolver, secrets not in config files). Do not import it.
  Precedence here adds keyring, which cellpy's resolver does not have.
- Toolbox: none (`00-tools/` index empty).
- Graph: no `graphify-out/` in this repo.

## Approach

1. **Errors** (`cellpy_connectors/errors.py`).
   - `ConnectorError` — transport / unexpected HTTP.
   - `ConnectorCredentialsError` — nothing resolved (distinct message: no
     credentials configured).
   - `ConnectorAuthError(ConnectorError)` — credentials were present and the
     server rejected them (401/403), distinct from a missing secret and from
     `requests.HTTPError`.

2. **Credentials** (`cellpy_connectors/credentials.py`).
   - `CredentialField`: `name`, `env_var`, `keyring_service`, `keyring_username`,
     `prompt`.
   - `resolve_secret(explicit, field) -> SecretStr`:
     1. explicit `str` / `SecretStr` if non-empty;
     2. `os.environ[field.env_var]` if set;
     3. `keyring.get_password(service, username)` if a backend exists;
     4. else `ConnectorCredentialsError` naming the env var and the configure
        command.
   - `NoKeyringError` (and backend errors on read) count as "not in keyring",
     not a crash, so CI with env vars still works.
   - `store_secret(field, value)` writes via `keyring.set_password`. Never log
     or return the raw secret from CLI output.

3. **Registry** (`cellpy_connectors/registry.py`).
   - `ConnectorSpec(name, fields: tuple[CredentialField, ...])`.
   - `register` / `get` / `names`. Empty in production. #1 will register
     `batbase`. Tests register a fake spec and unregister in a fixture.
   - Specs are data only. The HTTP subclass lives with the connector (#1),
     not in the registry.

4. **HTTP base** (`cellpy_connectors/client.py`).
   - `ApiClientBase(base_url, *, timeout=10.0, session=None)`.
   - `requests.Session` with `HTTPAdapter` + urllib3 `Retry`: 3 attempts,
     `backoff_factor=0.5`, status 429/500/502/503/504, methods GET/HEAD/OPTIONS
     only (no automatic POST retry; token fetch in #1 must opt in).
   - `request(method, path, **kwargs)` joins `base_url`, applies timeout, and
     maps:
     - 401/403 → `ConnectorAuthError` (body snippet, no secrets);
     - other `HTTPError` → `ConnectorError`;
     - `requests.RequestException` (network) → `ConnectorError`.
   - `check_connection()` GETs `health_path` (subclass attribute, default
     `""` meaning the base URL) and returns the response. Same error mapping.
     Subclasses override `health_path` or the method. This issue's tests use a
     `requests` mock / stubbed transport, not a live server.

5. **CLI.** On the existing `app`:
   - `configure NAME` looks up the spec. Unknown name exits non-zero and lists
     known names (or says none are registered).
   - For each field, `typer.prompt(..., hide_input=True)` then `store_secret`.
   - Prints `Stored credentials for <name> in the OS keyring.` and never the
     values.
   - Headless path is the env-var step in `resolve_secret`, not a second
     configure mode. Users with env vars do not need to run `configure`.
   - Update the group help that still says "configure comes later".
   - `ping` stays unchanged.

6. **Deps.** `uv add pydantic keyring requests` (runtime). Lockfile updated.
   Dev group stays `pytest` only; mock HTTP with `unittest.mock` or a
   `requests` transport adapter, no extra test dependency.

7. **Design note** (during build):
   `.issueflows/04-designs-and-guides/connector-base.md` — precedence, Typer
   command shape, why no console script and no `metadata_sources` entry yet,
   link to #3.

## Files to touch

| Path | Change |
| --- | --- |
| `cellpy_connectors/errors.py` | **New.** Exception hierarchy. |
| `cellpy_connectors/credentials.py` | **New.** Field spec, resolve, keyring store. |
| `cellpy_connectors/registry.py` | **New.** `ConnectorSpec` + register/get. |
| `cellpy_connectors/client.py` | **New.** `ApiClientBase`, timeout, retry, `check_connection`. |
| `cellpy_connectors/cli.py` | Add `configure`; refresh help text. |
| `pyproject.toml`, `uv.lock` | Add `pydantic`, `keyring`, `requests`. |
| `tests/test_credentials.py` | **New.** Precedence, missing secret, keyring miss, no secret in repr. |
| `tests/test_client.py` | **New.** Retry not asserted against a live host; map 401 vs network vs 500; `check_connection`. |
| `tests/test_cli.py` | `configure` unknown name; fake spec + prompt stores via a fake keyring. `ping` tests stay. |
| `README.md` | `configure` shape and env-var fallback. Still no BatBase onboarding (that is #1). |
| `.issueflows/04-designs-and-guides/this-project.md` | Drop the "no keyring / ApiClientBase yet" line; keep metadata entry point as #2. |
| `.issueflows/04-designs-and-guides/test-registry.md` | Rows for the new tests. |
| `.issueflows/04-designs-and-guides/connector-base.md` | **New.** Decision note. |

## Test strategy

```bash
uv sync
uv run pytest
```

All new tests are offline: monkeypatched keyring, stubbed `requests` session.
Existing cellpy-mount tests still skip unless `CellpyCLIGroup` is importable.
No conda.

## Open questions

None. Stale lines in the GitHub issue (Click group, console-script fallback,
`cellpy.metadata_sources` entry point) are treated as superseded by #4 and
[this-project.md](../04-designs-and-guides/this-project.md). Revise if those
should be implemented literally instead.
