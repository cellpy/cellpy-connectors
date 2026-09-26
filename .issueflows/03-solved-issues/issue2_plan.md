# Plan: #2 BatBase MetadataSource adapter (M2)

Non-yolo (mapping decisions against an unsettled API). Executed after the
maintainer merged jepegit/cellpy#1106 (M1); the PR is the review point and is
**not** auto-merged.

## Approach

- `cellpy_connectors/batbase_source.py`: `BatBaseMetadataSource` (`name =
  "batbase"`, `fetch(query)`), lazy `BatBaseClient`, journal-listing cache,
  pure `journal_row_to_meta(row) -> (cell, test)`; error translation
  `ConnectorAuthError → MetadataSourceAuthError`, `ConnectorError →
  MetadataSourceError`.
- Entry point `cellpy.metadata_sources: batbase = …:BatBaseMetadataSource`.
- Query kinds: `cell_name` (label → name → device_name, client-side),
  `tag` (+`project` server-side; numeric = tag id; unscoped resolved via
  `test-cellpy-tag`), `external_id`, `test_name`.
- Tests: mapping (cellpy-free), plumbing, and cellpy-dependent contract /
  conformance-kit / end-to-end `CellpyCell.fetch_meta` (skip without cellpy).
- Docs: README, `this-project.md`, `batbase-metadata-source.md`, test registry.
- BatBase side: file the API gap (annotations + filters) as an ife-bat/batbase
  issue; keep the mapping tolerant so it needs no change when it lands.

## Out of scope

Push (`SupportsMetadataPush`, M3), `batch.from_source`, BattINFO vocabulary
beyond the cell_type / cycle_mode codes, `CellMeta.uuid` (cellpy/cellpy-core#151).
