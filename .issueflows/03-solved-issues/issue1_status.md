# Issue #1 status

- [x] Done

## What's done

- `cellpy_connectors/batbase.py`: `BatBaseClient(ApiClientBase)` with OAuth2
  client-credentials token fetch (`POST o/token/`, HTTP Basic), in-memory token
  cache with expiry margin, one re-auth on 401, `BatBaseAuthError`, credential
  fields on env/keyring, `ConnectorSpec("batbase")` registration, `get` /
  `get_all` / `iter_rows` read passthrough, `whoami` check.
- CLI: `cellpy connectors batbase check|get`; `configure batbase` works through
  the registry (`cli._load_builtin_connectors()`).
- Tests: `tests/test_batbase.py` (27 offline tests, scripted fake session);
  `uv run pytest` → 46 passed, 3 skipped (live cellpy mount tests skip
  without cellpy in the env).
- Manual smoke against the local BatBase dev server: `check --anonymous` 200,
  `get test-cellpy-tag --anonymous` and `get project --all --anonymous` return
  JSON, bogus credentials → `BatBaseAuthError … invalid_client`.
- Docs: README "BatBase" section, `this-project.md`, `connector-base.md`
  registry row, new `batbase-client.md`, test-registry rows.
- No `HISTORY.md` in this repo, so no changelog step.

## Remaining work

None for #1. Follow-ups: #2 (`MetadataSource` adapter + entry point),
jepegit/cellpy#784 (cellpy-side Protocol).
