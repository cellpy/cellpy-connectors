# <img src="cellpy-icon-bw.svg" height="40" alt="cellpy-icon"> cellpy-connectors

Pluggable connectors for [cellpy](https://github.com/jepegit/cellpy).

This repo mounts a Typer group on the cellpy CLI (`cellpy connectors`).
It includes a no-I/O `ping` command, a shared base connectors subclass
(credential resolution: argument, then environment, then OS keyring;
`ApiClientBase`; `cellpy connectors configure <name>`), and the first real
connector: **BatBase** (`BatBaseClient` + `cellpy connectors batbase …`) and
its cellpy `MetadataSource` adapter (`BatBaseMetadataSource`, entry point
`cellpy.metadata_sources`).

## Install next to cellpy

From a checkout next to `cellpy`:

```bash
cd cellpy-connectors
uv sync
# optional: live mount tests need a cellpy that includes #1058 / #1059
uv pip install -e ../cellpy
```

Or install this package into cellpy's environment:

```bash
cd cellpy
uv pip install -e ../cellpy-connectors
```

Do not commit a `[tool.uv.sources]` path override.

## Ping

With both packages installed:

```bash
uv run cellpy connectors ping
```

Prints `cellpy-connectors: ok` and exits 0. `cellpy --help` lists `connectors`
without importing this package.

## Configure

`configure` writes secrets to the OS keyring. It only accepts connector names
that have registered a spec (currently `batbase`):

```bash
uv run cellpy connectors configure batbase
```

Prompts are hidden and the values are not printed. On a machine with no
keyring (CI, HPC), set the connector's environment variables instead. Resolution
order for every secret is: explicit argument, environment variable, OS keyring.
Secrets are never read from a config file.

## BatBase

BatBase (IFE's cell-testing metadata database) exposes a DRF API under `/api/`
and issues OAuth2 client-credentials tokens at `/o/token/`. Create an API
client in BatBase (user menu → API credentials), then either

```bash
uv run cellpy connectors configure batbase          # id + secret -> OS keyring
# or, headless:
export CELLPY_BATBASE_CLIENT_ID=... CELLPY_BATBASE_CLIENT_SECRET=...
export CELLPY_BATBASE_URL=https://d1-odin-01.ad.ife.no   # default: http://localhost:8000
```

Then:

```bash
uv run cellpy connectors batbase check                       # token + GET /api/
uv run cellpy connectors batbase get test-cellpy-tag -p search=SAL_010
uv run cellpy connectors batbase get project --all           # follow pagination
uv run cellpy connectors batbase get '' --anonymous          # API index on a local dev server
```

From Python:

```python
from cellpy_connectors.batbase import BatBaseClient

bb = BatBaseClient()                       # host from $CELLPY_BATBASE_URL
page = bb.get("test-cellpy-journal", search="SAL_010")   # one DRF page (dict)
rows = bb.get_all("test-batch")                          # every row (list)
```

### As a cellpy metadata source

With a cellpy that has `cellpy.readers.metadata_sources` (jepegit/cellpy#784),
this package registers BatBase under the `cellpy.metadata_sources` entry point,
so a cell can pull its lab metadata directly:

```python
import cellpy

c = cellpy.get("20240101_SAL_010_cc_01.res")
c.fetch_meta("batbase")                              # key defaults to c.cell_name (journal label)
c.fetch_meta("batbase", "SAL_010", kind="tag", project="3")   # every test under a cellpy tag
c.fetch_meta("batbase", "42", kind="external_id")    # one journal row by id
c.external_links["batbase"]                          # ExternalLink(external_id="42", source_uri=…)
```

Mapping (`cellpy_connectors.batbase_source.journal_row_to_meta`): journal
`mass`/`total_mass`/`area`/`loading` → `CellMeta.mass`/`tot_mass`/
`active_electrode_area`/`active_electrode_loading`; `nominal_capacity_value` +
unit → `nom_cap` in mAh/g (or mAh/cm², mAh) + `nom_cap_specifics`; `cell_type`
`hc/fc/3e/sym` → `half_cell/full_cell/…`; `test_mode` → `cycle_mode`
(`anode` / `cathode` / `full_cell`); `label` → `cell_name`; `comments`,
`test_schedule`. BatBase unreachable ⇒ cellpy logs a warning and the cell
loads without the layer; rejected credentials raise
`MetadataSourceAuthError`. The mass/area/loading/cell_type columns are not on
the API yet (ife-bat/batbase#473); until then records carry the experiment's
own fields (label, nominal capacity, test mode, schedule, comments).

Tokens are fetched with the `read` scope, cached in memory until shortly before
they expire, and refreshed once automatically if BatBase answers 401. Missing
or rejected credentials raise `BatBaseAuthError` with the fix in the message.
`--anonymous` / `anonymous=True` skips authentication; only a local dev server
(`DJANGO_ENV` not production) allows that. Pass `scope="read write"` (or
`--scope`) to request write access; BatBase grants it only to members of its
`api-write` group. See
[`.issueflows/04-designs-and-guides/batbase-client.md`](.issueflows/04-designs-and-guides/batbase-client.md).

## Tests

```bash
uv sync
uv run pytest
```

Tests that invoke the live `cellpy` CLI, or the cellpy `MetadataSource`
contract, skip if cellpy is missing or predates the plugin mount / #784.

## Python

3.13+. Day-to-day toolchain is **uv** (`uv sync`, `uv run pytest`).
