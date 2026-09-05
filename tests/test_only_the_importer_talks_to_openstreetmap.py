"""Nothing serving a request may call OpenStreetMap (ADR-0017 §2.2, §5).

The import is a script an operator runs. If a route, a service or an adapter
ever reached Overpass while answering somebody, three things would follow at
once: a page would hang on a third party's rate limit, a stranger's query
would leave the box on every read, and the catalogue would stop being data we
hold and start being data we borrow per request.

Written as a tree scan rather than a rule in a review checklist, because the
repo guard sees what enters Git and nothing sees what leaves over HTTP.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = REPO_ROOT / "services" / "api" / "app"
IMPORTER = REPO_ROOT / "scripts" / "import_osm_places.py"

HOSTS = re.compile(
    r"overpass-api\.de|overpass\.kumi\.systems|nominatim\.openstreetmap\.org"
    r"|api\.openstreetmap\.org",
    re.IGNORECASE,
)


class OnlyTheImporterTalksToOsm(unittest.TestCase):
    def test_the_importer_exists_and_is_the_one_that_calls_overpass(self):
        self.assertTrue(IMPORTER.is_file(), "script nhập không còn ở chỗ cũ")
        text = IMPORTER.read_text(encoding="utf-8")
        self.assertRegex(text, HOSTS, "script nhập phải là nơi gọi Overpass")

    def test_no_module_under_app_names_an_openstreetmap_host(self):
        offenders = []
        for path in sorted(APP.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                # Prose may explain where the data came from; code may not go
                # and get it. A comment or a docstring line is documentation.
                if stripped.startswith("#"):
                    continue
                if HOSTS.search(line) and '"""' not in line:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}")
        self.assertEqual(
            offenders,
            [],
            "mã phục vụ request không được gọi ra OpenStreetMap: "
            + ", ".join(offenders),
        )

    def test_the_scan_can_go_red(self):
        """A tree scan that reads nothing passes silently. Prove it bites."""
        fake = "response = urlopen('https://overpass-api.de/api/interpreter')"
        self.assertTrue(HOSTS.search(fake))
        self.assertIsNone(HOSTS.search("response = urlopen('https://example.test')"))

    def test_the_scan_actually_read_the_tree(self):
        files = list(APP.rglob("*.py"))
        self.assertGreater(len(files), 50, "quét được quá ít file, glob hỏng rồi")


if __name__ == "__main__":
    unittest.main()
