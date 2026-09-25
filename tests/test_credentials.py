"""Offline tests for secret resolution and keyring storage."""

from __future__ import annotations

import pytest
from keyring.errors import NoKeyringError
from pydantic import SecretStr

from cellpy_connectors.credentials import CredentialField, resolve_secret, store_secret
from cellpy_connectors.errors import ConnectorCredentialsError, ConnectorError

FIELD = CredentialField(
    name="token",
    env_var="CELLPY_FAKE_TOKEN",
    keyring_service="cellpy-connectors-test",
    keyring_username="token",
    prompt="Token",
)


def test_explicit_beats_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FIELD.env_var, "from-env")
    secret = resolve_secret("from-arg", FIELD)
    assert secret.get_secret_value() == "from-arg"
    assert "from-arg" not in repr(secret)


def test_explicit_secretstr_is_kept() -> None:
    given = SecretStr("from-arg")
    assert resolve_secret(given, FIELD) is given


def test_empty_explicit_falls_through_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FIELD.env_var, "from-env")
    secret = resolve_secret("", FIELD)
    assert secret.get_secret_value() == "from-env"


def test_environment_beats_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FIELD.env_var, "from-env")
    monkeypatch.setattr("keyring.get_password", lambda *_args: "from-ring")
    secret = resolve_secret(None, FIELD)
    assert secret.get_secret_value() == "from-env"


def test_keyring_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FIELD.env_var, raising=False)
    monkeypatch.setattr("keyring.get_password", lambda *_args: "from-ring")
    secret = resolve_secret(None, FIELD)
    assert secret.get_secret_value() == "from-ring"


def test_missing_keyring_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FIELD.env_var, raising=False)

    def _no_backend(*_args: object) -> str:
        raise NoKeyringError("none")

    monkeypatch.setattr("keyring.get_password", _no_backend)
    with pytest.raises(ConnectorCredentialsError, match=FIELD.env_var):
        resolve_secret(None, FIELD)


def test_store_secret_writes_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[tuple[str, str], str] = {}

    def _set(service: str, username: str, value: str) -> None:
        stored[(service, username)] = value

    monkeypatch.setattr("keyring.set_password", _set)
    store_secret(FIELD, "s3cret")
    assert stored[(FIELD.keyring_service, FIELD.keyring_username)] == "s3cret"


def test_store_secret_without_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    def _set(*_args: object) -> None:
        raise NoKeyringError("none")

    monkeypatch.setattr("keyring.set_password", _set)
    with pytest.raises(ConnectorError, match=FIELD.env_var):
        store_secret(FIELD, "s3cret")
