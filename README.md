# <img src="cellpy-icon-bw.svg" height="40" alt="cellpy-icon"> cellpy-connectors

Pluggable connectors for [cellpy](https://github.com/jepegit/cellpy).

This repo mounts a Typer group on the cellpy CLI (`cellpy connectors`).
It includes a no-I/O `ping` command and a shared base later connectors
subclass: credential resolution (argument, then environment, then OS keyring),
`ApiClientBase`, and `cellpy connectors configure <name>`. BatBase itself is
still a later issue (#1, then #2).

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
that have registered a spec (none ship yet; BatBase will, in #1):

```bash
uv run cellpy connectors configure <name>
```

Prompts are hidden and the values are not printed. On a machine with no
keyring (CI, HPC), set the connector's environment variables instead. Resolution
order for every secret is: explicit argument, environment variable, OS keyring.
Secrets are never read from a config file.

## Tests

```bash
uv sync
uv run pytest
```

Tests that invoke the live `cellpy` CLI skip if cellpy is missing or predates
the plugin mount.

## Python

3.13+. Day-to-day toolchain is **uv** (`uv sync`, `uv run pytest`).
