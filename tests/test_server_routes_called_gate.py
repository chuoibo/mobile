"""What the "is anybody calling this route?" gate must catch, and must not.

## The hole this closes

`scripts/check_api_contract.py` asks whether every path the app calls exists on
the server. Nothing asked the other direction until 2026-08-30, and the other
direction is where a merged, tested, green feature can be unreachable: a route
no screen calls does not exist for a user.

The question was attempted twice by hand that day and got a different wrong
answer each time. Both wrong answers are canaries here, because they are the
two ways this specific check fails:

  - **Substring matching** (`"posts" in source`) called the four `/posts`
    routes of #308 alive. This codebase writes about itself constantly; the
    word "posts" is English prose in `CheckIn.tsx` and `KyNiem.tsx`. A false
    PASS, and the dangerous direction -- four dead routes reported healthy.
  - **Whole-string matching** called 32 live routes dead, `/places/search` and
    the `/contexts/{id}/messages` family among them, because the client writes
    `` `${base}/contexts/${nhomId}/messages` `` and the server writes
    `/contexts/{context_id}/messages`. A false FAIL, and a gate wrong about 32
    routes on the day it lands is a gate nobody runs twice.

So the tests come in three parts and all three are load bearing: the gate BITES
on a route with no caller and names it; it stays QUIET about prose and about a
client that spells its parameters differently; and the accounting that makes
today's tree green is proven to be doing work rather than returning `[]`.

## Why `test_without_the_debt_file_the_real_tree_is_red` matters most

`.server-routes-uncalled.json` records 22 routes with no caller, which is what
makes `main` exit 0. Every other test in this file would still pass if the
comparison were replaced with `return []`. That one fails in that world.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "check_server_routes_called.py"

SPEC = importlib.util.spec_from_file_location("check_server_routes_called", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
# Registered before exec for the reason its twin's test file records:
# `@dataclass` resolves annotations through `sys.modules[cls.__module__]`.
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)

TEMPLATES = REPO_ROOT / "services" / "api" / "app" / "web" / "templates"


def server(*paths: str):
    """A server declaring exactly these paths, spelled the way FastAPI does."""
    return gate.twin.read_contract({"paths": {p: {"get": {}} for p in paths}})


def client(*sources: str) -> dict[str, list]:
    """The routes a client made of these sources names."""
    found: dict[str, list] = {}
    for i, src in enumerate(sources):
        for key, where in gate.mentions_in_source(src, f"__t{i}__.ts").items():
            found.setdefault(key, []).extend(where)
    return found


def reported(contract, mentions, *, debt=None) -> set[str]:
    """The route names the gate would print, under the real exemption list."""
    findings, _, _ = gate.uncalled(
        contract, mentions, gate.load_exemptions(), debt or {}
    )
    return {f.route for f in findings}


class TheGateBites(unittest.TestCase):
    """The defect: a route the server declares and nobody calls."""

    def test_selftest_passes(self):
        """The canary table the gate carries for `gate.sh` to run first."""
        self.assertEqual(gate.selftest(), 0)

    def test_a_route_with_no_caller_is_reported_by_name(self):
        # Asserting on the name, not on "some finding appeared". A gate that
        # reddens for the wrong route reads exactly like one that works.
        got = reported(
            server("/healthz", "/ai-khong-goi"), client('const a = "/healthz";')
        )
        self.assertEqual(got, {"/ai-khong-goi"})

    def test_a_route_named_only_in_prose_is_still_reported(self):
        """The substring attempt's false pass, pinned.

        `tokenize` classifies comments as their own token kind and
        `literal_shape` refuses them, which is the whole reason this is not a
        text search over the file.
        """
        source = """
        /* F42. POST /posts writes a post; GET /posts reads the wall. */
        // TODO: call /posts from the wall screen.
        const unrelated = "/healthz";
        """
        self.assertEqual(
            reported(server("/posts", "/healthz"), client(source)), {"/posts"}
        )

    def test_a_suffix_route_is_not_covered_by_its_longer_sibling(self):
        """`/posts` is a suffix of `/people/{id}/posts` and a separate route."""
        source = "const a = `/people/${id}/posts`;"
        got = reported(server("/posts", "/people/{person_id}/posts"), client(source))
        self.assertEqual(got, {"/posts"})

    def test_a_prefix_route_is_not_covered_by_its_longer_child(self):
        """The mirror of the case above: `/contexts` vs `/contexts/{id}`."""
        source = "const a = `/contexts/${id}`;"
        got = reported(server("/contexts", "/contexts/{context_id}"), client(source))
        self.assertEqual(got, {"/contexts"})


class TheGateStaysQuiet(unittest.TestCase):
    """The false-fail direction: 32 live routes called dead."""

    def test_a_client_parameter_named_differently_is_still_a_caller(self):
        source = "const a = `${base}/contexts/${nhomId}/messages`;"
        self.assertEqual(
            reported(server("/contexts/{context_id}/messages"), client(source)), set()
        )

    def test_a_path_built_without_the_base_url_is_still_a_caller(self):
        """Both spellings occur in this client and both must be understood."""
        source = "const a = `/contexts/${id}/messages`;"
        self.assertEqual(
            reported(server("/contexts/{context_id}/messages"), client(source)), set()
        )

    def test_a_caller_in_any_file_counts(self):
        """The scope is the whole client, not one module.

        Deliberately wider than the twin gate's request-call-site scope: for
        THIS question a call the reader cannot follow becomes a route falsely
        declared dead, which is the expensive direction.
        """
        self.assertEqual(
            reported(
                server("/places/search"),
                client("const x = 1;", 'const y = "/places/search";'),
            ),
            set(),
        )

    def test_a_debt_pin_excuses_its_route(self):
        contract = server("/posts")
        debt = {gate.twin.normalise("/posts"): gate.Accounted("/posts", "vì sao", "no")}
        self.assertEqual(reported(contract, client("const a = 1;"), debt=debt), set())


class TheExemptionIsNotABlanket(unittest.TestCase):
    """The guest page has a real caller; a prefix rule would swallow more."""

    def test_a_listed_guest_route_is_quiet(self):
        contract = server("/g/{token}", "/g/{token}/da-chuyen")
        self.assertEqual(reported(contract, client('const a = "/healthz";')), set())

    def test_an_unlisted_guest_route_is_reported(self):
        """The canary against somebody rewriting the list as `startswith("/g")`."""
        contract = server("/g/{token}/canary-chua-ghi-ly-do")
        got = reported(contract, client('const a = "/healthz";'))
        self.assertEqual(got, {"/g/{token}/canary-chua-ghi-ly-do"})

    def test_every_exemption_carries_a_reason(self):
        for entry in gate.EXEMPT_ROUTES:
            with self.subTest(route=entry.get("route")):
                self.assertTrue(
                    entry.get("reason"), "miễn không lý do là một cái nhún vai"
                )

    def test_every_exempt_route_is_really_called_by_a_guest_template(self):
        """The exemption claims a caller. This checks the claim.

        Without it the list is five assertions nobody has verified, which is the
        same shape as the pin lists this repository keeps finding gone stale.
        """
        if not TEMPLATES.is_dir():
            self.skipTest("services/api/app/web/templates không có trên nhánh này")
        blob = "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(TEMPLATES.glob("*.html"))
        )
        for entry in gate.EXEMPT_ROUTES:
            route = entry["route"]
            # `/g/{token}/da-chuyen` is written `/g/{{ token }}/da-chuyen` in
            # Jinja, so the tail after the parameter is what is comparable.
            tail = route.split("}", 1)[1]
            with self.subTest(route=route):
                needle = f"/g/{{{{ token }}}}{tail}"
                self.assertIn(
                    needle,
                    blob,
                    f"{route} được miễn với lý do 'template trang khách gọi', "
                    f"nhưng không template nào chứa {needle!r}. Lý do đã cũ.",
                )


class TheDebtFileIsHonest(unittest.TestCase):
    def test_it_parses_and_every_entry_has_a_reason(self):
        if not gate.DEBT_PIN.exists():
            self.skipTest("không có file nợ trên nhánh này")
        raw = json.loads(gate.DEBT_PIN.read_text(encoding="utf-8"))
        entries = raw.get("uncalled", [])
        self.assertGreater(len(entries), 0, "file nợ tồn tại mà rỗng")
        for entry in entries:
            with self.subTest(route=entry.get("route")):
                self.assertTrue(entry.get("route"))
                self.assertTrue(entry.get("reason"), "nợ không lý do là bãi đỗ xe")

    def test_no_route_is_pinned_twice(self):
        if not gate.DEBT_PIN.exists():
            self.skipTest("không có file nợ trên nhánh này")
        raw = json.loads(gate.DEBT_PIN.read_text(encoding="utf-8"))
        routes = [e["route"] for e in raw.get("uncalled", [])]
        self.assertEqual(
            sorted(routes), sorted(set(routes)), "có route bị ghim hai lần"
        )

    def test_debt_and_exemption_do_not_overlap(self):
        """A route is either called from elsewhere or uncalled. Never both.

        Collapsing the two loses the only distinction worth reading later: an
        exemption says "somebody calls this", a debt says "nobody does".
        """
        overlap = sorted(set(gate.load_debt()) & set(gate.load_exemptions()))
        self.assertEqual(overlap, [], f"vừa miễn vừa nợ: {overlap}")

    def test_a_pin_without_a_reason_refuses_to_run(self):
        # Refusing is exit 2, and could-not-run is never a pass.
        with tempfile.TemporaryDirectory() as tmp:
            pin = Path(tmp) / "debt.json"
            pin.write_text(
                json.dumps({"uncalled": [{"route": "/x"}]}), encoding="utf-8"
            )
            original, gate.DEBT_PIN = gate.DEBT_PIN, pin
            try:
                with self.assertRaises(RuntimeError):
                    gate.load_debt()
            finally:
                gate.DEBT_PIN = original

    def test_a_malformed_pin_file_refuses_to_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            pin = Path(tmp) / "debt.json"
            pin.write_text("{ khong phai json", encoding="utf-8")
            original, gate.DEBT_PIN = gate.DEBT_PIN, pin
            try:
                with self.assertRaises(RuntimeError):
                    gate.load_debt()
            finally:
                gate.DEBT_PIN = original

    def test_a_debt_that_gained_a_caller_is_reported_but_not_fatal(self):
        """Paying a debt down must not turn the gate red.

        A gate that goes red for an improvement is switched off within a day.
        """
        contract = server("/posts")
        debt = {gate.twin.normalise("/posts"): gate.Accounted("/posts", "vì sao", "no")}
        findings, _, stale = gate.uncalled(
            contract, client('const a = "/posts";'), {}, debt
        )
        self.assertEqual([f.route for f in findings], [])
        self.assertTrue(any("/posts" in note for note in stale))

    def test_a_pin_for_a_route_the_server_dropped_is_reported(self):
        _, _, stale = gate.uncalled(
            server("/healthz"),
            client('const a = "/healthz";'),
            {},
            {gate.twin.normalise("/da-xoa"): gate.Accounted("/da-xoa", "r", "no")},
        )
        self.assertTrue(any("/da-xoa" in note for note in stale))


class TheMechanismIsLoadBearing(unittest.TestCase):
    def test_without_the_debt_file_the_real_tree_is_red(self):
        """Every other test here would pass if the comparison returned `[]`.

        The debt file is what makes `main` exit 0, so its removal has to be
        visible. This reads the real client and the routes the debt file names,
        and asserts they genuinely have no caller -- which is the claim the file
        makes, checked rather than trusted.
        """
        if not gate.twin.CLIENT_ROOT.is_dir():
            self.skipTest("apps/mobile không có trên nhánh này")
        if not gate.DEBT_PIN.exists():
            self.skipTest("không có file nợ trên nhánh này")
        raw = json.loads(gate.DEBT_PIN.read_text(encoding="utf-8"))
        pinned = [e["route"] for e in raw.get("uncalled", [])]
        contract = server(*pinned)
        got = reported(contract, gate.client_mentions(), debt={})
        self.assertEqual(
            sorted(got),
            sorted(pinned),
            "file nợ khai những route này không ai gọi, nhưng cổng không báo "
            "đúng tập đó khi bỏ ghim đi -- hoặc cơ chế không gác gì, hoặc có "
            "dòng đã trả nợ mà chưa gỡ.",
        )

    def test_the_real_client_names_some_routes_at_all(self):
        """A reader that finds nothing calls every route dead.

        This is the denominator. Without it the assertion above passes just as
        happily on a broken tokenizer, because "no client mentions anything" and
        "every pinned route is uncalled" are the same sentence.
        """
        if not gate.twin.CLIENT_ROOT.is_dir():
            self.skipTest("apps/mobile không có trên nhánh này")
        self.assertGreater(len(gate.client_mentions()), 20)


class CouldNotRunIsNeverAPass(unittest.TestCase):
    def test_reading_no_client_path_refuses_to_run(self):
        """Zero paths is what a broken reader prints, and it is not green.

        Without this guard a break in `tokenize` reports every route on the
        server as dead -- the loudest possible wrong answer.
        """
        original = gate.client_mentions
        gate.client_mentions = lambda: {}
        try:
            with self.assertRaises(RuntimeError):
                gate.check()
        finally:
            gate.client_mentions = original

    def test_a_server_with_no_routes_refuses_to_run(self):
        original = gate.twin.load_openapi
        gate.twin.load_openapi = lambda: {"paths": {}}
        try:
            with self.assertRaises(RuntimeError):
                gate.check()
        finally:
            gate.twin.load_openapi = original


if __name__ == "__main__":
    unittest.main()
