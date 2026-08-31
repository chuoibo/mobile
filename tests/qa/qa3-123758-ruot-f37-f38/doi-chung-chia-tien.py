#!/usr/bin/env python3
"""The positive control: run the SAME measurement against bill splitting, which
is known to be wired to real data, and require it to come out wired.

## Why this file has to exist

The F37/F38 measurement is "put a token nobody has ever seen into the server's
data, press the screen open, and look for the token". A measurement shaped like
that has a failure mode that produces exactly the answer its author was hoping
for: if the injection silently does nothing, or the walk stands on the wrong
screen, or the token never gets as far as the database, then EVERY feature reads
as "shell". A run of all-negative results is indistinguishable from a broken
instrument, and the conclusion would be a big confident number pointing the
wrong way.

So the instrument is pointed at splitting first. Splitting is the one part of
this product whose wiring is not in question -- 41 hand-computed golden vectors,
a ledger, a state machine, and a gate on every one of them. If the measurement
calls splitting a shell, the measurement is what is broken, and nothing it says
about F37 or F38 may be repeated.

## What is injected, and why an amount rather than a caption

The token here is money: an odd total whose digits appear nowhere in the seed
(`scripts/seed_demo_data.py` uses round numbers) and which is spent through the
product's own two-step allocation -- `POST /expenses` for a proposal, then
`POST /expenses/{id}/confirm` echoing that proposal back. The confirm carries
`expected_allocations` copied verbatim from the proposal, which is what keeps
this file from becoming a second splitter: it never computes a share, it agrees
or the server refuses.

The expense is dated INSIDE the injected trip's window, because the screens the
walk can reach report money per trip. Dating it outside would produce a screen
that correctly shows nothing, and "correctly shows nothing" and "shows nothing
because it is a shell" are the two states this whole exercise exists to separate.

    doi-chung-chia-tien.py <api-base> <context-id> <payer-id> <participant-ids-csv>

Prints JSON: the amount, the server's own allocation, and the expense version.
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROLES = "group_admin,member,advancer,recipient,batch_owner"
VIETNAM = timezone(timedelta(hours=7))


def call(api, method, path, *, body=None, actor=None, ctx=None, key=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if actor:
        headers["X-Actor-ID"] = actor
        headers["X-Actor-Roles"] = ROLES
    if ctx:
        headers["X-Actor-Contexts"] = ctx
    if key:
        headers["Idempotency-Key"] = key
    req = urllib.request.Request(api + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} -> {e.code}\n{e.read().decode('utf-8', 'replace')}")
    return json.loads(raw) if raw else {}


def main() -> int:
    api, ctx, payer = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    people = sys.argv[4].split(",")
    # 1.357.913đ: not a round number, not divisible by seven, and absent from the
    # seed. If this exact string turns up on a screen, no fixture put it there.
    tong = 1_357_913
    khi = datetime.now(VIETNAM).replace(microsecond=0)

    de_xuat = call(
        api,
        "POST",
        "/expenses",
        body={
            "context_id": ctx,
            "description": f"Đối chứng chia tiền {tong}",
            "recorded_by_id": payer,
            "paid_by_id": payer,
            "verification_scope": "totals_only",
            "occurred_at": khi.isoformat(),
            "participants": people,
            "total_amount_vnd": tong,
            "items": [],
            "surcharges": [],
            "discounts": [],
        },
        actor=payer,
        ctx=ctx,
        key=f"qa3-doi-chung-expense-{tong}",
    )
    xac_nhan = call(
        api,
        "POST",
        f"/expenses/{de_xuat['expense_id']}/confirm",
        body={
            "proposal": de_xuat["proposal"],
            # Echoed, never recomputed. This script must not own an opinion
            # about how 1.357.913đ divides by seven.
            "expected_allocations": de_xuat["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
        actor=payer,
        ctx=ctx,
        key=f"qa3-doi-chung-confirm-{tong}",
    )
    print(
        json.dumps(
            {
                "tong_vnd": tong,
                "phan_bo": de_xuat["allocation"]["allocations"],
                "sum_phan_bo": sum(de_xuat["allocation"]["allocations"].values()),
                "expense_id": de_xuat["expense_id"],
                "expense_version_id": xac_nhan["expense_version_id"],
                "occurred_at": khi.isoformat(),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
