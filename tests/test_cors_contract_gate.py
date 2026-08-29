"""`scripts/check_cors_contract.py` has to stay able to be red, and to say so.

Sibling of `tests/test_server_routes_gate.py` and written for the same reason:
a checker is only worth the run if it can fail, and the way a checker stops
being able to fail is never loud. This file holds two properties the gate
cannot lose quietly.

**It reaches the answer.** The canaries in the checker are what prove it goes
red on a header the allowlist does not name. Running them from here means a
canary that stops being run is a failing test rather than a line nobody reads.

**It cannot go silent.** A reader that finds nothing must exit 2, never 0.
That distinction is the entire difference between "the client sends nothing
unusual" and "the reader broke", and every gate in this repository that
collapsed them has been wrong at least once -- most recently the URL scans that
returned `[]` with exit 0 for two days because puppeteer had no browser.

## What this does not prove

That the allowlist is *right*. `services/api/tests/api/test_cors.py` owns that
question and answers it from the server's side. This file only holds that the
client's side keeps being asked.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "check_cors_contract.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_cors_contract", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the checker's dataclasses are declared under
    # `from __future__ import annotations`, and resolving those annotations
    # sends `dataclasses` to `sys.modules[cls.__module__]`. Loading a module
    # without registering it makes that lookup return None.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GateExists(unittest.TestCase):
    def test_the_gate_is_on_disk_and_executable(self):
        self.assertTrue(GATE.is_file(), f"{GATE} không có")

    def test_the_gate_is_wired_into_gate_sh(self):
        """A checker nothing invokes is a file, not a gate."""
        gate_sh = (REPO_ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
        self.assertIn("check_cors_contract.py", gate_sh)
        self.assertIn("do_cors()", gate_sh)


class ReaderReadsTheRealTree(unittest.TestCase):
    """The reader has to actually find the headers this client sends."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load()
        cls.client = REPO_ROOT / "apps" / "mobile" / "src"
        if not cls.client.is_dir():
            raise unittest.SkipTest("apps/mobile/src không có trên nhánh này")
        cls.facts = cls.mod.read_client(cls.client)

    def test_it_finds_the_actor_headers(self):
        """These five are in the tree by hand-count; a reader that misses one
        would print a smaller number and still exit 0."""
        for name in (
            "X-Actor-ID",
            "X-Actor-Roles",
            "X-Actor-Contexts",
            "Content-Type",
            "Idempotency-Key",
        ):
            self.assertIn(name, self.facts.headers, f"reader bỏ sót {name}")

    def test_it_finds_more_than_one_header_site(self):
        """`api.ts` is not the only place headers are built -- there are
        helpers in three chat modules and inline literals in three screens.
        A reader that only followed `api.ts` would answer for a fraction of
        the client and look identical to one that read all of it."""
        self.assertGreater(self.facts.literal_sites, 5)
        self.assertGreater(self.facts.files_read, 20)

    def test_it_reads_methods_too(self):
        self.assertIn("POST", self.facts.methods)


class CannotGoSilent(unittest.TestCase):
    """Nothing read must be exit 2, never exit 0."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATE), *args],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=REPO_ROOT,
        )

    def test_an_empty_client_tree_is_cannot_run_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self._run("--client-dir", tmp)
        self.assertEqual(
            done.returncode,
            2,
            "cây rỗng phải là 'không chạy được' (2), không phải 'sạch' (0).\n"
            f"stdout={done.stdout}\nstderr={done.stderr}",
        )

    def test_a_tree_with_no_header_site_is_cannot_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "x.ts").write_text("export const a = 1;\n", encoding="utf-8")
            done = self._run("--client-dir", str(root))
        self.assertEqual(
            done.returncode,
            2,
            "không thấy chỗ dựng header nào phải là 2, không phải 0.\n"
            f"stdout={done.stdout}\nstderr={done.stderr}",
        )

    def test_the_selftest_passes(self):
        """The canaries are the proof the gate can be red. Run them here so a
        canary that stops holding is a failing test, not a quiet line."""
        done = self._run("--selftest")
        self.assertEqual(
            done.returncode, 0, f"stdout={done.stdout}\nstderr={done.stderr}"
        )
        self.assertIn("self-test ĐẠT", done.stdout)

    def test_the_selftest_actually_runs_every_canary(self):
        """A self-test that quietly ran zero canaries would also print ĐẠT."""
        mod = _load()
        done = self._run("--selftest")
        self.assertGreaterEqual(len(mod.CANARIES), 8)
        for name, _source, _want in mod.CANARIES:
            self.assertIn(name, done.stdout, f"canary {name} không được chạy")

    def test_canaries_cover_both_directions(self):
        """Only-red and only-green canary sets are both decoration."""
        mod = _load()
        wants = {want for _n, _s, want in mod.CANARIES}
        self.assertIn(mod.EXIT_OK, wants)
        self.assertIn(mod.EXIT_MISMATCH, wants)
        self.assertIn(mod.EXIT_CANNOT_RUN, wants)


class PolicyComesFromTheServer(unittest.TestCase):
    """The allowlist must be imported, never transcribed."""

    def test_the_gate_does_not_hold_its_own_copy_of_the_allowlist(self):
        source = GATE.read_text(encoding="utf-8")
        body = source.split('"""', 2)[-1]  # skip the module docstring
        self.assertIn("from app.api.cors import", body)
        for header in ("x-actor-roles", "x-actor-contexts", "idempotency-key"):
            self.assertNotIn(
                f'"{header}"',
                body,
                f"`{header}` bị chép vào cổng — bản chép là thứ thứ ba để lệch, "
                "và lệch đúng chiều không ai nhìn thấy.",
            )

    def test_content_type_is_not_treated_as_safelisted(self):
        """`application/json` is not a safelisted media type, so Content-Type
        genuinely needs an allowlist entry. Calling it free here would make the
        gate agree with a request the browser refuses."""
        mod = _load()
        self.assertNotIn("content-type", mod.SAFELISTED_HEADERS)
        self.assertIn("accept", mod.SAFELISTED_HEADERS)


if __name__ == "__main__":
    unittest.main()
