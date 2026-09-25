"""Unit and optional cellpy-mount tests for the ping connector."""

from __future__ import annotations

import importlib
import subprocess
import sys
from importlib import metadata

import pytest
from typer.testing import CliRunner

from cellpy_connectors.cli import PING_MESSAGE, app
from cellpy_connectors.credentials import CredentialField
from cellpy_connectors.registry import ConnectorSpec, register, unregister

ENTRY_POINT_GROUP = "cellpy.cli_plugins"
ENTRY_POINT_NAME = "connectors"
ENTRY_POINT_VALUE = "cellpy_connectors.cli:app"


def test_package_imports() -> None:
    import cellpy_connectors

    assert cellpy_connectors.__version__


def test_entry_point_is_declared() -> None:
    matches = [
        ep
        for ep in metadata.entry_points(group=ENTRY_POINT_GROUP)
        if ep.name == ENTRY_POINT_NAME
    ]
    assert matches, f"no {ENTRY_POINT_NAME!r} entry in {ENTRY_POINT_GROUP}"
    assert matches[0].value == ENTRY_POINT_VALUE


def test_ping_via_app() -> None:
    result = CliRunner().invoke(app, ["ping"])
    assert result.exit_code == 0, result.output
    assert PING_MESSAGE in result.output


def _cellpy_with_mount():
    cellpy_cli = pytest.importorskip("cellpy.cli")
    cli_plugins = pytest.importorskip("cellpy.cli_plugins")
    if not hasattr(cli_plugins, "CellpyCLIGroup"):
        pytest.skip("cellpy has no CellpyCLIGroup (need #1058 / #1059)")
    return cellpy_cli, cli_plugins


def test_cellpy_help_lists_connectors_without_import() -> None:
    _cellpy_with_mount()
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "from typer.testing import CliRunner\n"
                "from cellpy import cli as cellpy_cli\n"
                "from cellpy import cli_plugins\n"
                "cli_plugins.clear()\n"
                "result = CliRunner().invoke(cellpy_cli.cli, ['--help'])\n"
                "assert result.exit_code == 0, result.output\n"
                "assert 'connectors' in result.output\n"
                "assert 'cellpy_connectors' not in sys.modules\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cellpy_connectors_ping() -> None:
    cellpy_cli, cli_plugins = _cellpy_with_mount()
    cli_plugins.clear()
    result = CliRunner().invoke(cellpy_cli.cli, ["connectors", "ping"])
    assert result.exit_code == 0, result.output
    assert PING_MESSAGE in result.output


def test_import_cellpy_does_not_import_connectors() -> None:
    pytest.importorskip("cellpy")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, cellpy; assert 'cellpy_connectors' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_configure_unknown_name() -> None:
    result = CliRunner().invoke(app, ["configure", "nope"])
    assert result.exit_code == 1, result.output
    assert "No connectors are registered" in result.output


def test_configure_stores_without_echoing_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[tuple[str, str], str] = {}
    field = CredentialField(
        name="token",
        env_var="CELLPY_FAKE_TOKEN",
        keyring_service="cellpy-connectors-test",
        keyring_username="token",
        prompt="Token",
    )
    register(ConnectorSpec(name="fake", fields=(field,)))

    def _store(got: CredentialField, value: str) -> None:
        stored[(got.keyring_service, got.keyring_username)] = value

    monkeypatch.setattr("cellpy_connectors.credentials.store_secret", _store)
    try:
        result = CliRunner().invoke(app, ["configure", "fake"], input="s3cret\n")
    finally:
        unregister("fake")
    assert result.exit_code == 0, result.output
    assert "Stored credentials for fake" in result.output
    assert "s3cret" not in result.output
    assert stored[(field.keyring_service, field.keyring_username)] == "s3cret"


def test_entry_point_loads_typer_app() -> None:
    loaded = importlib.import_module("cellpy_connectors.cli").app
    result = CliRunner().invoke(loaded, ["--help"])
    assert result.exit_code == 0, result.output
    assert "ping" in result.output
