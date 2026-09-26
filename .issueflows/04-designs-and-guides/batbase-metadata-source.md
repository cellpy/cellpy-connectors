# BatBase MetadataSource adapter (M2)

Issue: cellpy/cellpy-connectors#2 (Epic M stage 4 in jepegit/cellpy#783).
Builds on [batbase-client.md](batbase-client.md) (#1) and cellpy's
`cellpy.readers.metadata_sources` (jepegit/cellpy#784, design note
`metadata-sources.md` in the cellpy repo).

## Context

cellpy's contract: `MetadataSource.fetch(MetaQuery) -> tuple[MetaRecord, ...]`,
records are `CellMeta`/`TestMeta` field mappings plus `external_id` /
`source_uri`; unknown key ⇒ `()`; provenance fields (`source_type`, `uuid`, …)
must not be pre-filled; `None` values are forbidden. BatBase's
`/api/test-cellpy-journal/` is the natural row: one experiment carrying its
cellpy tags, label, nominal capacity and test mode. Its serializer is
`fields="__all__"` on a proxy model, so the journal-table **annotations**
(`mass`, `total_mass`, `area`, `loading`, `nom_cap`, `cell_type`, `user`)
are **not on the API today** — filed as ife-bat/batbase#473.

## Decisions

| Topic | Decision |
| --- | --- |
| Module | `cellpy_connectors/batbase_source.py`; entry point `cellpy.metadata_sources` → `batbase = …:BatBaseMetadataSource` |
| cellpy dependency | still not a runtime dependency: cellpy imported lazily inside `fetch` / `_record`; `journal_row_to_meta` is pure and cellpy-free (testable without cellpy) |
| Client | injected `BatBaseClient` or built lazily on first use from env/keyring (registry instantiates with no args; no network on import/instantiation) |
| Row | one `test-cellpy-journal` row → one `MetaRecord`; `external_id = str(row.id)`, `source_uri = <base>api/test-cellpy-journal/<id>/`, `raw = row` |
| Query kinds | `cell_name` (default): `label`, else `name`, else `device_name`, matched client-side over the cached listing; `tag`: server filter with `project` (`cellpy_tag__name` + `cellpy_tag__project`), numeric key = tag id, unscoped name resolved via `test-cellpy-tag` across visible projects; `external_id`: single row, 404 ⇒ `()`; `test_name`: `name`. Others ⇒ `()` |
| Cache | journal listing cached per source instance for 300 s (`cache_seconds`, `invalidate()`), so batch use does not re-list per cell |
| Field map | `mass`→`mass` (mg), `total_mass`→`tot_mass`, `area`→`active_electrode_area` (cm²), `loading`→`active_electrode_loading` (mg/cm²), `nominal_capacity_value`+`nominal_capacity_unit` → `nom_cap` converted to mAh/g / mAh/cm² / mAh + `nom_cap_specifics` (`nom_cap` annotation as fallback), `cell_type` hc/fc/3e/sym → half_cell/full_cell/three_electrode/symmetrical, `test_mode` i→`anode`, n→`full_cell` (fc) / `cathode`, `label`→`cell_name`, `comments`→`comment`, `test_schedule`→`schedule_file_name` |
| Not mapped | `instrument` (would be `source_type`, which is load provenance), `channel`/`device` pks, `date`, `temperature`, `pressure`, `name` (kept in `raw`) |
| Errors | `ConnectorAuthError` → `MetadataSourceAuthError` (cellpy never swallows); other `ConnectorError` → `MetadataSourceError` (cellpy's `fetch_meta` degrades to `()`) |
| Push | not implemented; `SupportsMetadataPush` deliberately absent (M3, `write` scope) |

## Alternatives rejected

- Query `test-experiment` instead of the journal proxy — the journal
  queryset already restricts to tagged experiments and is what BatBase's own
  cellpy-journal export uses.
- Fetch `device` → electrode masses via `electrode` endpoints to work around
  the missing annotations — duplicates BatBase's `nominal_capacity_from`
  logic client-side; better to expose the annotations once (#473).
- Map `instrument` → `source_type` like `journal_layer` does — contract
  forbids sources filling provenance; the loader owns `source_type`.

## Verify manually

```bash
uv pip install -e ../cellpy        # cellpy with #784
uv run python -c "from cellpy.readers import metadata_sources as ms; print(ms.names())"   # ('batbase',)
uv run python -c "
import cellpy; c = cellpy.get('<raw file>'); print(c.fetch_meta('batbase', '<tag>', kind='tag', project='<id>')); print(c.external_links)"
```
