"""Two gate anchor tables must refuse to run when gutted, not report a clean tree.

`scripts/check_pin_drift.py` and `scripts/check_api_contract.py` each decide what
to look at by consulting a hardcoded table. Neither table had a floor, so both
gates expressed two opposite facts with one value:

    "no import-critical pin drifted"   /   "no pin is treated as import-critical"
    "the client matches the contract"  /   "the reader recognises no call at all"

In each pair the second sentence is the gate switched off, and it is the one
that makes no sound. Measured on this tree before these floors existed:

    check_pin_drift, requirements pinning fastapi+pytest to versions nobody has
        IMPORT_CRITICAL intact      exit 1
        IMPORT_CRITICAL = frozenset()   exit 0        <- gate off, reads as clean

    check_api_contract, real client
        intact                      67 đường dẫn, 79 lần gọi, 12 file, exit 0
        bỏ "translatedAnonymous"    64 đường dẫn, 75 lần gọi, 12 file, exit 0
        bỏ "doFetch"                63 đường dẫn, 75 lần gọi,  8 file, exit 0

Four files stopped being read and the gate still printed "Client và máy chủ khớp
hợp đồng". #430 already put a floor under `WRAPPERS`, but it only fires at
*empty*, and emptiness is not how these tables degrade -- losing one name leaves
the derived tuple non-empty and the floor quiet. The sibling test
`test_every_wrapper_it_reads_is_still_declared_in_api_ts` iterates `WRAPPERS`, so
a deleted name deletes its own guard. Both existing defences ask "is every name I
know still in the client"; neither can ask "is every name the client has still
known to me". That second question is what this file pins.

Each floor is anchored to a literal written a second time, so disarming it means
editing two places in step; a count pins the anchor itself so that gutting the
anchor is not the cheap way through.

Every mutation asserts its own substitution landed before drawing a conclusion.
A `str.replace` that matches nothing yields an unmutated module that loads fine
-- which reads exactly like "the floor held".
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIN_DRIFT = REPO / "scripts" / "check_pin_drift.py"
API_CONTRACT = REPO / "scripts" / "check_api_contract.py"

# Restated here rather than imported: a floor that reads its expectation out of
# the module it guards is satisfied by emptying both. Two files must move in
# step, which is the point.
PINNED_IMPORT_CRITICAL = frozenset(
    {
        "fastapi",
        "starlette",
        "pydantic",
        "sqlalchemy",
        "alembic",
        "pytest",
        "pytest-subtests",
    }
)
PINNED_REQUEST_FUNCTIONS = frozenset(
    {
        "fetch",
        "doFetch",
        "callAsActor",
        "callAnonymous",
        "translatedAsActor",
        "translatedAnonymous",
    }
)

# `check_api_contract` reserves 2 for "could not read" and 1 for "the client
# violates the contract". A broken reader must never claim the second.
EXIT_CANNOT_READ = 2
EXIT_VIOLATION = 1


class FloorCase(unittest.TestCase):
    """Shared machinery: mutate a source file, then load or run the result."""

    module_path: Path

    def mutate(self, old: str, new: str, *, source: str | None = None) -> str:
        original = (
            source
            if source is not None
            else self.module_path.read_text(encoding="utf-8")
        )
        self.assertIn(
            old,
            original,
            f"mutation target không còn trong {self.module_path.name} -- "
            "ca này đang không đo gì cả",
        )
        mutated = original.replace(old, new, 1)
        self.assertNotEqual(mutated, original, "đột biến là no-op")
        return mutated

    def load(self, src: str, name: str) -> dict:
        """Execute a source string as a module body, returning its namespace.

        Registered in `sys.modules` under a real module object, not exec'd into
        a bare dict: `@dataclass` resolves its annotations through
        `sys.modules[cls.__module__]`, so a bare dict raises `AttributeError`
        from inside dataclasses and every case would fail for a reason that has
        nothing to do with the floor being measured.
        """

        module = types.ModuleType(name)
        module.__file__ = str(self.module_path)
        sys.modules[name] = module
        try:
            exec(compile(src, str(self.module_path), "exec"), module.__dict__)  # noqa: S102
        finally:
            sys.modules.pop(name, None)
        return module.__dict__

    def assert_refuses_to_load(self, src: str, name: str, expect: str) -> None:
        with self.assertRaises(RuntimeError) as caught:
            self.load(src, name)
        self.assertIn(expect, str(caught.exception))

    def run_mutated_cli(self, src: str) -> subprocess.CompletedProcess:
        """Run a mutated copy as a real script, for the real exit code.

        Safe to run from a temp directory: the floor raises while the module
        body is still executing, before anything resolves a repo path, so the
        copy never depends on where it sits. The intact controls run the real
        file in place, where the paths do matter.
        """

        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / self.module_path.name
            script.write_text(src, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                timeout=300,
            )


class ImportCriticalFloorTests(FloorCase):
    module_path = PIN_DRIFT

    def test_the_intact_table_still_loads_and_lists_every_pinned_name(self):
        """Positive control. Red here means the floor is over-tight, not safe."""

        namespace = self.load(
            self.module_path.read_text(encoding="utf-8"), "check_pin_drift_intact"
        )
        self.assertEqual(
            sorted(PINNED_IMPORT_CRITICAL - namespace["IMPORT_CRITICAL"]),
            [],
            "IMPORT_CRITICAL đã mất tên so với danh sách ghim trong test này",
        )

    def test_the_intact_cli_never_answers_could_not_run(self):
        """Positive control on the real file, in place.

        Deliberately not asserting 0: this repository's own measurement is that
        pins here genuinely drift, so 1 is a truthful answer. 2 would mean the
        floor is firing on an intact tree.
        """

        done = subprocess.run(
            [sys.executable, str(self.module_path)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=REPO,
        )
        self.assertIn(done.returncode, (0, 1), done.stderr[-400:])

    def test_an_empty_table_refuses_to_load(self):
        """The shape qa2's probe measured: the table bound to nothing.

        Rebound after the real table is built and before the floor runs, so the
        `not IMPORT_CRITICAL` branch is what answers rather than the
        missing-names branch that would also catch it.
        """

        src = self.mutate(
            "\nclass GateBroken(RuntimeError):",
            "\nIMPORT_CRITICAL = frozenset()\n\n\nclass GateBroken(RuntimeError):",
        )
        self.assert_refuses_to_load(
            src, "check_pin_drift_empty", "IMPORT_CRITICAL rỗng"
        )

    def test_dropping_one_required_name_refuses_to_load(self):
        """The case #430's kind of floor cannot see: smaller, not empty."""

        src = self.mutate('        "fastapi",\n', "")
        self.assert_refuses_to_load(
            src, "check_pin_drift_partial", "không còn liệt kê ['fastapi']"
        )

    def test_gutting_the_anchor_as_well_is_still_caught_by_the_count(self):
        """Editing both places in step must not be the cheap way through."""

        src = self.mutate('        "fastapi",\n', "")
        src = self.mutate('        "fastapi",\n', "", source=src)
        self.assert_refuses_to_load(
            src, "check_pin_drift_both", "REQUIRED_IMPORT_CRITICAL chỉ còn 6 tên"
        )

    def test_cutting_the_wire_to_the_exit_code_is_caught_by_consequence(self):
        """Table full, derivation rewritten -- the branch that checks an effect."""

        src = self.mutate(
            'return [r for r in rows if r["critical"] and r["state"] != "match"]',
            "return []",
        )
        self.assert_refuses_to_load(
            src, "check_pin_drift_wire", "KHÔNG bị critical_offenders báo"
        )

    def test_a_gutted_table_exits_two_not_zero_and_not_one(self):
        """The whole point, at the real entry point.

        2 is this file's documented "could not run at all". 0 would be the
        silent pass this floor exists to remove; 1 would be a false claim about
        the requirements file.
        """

        src = self.mutate('        "fastapi",\n', "")
        done = self.run_mutated_cli(src)
        self.assertEqual(done.returncode, 2, done.stdout[-300:] + done.stderr[-300:])
        self.assertIn("cổng tự từ chối chạy", done.stderr)


