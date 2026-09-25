"""Small HTTP base for concrete connectors.

Subclasses implement endpoints. This class owns the session, timeouts,
retry on idempotent GETs, and the exception mapping.
"""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from cellpy_connectors.errors import ConnectorAuthError, ConnectorError

_RETRY_STATUSES = (429, 500, 502, 503, 504)
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class SupportsRequest(Protocol):
    """``requests.Session`` or a test double with the same ``request`` method."""

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send one HTTP request."""


class ApiClientBase:
    """HTTP client with a shared session.

    ``health_path`` is joined onto ``base_url`` by ``check_connection``.
    An empty path probes the base URL itself. Subclasses override the
    attribute or the method.
    """

    health_path: str = ""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        session: SupportsRequest | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = session if session is not None else _new_session()

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send ``method`` to ``path`` under ``base_url``.

        401 and 403 become ``ConnectorAuthError``. Other HTTP errors and
        network failures become ``ConnectorError``. POST is not retried.
        """
        url = urljoin(self.base_url, path.lstrip("/"))
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise ConnectorError(f"Request to {url} failed: {exc}") from exc
        return _raise_for_status(response)

    def check_connection(self) -> requests.Response:
        """GET ``health_path``. Raises the same errors as ``request``."""
        return self.request("GET", self.health_path)


def _new_session() -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=_RETRY_STATUSES,
        allowed_methods=_IDEMPOTENT_METHODS,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _raise_for_status(response: requests.Response) -> requests.Response:
    if response.status_code in (401, 403):
        snippet = (response.text or "").strip()[:200]
        detail = f" {snippet}" if snippet else ""
        raise ConnectorAuthError(
            f"Credentials rejected by {response.url} "
            f"({response.status_code}).{detail}"
        )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ConnectorError(
            f"HTTP {response.status_code} from {response.url}"
        ) from exc
    return response
