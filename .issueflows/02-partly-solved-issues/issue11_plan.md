# Plan: #11 BatBase `files[]` → `MetaRecord.files`

## Goal

Map BatBase journal `files[]` onto cellpy `FileRef`s so `cellpy.get(source="batbase", …)` can open those URIs directly. A row with no `files` stays `files=()`.

## Constraints

- cellpy stays **not** a runtime dependency. The pin is documentary: file pointers need **cellpy >= 2.1.5.post7** (jepegit/cellpy#1119, the release that shipped `FileRef`, including `location`). That same post also shipped `metadata_sources` (#784), so a released cellpy that already runs this adapter accepts `files=`.
- Do not switch the shared `/workspace/cellpy` checkout (detached at 2.1.5.post5, no `FileRef`). Conformance runs install `cellpy>=2.1.5.post7` into **this worktree's** env.
- `journal_row_to_meta` stays the cell/test map. File pointers are a sibling helper, not new `CellMeta` fields.
- `instrument` on the journal row stays in `raw` only (provenance). A file's `instrument_loader` is a different field and becomes `FileRef.loader`.
- Live BatBase calls stay manual. Pytest stays offline.
- One PR. No split.

### Prior art

- `journal_row_to_meta` in `cellpy_connectors/batbase_source.py` — coexist. New `journal_row_files` next to it; `_record` calls both.
- `FileRef.from_dict` (cellpy `contract.py`) reads `loader`, not `instrument_loader`. Do not pass the raw BatBase dict through `MetaRecord.files` and rely on coercion.
- `validate_record` / `check_metadata_source` already check `files` (kind ∈ {raw, cellpy, processed, other}, non-empty uri, no duplicate uri). No cellpy kit change. `ROW_SAL_010` is the conformance `known` row, so giving it `files` exercises that check.
- `MetaRecord.raw_files()` sorts by `order`; `cellpy_file()` is the first `kind="cellpy"` in tuple order.
- Toolbox (`.issueflows/00-tools/`): none. No `graphify-out/`.

## Approach

1. **`journal_row_files(row) -> tuple[dict, ...]`** — pure, cellpy-free. Read `row.get("files")`. Missing / `None` / not a list → `()`. Skip non-mappings and entries whose `uri` is empty after strip. Keep BatBase order (do not sort).
   - `kind` → `kind` (stripped; unknown kinds pass through so `validate_record` fails loudly).
   - `uri` → `uri`.
   - `order` → `int(order or 0)` (same as `FileRef.from_dict`).
   - `size` / `mtime` / `checksum` passthrough; blank text → omit (`None`).
   - `instrument_loader` → `loader`.
   - `location` → `location`.
   - **`is_primary` is not a `FileRef` field.** Include `is_primary=False` raw files; they are ordered parts of the set. (ife-bat/batbase#478 is not readable with this token; the issue spec is the decision.)
   - Duplicate URIs are kept; `validate_record` rejects them.
2. **`_record`** builds `FileRef(**kwargs)` from that tuple and passes `files=` into `MetaRecord`. Import `FileRef` lazily next to `MetaRecord`.
3. **Fixtures.** `ROW_SAL_010` gets a `files` list: two raw URIs (one `is_primary=False`), one `.cellpy`, one empty-uri entry that must be dropped. `ROW_OTHER` has no `files` key.
4. **Docs.** README example `cellpy.get(source="batbase", key="SAL_010", kind="tag")` plus the minimum cellpy version. Design note records the map and the `is_primary` choice. `this-project.md` notes the post7 floor.

## Files to touch

- `cellpy_connectors/batbase_source.py` — `journal_row_files`; `_record(..., files=...)`.
- `tests/test_batbase_source.py` — cellpy-free mapping tests; cellpy tests for `raw_files()` order, `cellpy_file()`, `loader`, and `files == ()`.
- `README.md` — "BatBase tells cellpy where the files are" example and `>= 2.1.5.post7`.
- `.issueflows/04-designs-and-guides/batbase-metadata-source.md` — file map, `is_primary`, pin.
- `.issueflows/04-designs-and-guides/this-project.md` — minimum cellpy for file pointers.
- `.issueflows/04-designs-and-guides/test-registry.md` — new rows.

## Test strategy

```bash
uv sync
uv pip install -e 'cellpy @ git+https://github.com/jepegit/cellpy.git@v2.1.5.post7'
uv run pytest
```

Use this worktree's env only. Offline assertions:

- Row with `files`: `raw_files()` URIs follow `order`; `cellpy_file().uri` is the `.cellpy`; each `loader` equals that entry's `instrument_loader`; the `is_primary=False` raw URI is present; the empty `uri` is absent.
- Row without `files`: `files == ()`.
- Existing `check_metadata_source` still passes (`known` = SAL_010, which now has files).

Manual, not pytest: against a BatBase dev server, after a `TestDataFile` row exists, `cellpy.get(source="batbase", key=<tag>, kind="tag")` loads without `filefinder`. Record the result in the status file. If no server is reachable, the issue stays `- [ ] Done` on that acceptance line until it is run.

## Open questions

None. Mapping, `is_primary`, and the docs-only pin follow the issue spec and the released `FileRef` contract.
