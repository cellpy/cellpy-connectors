"""Offline tests for processing BatBase tests and posting readings. No network, no cellpy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cellpy_connectors import cli
from cellpy_connectors.batbase import BatBaseAuthError
from cellpy_connectors.batbase_results import (
    ProcessingError,
    local_path,
    parse_path_map,
    process_test,
    raw_files,
    readings_payload,
)


@dataclass(frozen=True)
class FakeReading:
    name: str
    value: float
    unit: str
    cycle: int | None = None
    note: str = ""


class FakeClient:
    def __init__(self, rows, fail_post=None):
        self.rows = rows
        self.posted = []
        self.fail_post = fail_post

    def get(self, endpoint, **params):
        test_id = int(endpoint.rstrip("/").rsplit("/", 1)[-1])
        return self.rows[test_id]

    def post(self, endpoint, payload):
        if self.fail_post:
            raise self.fail_post
        self.posted.append((endpoint, payload))
        return {"created": len(payload["readings"]), "updated": 0, "readings": []}


def _row(*files):
    return {"id": 7, "files": list(files)}


def _file(uri, kind="raw", order=0, loader="pec_csv"):
    return {"uri": uri, "kind": kind, "order": order, "instrument_loader": loader}


def test_path_map_longest_prefix_wins():
    mapping = parse_path_map("smb://share=/a; smb://share/raw=/b ;")
    assert local_path("smb://share/raw/x/Test1.csv", mapping) == Path("/b/x/Test1.csv")
    assert local_path("smb://share/other.csv", mapping) == Path("/a/other.csv")
    assert local_path("file:///data/T%201.csv", []) == Path("/data/T 1.csv")
    assert local_path("/plain/path.csv", []) == Path("/plain/path.csv")
    with pytest.raises(ProcessingError, match="CELLPY_BATBASE_PATH_MAP"):
        local_path("smb://unmapped/x.csv", [])
    with pytest.raises(ValueError):
        parse_path_map("no-equals-sign")


def test_raw_files_keep_order_skip_other_kinds_and_need_one_loader():
    row = _row(
        _file("b.csv", order=2),
        _file("a.csv", order=1),
        _file("x.cellpy", kind="cellpy", loader=""),
        _file("  ", order=0),
    )
    assert raw_files(row) == (["a.csv", "b.csv"], "pec_csv")
    with pytest.raises(ProcessingError, match="different loaders"):
        raw_files(_row(_file("a.res", loader="arbin_res"), _file("b.csv")))


def test_readings_payload_carries_cycle_in_text():
    items = readings_payload(7, [FakeReading("capacity", 1.5, "Ah", 3, "discharge"), FakeReading("ocv", 3.6, "V")])
    assert items == [
        {"experiment": 7, "name": "capacity", "value": 1.5, "unit": "Ah", "text": "cycle 3: discharge"},
        {"experiment": 7, "name": "ocv", "value": 3.6, "unit": "V", "text": ""},
    ]


def test_process_posts_readings_with_the_source(tmp_path):
    raw = tmp_path / "Test1.csv"
    raw.write_text("x")
    client = FakeClient({7: _row(_file("smb://share/Test1.csv"))})
    loaded = []

    result = process_test(
        client,
        7,
        source="cellpy-checkup",
        path_map=parse_path_map(f"smb://share={tmp_path}"),
        load=lambda paths, loader: loaded.append((paths, loader)) or "cell",
        extract=lambda cell: [FakeReading("ocv", 3.57, "V", 1)],
    )

    assert result.ok, result.error
    assert loaded == [([raw], "pec_csv")]
    endpoint, payload = client.posted[0]
    assert endpoint == "test-observation/bulk"
    assert payload["source"] == "cellpy-checkup"
    assert payload["readings"][0]["value"] == 3.57


def test_dry_run_posts_nothing(tmp_path):
    (tmp_path / "a.csv").write_text("x")
    client = FakeClient({7: _row(_file(str(tmp_path / "a.csv")))})
    result = process_test(client, 7, dry_run=True, path_map=[], load=lambda p, l: "c", extract=lambda c: [FakeReading("ocv", 1, "V")])
    assert result.ok and result.readings and not client.posted


@pytest.mark.parametrize(
    "row, message",
    [
        (_row(), "no raw files"),
        (_row(_file("/nowhere/a.csv", loader="")), "instrument_loader"),
        (_row(_file("/nowhere/a.csv")), "not found"),
    ],
)
def test_problems_are_reported_not_raised(row, message):
    result = process_test(FakeClient({7: row}), 7, path_map=[])
    assert not result.ok
    assert message in result.error


def test_auth_errors_are_raised(tmp_path):
    (tmp_path / "a.csv").write_text("x")
    client = FakeClient({7: _row(_file(str(tmp_path / "a.csv")))}, fail_post=BatBaseAuthError("no write scope"))
    with pytest.raises(BatBaseAuthError):
        process_test(client, 7, path_map=[], load=lambda p, l: "c", extract=lambda c: [FakeReading("ocv", 1, "V")])


def test_cli_process_reports_each_test_and_fails_if_one_failed(monkeypatch, tmp_path):
    (tmp_path / "a.csv").write_text("x")
    client = FakeClient({7: _row(_file(str(tmp_path / "a.csv"))), 8: _row()})
    monkeypatch.setattr(cli, "_client", lambda url, anonymous, scope: client)
    # process_test binds its loader at definition time; wrap the function the CLI imports.
    import cellpy_connectors.batbase_results as results

    original = results.process_test
    monkeypatch.setattr(
        results,
        "process_test",
        lambda *a, **k: original(*a, load=lambda p, l: "cell", extract=lambda c: [FakeReading("ocv", 3.5, "V")], **k),
    )

    outcome = CliRunner().invoke(cli.app, ["batbase", "process", "7", "8", "--json", "--path-map", ""])

    lines = [json.loads(line) for line in outcome.stdout.splitlines() if line.startswith("{")]
    assert outcome.exit_code == 1
    assert [(line["test_id"], line["ok"]) for line in lines] == [(7, True), (8, False)]
    assert client.posted[0][1]["readings"][0]["name"] == "ocv"


def test_zero_or_negative_mass_from_batbase_is_left_out():
    from cellpy_connectors.batbase_source import journal_row_to_meta

    cell, _test = journal_row_to_meta({"mass": 0.0, "total_mass": -1, "area": 1.5, "loading": 0})
    assert cell == {"active_electrode_area": 1.5}
