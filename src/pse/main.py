"""Command-line entry point for pse."""

from __future__ import annotations

import argparse
import sys

from .modules.common import (
    CONDA_CHANNEL,
    DEFAULT_CACHE_TTL,
    DEFAULT_LIMIT,
    DEFAULT_VERSIONS,
    EXPECTED_ERRORS,
    PYPI_INDEX,
    VERSION,
    Options,
    default_platform,
)
from .modules.conda import search as search_conda
from .modules.output import json_document, table
from .modules.pypi import search_indexes


def integer(value: str, minimum: int = 0) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if number < minimum:
        raise argparse.ArgumentTypeError(f"must be at least {minimum}")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pse",
        description="Search package names and versions across PyPI and Conda channels.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("query", help="Search text, for example: torch")
    parser.add_argument(
        "-n",
        "--limit",
        type=lambda value: integer(value, 1),
        metavar="N",
        default=DEFAULT_LIMIT,
        help="Maximum matching names per source or channel.",
    )
    parser.add_argument(
        "-v",
        "--versions",
        dest="version_limit",
        type=lambda value: integer(value, 1),
        metavar="N",
        default=DEFAULT_VERSIONS,
        help="Maximum versions shown per package.",
    )
    parser.add_argument(
        "-p",
        "--platform",
        default=default_platform(),
        help="Conda platform.",
    )
    parser.add_argument(
        "--pypi-index",
        action="append",
        default=[],
        metavar="URL",
        help="Additional PyPI-compatible Simple index; repeatable.",
    )
    parser.add_argument(
        "--conda-channel",
        action="append",
        default=[],
        metavar="CHANNEL",
        help="Additional Conda channel name or URL; repeatable.",
    )
    parser.add_argument(
        "--refresh",
        "--no-cache",
        action="store_true",
        help="Bypass the local cache.",
    )
    parser.add_argument(
        "--cache-ttl",
        type=integer,
        default=DEFAULT_CACHE_TTL,
        help="Cache lifetime in seconds.",
    )
    parser.add_argument("--json", action="store_true", help="Output one JSON document.")
    parser.add_argument("--version", action="version", version=f"pse.py {VERSION}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    query = args.query.strip()
    if not query:
        print("The search query must not be empty.", file=sys.stderr)
        return 2

    options = Options(
        query=query,
        limit=args.limit,
        versions=args.version_limit,
        platform=args.platform,
        refresh=args.refresh,
        cache_ttl=args.cache_ttl,
    )
    rows, errors = search_indexes(
        [PYPI_INDEX, *args.pypi_index],
        options,
    )
    try:
        conda_rows, conda_errors = search_conda(
            [CONDA_CHANNEL, *args.conda_channel],
            options,
        )
        rows.extend(conda_rows)
        errors.extend(conda_errors)
    except EXPECTED_ERRORS as error:
        errors.append({"source": "conda", "error": str(error)})

    if args.json:
        json_document(options, rows, errors)
    else:
        table(rows)
        for error in errors:
            print(f"Error: {error['source']}: {error['error']}", file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
