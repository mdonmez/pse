import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pse.modules import conda
from pse.modules.common import (
    Options,
    as_json,
    cache_key,
    conda_source,
    load_cached,
    normalize,
    pypi_source,
    rank,
    result,
    version_key,
    write_cache,
)
from pse.modules.pypi import version_from_file


class CommonTests(unittest.TestCase):
    def test_normalize_and_rank_package_names(self):
        self.assertEqual(normalize(" Demo_Package "), "demo-package")
        self.assertEqual(rank("demo-package", "demo"), (1, "demo-package"))
        self.assertEqual(rank("other-demo", "demo"), (2, "other-demo"))

    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.json"
            write_cache(path, {"value": 42})
            self.assertEqual(
                load_cached(path, False, 3600, lambda: None), {"value": 42}
            )

    def test_json_and_result_helpers(self):
        self.assertEqual(as_json(b'{"value": 42}'), {"value": 42})
        self.assertIsNone(as_json(b"not json"))
        self.assertEqual(
            result("pypi", "demo", [{"version": "1.0"}]),
            {"source": "pypi", "name": "demo", "versions": [{"version": "1.0"}]},
        )

    def test_version_order_handles_prereleases(self):
        versions = [
            "2.0",
            "2.0rc1",
            "2.0b1",
            "2.0a1",
            "2.0.dev1",
            "1.0.post1",
            "1.0",
            "1.0rc1",
            "1.0a1",
        ]
        self.assertEqual(
            sorted(versions, key=version_key),
            [
                "1.0a1",
                "1.0rc1",
                "1.0",
                "1.0.post1",
                "2.0.dev1",
                "2.0a1",
                "2.0b1",
                "2.0rc1",
                "2.0",
            ],
        )

    def test_source_labels_hide_credentials(self):
        pypi = pypi_source("https://alice:secret@example.com/simple/")
        conda_url, conda = conda_source("https://alice:secret@example.com/channel")
        self.assertEqual(pypi, "pypi:example.com/simple")
        self.assertEqual(conda, "conda:example.com/channel")
        self.assertNotIn("secret", conda)
        self.assertNotIn("secret", cache_key(conda_url))


class PyPITests(unittest.TestCase):
    def test_version_from_common_archive_names(self):
        self.assertEqual(
            version_from_file("demo_package-1.2.3.tar.gz", "demo-package"),
            "1.2.3",
        )
        self.assertEqual(
            version_from_file("demo_package-1.2.3-py3-none-any.whl", "demo-package"),
            "1.2.3",
        )


class CondaTests(unittest.TestCase):
    def test_versions_are_sorted_before_build_metadata(self):
        options = Options("demo", 10, 10, "noarch", True, 3600)
        records = [
            {
                "name": "demo",
                "source": "conda-forge",
                "version": "1.0",
                "build": "old",
                "build_number": 99,
                "subdir": "noarch",
                "timestamp": 999,
            },
            {
                "name": "demo",
                "source": "conda-forge",
                "version": "2.0",
                "build": "new",
                "build_number": 0,
                "subdir": "noarch",
                "timestamp": 1,
            },
        ]
        with patch.object(conda, "records", return_value=records):
            results, errors = conda.search(["conda-forge"], options)
        self.assertEqual(errors, [])
        self.assertEqual(
            [item["version"] for item in results[0]["versions"]], ["2.0", "1.0"]
        )


if __name__ == "__main__":
    unittest.main()
