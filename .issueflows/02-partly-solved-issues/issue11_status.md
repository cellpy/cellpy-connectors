# Issue #11 status

- [ ] Done

## What's done

- Plan accepted and followed.
- `journal_row_files` maps BatBase `files[]` to `FileRef` kwargs (`instrument_loader` → `loader`, empty `uri` dropped, BatBase order kept, `is_primary=False` raw files included). `_record` passes `files=` into `MetaRecord`.
- Fixtures: `ROW_SAL_010` has files (including an empty uri and a non-primary raw); `ROW_OTHER` has none.
- README, `batbase-metadata-source.md`, `this-project.md`, and the test registry document the map and the cellpy >= 2.1.5.post7 floor. cellpy is still not a runtime dependency.
- Close sanity check: `uv run pytest` 82 passed against cellpy 2.1.5.post7 in this worktree. No version bump (none requested, issue has no `publish` label). Changelog trailers are on the close commit. `HISTORY.md` was not edited.

## Remaining work

- Manual live check against a BatBase dev server (none reachable here): create a `TestDataFile` via `/api/test-data-file/`, then `cellpy.get(source="batbase", key=<tag>, kind="tag")` loads without `filefinder`.
