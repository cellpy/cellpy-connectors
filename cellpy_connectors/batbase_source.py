"""BatBase as a cellpy ``MetadataSource`` (cellpy/cellpy-connectors#2, Epic M / M2).

Turns rows of BatBase's ``/api/test-cellpy-journal/`` into cellpy
``MetaRecord`` drafts, so ``c.fetch_meta("batbase", ...)`` can pull mass,
area, nominal capacity and friends onto a cell. Transport and auth live in
`cellpy_connectors.batbase.BatBaseClient`; this module holds no credentials.

Registered under the ``cellpy.metadata_sources`` entry-point group as
``batbase``. cellpy discovers it lazily; importing this module does not import
cellpy, and instantiating the source does not touch the network.

Query kinds (``MetaQuery.kind``):

- ``"cell_name"`` (cellpy's default): the journal row whose ``label`` — or,
  failing that, ``name`` (test name) or the cell's ``device_name`` — equals
  ``key``. Matched client-side over the journal listing (cached per source
  for `JOURNAL_CACHE_SECONDS`), because the API has no filter for it yet.
- ``"tag"``: all rows carrying the cellpy tag ``key``. With
  ``MetaQuery.project`` (BatBase project id) the API filters server-side
  (``cellpy_tag__name`` + ``cellpy_tag__project``); without it the tag is
  looked up by name across the projects you can see. A numeric ``key`` is a
  tag id.
- ``"external_id"``: one journal row by id (``/api/test-cellpy-journal/<id>/``).
- ``"test_name"``: rows whose ``name`` equals ``key``.

Anything else → ``()``.

Field map (declarative, tolerant of missing keys — the API currently returns
the experiment's own columns; the mass / area / loading / nom_cap / cell_type
annotations shown in BatBase's journal table are requested on the API in
ife-bat/batbase#473; until they land, records carry what is there):

    BatBase journal row            -> CellMeta / TestMeta
    mass [mg]                      -> mass [mg]
    total_mass [mg]                -> tot_mass [mg]
    area [cm2]                     -> active_electrode_area [cm2]
    loading [mg/cm2]               -> active_electrode_loading
    nom_cap / nominal_capacity_value (+ nominal_capacity_unit)
                                   -> nom_cap [mAh/g | mAh/cm2 | mAh], nom_cap_specifics
    cell_type (hc/fc/3e/sym)       -> cell_type (half_cell/full_cell/…)
    test_mode (n/i) + cell_type    -> cycle_mode (cathode/full/anode)
    label                          -> cell_name
    comments                       -> comment
    test_schedule                  -> schedule_file_name
    instrument                     -> (kept in MetaRecord.raw only; source_type is provenance)
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cellpy_connectors.errors import ConnectorAuthError, ConnectorError

if TYPE_CHECKING:  # pragma: no cover
    from cellpy.readers.metadata_sources import MetaQuery, MetaRecord

    from cellpy_connectors.batbase import BatBaseClient

logger = logging.getLogger(__name__)

SOURCE_NAME = "batbase"
JOURNAL_ENDPOINT = "test-cellpy-journal"
TAG_ENDPOINT = "test-cellpy-tag"

#: How long one source instance reuses a fetched journal listing for
#: client-side matching (``cell_name`` / ``test_name`` / unscoped ``tag``).
JOURNAL_CACHE_SECONDS = 300.0

# -- vocabulary --------------------------------------------------------------

_CELL_TYPES = {
    "hc": "half_cell",
    "fc": "full_cell",
    "3e": "three_electrode",
    "sym": "symmetrical",
}

#: BatBase ``nominal_capacity_unit`` -> (factor to cellpy unit, nom_cap_specifics).
#: cellpy's nominal capacity is mAh/g (gravimetric), mAh/cm2 (areal) or mAh (absolute).
_NOM_CAP_UNITS: dict[str, tuple[float, str]] = {
    "mAh/g": (1.0, "gravimetric"),
    "Ah/g": (1000.0, "gravimetric"),
    "mAh/mg": (1000.0, "gravimetric"),
    "Ah/kg": (1.0, "gravimetric"),
    "mAh/cm2": (1.0, "areal"),
    "Ah/cm2": (1000.0, "areal"),
    "mAh/cm3": (1.0, "volumetric"),
    "Ah/cm3": (1000.0, "volumetric"),
    "mAh": (1.0, "absolute"),
    "Ah": (1000.0, "absolute"),
}


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def journal_row_to_meta(row: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Map one BatBase journal row to ``(cell_fields, test_fields)``.

    Pure and cellpy-free so it can be tested without cellpy installed. Only
    keys with a usable value are emitted (the cellpy contract forbids
    ``None`` placeholders).
    """
    cell: dict[str, Any] = {}
    test: dict[str, Any] = {}

    for source_key, target in (
        ("mass", "mass"),
        ("total_mass", "tot_mass"),
        ("area", "active_electrode_area"),
        ("loading", "active_electrode_loading"),
    ):
        value = _float(row.get(source_key))
        if value is not None:
            cell[target] = value

    nom_cap, specifics = _nominal_capacity(row)
    if nom_cap is not None:
        cell["nom_cap"] = nom_cap
        if specifics:
            cell["nom_cap_specifics"] = specifics

    cell_type_code = _text(row.get("cell_type"))
    cell_type = _CELL_TYPES.get(cell_type_code or "", cell_type_code)
    if cell_type:
        cell["cell_type"] = cell_type

    comment = _text(row.get("comments"))
    if comment:
        cell["comment"] = comment

    label = _text(row.get("label"))
    if label:
        test["cell_name"] = label

    cycle_mode = _cycle_mode(_text(row.get("test_mode")), cell_type_code)
    if cycle_mode:
        test["cycle_mode"] = cycle_mode

    schedule = _text(row.get("test_schedule"))
    if schedule:
        test["schedule_file_name"] = schedule

    # ``instrument`` (the channel's loader) stays in ``raw``: cellpy's
    # ``source_type`` is load provenance the framework stamps, and the
    # contract forbids a source pre-filling it.
    return cell, test


