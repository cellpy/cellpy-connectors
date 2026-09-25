"""Typer group mounted on ``cellpy connectors`` via ``cellpy.cli_plugins``."""

from __future__ import annotations

import typer

PING_MESSAGE = "cellpy-connectors: ok"

app = typer.Typer(
    name="connectors",
    help="Connector commands.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _connectors() -> None:
    """Connector commands."""


@app.command()
def ping() -> None:
    """Prove the cellpy CLI plugin hook is alive."""
    typer.echo(PING_MESSAGE)


@app.command()
def configure(name: str) -> None:
    """Store a connector's credentials in the OS keyring.

    Headless runs should set the connector's environment variables instead
    of calling this command. Values typed here are not printed.
    """
    from cellpy_connectors.credentials import store_secret
    from cellpy_connectors.errors import ConnectorError
    from cellpy_connectors.registry import get, names

    spec = get(name)
    if spec is None:
        known = names()
        if known:
            typer.echo(
                f"Unknown connector {name!r}. Known: {', '.join(known)}",
                err=True,
            )
        else:
            typer.echo(
                f"Unknown connector {name!r}. No connectors are registered.",
                err=True,
            )
        raise typer.Exit(code=1)

    for field in spec.fields:
        value = typer.prompt(field.prompt, hide_input=True)
        try:
            store_secret(field, value)
        except ConnectorError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    typer.echo(f"Stored credentials for {name} in the OS keyring.")
