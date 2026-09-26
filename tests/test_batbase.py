"""Offline tests for the BatBase client (#1). No network: a scripted fake session."""

from __future__ import annotations

import base64
import json
from typing import Any, ClassVar

import pytest
import requests
from typer.testing import CliRunner

from cellpy_connectors import registry
from cellpy_connectors.batbase import (
    CLIENT_ID_FIELD,
    CLIENT_SECRET_FIELD,
    BatBaseAuthError,
    BatBaseClient,
    api_path,
    resolve_base_url,
)
from cellpy_connectors.cli import app
from cellpy_connectors.errors import ConnectorError

BASE = "https://batbase.test"
TOKEN_URL = f"{BASE}/o/token/"


def _json_response(status: int, payload: Any, url: str = BASE) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = url
    response._content = json.dumps(payload).encode()
    response.headers["Content-Type"] = "application/json"
    return response


def _token_response(token: str = "tok-1", expires_in: int = 36000) -> requests.Response:
    return _json_response(
        200,
        {"access_token": token, "expires_in": expires_in, "token_type": "Bearer", "scope": "read"},
        TOKEN_URL,
    )


class _Call:
    def __init__(self, method: str, url: str, kwargs: dict[str, Any]) -> None:
        self.method = method
        self.url = url
        self.kwargs = kwargs

    @property
    def bearer(self) -> str | None:
        auth = (self.kwargs.get("headers") or {}).get("Authorization")
        return auth.removeprefix("Bearer ") if auth else None


class _ScriptedSession:
    """Returns responses in order; records every call."""

    def __init__(self, *responses: requests.Response) -> None:
        self.responses = list(responses)
        self.calls: list[_Call] = []

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.calls.append(_Call(method, url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected request {method} {url}")
        return self.responses.pop(0)

    def get_adapter(self, _url: str):  # pragma: no cover - not used by these tests
        raise NotImplementedError

    @property
    def api_calls(self) -> list[_Call]:
        return [c for c in self.calls if c.url != TOKEN_URL]

    @property
    def token_calls(self) -> list[_Call]:
        return [c for c in self.calls if c.url == TOKEN_URL]


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (CLIENT_ID_FIELD.env_var, CLIENT_SECRET_FIELD.env_var, "CELLPY_BATBASE_URL"):
        monkeypatch.delenv(var, raising=False)
    # keyring must not be consulted in tests.
    monkeypatch.setattr("cellpy_connectors.credentials._keyring_get", lambda *_: None)


def _client(session: _ScriptedSession, clock: _Clock | None = None, **kwargs: Any) -> BatBaseClient:
    kwargs.setdefault("client_id", "cid")
    kwargs.setdefault("client_secret", "shh")
    return BatBaseClient(BASE, session=session, clock=clock or _Clock(), **kwargs)


# -- registry / config -----------------------------------------------------


def test_batbase_spec_is_registered() -> None:
    spec = registry.get("batbase")
    assert spec is not None
    assert [f.env_var for f in spec.fields] == ["CELLPY_BATBASE_CLIENT_ID", "CELLPY_BATBASE_CLIENT_SECRET"]


def test_resolve_base_url_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CELLPY_BATBASE_URL", raising=False)
    assert resolve_base_url() == "http://localhost:8000"
    monkeypatch.setenv("CELLPY_BATBASE_URL", "https://staging.test:8500/")
    assert resolve_base_url() == "https://staging.test:8500"
    assert resolve_base_url("https://prod.test") == "https://prod.test"


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("test-cellpy-tag", "api/test-cellpy-tag/"),
        ("/test-cellpy-tag/", "api/test-cellpy-tag/"),
        ("api/project/12", "api/project/12/"),
        ("", "api/"),
        ("project?search=x", "api/project/?search=x"),
    ],
)
def test_api_path_normalisation(endpoint: str, expected: str) -> None:
    assert api_path(endpoint) == expected


# -- token handling --------------------------------------------------------


def test_fetch_token_uses_basic_auth_and_client_credentials_grant() -> None:
    session = _ScriptedSession(_token_response("abc"))
    client = _client(session, scope="read write")

    assert client.token() == "abc"
    (call,) = session.token_calls
    assert call.method == "POST"
    assert call.kwargs["auth"] == ("cid", "shh")
    assert call.kwargs["data"] == {"grant_type": "client_credentials", "scope": "read write"}
    assert "Authorization" not in (call.kwargs.get("headers") or {})


