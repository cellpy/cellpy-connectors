# Issue #3: Shared connector base: credential resolution, ApiClientBase, configure CLI

Source: https://github.com/cellpy/cellpy-connectors/issues/3

## Original issue text

## Context

This package will host several API connectors (BatBase first). Rather than each connector reinventing credential storage, resolution and CLI wiring, provide one shared, minimal base here. This was originally drafted as a cellpy-core change (jepegit/cellpy#1042) and deliberately moved out: core only gains a generic CLI plugin hook (#1042 as slimmed) plus the `MetadataSource` Protocol/registry from jepegit/cellpy#784. Everything below is plugin-package code; `requests`/`keyring` are plain dependencies of this package and never of `import cellpy` (#784 §3.5).

## Tasks

- [ ] Credential resolution with a fixed precedence used by all connectors: explicit constructor argument → environment variable → OS keyring (via the `keyring` package). No plaintext config-file fallback — #784 records "credentials in config files" as a rejected alternative; env vars are the headless/CI/HPC path. Hold secrets as `SecretStr`.
- [ ] A small base class (e.g. `ConnectorConfig` / `ApiClientBase`) that concrete connectors subclass: credential resolution, session/timeouts, retry/backoff, and a common exception hierarchy (`ConnectorError` → `ConnectorAuthError` etc.) so "no credentials configured" and "credentials rejected" are distinct, clearly worded failures rather than raw `requests.HTTPError`.
- [ ] A `check_connection()` diagnostic on the base (mirrors #784 §3.5 and BatBase's `scripts/check_api_connection.py`).
- [ ] CLI: one Click group for this package, mounted into the `cellpy` CLI via the plugin hook from jepegit/cellpy#1042, with a generic `configure <connector>` subcommand (prompts via `getpass`, writes to keyring) that each connector plugs into by declaring which credentials it needs. Decide the command shape here (e.g. `cellpy connectors configure batbase`); the core hook is name-agnostic. Also ship a fallback console script so configuration works even if the installed cellpy predates #1042.
- [ ] Declare the `cellpy.metadata_sources` (from #784) and CLI entry points in `pyproject.toml`.

## Acceptance criteria

A new connector can be built by subclassing the shared base and only implementing its own endpoints/auth flow — no credential storage, error typing or CLI scaffolding from scratch. Installing this package adds its commands to `cellpy` when the plugin hook is present; `import cellpy` alone pulls in none of this package's dependencies.

## Related

- Core hook: jepegit/cellpy#1042
- Parent design: jepegit/cellpy#784
- First consumers: #1 (`BatBaseClient`), #2 (`BatBaseMetadataSource`)
