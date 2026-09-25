"""Resolve and store connector secrets.

Precedence for every field: explicit argument, then environment variable,
then the OS keyring. Nothing is read from a config file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import SecretStr

from cellpy_connectors.errors import ConnectorCredentialsError, ConnectorError


@dataclass(frozen=True, slots=True)
class CredentialField:
    """One secret a connector needs."""

    name: str
    env_var: str
    keyring_service: str
    keyring_username: str
    prompt: str


def resolve_secret(
    explicit: str | SecretStr | None,
    field: CredentialField,
) -> SecretStr:
    """Return the first configured value for ``field``.

    Raises ``ConnectorCredentialsError`` when the argument, the environment,
    and the keyring are all empty. A missing keyring backend is treated as
    "not stored", not as a crash, so CI can rely on the environment alone.
    """
    from_arg = _coerce_explicit(explicit)
    if from_arg is not None:
        return from_arg

    from_env = os.environ.get(field.env_var)
    if from_env:
        return SecretStr(from_env)

    from_ring = _keyring_get(field)
    if from_ring:
        return SecretStr(from_ring)

    raise ConnectorCredentialsError(
        f"No credentials configured for {field.name}. "
        f"Set {field.env_var} or run `cellpy connectors configure <name>`."
    )


def store_secret(field: CredentialField, value: str) -> None:
    """Write ``value`` to the OS keyring. Does not echo it."""
    import keyring
    from keyring.errors import KeyringError

    try:
        keyring.set_password(field.keyring_service, field.keyring_username, value)
    except KeyringError as exc:
        raise ConnectorError(
            f"Could not store {field.name} in the OS keyring ({exc}). "
            f"Set {field.env_var} instead."
        ) from exc


def _coerce_explicit(explicit: str | SecretStr | None) -> SecretStr | None:
    if explicit is None:
        return None
    if isinstance(explicit, SecretStr):
        raw = explicit.get_secret_value()
        return explicit if raw else None
    if explicit:
        return SecretStr(explicit)
    return None


def _keyring_get(field: CredentialField) -> str | None:
    import keyring
    from keyring.errors import KeyringError

    try:
        return keyring.get_password(field.keyring_service, field.keyring_username)
    except KeyringError:
        return None
