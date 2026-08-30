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


def declares(source: str) -> frozenset[str]:
    return contract_gate.findings_for_source(
        textwrap.dedent(source), "snippet.ts", a_contract()
    ).declares


class GateBites(unittest.TestCase):
    def test_a_route_the_server_does_not_have(self):
        # The defect `src/api.ts` records: "The app called
        # /batches/current/publish, a route that has never existed."
        self.assertEqual(
            kinds(
                """
                await translated(PUBLISH_REFUSALS, `/batches/current/publish`, {
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
                await translated(TABLE, `/batches/${batchId}/publish`, { actorId });
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


class ReaderKnowsItLostTheWrappers(unittest.TestCase):
    """The floor above is a floor, and a floor gets lifted past the failure.

    Measured on main a6fdbe4 on 2026-08-31, renaming `call` and `translated`
    the way PR #397 did: the reader fell from 67 paths to 11, and 11 is greater
    than 10, so the floor stayed green. So did `--selftest`, whose canaries
    write `call` themselves. So did the script, which printed "Client và máy
    chủ khớp hợp đồng" and exited 0.

    A count cannot tell blindness from a client that got smaller. The name can:
    the reader knows which wrappers it is looking for, so it can be made to say
    when the client no longer has them.
    """

    def test_the_wrappers_this_reader_depends_on_are_still_in_the_client(self):
        # The whole point, stated against the real tree: no snippet, no
        # rename, main as it stands.
        if not contract_gate.CLIENT_ROOT.is_dir():
            self.skipTest("apps/mobile không có trên nhánh này")
        self.assertEqual(
            contract_gate.lost_wrappers(contract_gate.declared_wrappers()), []
        )

    def test_a_wrapper_that_no_longer_exists_is_named(self):
        # #397 renamed `call` -> `callApi`. The reader does not report fewer
        # routes -- it stops seeing those call sites, and nothing seen is
        # printed as agreement.
        problems = contract_gate.lost_wrappers({"translated"})
        self.assertEqual(len(problems), 1)
        self.assertIn("call", problems[0])

    def test_losing_both_wrappers_names_both(self):
        self.assertEqual(len(contract_gate.lost_wrappers(set())), 2)

    def test_a_healthy_anchor_is_silent(self):
        self.assertEqual(
            contract_gate.lost_wrappers(set(contract_gate.CLIENT_WRAPPERS)), []
        )

    def test_a_declaration_is_the_definition_not_the_import(self):
        # Every screen does `import { call } from "./api"`. If an import
        # counted, the anchor would hold on to a name that no longer exists
        # anywhere -- which is the failure it was written for.
        self.assertEqual(declares('import { call } from "./api";'), frozenset())
        self.assertEqual(
            declares("async function call<T>(path: string) { return fetch(path); }"),
            frozenset({"call"}),
        )

    def test_the_renamed_wrapper_is_invisible_rather_than_unresolved(self):
        # Why a count could never have caught this: after the rename the call
        # site produces no path AND no unresolved entry AND no finding. There
        # is nothing for the gate to print.
        scan = contract_gate.findings_for_source(
            textwrap.dedent(
                """
                import { callApi } from "./api";
                export async function a() { return callApi<void>("/places", {}); }
                """
            ),
            "snippet.ts",
            a_contract(),
        )
        self.assertEqual(
            (scan.paths, scan.sites, scan.findings, scan.unresolved), (0, 0, [], [])
        )
        self.assertEqual(scan.declares, frozenset())


if __name__ == "__main__":
    unittest.main()