def test_token_is_cached_until_close_to_expiry() -> None:
    clock = _Clock(0.0)
    session = _ScriptedSession(_token_response("first", expires_in=600), _token_response("second"))
    client = _client(session, clock=clock)

    assert client.token() == "first"
    clock.now = 500.0  # 100 s left, above the 60 s margin
    assert client.token() == "first"
    clock.now = 545.0  # 55 s left -> stale
    assert client.token() == "second"
    assert len(session.token_calls) == 2


def test_requests_carry_bearer_and_reuse_token() -> None:
    session = _ScriptedSession(
        _token_response("tok"),
        _json_response(200, {"count": 0, "results": []}),
        _json_response(200, {"count": 0, "results": []}),
    )
    client = _client(session)

    client.get("test-cellpy-tag", search="SAL")
    client.get("project")

    assert len(session.token_calls) == 1
    first, second = session.api_calls
    assert first.url == f"{BASE}/api/test-cellpy-tag/"
    assert first.kwargs["params"] == {"search": "SAL"}
    assert first.bearer == second.bearer == "tok"


def test_401_triggers_one_reauth_then_raises() -> None:
    session = _ScriptedSession(
        _token_response("old"),
        _json_response(401, {"detail": "Invalid token."}),
        _token_response("new"),
        _json_response(200, {"ok": True}),
    )
    client = _client(session)
    assert client.get("project") == {"ok": True}
    assert [c.bearer for c in session.api_calls] == ["old", "new"]

    # Second scenario: still 401 after re-auth -> BatBaseAuthError, no infinite loop.
    session = _ScriptedSession(
        _token_response("old"),
        _json_response(401, {"detail": "nope"}),
        _token_response("new"),
        _json_response(401, {"detail": "nope"}),
    )
    client = _client(session)
    with pytest.raises(BatBaseAuthError, match="401"):
        client.get("project")
    assert len(session.api_calls) == 2


def test_rejected_client_credentials_raise_auth_error() -> None:
    session = _ScriptedSession(_json_response(401, {"error": "invalid_client"}, TOKEN_URL))
    with pytest.raises(BatBaseAuthError, match="rejected the client credentials"):
        _client(session).get("project")


def test_missing_credentials_error_names_env_vars_and_configure(no_env: None) -> None:
    session = _ScriptedSession()
    client = BatBaseClient(BASE, session=session)
    with pytest.raises(BatBaseAuthError) as excinfo:
        client.get("project")
    message = str(excinfo.value)
    assert "CELLPY_BATBASE_CLIENT_ID" in message
    assert "cellpy connectors configure batbase" in message
    assert session.calls == []  # never hit the network without credentials


def test_anonymous_mode_sends_no_authorization(no_env: None) -> None:
    session = _ScriptedSession(_json_response(200, {"ok": True}))
    client = BatBaseClient(BASE, session=session, anonymous=True)
    assert client.get("project") == {"ok": True}
    (call,) = session.calls
    assert call.bearer is None
    assert session.token_calls == []


def test_anonymous_403_gives_hint(no_env: None) -> None:
    session = _ScriptedSession(_json_response(403, {"detail": "Authentication credentials were not provided."}))
    client = BatBaseClient(BASE, session=session, anonymous=True)
    with pytest.raises(BatBaseAuthError, match="requires a token"):
        client.get("project")


def test_secret_never_appears_in_error_text() -> None:
    session = _ScriptedSession(_json_response(401, {"error": "invalid_client"}, TOKEN_URL))
    with pytest.raises(BatBaseAuthError) as excinfo:
        _client(session, client_secret="super-secret-value").get("project")
    assert "super-secret-value" not in str(excinfo.value)


# -- read passthrough ------------------------------------------------------


def test_get_all_follows_drf_pagination() -> None:
    session = _ScriptedSession(
        _token_response(),
        _json_response(200, {"count": 3, "next": f"{BASE}/api/project/?page=2", "results": [1, 2]}),
        _json_response(200, {"count": 3, "next": None, "results": [3]}),
    )
    client = _client(session)
    assert client.get_all("project") == [1, 2, 3]
    assert session.api_calls[1].url == f"{BASE}/api/project/?page=2"


def test_get_all_handles_unpaginated_list_and_single_object() -> None:
    session = _ScriptedSession(_token_response(), _json_response(200, [1, 2]), _json_response(200, {"id": 7}))
    client = _client(session)
    assert client.get_all("project") == [1, 2]
    assert client.get_all("project/7") == [{"id": 7}]


