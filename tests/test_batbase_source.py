"""BatBase ``MetadataSource`` adapter (#2). Offline: a fake BatBaseClient.

The mapping tests need no cellpy. The contract / conformance / end-to-end
tests skip when cellpy (with ``cellpy.readers.metadata_sources``, jepegit/cellpy#784)
is not importable in this environment — install the sibling checkout with
``uv pip install -e ../cellpy`` to run them.
"""

from __future__ import annotations

import importlib.util
from typing import Any

import pytest

from cellpy_connectors.batbase_source import (
    JOURNAL_ENDPOINT,
    TAG_ENDPOINT,
    BatBaseMetadataSource,
    journal_row_to_meta,
)
from cellpy_connectors.errors import ConnectorAuthError, ConnectorError

HAS_CELLPY = importlib.util.find_spec("cellpy") is not None and (
    importlib.util.find_spec("cellpy.readers.metadata_sources") is not None
)
needs_cellpy = pytest.mark.skipif(not HAS_CELLPY, reason="cellpy with metadata_sources (#784) not installed")

BASE = "https://batbase.test/"

# What /api/test-cellpy-journal/ returns today (serializer = model fields) plus
# the journal-table annotations we asked BatBase to expose on the API.
ROW_SAL_010 = {
    "id": 42,
    "cellpy_tag": [{"id": 7, "name": "SAL_010", "project": 3, "user": 1}],
    "name": "20240101_SAL_010_cc_01",
    "code": "cc_01",
    "date": "2024-01-01",
    "comments": "first formation",
    "test_schedule": "sal_formation_v2.sdu",
    "status": "done",
    "label": "SAL_010",
    "nominal_capacity_value": 3.579,
    "nominal_capacity_unit": "Ah/g",
    "nominal_capacity_from": "negative_electrode",
    "test_mode": "i",
    "channel": 12,
    "device": 88,
    # annotations (not yet on the API):
    "mass": 1.2345,
    "total_mass": 2.5,
    "area": 1.767,
    "loading": 0.6987,
    "cell_type": "hc",
    "device_name": "SAL_010_cell",
    "instrument": "arbin_res",
}
ROW_OTHER = {
    "id": 43,
    "cellpy_tag": [{"id": 8, "name": "SAL_011", "project": 3}],
    "name": "20240102_SAL_011_cc_01",
    "label": "SAL_011",
    "test_mode": "n",
    "cell_type": "fc",
    "nominal_capacity_value": 150,
    "nominal_capacity_unit": "mAh/g",
}


