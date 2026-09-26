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

    _load_builtin_connectors()
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


def _load_builtin_connectors() -> None:
    """Import the shipped connectors so their specs are registered."""
    import cellpy_connectors.batbase  # noqa: F401  (registers "batbase")


# -- batbase ---------------------------------------------------------------

batbase_app = typer.Typer(
    name="batbase",
    help="BatBase (IFE cell-testing metadata) read access.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(batbase_app, name="batbase")

_URL_OPTION = typer.Option(
    None,
    "--url",
    help="BatBase host, e.g. https://d1-odin-01.ad.ife.no. Default: $CELLPY_BATBASE_URL or the local dev server.",
)
_ANON_OPTION = typer.Option(False, "--anonymous", help="Skip authentication (local dev server only).")
_SCOPE_OPTION = typer.Option("read", "--scope", help="OAuth2 scope to request.")


def _client(url: str | None, anonymous: bool, scope: str):
    from cellpy_connectors.batbase import BatBaseClient

    return BatBaseClient(url, anonymous=anonymous, scope=scope)


def _parse_params(items: list[str] | None) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"expected key=value, got {item!r}", param_hint="--param")
        params[key] = value
    return params


@batbase_app.command("check")
def batbase_check(
    url: str | None = _URL_OPTION,
    anonymous: bool = _ANON_OPTION,
    scope: str = _SCOPE_OPTION,
) -> None:
    """Fetch a token and GET /api/ to prove the connection works."""
    import json

    from cellpy_connectors.errors import ConnectorError

    try:
        report = _client(url, anonymous, scope).whoami()
    except ConnectorError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2))


@batbase_app.command("get")
def batbase_get(
    endpoint: str = typer.Argument(..., help="Resource under /api/, e.g. test-cellpy-tag or project/12."),
    param: list[str] | None = typer.Option(None, "--param", "-p", help="Query parameter key=value (repeatable)."),
    all_pages: bool = typer.Option(False, "--all", help="Follow DRF pagination and print every row."),
    url: str | None = _URL_OPTION,
    anonymous: bool = _ANON_OPTION,
    scope: str = _SCOPE_OPTION,
) -> None:
    """GET an endpoint and print the JSON. Use `get ''` for the API index."""
    import json

    from cellpy_connectors.errors import ConnectorError

    client = _client(url, anonymous, scope)
    try:
        params = _parse_params(param)
        payload = client.get_all(endpoint, **params) if all_pages else client.get(endpoint, **params)
    except ConnectorError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
