"""Process BatBase tests with cellpy and post check-up readings back.

The results half of Epic M stage M3 (jepegit/cellpy#783). The metadata half,
``SupportsMetadataPush.register``, is a different thing: it would push a
cell's description, while this posts numbers measured in one test.

For each BatBase test id:

1. GET ``api/test-experiment/<id>/``. Its ``files`` list (``TestDataFile``)
   says where the raw files are and which cellpy loader reads them
   (``instrument_loader``).
2. Map each ``uri`` to a local path (``path_map``; see `parse_path_map`) and
   load the raw files with ``cellpy.get(paths, instrument=loader)``.
3. Pick the readings with ``cellpy.utils.readings.checkup_readings``
   (capacity Ah, dc_resistance mOhm, ocv V).
4. POST them to ``api/test-observation/bulk/`` with a ``source``. BatBase keeps
   one reading per (test, name, source), so processing again updates.

cellpy is imported lazily: this package still does not depend on it at
runtime. Processing needs cellpy with ``cellpy.utils.readings``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from cellpy_connectors.errors import ConnectorError

DEFAULT_SOURCE = "cellpy-checkup"
PATH_MAP_ENV_VAR = "CELLPY_BATBASE_PATH_MAP"
BULK_ENDPOINT = "test-observation/bulk"


class ProcessingError(ConnectorError):
    """A test could not be processed (no raw files, no loader, file missing, ...)."""


@dataclass
class ProcessResult:
    """What happened to one test."""

    test_id: int
    files: list[str] = field(default_factory=list)
    loader: str | None = None
    readings: list[dict[str, Any]] = field(default_factory=list)
    answer: dict[str, Any] | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "ok": self.ok,
            "files": self.files,
            "loader": self.loader,
            "readings": self.readings,
            "answer": self.answer,
            "error": self.error,
        }


def parse_path_map(text: str | None) -> list[tuple[str, str]]:
    """``"smb://share/raw=/data/raw;file:///mnt/x=/data/x"`` → prefix pairs.

    Pairs are separated by ``;``, prefix and local path by the first ``=``.
    Longer prefixes are tried first. Empty text → no mapping.
    """
    pairs = []
    for part in (text or "").split(";"):
        part = part.strip()
        if not part:
            continue
        prefix, sep, local = part.partition("=")
        if not sep or not prefix.strip() or not local.strip():
            raise ValueError(f"Bad path map entry {part!r}; expected prefix=/local/path")
        pairs.append((prefix.strip(), local.strip()))
    return sorted(pairs, key=lambda pair: -len(pair[0]))


def local_path(uri: str, path_map: list[tuple[str, str]]) -> Path:
    """The local path for a BatBase ``uri``.

    The first matching prefix in ``path_map`` is replaced. Otherwise a
    ``file://`` URI becomes its path, and anything else is taken as a path.
    """
    for prefix, local in path_map:
        if uri.startswith(prefix):
            rest = uri[len(prefix) :].lstrip("/\\")
            return Path(local) / unquote(rest).replace("\\", "/")
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme and len(parsed.scheme) > 1:
        raise ProcessingError(
            f"No local path for {uri!r}. Add its prefix to {PATH_MAP_ENV_VAR} "
            "(e.g. 'smb://share/raw=/data/raw')."
        )
    return Path(uri)


def raw_files(test_row: dict[str, Any]) -> tuple[list[str], str | None]:
    """URIs of the test's raw files in BatBase order, and their common loader."""
    files = [
        f
        for f in (test_row.get("files") or [])
        if isinstance(f, dict) and f.get("kind") == "raw" and (f.get("uri") or "").strip()
    ]
    files.sort(key=lambda f: int(f.get("order") or 0))
    loaders = {(f.get("instrument_loader") or "").strip() for f in files} - {""}
    if len(loaders) > 1:
        raise ProcessingError(f"Raw files use different loaders: {sorted(loaders)}")
    return [f["uri"].strip() for f in files], (loaders.pop() if loaders else None)


def readings_payload(test_id: int, readings) -> list[dict[str, Any]]:
    """cellpy `Reading`s → items for ``test-observation/bulk``."""
    items = []
    for reading in readings:
        note = reading.note
        if reading.cycle is not None:
            note = f"cycle {reading.cycle}: {note}" if note else f"cycle {reading.cycle}"
        items.append(
            {
                "experiment": test_id,
                "name": reading.name,
                "value": reading.value,
                "unit": reading.unit,
                "text": note,
            }
        )
    return items


def _default_load(paths: list[Path], loader: str):
    import cellpy

    target = [str(p) for p in paths]
    return cellpy.get(target if len(target) > 1 else target[0], instrument=loader)


def _default_extract(cell):
    try:
        from cellpy.utils.readings import checkup_readings
    except ImportError as exc:  # pragma: no cover - depends on the installed cellpy
        raise ProcessingError(
            "This cellpy has no cellpy.utils.readings; install a cellpy that includes it."
        ) from exc
    return checkup_readings(cell)


def process_test(
    client,
    test_id: int,
    *,
    source: str = DEFAULT_SOURCE,
    path_map: list[tuple[str, str]] | None = None,
    dry_run: bool = False,
    load: Callable[[list[Path], str], Any] = _default_load,
    extract: Callable[[Any], Any] = _default_extract,
) -> ProcessResult:
    """Load one BatBase test with cellpy and post its readings.

    Never raises for a problem with this test; the result carries ``error``.
    Auth errors are raised: every other test would fail the same way.
    """
    from cellpy_connectors.batbase import BatBaseAuthError

    result = ProcessResult(test_id=test_id)
    if path_map is None:
        path_map = parse_path_map(os.environ.get(PATH_MAP_ENV_VAR))
    try:
        row = client.get(f"test-experiment/{test_id}")
        uris, loader = raw_files(row)
        result.files, result.loader = uris, loader
        if not uris:
            raise ProcessingError(f"Test {test_id} has no raw files in BatBase (add them under Data files).")
        if not loader:
            raise ProcessingError(
                f"Test {test_id}: its raw files have no instrument_loader (e.g. pec_csv, arbin_res, neware_nda)."
            )
        paths = [local_path(uri, path_map) for uri in uris]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            raise ProcessingError(f"Test {test_id}: file(s) not found here: {', '.join(missing)}")
        cell = load(paths, loader)
        result.readings = readings_payload(test_id, extract(cell))
        if result.readings and not dry_run:
            result.answer = client.post(BULK_ENDPOINT, {"source": source, "readings": result.readings})
    except BatBaseAuthError:
        raise
    except Exception as exc:  # one bad file must not stop a batch
        result.error = f"{type(exc).__name__}: {exc}"
    return result
