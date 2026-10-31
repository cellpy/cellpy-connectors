# Issue #11: BatBase adapter: map experiment files[] to MetaRecord.files (FileRef)

Source: https://github.com/cellpy/cellpy-connectors/issues/11

## Original issue text

## Context

cellpy #1107 (jepegit/cellpy#1119) added `MetaRecord.files: tuple[FileRef, ...]` — `FileRef(kind, uri, order=0, size=None, mtime=None, checksum=None, loader=None, location=None)`, `kind ∈ {raw, cellpy, processed, other}`. `cellpy.get(source="batbase", key=…, kind="tag")` and `batch.from_source("batbase", tag)` open those files directly and only fall back to `filefinder` when a record has none.

BatBase (ife-bat/batbase#478) exposes `files: [{kind, uri, location, order, is_primary, size, mtime, checksum, instrument_loader}]` on `/api/test-cellpy-journal/` and `/api/experiment/`.

## Spec

- `batbase_source._record(row)` maps `row["files"]` → `FileRef`s: `kind`→`kind`, `uri`→`uri`, `order`→`order`, `size`/`mtime`/`checksum` passthrough, `instrument_loader`→`loader`, `location`→`location`. Skip entries with empty `uri`; keep BatBase order. Rows without `files` (older servers) ⇒ `files=()`.
- `is_primary=False` raw files are still included (they are ordered parts of the set) unless BatBase semantics say otherwise — document the choice.
- Conformance: `check_metadata_source` now validates `files` via `validate_record`; fixtures in `tests/` get `files` on at least one row, one row without.
- README / design note: "BatBase tells cellpy where the files are" example with `cellpy.get(source="batbase", key="SAL_010", kind="tag")`.
- Requires the cellpy pin to include #1119 (next cellpy release / `>=` the version that ships it).

## Acceptance

- A journal row with `files` yields a record where `record.raw_files()` has the raw URIs in `order` and `record.cellpy_file()` the `.cellpy` one; `loader` equals `instrument_loader`.
- A row without `files` yields `files == ()` and the conformance kit still passes.
- Live check against a BatBase dev server (after a `TestDataFile` row is created via `/api/test-data-file/`): `cellpy.get(source="batbase", key=<tag>, kind="tag")` loads without `filefinder`.

## Related

jepegit/cellpy#1107, ife-bat/batbase#474 / #478, cellpy/cellpy-connectors#2.
