"""PyPI and PyPI-compatible Simple-index searches."""

from __future__ import annotations

import urllib.error
import urllib.parse
from typing import Any

from .common import (
    CACHE_DIR,
    EXPECTED_ERRORS,
    Options,
    as_json,
    cache_key,
    fetch,
    links,
    load_cached,
    normalize,
    parallel,
    pypi_source,
    rank,
    result,
    version_key,
)


def project_names(content: bytes) -> list[str]:
    data = as_json(content)
    if isinstance(data, dict):
        names = [
            item["name"]
            for item in data.get("projects", [])
            if isinstance(item, dict) and item.get("name")
        ]
    else:
        names = [
            urllib.parse.unquote(
                urllib.parse.urlsplit(href).path.rstrip("/").split("/")[-1]
            )
            for href in links(content)
        ]
    return sorted({name for name in names if name not in {".", ".."}}, key=normalize)


def index_projects(index: str, options: Options) -> list[str]:
    index = index.rstrip("/") + "/"
    path = CACHE_DIR / "projects" / f"{cache_key(pypi_source(index))}.json"
    return load_cached(
        path,
        options.refresh,
        options.cache_ttl,
        lambda: project_names(
            fetch(index, "application/vnd.pypi.simple.v1+json, text/html;q=0.9")
        ),
    )


def version_from_file(filename: str, package: str) -> str | None:
    filename = urllib.parse.unquote(filename.split("#", 1)[0]).rsplit("/", 1)[-1]
    if filename.endswith(".whl"):
        parts = filename[:-4].split("-")
        if len(parts) < 5:
            return None
        head = "-".join(parts[:-3])
    elif filename.endswith(".tar.gz"):
        head = filename[:-7]
    elif filename.endswith(".zip"):
        head = filename[:-4]
    else:
        return None

    parts = head.split("-")
    for split in range(1, len(parts)):
        if normalize("-".join(parts[:split])) == normalize(package):
            return parts[split]
    return None


def project_files(content: bytes) -> list[str]:
    data = as_json(content)
    if isinstance(data, dict) and isinstance(data.get("files"), list):
        return [
            item.get("filename", "") for item in data["files"] if isinstance(item, dict)
        ]
    return links(content)


def package_versions(
    name: str,
    index: str,
    options: Options,
) -> list[str]:
    source = pypi_source(index)
    path = CACHE_DIR / "metadata" / f"{cache_key(source)}-{cache_key(name)}.json"
    url = f"{index.rstrip('/')}/{urllib.parse.quote(name, safe='')}/"
    versions = load_cached(
        path,
        options.refresh,
        options.cache_ttl,
        lambda: sorted(
            {
                version
                for filename in project_files(
                    fetch(url, "text/html, application/json;q=0.9")
                )
                if (version := version_from_file(filename, name))
            },
            key=version_key,
            reverse=True,
        ),
    )
    return versions[: options.versions]


def search(index: str, options: Options) -> list[dict[str, Any]]:
    index = index.rstrip("/") + "/"
    source = pypi_source(index)
    query = normalize(options.query)
    names = index_projects(index, options)
    matches = sorted(
        (name for name in names if query in normalize(name)),
        key=lambda name: rank(name, query),
    )[: options.limit]

    def load(name: str) -> dict[str, Any] | None:
        try:
            versions = package_versions(name, index, options)
            return (
                result(
                    source,
                    name,
                    [
                        {"version": version, "build": None, "platform": None}
                        for version in versions
                    ],
                )
                if versions
                else None
            )
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            return {
                "source": source,
                "name": name,
                "versions": [],
                "error": "metadata unavailable",
            }
        except EXPECTED_ERRORS:
            return {
                "source": source,
                "name": name,
                "versions": [],
                "error": "metadata unavailable",
            }

    return [row for row in parallel(load, matches) if row is not None]


def search_indexes(
    indexes: list[str],
    options: Options,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    def load(index: str):
        try:
            return search(index, options), None
        except EXPECTED_ERRORS as error:
            return [], {"source": pypi_source(index), "error": str(error)}

    results, errors = [], []
    for rows, error in parallel(load, indexes):
        results.extend(rows)
        if error:
            errors.append(error)
    return results, errors
