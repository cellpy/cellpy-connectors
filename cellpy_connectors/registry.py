"""Named connector specs that ``configure`` looks up.

Production starts empty. Each connector (#1 registers ``batbase``) calls
``register`` at import time. Specs are data only: the HTTP subclass stays
with the connector.
"""

from __future__ import annotations

from dataclasses import dataclass

from cellpy_connectors.credentials import CredentialField

_REGISTRY: dict[str, ConnectorSpec] = {}


@dataclass(frozen=True, slots=True)
class ConnectorSpec:
    """Credentials a connector asks ``configure`` to collect."""

    name: str
    fields: tuple[CredentialField, ...]


def register(spec: ConnectorSpec) -> None:
    """Add or replace ``spec`` under ``spec.name``."""
    _REGISTRY[spec.name] = spec


def unregister(name: str) -> None:
    """Drop ``name`` if present. Tests use this to leave the registry empty."""
    _REGISTRY.pop(name, None)


def get(name: str) -> ConnectorSpec | None:
    """Return the spec for ``name``, or ``None`` when it is not registered."""
    return _REGISTRY.get(name)


def names() -> tuple[str, ...]:
    """Registered connector names, sorted."""
    return tuple(sorted(_REGISTRY))
