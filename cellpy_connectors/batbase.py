"""BatBase connector: OAuth2 client-credentials transport and a read passthrough.

BatBase (IFE's Django app for cell-testing metadata) mounts django-oauth-toolkit
at ``/o/`` and a DRF API at ``/api/``. Scripts authenticate with the
client-credentials grant: ``POST /o/token/`` with the client id/secret as HTTP
Basic auth, then ``Authorization: Bearer <token>`` on every API call. Tokens
are short-lived and there is no refresh token, so this client caches the token
in memory and fetches a fresh one when it expires or is rejected.

Credentials follow the connector-base precedence: explicit argument, then
``CELLPY_BATBASE_CLIENT_ID`` / ``CELLPY_BATBASE_CLIENT_SECRET``, then the OS
keyring (filled by ``cellpy connectors configure batbase``). The host comes
from the ``base_url`` argument, else ``CELLPY_BATBASE_URL``, else the local
dev server. A local dev server accepts anonymous reads; pass
``anonymous=True`` to skip authentication there.

Examples:
    ```python
    from cellpy_connectors.batbase import BatBaseClient

    bb = BatBaseClient("https://d1-odin-01.ad.ife.no")
    tags = bb.get("test-cellpy-tag", search="SAL_010")
    for row in bb.get_all("project"):
        print(row["name"])
    ```
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import requests
from pydantic import SecretStr

from cellpy_connectors.client import ApiClientBase, SupportsRequest, _raise_for_status
from cellpy_connectors.credentials import CredentialField, resolve_secret
from cellpy_connectors.errors import (
    ConnectorAuthError,
    ConnectorCredentialsError,
    ConnectorError,
)
from cellpy_connectors.registry import ConnectorSpec, register

CONNECTOR_NAME = "batbase"
DEFAULT_URL = "http://localhost:8000"
URL_ENV_VAR = "CELLPY_BATBASE_URL"
TOKEN_PATH = "o/token/"
API_PREFIX = "api/"
DEFAULT_SCOPE = "read"

#: Seconds before ``expires_in`` elapses at which the token is treated as stale.
EXPIRY_MARGIN = 60.0

_KEYRING_SERVICE = "cellpy-connectors/batbase"

CLIENT_ID_FIELD = CredentialField(
    name="BatBase client id",
    env_var="CELLPY_BATBASE_CLIENT_ID",
    keyring_service=_KEYRING_SERVICE,
    keyring_username="client_id",
    prompt="BatBase client id",
)
CLIENT_SECRET_FIELD = CredentialField(
    name="BatBase client secret",
    env_var="CELLPY_BATBASE_CLIENT_SECRET",
    keyring_service=_KEYRING_SERVICE,
    keyring_username="client_secret",
    prompt="BatBase client secret",
)

SPEC = ConnectorSpec(name=CONNECTOR_NAME, fields=(CLIENT_ID_FIELD, CLIENT_SECRET_FIELD))
register(SPEC)


class BatBaseAuthError(ConnectorAuthError):
    """No BatBase credentials are configured, or BatBase rejected them."""


@dataclass(frozen=True, slots=True)
class _Token:
    access_token: str
    expires_at: float  # time.monotonic() seconds

    def is_fresh(self, now: float) -> bool:
        return now < self.expires_at - EXPIRY_MARGIN


def resolve_base_url(base_url: str | None = None) -> str:
    """``base_url`` argument, else ``CELLPY_BATBASE_URL``, else the dev server."""
    return (base_url or os.environ.get(URL_ENV_VAR) or DEFAULT_URL).rstrip("/")


def api_path(endpoint: str) -> str:
    """Normalise ``endpoint`` to a DRF path under ``api/``.

    ``"test-cellpy-tag"``, ``"/test-cellpy-tag/"`` and ``"api/test-cellpy-tag"``
    all give ``"api/test-cellpy-tag/"``. A trailing slash is added because DRF
    routers redirect without it. Query strings are left alone.
    """
    path, sep, query = endpoint.partition("?")
    path = path.strip().lstrip("/")
    if not path.startswith(API_PREFIX.rstrip("/")):
        path = API_PREFIX + path
    if not path.endswith("/"):
        path += "/"
    return path + sep + query


class BatBaseClient(ApiClientBase):
    """HTTP client for the BatBase API with transparent bearer-token handling.

    Args:
        base_url: BatBase host (scheme + host [+ port]); see `resolve_base_url`.
        client_id / client_secret: explicit credentials; normally left ``None``
            so the environment or the keyring is used.
        scope: OAuth2 scope requested for the token. ``"read"`` by default;
            ``"read write"`` needs membership of BatBase's ``api-write`` group.
        anonymous: skip authentication entirely (local dev server).
        timeout / session: see `ApiClientBase`.

    Raises:
        BatBaseAuthError: on the first authenticated request when no
            credentials are configured, or when BatBase rejects them.
    """

    health_path = API_PREFIX

    def __init__(
        self,
        base_url: str | None = None,
        *,
        client_id: str | SecretStr | None = None,
        client_secret: str | SecretStr | None = None,
        scope: str = DEFAULT_SCOPE,
        anonymous: bool = False,
        timeout: float = 10.0,
        session: SupportsRequest | None = None,
        clock=time.monotonic,
    ) -> None:
        super().__init__(resolve_base_url(base_url), timeout=timeout, session=session)
        self._client_id = client_id
        self._client_secret = client_secret
        self.scope = scope
        self.anonymous = anonymous
        self._clock = clock
        self._token: _Token | None = None

    # -- auth -------------------------------------------------------------
    def credentials(self) -> tuple[SecretStr, SecretStr]:
        """Resolved (client id, client secret). Raises `BatBaseAuthError` if unset."""
        try:
            client_id = resolve_secret(self._client_id, CLIENT_ID_FIELD)
            client_secret = resolve_secret(self._client_secret, CLIENT_SECRET_FIELD)
        except ConnectorCredentialsError as exc:
            raise BatBaseAuthError(
                "No BatBase credentials configured. Create an API client in BatBase "
                "(user menu -> API credentials), then run "
                "`cellpy connectors configure batbase` or set "
                f"{CLIENT_ID_FIELD.env_var} and {CLIENT_SECRET_FIELD.env_var}."
            ) from exc
        return client_id, client_secret

    def fetch_token(self) -> str:
        """Request a new access token from ``o/token/`` and cache it."""
        client_id, client_secret = self.credentials()
        url = self.base_url + TOKEN_PATH
        try:
            response = self.session.request(
                "POST",
                url,
                auth=(client_id.get_secret_value(), client_secret.get_secret_value()),
                data={"grant_type": "client_credentials", "scope": self.scope},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ConnectorError(f"Token request to {url} failed: {exc}") from exc
        if response.status_code in (400, 401, 403):
            raise BatBaseAuthError(
                f"BatBase rejected the client credentials at {url} "
                f"({response.status_code}): {(response.text or '').strip()[:200]}. "
                "Check the client id/secret (rotate it in BatBase if lost) and "
                f"that the scope {self.scope!r} is allowed for your user."
            )
        _raise_for_status(response)
        try:
            payload = response.json()
            access_token = payload["access_token"]
            expires_in = float(payload.get("expires_in", 36000))
        except (ValueError, KeyError, TypeError) as exc:
            raise ConnectorError(f"Unexpected token response from {url}: {exc}") from exc
        self._token = _Token(access_token, self._clock() + expires_in)
        return access_token

    def token(self) -> str:
        """A fresh access token (cached until close to expiry)."""
        now = self._clock()
        if self._token is not None and self._token.is_fresh(now):
            return self._token.access_token
        return self.fetch_token()

    def invalidate_token(self) -> None:
        """Forget the cached token so the next call fetches a new one."""
        self._token = None

    # -- transport --------------------------------------------------------
    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send ``method`` to ``path`` with a bearer token; re-auth once on 401."""
        return self._request(method, path, retry_auth=True, **kwargs)

    def _request(self, method: str, path: str, *, retry_auth: bool, **kwargs: Any) -> requests.Response:
        url = self.base_url + path.lstrip("/")  # base_url always ends with "/"
        headers = dict(kwargs.pop("headers", None) or {})
        if not self.anonymous:
            headers["Authorization"] = f"Bearer {self.token()}"
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise ConnectorError(f"Request to {url} failed: {exc}") from exc
        if response.status_code == 401 and not self.anonymous and retry_auth:
            # Token revoked or the secret rotated mid-session: one fresh token, one retry.
            self.invalidate_token()
            return self._request(method, path, retry_auth=False, **kwargs)
        if response.status_code in (401, 403):
            hint = " (anonymous access; this host requires a token)" if self.anonymous else ""
            raise BatBaseAuthError(
                f"BatBase refused {method} {url} ({response.status_code}){hint}: "
                f"{(response.text or '').strip()[:200]}"
            )
        return _raise_for_status(response)

    # -- read passthrough -------------------------------------------------
    def get(self, endpoint: str, **params: Any) -> Any:
        """GET one API endpoint and return the decoded JSON.

        ``endpoint`` is a resource under ``api/`` (``"test-cellpy-tag"``,
        ``"project/12"``); keyword arguments become the query string
        (``search="SAL"``, ``page=2``). Returns whatever the endpoint returns —
        a DRF page (``{"count", "next", "previous", "results"}``), a list, or
        one object.
        """
        response = self.request("GET", api_path(endpoint), params=params or None)
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(f"Non-JSON response from {response.url}") from exc

    def get_all(self, endpoint: str, **params: Any) -> list[Any]:
        """GET every row of a list endpoint, following DRF pagination."""
        return list(self.iter_rows(endpoint, **params))

    def iter_rows(self, endpoint: str, **params: Any) -> Iterator[Any]:
        """Yield rows of a list endpoint page by page."""
        payload = self.get(endpoint, **params)
        while True:
            if isinstance(payload, list):
                yield from payload
                return
            if not isinstance(payload, dict) or "results" not in payload:
                yield payload
                return
            yield from payload["results"]
            next_url = payload.get("next")
            if not next_url:
                return
            # ``next`` is absolute and already carries the query string.
            path = next_url.split(self.base_url, 1)[-1] if next_url.startswith(self.base_url) else next_url
            response = self.request("GET", path)
            payload = response.json()

    def whoami(self) -> dict[str, Any]:
        """Token + connection check: GET ``api/`` and report what worked."""
        response = self.check_connection()
        return {
            "url": self.base_url,
            "status": response.status_code,
            "authenticated": not self.anonymous,
            "scope": None if self.anonymous else self.scope,
        }
