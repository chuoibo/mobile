"""What the route-existence gate must catch, and what it must not report.

`scripts/check_api_contract.py` is a reader, and a reader has exactly one
failure mode worth fearing: going quiet. While it was being written its
statement scanner stopped at a parameter list, and it reported nothing and
exited 0 -- indistinguishable from a clean tree, and the same shape as the
detector with no browser and the postgres tier with no database that this
repository has already been bitten by.

So these tests come in three parts, and all three are load bearing:

  - The gate BITES on the defect that really shipped: a call to
    `/batches/current/publish`, a route that has never existed, recorded in
    `src/api.ts`'s own header comment.
  - The gate stays QUIET about prose. This codebase documents its past mistakes
    by name, so its comments are full of routes that do not exist. A checker
    that read comments would fail `main` on the strength of a docstring, get
    switched off, and catch nothing ever again.
  - The reader does not GO BLIND. Two shapes in the real client -- a regular
    expression in the middle of a URL, and a path two declarations away from
    the request -- each made it silently stop finding anything.

The reader is exercised on snippets against a hand-built contract, so a failure
here names the reading rule that broke rather than "something in apps/mobile".
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "check_api_contract.py"

SPEC = importlib.util.spec_from_file_location("check_api_contract", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
contract_gate = importlib.util.module_from_spec(SPEC)
# Registered before exec: `@dataclass` resolves annotations through
# `sys.modules[cls.__module__]`, and without this the import fails outright.
sys.modules[SPEC.name] = contract_gate
SPEC.loader.exec_module(contract_gate)


def a_contract():
    """A small server, spelled the way FastAPI spells one."""
    return contract_gate.read_contract(
        {
            "paths": {
                "/places": {"get": {}},
                "/places/search": {"post": {}},
                "/contexts/{context_id}/messages": {"get": {}, "post": {}},
                "/batches/{batch_id}/publish": {"post": {}},
            }
        }
    )


def kinds(source: str) -> list[str]:
    scan = contract_gate.findings_for_source(
        textwrap.dedent(source), "snippet.ts", a_contract()
    )
    return [f.kind for f in scan.findings]


def paths_read(source: str) -> int:
    return contract_gate.findings_for_source(
        textwrap.dedent(source), "snippet.ts", a_contract()
    ).paths


class GateBites(unittest.TestCase):
    def test_a_route_the_server_does_not_have(self):
        # The defect `src/api.ts` records: "The app called
        # /batches/current/publish, a route that has never existed."
        self.assertEqual(
            kinds(
                """
                await translatedAsActor(PUBLISH_REFUSALS, `/batches/current/publish`, {
                  body: { delivery_method: "personal_link" },
                  actorId,
                });
                """
            ),
            ["route_khong_ton_tai"],
        )

    def test_a_renamed_route_is_caught_through_a_url_builder(self):
        # The server renaming /places/search would leave this call compiling,
        # typechecking and passing every mobile test.
        self.assertEqual(
            kinds(
                """
                function searchUrl(base: string): string {
                  return `${base}/places/tim-kiem`;
                }
                const url = searchUrl(base);
                const res = await doFetch(url, { method: "POST" });
                """
            ),
            ["route_khong_ton_tai"],
        )

    def test_a_path_that_exists_is_not_reported(self):
        self.assertEqual(
            kinds(
                """
                const res = await fetch(`${base}/contexts/${id}/messages`, {
                  method: "POST",
                });
                """
            ),
            [],
        )


class GateStaysQuiet(unittest.TestCase):
    """Everything that looks like a defect and is not."""

    def test_a_route_named_only_in_a_comment_is_not_a_call(self):
        # Both of these appear verbatim in `apps/mobile/src`: api.ts recording
        # an old defect, and tin-nhan.ts explaining why F17 posts a card.
        # Reporting either would fail `main` for writing documentation.
        self.assertEqual(
            kinds(
                """
                /**
                 * The app called `/batches/current/publish`, a route that has
                 * never existed.
                 */
                // there is no `/polls` route to post either one to
                await translatedAsActor(TABLE, `/batches/${batchId}/publish`, { actorId });
                """
            ),
            [],
        )

    def test_a_formatted_date_is_not_a_route(self):
        # `${dd}/${mm}` is how three modules print a date. An earlier draft
        # reported four of them as missing endpoints.
        self.assertEqual(
            kinds(
                """
                const dd = `${vn.getUTCDate()}`.padStart(2, "0");
                const label = `${dd}/${mm}`;
                const res = await fetch(`${base}/places`, {});
                """
            ),
            [],
        )

    def test_a_path_in_an_error_message_is_not_a_call(self):
        # `nhom.ts` builds `${goc(base)}/people` as a label for a failure state
        # it reports without ever sending a request.
        self.assertEqual(
            kinds(
                """
                return hong("dat-ten", `${goc(base)}/people`, 0, "không có người");
                """
            ),
            [],
        )

    def test_fetching_a_local_blob_is_not_an_api_call(self):
        # `scanReceipt` and `src/camera/native.ts` both fetch a blob: url to
        # read bytes off the phone. There is no server involved.
        self.assertEqual(
            kinds(
                """
                const blob = await fetch(photo.uri).then((r) => r.blob());
                """
            ),
            [],
        )

    def test_a_query_string_does_not_make_a_path_unknown(self):
        self.assertEqual(
            kinds(
                """
                const url = `${base}/contexts/${id}/messages?limit=20&before=${c}`;
                const res = await fetch(url, {});
                """
            ),
            [],
        )


class ReaderDoesNotGoBlind(unittest.TestCase):
    """The failure mode that would make every result above meaningless."""

    def test_a_regex_literal_does_not_swallow_the_rest_of_the_line(self):
        # `base.replace(/\\/$/, "")` appears in three client modules. Reading
        # that `/` as division turns everything after it into a phantom literal
        # and the paths disappear -- nothing reported, exit 0, which is exactly
        # what a clean tree looks like.
        self.assertEqual(
            paths_read(
                """
                const url = `${base.replace(/\\/$/, "")}/places/search`;
                const res = await fetch(url, { method: "POST" });
                """
            ),
            1,
        )

    def test_a_url_two_declarations_away_is_still_found(self):
        # `fetchPlaces` does `const url = placesUrl(base, opts)`. A reader that
        # stops at one hop sees no path, reports nothing, and leaves the file
        # silently unchecked.
        self.assertEqual(
            paths_read(
                """
                function placesUrl(base: string, opts: Opts): string {
                  return `${base}/places?limit=20`;
                }
                const url = placesUrl(base, opts);
                const res = await doFetch(url, { headers: { Accept: "application/json" } });
                """
            ),
            1,
        )

    def test_a_function_body_is_read_past_its_parameter_list(self):
        # The scanner stopped at the first balanced group, so a URL built
        # inside a function body was never seen. Three modules build theirs
        # exactly this way.
        self.assertEqual(
            paths_read(
                """
                function messagesUrl(base: string, contextId: string): string {
                  const params = new URLSearchParams({ limit: "20" });
                  return `${base}/contexts/${contextId}/messages?${params}`;
                }
                const res = await fetch(messagesUrl(base, id), {});
                """
            ),
            1,
        )

    def test_every_wrapper_it_reads_is_still_declared_in_api_ts(self):
        # `REQUEST_FUNCTIONS` is the reader's one hardcoded dependency on how
        # the client spells itself, and drift in it is silent in the worst
        # direction: a name nobody calls any more matches nothing, every call
        # site through it stops being read, and the gate still exits 0 on the
        # sites it can still see.
        #
        # That is not hypothetical. This branch renamed `call` and `translated`
        # into four `*AsActor` / `*Anonymous` wrappers. Measured before the
        # reader was taught them: 13 paths across 19 call sites, against 65
        # across 77 after. 58 call sites unread, and the only thing that noticed
        # was `assertGreater(total, 10)` -- which then stopped noticing the
        # moment `main` merged three more direct `fetch` calls in and carried
        # the total from 10 to 13.
        #
        # So the count below is a backstop for the reader dying outright, not a
        # guard against this. This is the guard against this, and it names the
        # function instead of printing a number that got quietly satisfied.
        api_ts = contract_gate.CLIENT_ROOT / "api.ts"
        if not api_ts.is_file():
            self.skipTest("apps/mobile không có trên nhánh này")
        source = api_ts.read_text(encoding="utf-8")
        declared = contract_gate.declarations(
            source, contract_gate.mask(source, contract_gate.tokenize(source))
        )
        unknown = [name for name in contract_gate.WRAPPERS if name not in declared]
        self.assertEqual(
            unknown,
            [],
            f"bộ đọc còn nhận ra {unknown} nhưng api.ts không khai báo tên đó "
            "nữa -- mọi lời gọi qua tên mới sẽ KHÔNG được đọc, và cổng vẫn "
            "xanh trên phần nó còn thấy. Sửa REQUEST_FUNCTIONS trong "
            "scripts/check_api_contract.py cho khớp tên api.ts đang dùng.",
        )

    def test_the_real_client_still_has_routes_to_check(self):
        # The whole-repo guard, stated as a number. `check()` refuses to pass
        # when this reaches zero, but by then the gate has been green for
        # however long it took somebody to notice.
        if not contract_gate.CLIENT_ROOT.is_dir():
            self.skipTest("apps/mobile không có trên nhánh này")
        contract = a_contract()
        total = 0
        for path in contract_gate.client_files():
            total += contract_gate.findings_for_source(
                path.read_text(encoding="utf-8"), str(path), contract
            ).paths
        self.assertGreater(
            total,
            10,
            "bộ đọc chỉ thấy vài đường dẫn trong cả apps/mobile/src -- nhiều "
            "khả năng nó đã hỏng chứ không phải client đã ngừng gọi API",
        )


if __name__ == "__main__":
    unittest.main()
