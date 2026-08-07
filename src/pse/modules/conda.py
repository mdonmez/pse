"""Conda channel searches."""

from __future__ import annotations

import bz2
import json
from typing import Any

from .common import (
    CACHE_DIR,
    EXPECTED_ERRORS,
    Options,
    cache_key,
    conda_source,
    fetch,
    load_cached,
    normalize,
    parallel,
    rank,
    result,
)


def records(channel: str, subdir: str, options: Options) -> list[dict[str, Any]]:
    url, source = conda_source(channel)
    path = CACHE_DIR / "conda" / f"{cache_key(url)}-{cache_key(subdir)}.json"

    def load():
        data = json.loads(
            bz2.decompress(
                fetch(
                    f"{url}/{subdir}/current_repodata.json.bz2",
                    "application/octet-stream",
                    120,
                )
            )
        )
        return [
            {
                "name": package.get("name", ""),
                "source": source,
                "version": package.get("version", ""),
                "build": package.get("build", ""),
                "build_number": package.get("build_number", 0),
                "subdir": package.get("subdir", subdir),
                "timestamp": package.get("timestamp", 0),
            }
            for section in ("packages", "packages.conda")
            for package in data.get(section, {}).values()
        ]

    return load_cached(path, options.refresh, options.cache_ttl, load)


def search(
    channels: list[str],
    options: Options,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    subdirs = (
        [options.platform]
        if options.platform == "noarch"
        else [options.platform, "noarch"]
    )
    jobs = [(channel, subdir) for channel in channels for subdir in subdirs]

    def load(job: tuple[str, str]):
        channel, subdir = job
        try:
            return records(channel, subdir, options), None
        except EXPECTED_ERRORS as error:
            return [], {"source": conda_source(channel)[1], "error": str(error)}

    all_records, errors, seen_errors = [], [], set()
    for batch, error in parallel(load, jobs):
        all_records.extend(batch)
        if error and (key := (error["source"], error["error"])) not in seen_errors:
            seen_errors.add(key)
            errors.append(error)

    query = normalize(options.query)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for package in all_records:
        name = package["name"]
        if name and query in normalize(name):
            groups.setdefault((package["source"], name), []).append(package)

    by_source: dict[str, list[tuple[str, str]]] = {}
    for source, name in groups:
        by_source.setdefault(source, []).append((source, name))

    selected = []
    for source in dict.fromkeys(package["source"] for package in all_records):
        selected += sorted(
            by_source.get(source, []),
            key=lambda item: rank(item[1], query),
        )[: options.limit]

    results = []
    for source, name in selected:
        versions, seen = [], set()
        for package in sorted(
            groups[(source, name)],
            key=lambda item: (
                int(item.get("timestamp") or 0),
                int(item.get("build_number") or 0),
            ),
            reverse=True,
        ):
            version = package["version"]
            if version and version not in seen:
                seen.add(version)
                versions.append(
                    {
                        "version": version,
                        "build": package["build"],
                        "platform": package["subdir"],
                    }
                )
                if len(versions) == options.versions:
                    break
        if versions:
            results.append(result(source, name, versions))
    return results, errors
