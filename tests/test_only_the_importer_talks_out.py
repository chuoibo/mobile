"""Nothing serving a request may call OpenStreetMap or Wikimedia (ADR-0017).

The import is a script an operator runs. If a route, a service or an adapter
ever reached Overpass while answering somebody, three things would follow at
once: a page would hang on a third party's rate limit, a stranger's query
would leave the box on every read, and the catalogue would stop being data we
hold and start being data we borrow per request.

Written as a tree scan rather than a rule in a review checklist, because the
repo guard sees what enters Git and nothing sees what leaves over HTTP.

Two outward doors now, and the second one (Commons, M12) is the one with a
person on the other end of it: a picture request carries the reader's address
to a third party. It belongs to the import script, which runs on our machine
about places, not to a route that runs on a reader's tap.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = REPO_ROOT / "services" / "api" / "app"
IMPORTERS = {
    "osm": REPO_ROOT / "scripts" / "import_osm_places.py",
    "anh": REPO_ROOT / "scripts" / "import_place_photos.py",
}

HOSTS = re.compile(
    r"overpass-api\.de|overpass\.kumi\.systems|nominatim\.openstreetmap\.org"
    r"|api\.openstreetmap\.org|commons\.wikimedia\.org|upload\.wikimedia\.org"
    r"|api\.wikimedia\.org",
    re.IGNORECASE,
)


class OnlyTheImporterTalksOut(unittest.TestCase):
    def test_each_importer_exists_and_is_the_one_that_calls_out(self):
        for ten, path in IMPORTERS.items():
            with self.subTest(ten):
                self.assertTrue(path.is_file(), f"script nhập {ten} không còn ở chỗ cũ")
                text = path.read_text(encoding="utf-8")
                self.assertRegex(text, HOSTS, f"script {ten} phải là nơi gọi ra ngoài")

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
            "mã phục vụ request không được gọi ra OpenStreetMap hay Wikimedia: "
            + ", ".join(offenders),
        )

    def test_the_scan_can_go_red(self):
        """A tree scan that reads nothing passes silently. Prove it bites."""
        for fake in (
            "response = urlopen('https://overpass-api.de/api/interpreter')",
            "response = urlopen('https://commons.wikimedia.org/w/api.php')",
            "img = urlopen('https://upload.wikimedia.org/wikipedia/commons/x.jpg')",
        ):
            with self.subTest(fake):
                self.assertTrue(HOSTS.search(fake))
        self.assertIsNone(HOSTS.search("response = urlopen('https://example.test')"))

    def test_the_scan_actually_read_the_tree(self):
        files = list(APP.rglob("*.py"))
        self.assertGreater(len(files), 50, "quét được quá ít file, glob hỏng rồi")


if __name__ == "__main__":
    unittest.main()
