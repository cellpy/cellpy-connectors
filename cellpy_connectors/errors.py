"""Connector failures a caller can distinguish without reading a stack trace."""

from __future__ import annotations


class ConnectorError(Exception):
    """Transport failure or an unexpected HTTP status."""


class ConnectorCredentialsError(ConnectorError):
    """No secret was configured (argument, environment, or keyring)."""


class ConnectorAuthError(ConnectorError):
    """A secret was sent and the server rejected it."""
