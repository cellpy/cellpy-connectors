# Connector base

**Issue:** cellpy-connectors#3

## Context

Several API connectors will live in this package. Credential storage, HTTP
session policy, and `configure` should exist once. BatBase (#1) is the first
consumer and must not reimplement them.

## Decision

| Rule | Value |
| --- | --- |
| Secret precedence | explicit argument → environment variable → OS keyring |
| Secret type | pydantic `SecretStr` (not imported from cellpy) |
| Config files | never |
| CLI | `cellpy connectors configure <name>` on the existing Typer `app` |
| Console script | none (the cellpy plugin hook is already on master; #4) |
| `cellpy.metadata_sources` | not declared here; #2 registers the adapter |
| HTTP | `requests` session, timeout 10s |
| Retry | 3 attempts, backoff 0.5, statuses 429/500/502/503/504, methods GET/HEAD/OPTIONS |
| 401/403 | `ConnectorAuthError` |
| Missing secret | `ConnectorCredentialsError` |
| Other HTTP / network | `ConnectorError` |
| Registry | empty until a connector calls `register` |

Headless machines skip `configure` and set environment variables. A missing
keyring backend is "not stored", not a crash, when resolving. Storing still
fails with a message that names the env var.

## Alternatives

- Click group and a fallback console script — written in the original #3
  text, dropped after #4 shipped the Typer plugin on `cellpy.cli_plugins`.
- Declare `cellpy.metadata_sources` with no adapter — rejected; #2 owns that
  entry point.
- Retry POST — rejected; token fetches in #1 must opt in so a failed POST is
  not sent twice by the base.
