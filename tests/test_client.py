"""Offline tests for ApiClientBase error mapping and retry policy."""

from __future__ import annotations

import pytest
import requests

from cellpy_connectors.client import ApiClientBase
from cellpy_connectors.errors import ConnectorAuthError, ConnectorError


class _FakeSession:
    def __init__(
        self,
        response: requests.Response | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **_kwargs: object) -> requests.Response:
        self.calls.append((method, url))
        if self.exc is not None:
            raise self.exc
        assert self.response is not None
        return self.response


def _response(status: int, text: str = "", url: str = "https://example.test/health") -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = url
    response._content = text.encode()
    return response


def test_session_retries_idempotent_methods_only() -> None:
    client = ApiClientBase("https://example.test")
    retry = client.session.get_adapter("https://").max_retries
    assert retry.total == 3
    for status in (429, 500, 502, 503, 504):
        assert status in retry.status_forcelist
    assert set(retry.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert "POST" not in retry.allowed_methods


def test_401_is_auth_error() -> None:
    session = _FakeSession(_response(401, "nope"))
    client = ApiClientBase("https://example.test", session=session)
    with pytest.raises(ConnectorAuthError, match="401") as caught:
        client.check_connection()
    assert "nope" in str(caught.value)
    assert session.calls == [("GET", "https://example.test/")]


def test_500_is_connector_error() -> None:
    session = _FakeSession(_response(500))
    client = ApiClientBase("https://example.test/api", session=session)
    with pytest.raises(ConnectorError, match="500") as caught:
        client.request("GET", "items")
    assert not isinstance(caught.value, ConnectorAuthError)
    assert session.calls == [("GET", "https://example.test/api/items")]


def test_network_error_is_connector_error() -> None:
    session = _FakeSession(exc=requests.ConnectionError("down"))
    client = ApiClientBase("https://example.test", session=session)
    with pytest.raises(ConnectorError, match="down"):
        client.request("GET", "health")


def test_check_connection_returns_ok() -> None:
    session = _FakeSession(_response(200, "ok"))
    client = ApiClientBase("https://example.test", session=session)
    client.health_path = "ready"
    response = client.check_connection()
    assert response.status_code == 200
    assert session.calls == [("GET", "https://example.test/ready")]