class RequestFunctionsFloorTests(FloorCase):
    module_path = API_CONTRACT

    def test_the_intact_table_still_loads_and_lists_every_pinned_name(self):
        """Positive control."""

        namespace = self.load(
            self.module_path.read_text(encoding="utf-8"), "check_api_contract_intact"
        )
        self.assertEqual(
            sorted(PINNED_REQUEST_FUNCTIONS - set(namespace["REQUEST_FUNCTIONS"])),
            [],
            "REQUEST_FUNCTIONS đã mất tên so với danh sách ghim trong test này",
        )

    def test_dropping_one_wrapper_refuses_to_load(self):
        """Measured silent before this floor: 67 -> 64 paths, still exit 0."""

        src = self.mutate('    "translatedAnonymous": (1, 2),\n', "")
        self.assert_refuses_to_load(
            src, "cac_drop_wrapper", "không còn tên ['translatedAnonymous']"
        )

    def test_dropping_direct_fetch_refuses_to_load(self):
        """Measured silent before this floor: 12 files -> 8, still exit 0.

        `doFetch` is not a wrapper, so `WRAPPERS` never changes and #430's floor
        stays quiet -- this is the half of the question it could not ask.
        """

        src = self.mutate('    "doFetch": (0, 1),\n', "")
        self.assert_refuses_to_load(
            src, "cac_drop_dofetch", "không còn tên ['doFetch']"
        )

    def test_gutting_the_anchor_as_well_is_still_caught_by_the_count(self):
        src = self.mutate('    "translatedAnonymous": (1, 2),\n', "")
        src = self.mutate('        "translatedAnonymous",\n', "", source=src)
        self.assert_refuses_to_load(
            src, "cac_both", "REQUIRED_REQUEST_FUNCTIONS chỉ còn 5 tên"
        )

    def test_direct_fetch_swallowing_a_wrapper_is_caught(self):
        """`WRAPPERS` shrinks without `REQUEST_FUNCTIONS` losing anything."""

        src = self.mutate(
            'DIRECT_FETCH = ("fetch", "doFetch")',
            'DIRECT_FETCH = ("fetch", "doFetch", "callAsActor")',
        )
        self.assert_refuses_to_load(src, "cac_swallow", "không còn nằm trong WRAPPERS")

    def test_rewriting_the_matcher_is_caught_by_consequence(self):
        """Table full, regex no longer built from all of it."""

        src = self.mutate(
            '+ "|".join(sorted(REQUEST_FUNCTIONS, key=len, reverse=True))',
            '+ "|".join(\n        sorted(\n            [n for n in REQUEST_FUNCTIONS if n != "doFetch"],\n'
            "            key=len,\n            reverse=True,\n        )\n    )",
        )
        self.assert_refuses_to_load(src, "cac_regex", "CALLEE không khớp lời gọi qua")

    def test_a_gutted_table_exits_cannot_read_never_violation(self):
        """A broken reader must not be reported as a broken client.

        1 here is `EXIT_VIOLATION`, which gate.sh reads as "the client breaks the
        contract" -- blaming somebody else's code for this reader's own
        misconfiguration. That is the confusion #398 was opened to undo.

        Asserting the floor's OWN sentence, not just the code and not just the
        "KHÔNG CHẠY ĐƯỢC" prefix. Measured while writing this: the copy runs from
        a temp directory, so before the floor existed it already exited 2 saying
        `apps/mobile/src không có trên nhánh này` -- a real answer to a different
        question. Both looser assertions passed against the unpatched file, so
        this case was green for a reason that had nothing to do with the floor.
        """

        src = self.mutate('    "doFetch": (0, 1),\n', "")
        done = self.run_mutated_cli(src)
        self.assertNotEqual(done.returncode, EXIT_VIOLATION, "đổ lỗi cho client")
        self.assertEqual(
            done.returncode,
            EXIT_CANNOT_READ,
            done.stdout[-300:] + done.stderr[-300:],
        )
        self.assertIn(
            "REQUEST_FUNCTIONS không còn tên ['doFetch']",
            done.stderr,
            "thoát 2 nhưng vì lý do khác -- ca này không đo được cái sàn",
        )


if __name__ == "__main__":
    unittest.main()
