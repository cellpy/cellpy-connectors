# Issue #2 status

- [x] Done

## What's done

- `cellpy_connectors/batbase_source.py`: `BatBaseMetadataSource` satisfying
  cellpy's `MetadataSource` Protocol; registered via the
  `cellpy.metadata_sources` entry point (`batbase`); lazy client; per-instance
  journal cache (300 s); query kinds `cell_name` / `tag` / `external_id` /
  `test_name`; `journal_row_to_meta` field + unit + vocabulary map;
  `ConnectorAuthError → MetadataSourceAuthError` (never swallowed),
  other `ConnectorError → MetadataSourceError` (cellpy degrades to `()`).
- Tests: `tests/test_batbase_source.py` (29; 20 need cellpy #784 and skip
  otherwise). `uv run pytest` with sibling cellpy installed: 78 passed.
- Live smoke against the local BatBase dev server through the real entry
  point: `ms.names() == ('batbase',)`; `cell_name` / `tag` / `external_id`
  (404) queries all return `()` cleanly on the empty DB; `c.fetch_meta("batbase")`
  leaves the cell untouched.
- BatBase API gap (journal annotations `mass`/`area`/`loading`/`nom_cap`/
  `cell_type` and name filters not on `/api/test-cellpy-journal/`) filed as
  ife-bat/batbase#473; the mapping already reads those keys.
- Docs: README "As a cellpy metadata source", `this-project.md`,
  `batbase-metadata-source.md`, test registry.

## Remaining work

None in this repo for M2. Acceptance in full (BatBase mass on a loaded cell
against a real server) needs ife-bat/batbase#473 deployed and a tagged
experiment in the DB — the offline end-to-end test covers the cellpy side.
Follow-ups: M3 push (2.3), cellpy/cellpy-core#151.
