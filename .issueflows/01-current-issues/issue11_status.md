# Issue #11 status

- [ ] Done

## What's done

- Plan accepted and followed.
- `journal_row_files` maps BatBase `files[]` to `FileRef` kwargs (`instrument_loader` → `loader`, empty `uri` dropped, BatBase order kept, `is_primary=False` raw files included). `_record` passes `files=` into `MetaRecord`.
- Fixtures: `ROW_SAL_010` has files (including an empty uri and a non-primary raw); `ROW_OTHER` has none.
- README, `batbase-metadata-source.md`, `this-project.md`, and the test registry document the map and the cellpy >= 2.1.5.post7 floor. cellpy is still not a runtime dependency.
- `uv run pytest` in this worktree: 82 passed, with cellpy 2.1.5.post7 installed in the worktree env only.

## Remaining work

- Manual live check against a BatBase dev server (none reachable here): create a `TestDataFile` via `/api/test-data-file/`, then `cellpy.get(source="batbase", key=<tag>, kind="tag")` loads without `filefinder`.
- `/iflow-close` still owns the changelog bullet, version bump, commit polish, and the PR. Early PR was left off.