def test_non_json_response_is_connector_error() -> None:
    bad = requests.Response()
    bad.status_code = 200
    bad.url = BASE
    bad._content = b"<html>"
    session = _ScriptedSession(_token_response(), bad)
    with pytest.raises(ConnectorError, match="Non-JSON"):
        _client(session).get("project")


def test_http_500_is_connector_error_not_auth_error() -> None:
    session = _ScriptedSession(_token_response(), _json_response(500, {"detail": "boom"}))
    with pytest.raises(ConnectorError) as excinfo:
        _client(session).get("project")
    assert not isinstance(excinfo.value, BatBaseAuthError)


# -- CLI -------------------------------------------------------------------


class _StubClient:
    instances: ClassVar[list[_StubClient]] = []

    def __init__(self, url: str | None = None, *, anonymous: bool = False, scope: str = "read") -> None:
        self.url = url
        self.anonymous = anonymous
        self.scope = scope
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        _StubClient.instances.append(self)

    def get(self, endpoint: str, **params: Any) -> Any:
        self.calls.append(("get", endpoint, params))
        return {"count": 1, "results": [{"id": 1, "name": "æøå"}]}

    def get_all(self, endpoint: str, **params: Any) -> Any:
        self.calls.append(("get_all", endpoint, params))
        return [{"id": 1}]

    def whoami(self) -> dict[str, Any]:
        return {"url": self.url, "status": 200, "authenticated": not self.anonymous, "scope": self.scope}


@pytest.fixture
def stub_client(monkeypatch: pytest.MonkeyPatch) -> type[_StubClient]:
    _StubClient.instances = []
    monkeypatch.setattr("cellpy_connectors.batbase.BatBaseClient", _StubClient)
    return _StubClient


def test_cli_get_prints_json(stub_client: type[_StubClient]) -> None:
    result = CliRunner().invoke(
        app,
        ["batbase", "get", "test-cellpy-tag", "-p", "search=SAL", "--url", "https://x.test"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["results"][0]["name"] == "æøå"
    (client,) = stub_client.instances
    assert client.url == "https://x.test"
    assert client.calls == [("get", "test-cellpy-tag", {"search": "SAL"})]


def test_cli_get_all_and_anonymous(stub_client: type[_StubClient]) -> None:
    result = CliRunner().invoke(app, ["batbase", "get", "project", "--all", "--anonymous"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [{"id": 1}]
    (client,) = stub_client.instances
    assert client.anonymous is True
    assert client.calls == [("get_all", "project", {})]


def test_cli_get_rejects_malformed_param(stub_client: type[_StubClient]) -> None:
    result = CliRunner().invoke(app, ["batbase", "get", "project", "-p", "novalue"])
    assert result.exit_code != 0
    assert "key=value" in result.output


def test_cli_check_reports_connection(stub_client: type[_StubClient]) -> None:
    result = CliRunner().invoke(app, ["batbase", "check", "--url", "https://x.test"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == 200


def test_cli_auth_error_exits_1_without_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Failing(_StubClient):
        def whoami(self) -> dict[str, Any]:
            raise BatBaseAuthError("No BatBase credentials configured.")

    monkeypatch.setattr("cellpy_connectors.batbase.BatBaseClient", _Failing)
    result = CliRunner().invoke(app, ["batbase", "check"])
    assert result.exit_code == 1
    assert "No BatBase credentials configured" in result.output
    assert "Traceback" not in result.output


def test_cli_configure_batbase_uses_registered_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[str, str] = {}
    monkeypatch.setattr(
        "cellpy_connectors.credentials.store_secret",
        lambda field, value: stored.__setitem__(field.keyring_username, value),
    )
    result = CliRunner().invoke(app, ["configure", "batbase"], input="my-id\nmy-secret\n")
    assert result.exit_code == 0, result.output
    assert stored == {"client_id": "my-id", "client_secret": "my-secret"}
    assert "my-secret" not in result.output


def test_basic_auth_header_shape_matches_batbase_scripts() -> None:
    """Sanity: requests' (id, secret) tuple is what BatBase's scripts hand-roll."""
    expected = base64.b64encode(b"cid:shh").decode()
    prepared = requests.Request("POST", TOKEN_URL, auth=("cid", "shh")).prepare()
    assert prepared.headers["Authorization"] == f"Basic {expected}"
