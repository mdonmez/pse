"""Human and machine-readable output."""

from __future__ import annotations

import json
import sys
from typing import Any

from .common import Options


def table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No matching package names.")
        return

    source_width = min(36, max(6, max(len(row["source"]) for row in rows)))
    name_width = min(32, max(4, max(len(row["name"]) for row in rows)))

    def fit(value: str, width: int) -> str:
        return value if len(value) <= width else value[: width - 1] + "…"

    def version_text(item: dict[str, Any]) -> str:
        details = [str(item[name]) for name in ("build", "platform") if item.get(name)]
        return item["version"] + (f" [{'; '.join(details)}]" if details else "")

    print(f"{'Source':<{source_width}}  {'Name':<{name_width}}  Versions")
    print("-" * (source_width + name_width + 14))
    for row in rows:
        versions = ", ".join(version_text(item) for item in row.get("versions", []))
        print(
            f"{fit(row['source'], source_width):<{source_width}}  "
            f"{fit(row['name'], name_width):<{name_width}}  "
            f"{versions or 'unavailable'}"
        )
        if row.get("error"):
            print(
                f"Warning: {row['source']} {row['name']}: {row['error']}",
                file=sys.stderr,
            )


def json_document(
    options: Options,
    rows: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> None:
    document: dict[str, Any] = {
        "query": options.query,
        "platform": options.platform,
        "results": rows,
    }
    if errors:
        document["errors"] = errors
    print(json.dumps(document, indent=2, ensure_ascii=False))
