# BatBase client (M0)

Issue: cellpy/cellpy-connectors#1 (Epic M stage 4 in jepegit/cellpy#783).
Builds on [connector-base.md](connector-base.md).

## Context

BatBase is a Django app (DRF API under `/api/`, django-oauth-toolkit under
`/o/`). Its own scripts (`scripts/get_bearer_token.py`,
`get_cellpy_journal_from_tag.py`) authenticate with the client-credentials
grant: `POST /o/token/`, HTTP Basic `client_id:client_secret`, form body
`grant_type=client_credentials&scope=read`. The response has `access_token`
and `expires_in` (default 36000 s); there is **no refresh token**. Hosts:
dev `http://localhost:8000` (anonymous reads allowed when `DJANGO_ENV` is
not production), staging `https://d1-odin-01.ad.ife.no:8500`, production
`https://d1-odin-01.ad.ife.no` (403 without a Bearer token).

## Decision

`cellpy_connectors/batbase.py`:

| Thing | Choice |
| --- | --- |
| Class | `BatBaseClient(ApiClientBase)`; `health_path = "api/"` |
| Host | `base_url` arg → `CELLPY_BATBASE_URL` → `http://localhost:8000` |
| Secrets | `CredentialField`s: `CELLPY_BATBASE_CLIENT_ID` / `CELLPY_BATBASE_CLIENT_SECRET`; keyring service `cellpy-connectors/batbase`, usernames `client_id` / `client_secret` |
| Registry | `ConnectorSpec("batbase", …)` registered on import; `cli._load_builtin_connectors()` imports the module before `configure` |
| Token | fetched lazily on first authenticated request; cached in memory; treated stale 60 s before `expires_in`; `clock` injectable for tests |
| Token POST | sent directly on the session (not via `request()`), so the base's GET-only retry policy is respected and no Bearer header is attached |
| 401 on API | invalidate token, fetch once more, retry once; second 401/403 → `BatBaseAuthError` |
| Token 400/401/403 | `BatBaseAuthError` ("rejected the client credentials…"), secret never echoed |
| No credentials | `BatBaseAuthError` naming both env vars and `cellpy connectors configure batbase`; no network call made |
| Scope | `"read"` default; `"read write"` opt-in (BatBase gates on the `api-write` group) |
| Anonymous | `anonymous=True` / `--anonymous` sends no header; a 401/403 then says "this host requires a token" |
| Read API | `get(endpoint, **params)` → JSON; `get_all` / `iter_rows` follow DRF `results`/`next`; `api_path()` normalises to `api/<x>/` |
| CLI | `cellpy connectors batbase check|get <endpoint> [-p k=v]… [--all] [--url] [--anonymous] [--scope]`; prints JSON; `ConnectorError` → message on stderr, exit 1 |

`BatBaseAuthError` subclasses `ConnectorAuthError`, so callers written
against the base hierarchy keep working.

## Alternatives

- Reuse `requests-oauthlib` / a `BackendApplicationClient` — rejected; one
  POST and a timestamp are simpler than a dependency, and the base session
  keeps its retry adapter.
- Cache the token on disk between processes — rejected; tokens are secrets
  ("no config-file storage of secrets"), and a 10 h token is cheap to refetch.
- Retry 401 indefinitely — rejected; one re-auth distinguishes "token
  revoked" from "credentials wrong" without a loop.
- Typed endpoint methods (`tags()`, `journal()`) — deferred to #2, where the
  `MetadataSource` adapter decides which endpoints cellpy actually needs.

## Manual smoke (no test fixture)

```bash
uv run cellpy connectors batbase check --anonymous            # local dev server
uv run cellpy connectors batbase get project --all --anonymous
CELLPY_BATBASE_CLIENT_ID=bogus CELLPY_BATBASE_CLIENT_SECRET=bogus \
  uv run cellpy connectors batbase check                       # -> "rejected the client credentials"
```
