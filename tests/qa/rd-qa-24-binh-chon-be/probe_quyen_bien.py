"""Edge permissions around F17 that the happy path never touches.

Three questions the PR's own tests do not ask, all of them about somebody who
is *nearly* allowed rather than obviously not:

1. A member who has LEFT the group. They were legitimately inside when the
   vote opened, so a check written as "did this person ever belong here"
   would still let them in.
2. A member who is not the creator trying to close the vote. Group membership
   is necessary for closing but must not be sufficient.
3. An option id borrowed from a DIFFERENT vote in the SAME group. It is a real
   option, owned by a real vote the caller may read, so a scoped-by-group check
   would accept it and silently re-home the ballot.
"""

from __future__ import annotations

import sys

import httpx

from probe_binh_chon_that import (
    BASE_URL,
    REPORT,
    TIMEOUT,
    ballot_count,
    call,
    make_group,
    make_vote,
    must,
    register,
)


def main() -> int:
    if httpx.get(f"{BASE_URL}/healthz", timeout=TIMEOUT).status_code != 200:
        raise SystemExit(f"khong co server tai {BASE_URL}")

    an = register("an chu nhom")
    binh = register("binh se roi nhom")
    cuong = register("cuong o lai")
    context_id = make_group(an, [binh, cuong], "Nhom quyen bien")

    # --- 1. the member who left -------------------------------------------
    print("\n[A] Nguoi da ROI nhom khong con bo phieu duoc")
    vote = make_vote(context_id, an, "Con o lai khong?", ["Co", "Khong"])
    vote_id, options = vote["id"], vote["options"]
    must(
        call(
            "POST", f"/votes/{vote_id}/ballots", binh, {"option_id": options[0]["id"]}
        ),
        200,
        "ballot while still a member",
    )
    rows_while_member = ballot_count(vote_id)
    REPORT.check(
        "con la thanh vien: bo phieu duoc",
        rows_while_member == 1,
        f"rows={rows_while_member}",
    )

    # `manage_members_and_invites` requires `is_self`: leaving is the member's
    # own act, not something an admin does to them. The first draft of this
    # probe called it as the group admin, got 403 `is_self`, and would have
    # reported "a person who left can still vote" -- a finding about the probe,
    # not about the product.
    removed = call("DELETE", f"/contexts/{context_id}/members/{binh}", binh)
    REPORT.check(
        "thanh vien tu roi nhom",
        removed.status_code in (200, 204),
        f"http={removed.status_code} {removed.text[:160]}",
    )

    before = ballot_count(vote_id)
    after_leaving = call(
        "POST", f"/votes/{vote_id}/ballots", binh, {"option_id": options[1]["id"]}
    )
    REPORT.check(
        "da roi nhom: DOI phieu bi tu choi 403",
        after_leaving.status_code == 403,
        f"http={after_leaving.status_code} body={after_leaving.text[:200]}",
    )
    REPORT.check(
        "da roi nhom: khong ghi de len phieu cu",
        ballot_count(vote_id) == before,
        f"truoc={before}, sau={ballot_count(vote_id)}",
    )
    read_back = call("GET", f"/votes/{vote_id}", binh)
    REPORT.check(
        "da roi nhom: doc ket qua cung bi chan 403",
        read_back.status_code == 403,
        f"http={read_back.status_code}",
    )

    # --- 2. a member who is not the creator ------------------------------
    print("\n[B] Thanh vien KHONG phai nguoi tao khong dong duoc")
    closed_by_other = call("POST", f"/votes/{vote_id}/close", cuong)
    REPORT.check(
        "thanh vien thuong dong cuoc binh chon -> 403",
        closed_by_other.status_code == 403,
        f"http={closed_by_other.status_code} body={closed_by_other.text[:200]}",
    )
    still_open = must(call("GET", f"/votes/{vote_id}", an), 200, "read after refusal")
    REPORT.check(
        "sau lan tu choi: cuoc binh chon VAN mo",
        still_open["is_closed"] is False,
        f"is_closed={still_open['is_closed']}",
    )
    REPORT.check(
        "nguoi tao dong duoc",
        call("POST", f"/votes/{vote_id}/close", an).status_code == 200,
    )

    # --- 3. an option borrowed from another vote in the same group -------
    print("\n[C] Muon option_id cua cuoc binh chon KHAC trong CUNG nhom")
    first = make_vote(context_id, an, "Cuoc mot", ["A1", "A2"])
    second = make_vote(context_id, an, "Cuoc hai", ["B1", "B2"])
    stolen = first["options"][0]["id"]

    before_second = ballot_count(second["id"])
    crossed = call(
        "POST", f"/votes/{second['id']}/ballots", cuong, {"option_id": stolen}
    )
    REPORT.check(
        "option cua cuoc khac -> 422, khong phai 200",
        crossed.status_code == 422,
        f"http={crossed.status_code} body={crossed.text[:200]}",
    )
    REPORT.check(
        "khong hang nao duoc ghi vao cuoc thu hai",
        ballot_count(second["id"]) == before_second,
        f"truoc={before_second}, sau={ballot_count(second['id'])}",
    )
    REPORT.check(
        "phieu KHONG bi don sang cuoc thu nhat",
        ballot_count(first["id"]) == 0,
        f"rows cuoc mot={ballot_count(first['id'])}",
    )

    total = len(REPORT.checks)
    bad = REPORT.failed
    print(f"\n=== {total - len(bad)}/{total} phep kiem DAT ===")
    for name, _, detail in bad:
        print(f"  FAIL: {name} -- {detail}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