def _nominal_capacity(row: Mapping[str, Any]) -> tuple[float | None, str | None]:
    unit = _text(row.get("nominal_capacity_unit"))
    value = _float(row.get("nominal_capacity_value"))
    if value is None:
        # ``nom_cap`` is the journal-table annotation (experiment value, else
        # the electrode's areal capacity). Trust it only with a known unit.
        value = _float(row.get("nom_cap"))
    if value is None:
        return None, None
    if unit is None:
        return value, None
    conversion = _NOM_CAP_UNITS.get(unit)
    if conversion is None:
        logger.debug("batbase: nominal capacity unit %r not mapped; passing value through", unit)
        return value, None
    factor, specifics = conversion
    return value * factor, specifics


def _cycle_mode(test_mode: str | None, cell_type_code: str | None) -> str | None:
    if test_mode is None:
        return None
    mode = test_mode.lower()
    if mode.startswith("i"):  # "i" / "inverted (anode mode)"
        return "anode"
    if mode.startswith("n"):  # "n" / "normal"
        return "full_cell" if cell_type_code == "fc" else "cathode"
    return None


# -- the source ----------------------------------------------------------------


@dataclass
class _Cached:
    rows: list[dict[str, Any]]
    at: float


class BatBaseMetadataSource:
    """cellpy ``MetadataSource`` over `BatBaseClient`.

    Args:
        client: a configured `BatBaseClient`. Built lazily from the
            environment / keyring on first use when omitted, so the registry
            can instantiate the source without credentials being present.
        client_factory: alternative to ``client``; called once on first use.
        cache_seconds: journal-listing cache lifetime for client-side matches.
    """

    name = SOURCE_NAME

    def __init__(
        self,
        client: BatBaseClient | None = None,
        *,
        client_factory: Callable[[], BatBaseClient] | None = None,
        cache_seconds: float = JOURNAL_CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._client_factory = client_factory
        self.cache_seconds = cache_seconds
        self._clock = clock
        self._journal: _Cached | None = None

    # -- plumbing ---------------------------------------------------------
    @property
    def client(self) -> BatBaseClient:
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                from cellpy_connectors.batbase import BatBaseClient

                self._client = BatBaseClient()
        return self._client

    def invalidate(self) -> None:
        """Drop the cached journal listing."""
        self._journal = None

    def _journal_rows(self) -> list[dict[str, Any]]:
        now = self._clock()
        if self._journal is not None and now - self._journal.at < self.cache_seconds:
            return self._journal.rows
        rows = [r for r in self.client.get_all(JOURNAL_ENDPOINT) if isinstance(r, dict)]
        self._journal = _Cached(rows, now)
        return rows

    def _record(self, row: Mapping[str, Any]) -> MetaRecord:
        from cellpy.readers.metadata_sources import MetaRecord

        cell, test = journal_row_to_meta(row)
        row_id = row.get("id")
        return MetaRecord(
            source_name=self.name,
            external_id=str(row_id) if row_id is not None else None,
            source_uri=(
                f"{self.client.base_url}api/{JOURNAL_ENDPOINT}/{row_id}/" if row_id is not None else None
            ),
            cell=cell,
            test=test,
            raw=dict(row),
        )

    # -- contract ---------------------------------------------------------
    def fetch(self, query: MetaQuery) -> tuple[MetaRecord, ...]:
        """Look up journal rows for ``query``; ``()`` when nothing matches.

        Raises:
            MetadataSourceAuthError: BatBase refused the credentials (never
                swallowed by cellpy's null object).
            MetadataSourceError: BatBase unreachable or answered nonsense
                (cellpy degrades this to an empty layer unless ``strict``).
        """
        from cellpy.readers.metadata_sources import (
            MetadataSourceAuthError,
            MetadataSourceError,
        )

        key = (query.key or "").strip() if query.key is not None else ""
        if not key:
            return ()
        try:
            rows = self._rows_for(query.kind, key, query.project)
        except ConnectorAuthError as exc:
            raise MetadataSourceAuthError(f"batbase: {exc}") from exc
        except ConnectorError as exc:
            raise MetadataSourceError(f"batbase: {exc}") from exc
        return tuple(self._record(row) for row in rows)

    def _rows_for(self, kind: str, key: str, project: str | None) -> list[dict[str, Any]]:
        if kind == "external_id":
            if not key.isdigit():
                return []
            try:
                row = self.client.get(f"{JOURNAL_ENDPOINT}/{key}")
            except ConnectorError as exc:
                if _is_not_found(exc):
                    return []
                raise
            return [row] if isinstance(row, dict) else []

        if kind == "tag":
            return self._rows_for_tag(key, project)

        if kind == "cell_name":
            rows = self._journal_rows()
            hits = [r for r in rows if _text(r.get("label")) == key]
            if not hits:
                hits = [r for r in rows if _text(r.get("name")) == key or _text(r.get("device_name")) == key]
            return hits

        if kind == "test_name":
            return [r for r in self._journal_rows() if _text(r.get("name")) == key]

        logger.debug("batbase: query kind %r not supported", kind)
        return []

    def _rows_for_tag(self, key: str, project: str | None) -> list[dict[str, Any]]:
        if key.isdigit():
            return [r for r in self.client.get_all(JOURNAL_ENDPOINT, cellpy_tag=int(key)) if isinstance(r, dict)]
        if project:
            return [
                r
                for r in self.client.get_all(JOURNAL_ENDPOINT, cellpy_tag__name=key, cellpy_tag__project=project)
                if isinstance(r, dict)
            ]
        # No project scope: resolve the tag name across visible projects.
        tag_ids = [
            t["id"] for t in self.client.get_all(TAG_ENDPOINT) if isinstance(t, dict) and _text(t.get("name")) == key
        ]
        rows: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for tag_id in tag_ids:
            for r in self.client.get_all(JOURNAL_ENDPOINT, cellpy_tag=tag_id):
                if isinstance(r, dict) and r.get("id") not in seen:
                    seen.add(r.get("id"))
                    rows.append(r)
        return rows


def _is_not_found(exc: ConnectorError) -> bool:
    # ``ApiClientBase._raise_for_status`` formats "HTTP 404 from <url>".
    return "HTTP 404 " in str(exc)
