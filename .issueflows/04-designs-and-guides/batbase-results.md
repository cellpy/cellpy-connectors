# BatBase results push: check-up readings (M3, results half)

Builds on [batbase-client.md](batbase-client.md) and
[batbase-metadata-source.md](batbase-metadata-source.md). Epic M stage M3 in
jepegit/cellpy#783. BatBase side: `ife-bat/batbase` `runs.readings`,
`runs.processing`, `docs/checkup_readings_api.md`.

## Context

BatBase stores one value per reading per test (`ExperimentObservation` with a
`source`) and plots them per cell. Someone has to load the raw files and post
those values. The metadata adapter already reads the file pointers
(`files[]`, #11).

## Decisions

| Topic | Decision |
| --- | --- |
| Module | `cellpy_connectors/batbase_results.py`; CLI `cellpy connectors batbase process <ids>` |
| What to post | `cellpy.utils.readings.checkup_readings(c)` (in cellpy, explicit units). This package does not pick summary columns itself |
| Where files are | `api/test-experiment/<id>/` `files[]`: `kind=raw`, sorted by `order`, one shared `instrument_loader` (mixed loaders = error) |
| URI → path | `CELLPY_BATBASE_PATH_MAP` / `--path-map`: `prefix=/local;…`, longest prefix first; `file://` and plain paths work without a map; other schemes without a map = error that names the variable |
| Post | `POST api/test-observation/bulk/` with `source` (default `cellpy-checkup`); BatBase upserts on (test, name, source) |
| Errors | per test: reported in `ProcessResult.error`, the batch goes on, exit code 1 if any failed. `BatBaseAuthError` is raised (every test would fail) |
| Token | `CELLPY_BATBASE_TOKEN` / `access_token=`: a pre-issued bearer token, used as is, never refreshed. For BatBase's worker, which runs `process` as the requesting user |
| Not `SupportsMetadataPush` | `register(MetaRecord)` pushes a description; readings are measured values with their own endpoint |
| cellpy dependency | still lazy: imported only when a test is actually loaded |

## Alternatives rejected

- Pick capacity columns here: the base summary column is in the tester's unit
  and `_absolute` in cellpy units; that knowledge belongs in cellpy.
- Use the cellpy journal endpoint: it lists tagged tests only; processing works
  on any test with raw files.
- Retry POST: the bulk endpoint is an upsert, but generic POST retries are off
  in `ApiClientBase` and stay off.
