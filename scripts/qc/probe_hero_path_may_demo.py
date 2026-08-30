#!/usr/bin/env python3
"""Walk the hero path over real HTTP against a machine that is already running.

    chụp bill → AI đọc từng món → gán món cho người → khoản chi → đợt thu → trang khách

## Why this exists next to `scripts/e2e_slice.sh`

`e2e_slice.sh` provisions its own API and its own PostgreSQL, on purpose: it
answers "does THIS TREE's vertical slice work". That is the right question
before merging and the wrong question before a demo. Nobody demos a tree; they
demo a machine, and the machine can be behind, can be missing an API key, can
have a database somebody reseeded an hour ago.

This asks the other question: does the path run END TO END on the machine at
this address, right now, with whatever it actually has. It provisions nothing.

It also starts one step earlier than the slice does. `vertical-slice.test.mjs`
begins at `POST /expenses` with a total somebody typed. The demo begins at a
photograph, and the two steps in between -- the AI reading the lines, and a
human saying who ate what -- are the ones with no other coverage over the wire.

## Why it does not touch the demo group

`expenses` and `expense_versions` are append-only, so a walk through the group
`seed_demo_data.py` builds could never be undone. Worse, `check_demo_data.py`
compares counts by EQUALITY, so a single probe expense leaves the machine's own
data gate red until somebody reseeds. The walk therefore builds its own group.
That is not a weaker test of the machine: same containers, same database, same
Gemini key, same code.

## What it asserts, and what it refuses to assert

Never the answer, only the invariants -- recomputing the split here would be a
second allocator, and two allocators agreeing proves they share a bug:

    Σ phân bổ == tổng                    money law 2
    mọi phần là int                      money law 1
    người ứng tiền không có nghĩa vụ     they fronted it, they do not owe it
    phân bổ trong sổ == phân bổ theo món the assignment reached the ledger
    trang khách có phần của chính mình   asserted BEFORE the leak check
    trang khách không có số của người khác, không có tổng nhóm

The order of the last two matters. `assert not leaked` passes on a blank page
and on a page that prints money in another format; finding this guest's own
amount first is what turns the next line into a real leak check.

## What it does NOT prove

- That the QR is scannable. It checks an image is on the page. Whether a
  Vietnamese banking app accepts the payload needs a phone and a person
  (ADR-0010 §8), and no agent closes that.
- That the page is readable, or that the layout holds at any width.
- Anything about the demo group itself. It builds its own.
- Anything durable: it leaves a probe group behind on a shared machine, which
  is additive clutter. Say so when you report the run.

Usage:
    scripts/qc/probe_hero_path_may_demo.py --base-url http://127.0.0.1:8099

Exit codes: 0 mọi chặng đi được, 1 có chặng hỏng, 2 không chạy được.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta

EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_CANNOT_RUN = 2

# `deps.py` lets a trusted gateway assert roles outright. That is the vertical
# slice's placeholder for auth and CLAUDE.md says not to build on it; here it is
# simply how a client talks to this API today.
OWNER_ROLES = "group_admin,member,advancer,recipient,batch_owner"

# Proxies on a developer machine intercept localhost and answer 301 from a block
# page, which reads as "the server said something" all the way up the stack.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Walk:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.steps: list[tuple[str, bool, str]] = []
        self.failed: list[str] = []

    def call(
        self,
        method,
        path,
        body=None,
        actor=None,
        ctx=None,
        roles=OWNER_ROLES,
        raw=None,
        content_type=None,
    ):
        data = (
            raw
            if raw is not None
            else (json.dumps(body).encode() if body is not None else None)
        )
        request = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", content_type or "application/json")
        if actor:
            request.add_header("X-Actor-ID", str(actor))
            request.add_header("X-Actor-Roles", roles)
            if ctx:
                request.add_header("X-Actor-Contexts", str(ctx))
        try:
            response = OPENER.open(request, timeout=120)
            return response.status, json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode()
            try:
                return exc.code, json.loads(payload)
            except ValueError:
                return exc.code, {"_raw": payload[:300]}
        except OSError as exc:
            return 0, {"_raw": str(exc)[:300]}

    def step(self, name: str, ok: bool, detail: str = "") -> bool:
        self.steps.append((name, ok, detail))
        if not ok:
            self.failed.append(name)
        print(f"  {'ĐƯỢC' if ok else 'HỎNG'} {name:50s} {detail}")
        return ok


def synthetic_receipt(path: str) -> tuple[str, int]:
    """A receipt drawn from scratch. No real bill enters this repo or this machine.

    Returns (path, the total printed on it) so the caller can say whether the
    model read the paper or read its own expectations.
    """

    from PIL import Image, ImageDraw, ImageFont

    face = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    big = ImageFont.truetype(face, 34)
    small = ImageFont.truetype(face, 26)
    lines = [
        ("QUAN NUONG QC - DU LIEU THU NGHIEM", big),
        ("", small),
        ("Ba chi bo nuong        1   250.000", small),
        ("Lau nam chay           1   320.000", small),
        ("Rau tron               2    90.000", small),
        ("Nuoc suoi              4    40.000", small),
        ("Com trang              3    45.000", small),
        ("", small),
        ("TONG CONG              745.000", big),
    ]
    image = Image.new("RGB", (720, 900), "white")
    draw = ImageDraw.Draw(image)
    y = 40
    for text, font in lines:
        draw.text((40, y), text, fill="black", font=font)
        y += 60
    image.save(path)
    return path, 745_000


def fake_mobile(index: int) -> str:
    """Built, never written down.

    `repo_guard.py` refuses digit runs that look like a telephone number and
    cannot tell an invented one from somebody's real one -- so a literal here
    would make this file unable to enter the repository, and rightly.
    """

    return "0" + str(9_00_00_00_00 + 11_111 * (index + 1))


def vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8099")
    parser.add_argument("--keep-image", help="ghi ảnh bill tổng hợp ra đường dẫn này")
    args = parser.parse_args(argv)

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("KHÔNG CHẠY ĐƯỢC — thiếu Pillow để vẽ ảnh bill.", file=sys.stderr)
        return EXIT_CANNOT_RUN

    walk = Walk(args.base_url)

    print("=== 0. Máy còn sống không ===")
    status, _ = walk.call("GET", "/healthz")
    if not walk.step("GET /healthz", status == 200, f"status={status}"):
        print("KHÔNG CHẠY ĐƯỢC — máy không trả lời.", file=sys.stderr)
        return EXIT_CANNOT_RUN

    print("\n=== 1. Đăng nhập: bốn người mới ===")
    people: dict[str, str] = {}
    for index, who in enumerate(["An", "Bình", "Chi", "Dũng"]):
        status, body = walk.call(
            "POST", "/identity/person-id", {"phone": fake_mobile(index)}
        )
        if status != 200 or "person_id" not in body:
            walk.step(f"POST /identity/person-id ({who})", False, f"{status} {body}")
            break
        people[who] = body["person_id"]
    if not walk.step(
        "POST /identity/person-id ×4", len(people) == 4, f"{len(people)} person id"
    ):
        return EXIT_BROKEN

    registered = 0
    for who, person in people.items():
        status, _ = walk.call(
            "PUT", f"/people/{person}", {"display_name": f"{who} QC"}, actor=person
        )
        registered += status in (200, 201)
    walk.step("PUT /people/{id} — đặt tên ×4", registered == 4, f"{registered}/4")

    payer, *others = people.values()
    everyone = list(people.values())

    print("\n=== 2. Nhóm thăm dò (KHÔNG dùng nhóm demo) ===")
    status, context = walk.call(
        "POST",
        "/contexts",
        {"display_name": f"QC thăm dò hero {uuid.uuid4().hex[:6]}"},
        actor=payer,
    )
    cid = context.get("id") or context.get("context_id")
    if not walk.step(
        "POST /contexts", status in (200, 201) and bool(cid), f"{status} ctx={cid}"
    ):
        return EXIT_BROKEN

    accepted = 0
    for person in others:
        status, invite = walk.call(
            "POST",
            f"/contexts/{cid}/members",
            {"person_id": person},
            actor=payer,
            ctx=cid,
        )
        if status not in (200, 201):
            walk.step("POST /contexts/{id}/members", False, f"{status} {invite}")
            continue
        # Being added to a group happens to you; accepting is your own act, so
        # it goes out under the invitee's id, not the inviter's.
        status, _ = walk.call(
            "POST",
            f"/memberships/{invite['id']}/accept",
            {},
            actor=person,
            ctx=cid,
            roles="member",
        )
        accepted += status in (200, 201)
    walk.step("POST /memberships/{id}/accept ×3", accepted == 3, f"{accepted}/3")

    print("\n=== 3. Chụp bill → AI đọc từng món ===")
    image_path, printed_total = synthetic_receipt(
        args.keep_image or "/tmp/qc-hero-bill.png"
    )
    boundary = "----qc" + uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
            f'filename="bill.png"\r\nContent-Type: image/png\r\n\r\n'
        ).encode()
        + open(image_path, "rb").read()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    started = datetime.now(UTC)
    status, scan = walk.call(
        "POST",
        "/receipts/scan",
        actor=payer,
        ctx=cid,
        raw=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    elapsed = (datetime.now(UTC) - started).total_seconds()
    items = scan.get("items", [])
    if not walk.step(
        "POST /receipts/scan (AI thật)",
        status == 200 and bool(items),
        f"{status} {len(items)} món · items_total={scan.get('items_total_vnd')} "
        f"total={scan.get('total_vnd')} totals_agree={scan.get('totals_agree')} {elapsed:.1f}s",
    ):
        print("      ", json.dumps(scan, ensure_ascii=False)[:400])
        return EXIT_BROKEN
    for item in items:
        print(
            f"        - {item['name']:28s} ×{item['quantity']}  {vnd(item['line_total_vnd'])}"
        )
    walk.step(
        "AI đọc đúng tổng in trên giấy",
        scan.get("total_vnd") == printed_total,
        f"đọc {scan.get('total_vnd')} · trên giấy {printed_total}",
    )

    print("\n=== 4. Bản nháp bill từ kết quả AI ===")
    bill_items = [
        {
            "item_key": f"i{n}",
            "name": item["name"],
            "quantity": item["quantity"],
            "unit_price_vnd": item.get("unit_price_vnd"),
            "line_total_vnd": item["line_total_vnd"],
            "suggested_participant_ids": [],
        }
        for n, item in enumerate(items)
    ]
    items_total = sum(item["line_total_vnd"] for item in bill_items)
    status, bill = walk.call(
        "POST",
        "/bills",
        {
            "context_id": cid,
            "printed_total_vnd": scan.get("total_vnd"),
            "items_total_vnd": items_total,
            "confidence": scan.get("confidence", 90),
            "needs_review": bool(scan.get("needs_review", False)),
            "items": bill_items,
        },
        actor=payer,
        ctx=cid,
    )
    bill_id = bill.get("id")
    if not walk.step(
        "POST /bills",
        status in (200, 201) and bool(bill_id),
        f"{status} bill={bill_id}",
    ):
        print("      ", json.dumps(bill, ensure_ascii=False)[:400])
        return EXIT_BROKEN

    print("\n=== 5. Gán món cho từng người ===")
    # Deliberately uneven: if every item went to everybody the ledger split
    # would equal an even split and step 6's comparison would pass for free.
    assignments = [
        {
            "item_key": item["item_key"],
            "participant_ids": [everyone[n % len(everyone)]] if n % 3 else everyone,
        }
        for n, item in enumerate(bill_items)
    ]
    status, detail = walk.call(
        "PUT",
        f"/bills/{bill_id}/assignments",
        {"assignments": assignments},
        actor=payer,
        ctx=cid,
    )
    walk.step(
        "PUT /bills/{id}/assignments",
        status in (200, 201),
        f"{status} gán {len(assignments)} món "
        f"{'' if status in (200, 201) else json.dumps(detail, ensure_ascii=False)[:160]}",
    )

    print("\n=== 6. Chia tiền → khoản chi trong sổ ===")
    status, split = walk.call(
        "POST", f"/bills/{bill_id}/split", {"for_ledger": False}, actor=payer, ctx=cid
    )
    proposal = (split.get("allocation") or {}).get("allocations") or {}
    total = split.get("total_amount_vnd")
    walk.step(
        "POST /bills/{id}/split (xem trước)",
        status == 200 and bool(proposal),
        f"{status} total={total} state={split.get('assignment_state')}",
    )
    if proposal:
        walk.step(
            "luật 2: Σ phân bổ == tổng bill",
            sum(proposal.values()) == total,
            f"{vnd(sum(proposal.values()))} vs {vnd(total or 0)}",
        )
        walk.step(
            "luật 1: mọi phần là số nguyên đồng",
            all(isinstance(v, int) for v in proposal.values()),
            str({k[:8]: v for k, v in proposal.items()}),
        )

    occurred = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    expense_items = [
        {
            "item_id": a["item_key"],
            "label": next(
                i["name"] for i in bill_items if i["item_key"] == a["item_key"]
            ),
            "amount_vnd": next(
                i["line_total_vnd"]
                for i in bill_items
                if i["item_key"] == a["item_key"]
            ),
            "shared_by": a["participant_ids"],
        }
        for a in assignments
    ]
    expense_body = {
        "context_id": cid,
        "description": "QC thăm dò hero path",
        "recorded_by_id": payer,
        "paid_by_id": payer,
        "verification_scope": "items_reviewed",
        "occurred_at": occurred,
        "participants": everyone,
        "total_amount_vnd": total or items_total,
        "items": expense_items,
    }
    status, expense = walk.call("POST", "/expenses", expense_body, actor=payer, ctx=cid)
    expense_id = expense.get("expense_id") or expense.get("id")
    if not walk.step(
        "POST /expenses",
        status in (200, 201) and bool(expense_id),
        f"{status} expense={expense_id}",
    ):
        print("      ", json.dumps(expense, ensure_ascii=False)[:400])
        return EXIT_BROKEN

    ledger = (
        expense.get("allocations")
        or (expense.get("allocation") or {}).get("allocations")
        or {}
    )
    if ledger:
        walk.step(
            "luật 2 trên /expenses: Σ == tổng",
            sum(ledger.values()) == (total or items_total),
            vnd(sum(ledger.values())),
        )
        # The whole reason step 5 exists. Without this the walk would pass with
        # an even split and "gán món cho người" would have changed nothing.
        walk.step(
            "phân bổ trong SỔ == phân bổ theo MÓN đã gán",
            ledger == proposal,
            "khớp từng người"
            if ledger == proposal
            else f"lệch: bill={proposal} sổ={ledger}",
        )

    status, confirmed = walk.call(
        "POST",
        f"/expenses/{expense_id}/confirm",
        {
            "proposal": expense_body,
            "expected_allocations": ledger,
            "acknowledge_as_advancer": True,
        },
        actor=payer,
        ctx=cid,
    )
    walk.step(
        "POST /expenses/{id}/confirm",
        status in (200, 201),
        f"{status} version={confirmed.get('expense_version_id')}",
    )

    print("\n=== 7. Tài khoản nhận tiền + đợt thu ===")
    status, bank = walk.call(
        "PUT",
        f"/people/{payer}/bank-recipient",
        {
            "bank_bin": "970415",
            "account_number": "QCPROBE",
            "account_name": "AN - THU NGHIEM",
        },
        actor=payer,
        ctx=cid,
    )
    walk.step(
        "PUT /people/{id}/bank-recipient",
        status in (200, 201),
        f"{status} {bank.get('bank_name', '')}",
    )

    status, batch = walk.call(
        "POST",
        "/batches",
        {
            "context_id": cid,
            "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        },
        actor=payer,
        ctx=cid,
    )
    batch_id = batch.get("batch_id") or batch.get("id")
    if not walk.step(
        "POST /batches",
        status in (200, 201) and bool(batch_id),
        f"{status} batch={batch_id} status={batch.get('status')}",
    ):
        print("      ", json.dumps(batch, ensure_ascii=False)[:400])
        return EXIT_BROKEN

    status, published = walk.call(
        "POST",
        f"/batches/{batch_id}/publish",
        {
            "delivery_method": "personal_link",
            "guest_link_expires_at": (
                datetime.now(UTC) + timedelta(days=14)
            ).isoformat(),
        },
        actor=payer,
        ctx=cid,
    )
    links = published.get("guest_links", [])
    if not walk.step(
        "POST /batches/{id}/publish",
        status in (200, 201) and bool(links),
        f"{status} {len(links)} link",
    ):
        print("      ", json.dumps(published, ensure_ascii=False)[:400])
        return EXIT_BROKEN

    print("\n=== 8. Trang khách ===")
    status, board = walk.call(
        "GET", f"/batches/{batch_id}/obligations", actor=payer, ctx=cid
    )
    owed = {o["sender_id"]: o["amount_vnd"] for o in board.get("obligations", [])}
    group_total = sum(owed.values())
    walk.step(
        "GET /batches/{id}/obligations",
        status == 200 and bool(owed),
        f"{status} {len(owed)} nghĩa vụ, tổng {vnd(group_total)}",
    )
    walk.step(
        "người ứng tiền không có nghĩa vụ",
        payer not in owed,
        f"người ứng tiền trong danh sách={payer in owed}",
    )

    for link in links:
        sender = link["sender_id"]
        mine = owed.get(sender)
        try:
            html = OPENER.open(walk.base + link["path"], timeout=60).read().decode()
        except OSError as exc:
            walk.step(f"GET {link['path'][:18]}…", False, str(exc)[:120])
            continue
        # Positive first: a blank page satisfies every negative below for free.
        has_mine = mine is not None and vnd(mine) in html
        leaked = [
            vnd(a)
            for p, a in owed.items()
            if p != sender and a != mine and vnd(a) in html
        ]
        leaked_total = (
            len(owed) > 1 and group_total != mine and vnd(group_total) in html
        )
        walk.step(
            f"GET {link['path'][:18]}…",
            has_mine and not leaked and not leaked_total,
            f"phần mình {vnd(mine) if mine else '—'} có={has_mine} | "
            f"số người khác lộ={leaked} | tổng nhóm lộ={leaked_total} | {len(html)}B",
        )
        walk.step(
            "   trang có mã VietQR",
            "data:image/png;base64" in html or "<svg" in html,
            "chỉ kiểm CÓ ảnh — quét được hay không cần điện thoại thật",
        )

    print("\n" + "=" * 72)
    passed = len(walk.steps) - len(walk.failed)
    print(f"CHẶNG ĐI ĐƯỢC: {passed}/{len(walk.steps)}")
    if walk.failed:
        print("HỎNG:")
        for name in walk.failed:
            print("   -", name)
    print(f"nhóm thăm dò để lại trên máy: {cid}")
    return EXIT_BROKEN if walk.failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