class FakeBatBase:
    """Just enough of ``BatBaseClient`` for the adapter: ``get`` / ``get_all``."""

    base_url = BASE

    def __init__(self, rows: list[dict[str, Any]] | None = None, tags: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows if rows is not None else [ROW_SAL_010, ROW_OTHER]
        self.tags = tags if tags is not None else [
            {"id": 7, "name": "SAL_010", "project": 3},
            {"id": 8, "name": "SAL_011", "project": 3},
            {"id": 9, "name": "SAL_010", "project": 4},
        ]
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.fail_with: Exception | None = None

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def get(self, endpoint: str, **params: Any) -> Any:
        self.calls.append(("get", endpoint, params))
        self._check()
        head, _, ident = endpoint.rstrip("/").rpartition("/")
        if head == JOURNAL_ENDPOINT and ident.isdigit():
            for row in self.rows:
                if row["id"] == int(ident):
                    return row
            raise ConnectorError(f"HTTP 404 from {BASE}api/{endpoint}/")
        raise ConnectorError(f"HTTP 404 from {BASE}api/{endpoint}/")

    def get_all(self, endpoint: str, **params: Any) -> list[Any]:
        self.calls.append(("get_all", endpoint, params))
        self._check()
        if endpoint == TAG_ENDPOINT:
            return list(self.tags)
        if endpoint == JOURNAL_ENDPOINT:
            rows = list(self.rows)
            if "cellpy_tag" in params:
                rows = [r for r in rows if any(t["id"] == params["cellpy_tag"] for t in r.get("cellpy_tag", []))]
            if "cellpy_tag__name" in params:
                rows = [
                    r
                    for r in rows
                    if any(
                        t["name"] == params["cellpy_tag__name"] and str(t.get("project")) == str(params["cellpy_tag__project"])
                        for t in r.get("cellpy_tag", [])
                    )
                ]
            return rows
        return []


@pytest.fixture
def fake() -> FakeBatBase:
    return FakeBatBase()


@pytest.fixture
def source(fake: FakeBatBase) -> BatBaseMetadataSource:
    return BatBaseMetadataSource(client=fake)


# -- mapping (no cellpy needed) ------------------------------------------------


def test_journal_row_maps_cell_and_test_fields() -> None:
    cell, test = journal_row_to_meta(ROW_SAL_010)
    assert cell == {
        "mass": 1.2345,
        "tot_mass": 2.5,
        "active_electrode_area": 1.767,
        "active_electrode_loading": 0.6987,
        "nom_cap": pytest.approx(3579.0),  # Ah/g -> mAh/g
        "nom_cap_specifics": "gravimetric",
        "cell_type": "half_cell",
        "comment": "first formation",
    }
    assert test == {
        "cell_name": "SAL_010",
        "cycle_mode": "anode",
        "schedule_file_name": "sal_formation_v2.sdu",
    }


def test_journal_row_without_annotations_still_yields_what_is_there() -> None:
    cell, test = journal_row_to_meta(ROW_OTHER)
    assert cell == {"nom_cap": 150.0, "nom_cap_specifics": "gravimetric", "cell_type": "full_cell"}
    assert test == {"cell_name": "SAL_011", "cycle_mode": "full_cell"}


def test_mapping_never_emits_none_or_blank() -> None:
    cell, test = journal_row_to_meta({"id": 1, "mass": None, "label": "  ", "comments": "", "test_mode": None})
    assert cell == {} and test == {}


@pytest.mark.parametrize(
    ("unit", "value", "expected", "specifics"),
    [
        ("mAh/g", 150, 150.0, "gravimetric"),
        ("Ah/g", 3.5, 3500.0, "gravimetric"),
        ("mAh/mg", 0.15, 150.0, "gravimetric"),
        ("mAh/cm2", 2.0, 2.0, "areal"),
        ("Ah", 0.002, 2.0, "absolute"),
        ("mAh", 2.0, 2.0, "absolute"),
    ],
)
def test_nominal_capacity_units_convert_to_cellpy(unit, value, expected, specifics) -> None:
    cell, _ = journal_row_to_meta({"nominal_capacity_value": value, "nominal_capacity_unit": unit})
    assert cell["nom_cap"] == pytest.approx(expected)
    assert cell["nom_cap_specifics"] == specifics


def test_unknown_capacity_unit_passes_value_without_specifics() -> None:
    cell, _ = journal_row_to_meta({"nominal_capacity_value": 3.0, "nominal_capacity_unit": "Wh"})
    assert cell == {"nom_cap": 3.0}


def test_nom_cap_annotation_is_fallback_only() -> None:
    cell, _ = journal_row_to_meta({"nom_cap": 2.5, "nominal_capacity_unit": "mAh/cm2"})
    assert cell == {"nom_cap": 2.5, "nom_cap_specifics": "areal"}
    cell, _ = journal_row_to_meta({"nom_cap": 2.5, "nominal_capacity_value": 100, "nominal_capacity_unit": "mAh/g"})
    assert cell["nom_cap"] == 100.0


@pytest.mark.parametrize(
    ("test_mode", "cell_type", "expected"),
    [("i", "hc", "anode"), ("n", "hc", "cathode"), ("n", "fc", "full_cell"), ("normal", None, "cathode"), ("x", "hc", None)],
)
def test_cycle_mode_vocabulary(test_mode, cell_type, expected) -> None:
    _, test = journal_row_to_meta({"test_mode": test_mode, "cell_type": cell_type})
    assert test.get("cycle_mode") == expected


# -- source plumbing (no cellpy needed) ----------------------------------------


def test_source_is_lazy_about_the_client() -> None:
    built: list[int] = []

    def factory():
        built.append(1)
        return FakeBatBase()

    source = BatBaseMetadataSource(client_factory=factory)
    assert built == []
    assert source.client is source.client
    assert built == [1]


def test_journal_listing_is_cached_per_instance(fake: FakeBatBase) -> None:
    clock = {"now": 0.0}
    source = BatBaseMetadataSource(client=fake, cache_seconds=100, clock=lambda: clock["now"])
    source._journal_rows()
    source._journal_rows()
    assert len(fake.calls) == 1
    clock["now"] = 150.0
    source._journal_rows()
    assert len(fake.calls) == 2
    source.invalidate()
    source._journal_rows()
    assert len(fake.calls) == 3


# -- contract, needs cellpy ----------------------------------------------------


@needs_cellpy
def test_satisfies_the_cellpy_protocol(source: BatBaseMetadataSource) -> None:
    from cellpy.readers.metadata_sources import MetadataSource, SupportsMetadataPush

    assert isinstance(source, MetadataSource)
    assert not isinstance(source, SupportsMetadataPush)  # push is out of scope (#2)
    assert source.name == "batbase"


@needs_cellpy
def test_entry_point_is_declared() -> None:
    from importlib.metadata import entry_points

    eps = {ep.name: ep.value for ep in entry_points(group="cellpy.metadata_sources")}
    assert eps.get("batbase") == "cellpy_connectors.batbase_source:BatBaseMetadataSource"


@needs_cellpy
def test_conformance_kit_passes(source: BatBaseMetadataSource) -> None:
    from cellpy.readers.metadata_sources import MetaQuery
    from cellpy.readers.metadata_sources.testing import check_metadata_source

    records = check_metadata_source(
        source,
        known=MetaQuery(key="SAL_010", kind="tag", project="3"),
        unknown=MetaQuery(key="does-not-exist", kind="tag", project="3"),
    )
    (record,) = records
    assert record.external_id == "42"
    assert record.source_uri == f"{BASE}api/{JOURNAL_ENDPOINT}/42/"
    assert record.cell["mass"] == 1.2345
    assert record.raw["name"] == "20240101_SAL_010_cc_01"


@needs_cellpy
def test_cell_name_matches_label_then_name_then_device(source: BatBaseMetadataSource) -> None:
    from cellpy.readers.metadata_sources import MetaQuery

    assert [r.external_id for r in source.fetch(MetaQuery(key="SAL_010"))] == ["42"]
    assert [r.external_id for r in source.fetch(MetaQuery(key="20240102_SAL_011_cc_01"))] == ["43"]
    assert [r.external_id for r in source.fetch(MetaQuery(key="SAL_010_cell"))] == ["42"]
    assert source.fetch(MetaQuery(key="nope")) == ()
    assert source.fetch(MetaQuery(key="")) == ()
    assert source.fetch(MetaQuery(key=None)) == ()


@needs_cellpy
def test_tag_queries_use_server_filters_when_possible(source: BatBaseMetadataSource, fake: FakeBatBase) -> None:
    from cellpy.readers.metadata_sources import MetaQuery

    source.fetch(MetaQuery(key="SAL_010", kind="tag", project="3"))
    assert fake.calls[-1] == ("get_all", JOURNAL_ENDPOINT, {"cellpy_tag__name": "SAL_010", "cellpy_tag__project": "3"})

    source.fetch(MetaQuery(key="7", kind="tag"))
    assert fake.calls[-1] == ("get_all", JOURNAL_ENDPOINT, {"cellpy_tag": 7})

    # unscoped name: tags resolved by name across projects, rows de-duplicated
    fake.calls.clear()
    records = source.fetch(MetaQuery(key="SAL_010", kind="tag"))
    assert fake.calls[0] == ("get_all", TAG_ENDPOINT, {})
    assert {c[2].get("cellpy_tag") for c in fake.calls[1:]} == {7, 9}
    assert [r.external_id for r in records] == ["42"]


@needs_cellpy
def test_external_id_fetches_one_row_and_404_is_empty(source: BatBaseMetadataSource) -> None:
    from cellpy.readers.metadata_sources import MetaQuery

    (record,) = source.fetch(MetaQuery(key="43", kind="external_id"))
    assert record.test["cell_name"] == "SAL_011"
    assert source.fetch(MetaQuery(key="999", kind="external_id")) == ()
    assert source.fetch(MetaQuery(key="abc", kind="external_id")) == ()


@needs_cellpy
def test_unknown_kind_is_empty(source: BatBaseMetadataSource) -> None:
    from cellpy.readers.metadata_sources import MetaQuery

    assert source.fetch(MetaQuery(key="x", kind="serial")) == ()


@needs_cellpy
def test_auth_errors_become_cellpy_auth_errors(source: BatBaseMetadataSource, fake: FakeBatBase) -> None:
    from cellpy.readers.metadata_sources import (
        MetadataSourceAuthError,
        MetaQuery,
        fetch_meta,
    )

    fake.fail_with = ConnectorAuthError("BatBase rejected the client credentials")
    with pytest.raises(MetadataSourceAuthError, match="rejected"):
        source.fetch(MetaQuery(key="SAL_010"))
    # and cellpy's null object does not hide it
    with pytest.raises(MetadataSourceAuthError):
        fetch_meta(source, "SAL_010")


@needs_cellpy
def test_unreachable_batbase_is_an_empty_layer_via_cellpy(source: BatBaseMetadataSource, fake: FakeBatBase, caplog) -> None:
    from cellpy.readers.metadata_sources import (
        MetadataSourceError,
        MetaQuery,
        fetch_meta,
    )

    fake.fail_with = ConnectorError("Request to https://batbase.test/api/ failed: timeout")
    with pytest.raises(MetadataSourceError, match="timeout"):
        source.fetch(MetaQuery(key="SAL_010"))
    import logging

    with caplog.at_level(logging.WARNING):
        assert fetch_meta(source, "SAL_010") == ()
    assert "timeout" in caplog.text


@needs_cellpy
def test_records_validate_against_cellpy_contract(source: BatBaseMetadataSource) -> None:
    from cellpy.readers.metadata_sources import MetaQuery, validate_record

    for record in source.fetch(MetaQuery(key="SAL_010", kind="tag", project="3")):
        validate_record(record)


@needs_cellpy
def test_end_to_end_cell_fetch_meta_applies_batbase_mass(source: BatBaseMetadataSource) -> None:
    """The M2 acceptance criterion, offline: a tagged cell picks up BatBase mass."""
    cellpy = pytest.importorskip("cellpy")
    from cellpy.readers import metadata_sources as ms
    from cellpy.readers.cellreader import CellpyCell

    ms.clear_registry()
    ms.register(source)
    try:
        c = CellpyCell(initialize=True)
        c.cell_name = "SAL_010"
        records = c.fetch_meta("batbase")
        assert len(records) == 1
        assert c.data.meta_common.mass == pytest.approx(1.2345)
        assert c.data.meta_common.nom_cap == pytest.approx(3579.0)
        assert c.data.meta_common.active_electrode_area == pytest.approx(1.767)
        assert c.cycle_mode == "anode"
        link = c.external_links["batbase"]
        assert link.external_id == "42" and link.source_uri.endswith("/test-cellpy-journal/42/")
    finally:
        ms.clear_registry()
    del cellpy
