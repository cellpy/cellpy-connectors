"""Typer group mounted on ``cellpy connectors`` via ``cellpy.cli_plugins``."""

from __future__ import annotations

import typer

PING_MESSAGE = "cellpy-connectors: ok"

app = typer.Typer(
    name="connectors",
    help="Connector commands (test ping for now; configure comes later).",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _connectors() -> None:
    """Connector commands (test ping for now; configure comes later)."""


@app.command()
def ping() -> None:
    """Prove the cellpy CLI plugin hook is alive."""
    typer.echo(PING_MESSAGE)
