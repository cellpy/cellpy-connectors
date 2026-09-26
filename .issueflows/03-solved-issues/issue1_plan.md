# Plan: #1 BatBaseClient (M0)

Yolo-labelled; run under the maintainer's "start M0" instruction.

## Goal

A user who created a BatBase API client can run `cellpy connectors configure batbase`
once and then call any BatBase read endpoint from Python (`BatBaseClient.get`) or the
CLI (`cellpy connectors batbase get <endpoint>`) without handling tokens.

## Approach

- `cellpy_connectors/batbase.py`
  - `BatBaseAuthError(ConnectorAuthError)` for "no credentials configured" and
    "credentials rejected".
  - `CredentialField`s for client id / secret: env `CELLPY_BATBASE_CLIENT_ID` /
    `CELLPY_BATBASE_CLIENT_SECRET`, keyring service `cellpy-connectors/batbase`.
    `ConnectorSpec("batbase", …)` registered at import so `configure batbase` works.
  - `BatBaseClient(ApiClientBase)`: `base_url` from arg → `CELLPY_BATBASE_URL` →
    `http://localhost:8000`; `scope="read"` default; `anonymous=False` flag for the
    local dev server (no token). Token: `POST o/token/` with HTTP Basic auth,
    `grant_type=client_credentials`, cached in memory with `expires_in` (60 s safety
    margin); one re-auth + retry on 401; then `BatBaseAuthError`.
  - `get(endpoint, **params) -> Any` (JSON under `api/`), `get_all(endpoint, **params)`
    following DRF `next`/`results` pagination, `check_connection()` on `api/`.
- `cli.py`: `batbase` sub-app — `get <endpoint> [-p k=v]… [--all] [--url] [--anonymous]`
  prints JSON; `check [--url] [--anonymous]`.
- Tests (offline, fake session): token request shape, cache, expiry refetch, 401
  re-auth once then error, no-credentials error names the env var, anonymous mode,
  `get`/`get_all`, path normalisation, registry spec, CLI `get`/`check`.
- Docs: README section, `this-project.md`, `batbase-client.md` design note,
  test-registry rows.

## Out of scope

`MetadataSource` adapter (#2), push/`write` scope beyond passing it through, cellpy-side
Protocol (jepegit/cellpy#784).
