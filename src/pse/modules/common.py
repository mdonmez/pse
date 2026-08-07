"""Shared dependency-free helpers."""

from __future__ import annotations

import hashlib
import json
import platform as host_platform
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

VERSION = package_version("pse")
PYPI_INDEX = "https://pypi.org/simple/"
CONDA_CHANNEL = "conda-forge"
CACHE_DIR = Path(tempfile.gettempdir()) / "pse-cache"
DEFAULT_LIMIT = 10
DEFAULT_VERSIONS = 10
DEFAULT_CACHE_TTL = 60 * 60
MAX_WORKERS = 8
EXPECTED_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError)


@dataclass(frozen=True, slots=True)
class Options:
    query: str
    limit: int
    versions: int
    platform: str
    refresh: bool
    cache_ttl: int


def normalize(value: str) -> str:
    return re.sub(r"[-_.\s]+", "-", value.strip().lower())


def cache_key(value: str) -> str:
    """Return a compact cache key that does not expose the input value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def read_cache(path: Path, ttl: int) -> Any | None:
    try:
        if time.time() - path.stat().st_mtime <= ttl:
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        pass
    return None


def write_cache(path: Path, value: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        pass


def load_cached(path: Path, refresh: bool, ttl: int, loader):
    if not refresh and (value := read_cache(path, ttl)) is not None:
        return value
    value = loader()
    write_cache(path, value)
    return value


def parallel(function, values):
    values = list(values)
    if not values:
        return []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(values))) as pool:
        return list(pool.map(function, values))


def fetch(url: str, accept: str = "*/*", timeout: int = 60) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": f"pse.py/{VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a" and (href := dict(attrs).get("href")):
            self.hrefs.append(href)


def links(content: bytes) -> list[str]:
    parser = LinkParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.hrefs


def as_json(content: bytes) -> Any | None:
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


def pypi_source(index: str) -> str:
    parsed = urllib.parse.urlsplit(index)
    path = parsed.path.rstrip("/")
    host = _public_netloc(parsed).lower()
    if host == "pypi.org" and path in ("", "/simple"):
        return "pypi"
    return f"pypi:{host}{path}".strip("/")


def conda_source(channel: str) -> tuple[str, str]:
    channel = channel.strip()
    url = (
        f"https://conda.anaconda.org/{channel.strip('/')}"
        if "://" not in channel
        else channel.rstrip("/")
    )
    parsed = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(parsed._replace(query="", fragment="")).rstrip("/")
    location = f"{_public_netloc(parsed)}{parsed.path.rstrip('/')}".strip("/")
    label = (
        "conda-forge"
        if location == "conda.anaconda.org/conda-forge"
        else f"conda:{location}"
    )
    return url, label


def _public_netloc(parsed: urllib.parse.SplitResult) -> str:
    """Return a URL location without user names or passwords."""
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{host}:{port}" if port else host


def rank(name: str, query: str) -> tuple[int, str]:
    name, query = normalize(name), normalize(query)
    return (0 if name == query else 1 if name.startswith(query) else 2, name)


_VERSION_RE = re.compile(
    r"^\s*v?(?:(\d+)!)?(\d+(?:\.\d+)*)(?:(?:[-_.]?)(a|alpha|b|beta|c|pre|preview|rc)(\d*))?"
    r"(?:(?:[-_.]?)(post|rev|r)(\d*))?(?:(?:[-_.]?)dev(\d*))?"
    r"(?:\+([0-9a-z]+(?:[-_.][0-9a-z]+)*))?\s*$",
    re.IGNORECASE,
)
_PRE_RELEASES = {
    "a": 0,
    "alpha": 0,
    "b": 1,
    "beta": 1,
    "c": 2,
    "pre": 2,
    "preview": 2,
    "rc": 3,
}


def _local_key(value: str | None) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"[-_.]", value or "")
        if part
    )


def version_key(version: str) -> tuple[Any, ...]:
    """Return a dependency-free ordering key for common PEP 440 versions."""
    match = _VERSION_RE.match(version.lower().replace("-", "."))
    if not match:
        return (0, 0, (0,), -1, -1, -1, -1, -1, -1, ())

    epoch, release, pre, pre_number, post, post_number, dev_number, local = (
        match.groups()
    )
    release_parts = tuple(int(part) for part in release.split("."))
    while len(release_parts) > 1 and release_parts[-1] == 0:
        release_parts = release_parts[:-1]
    dev = dev_number is not None
    phase = -1 if dev and pre is None and post is None else 0 if pre else 1
    return (
        1,
        int(epoch or 0),
        release_parts,
        phase,
        _PRE_RELEASES.get(pre, -1),
        int(pre_number or 0),
        int(post_number) if post_number is not None else -1,
        0 if dev else 1,
        int(dev_number or 0),
        1 if local else 0,
        _local_key(local),
    )


def result(source: str, name: str, versions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"source": source, "name": name, "versions": versions}


def default_platform() -> str:
    if sys.platform.startswith("win"):
        return "win-64"
    if sys.platform == "darwin":
        return "osx-arm64" if "arm" in host_platform.machine().lower() else "osx-64"
    return "linux-64"
