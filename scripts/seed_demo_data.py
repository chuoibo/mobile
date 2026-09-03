#!/usr/bin/env python3
"""Build the dataset the PoC walkthrough is demonstrated on: one group with a past.

`scripts/seed_dev_data.py` proves the vertical slice answers at all: three
people, one round, one expense. That is the right fixture for "is the stack
alive". It is the wrong one to demo on -- every screen it produces is a screen
in its empty state, and an app whose every list has one row in it reads as
unfinished whether or not it is.

This builds the other thing: seven people, three outings already behind them,
and money still owed. Concretely it exists so that

  * a group screen has a history to scroll,
  * the itemised bill has eight lines assigned to different subsets of people,
    which is the only shape that shows why per-item assignment exists at all,
  * one split does not divide evenly, so the largest-remainder rule is on
    screen rather than only in the golden corpus,
  * and every obligation status the board can render -- outstanding,
    partially_confirmed, confirmed -- is present in real rows.

Every write goes through the HTTP API.
---------------------------------------
`seed_dev_data.py` writes `people` with SQL because when it was written no route
created them. `PUT /people/{id}` exists now, so this script has no SQL write path
at all. That is
not tidiness: a fixture that INSERTs its way around the API can succeed while
the product is broken, and then the demo is the first place anyone finds out.

The one thing read with SQL is "does this group already exist" -- a read, and
there is no route that answers it.

Not one real person, account, or amount
---------------------------------------
Every name here is a bare Vietnamese given name chosen to look ordinary on a
screen and to identify nobody. Account numbers are deliberately not numbers:
they carry letters, so they cannot be mistaken for a real destination and
cannot trip the repo guard's long-number rule either. Nothing in this file may
ever be swapped for something real -- it is committed to Git.

Money is never invented here
----------------------------
The script sends a proposal and echoes back the allocation the API answered
with. It never computes a share. There is exactly one splitter in this product
and it lives in `app/domain/allocator.py`; a second one hiding in a fixture is
how two screens end up showing two numbers for one dinner.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg

API_BASE = os.environ.get("MOBILE_SEED_API_BASE_URL", "http://api:8000").rstrip("/")
DATABASE_URL = os.environ.get("MOBILE_DATABASE_URL")

GROUP_NAME = "Team Đà Lạt"

# Trip dates are wall-clock Vietnamese days. The expenses are backdated from an
# instant, so the two have to be reconciled in one named zone rather than in
# whatever the container's clock happens to be -- `GET /contexts/{id}/recap`
# matches a trip to its spending by exactly these days.
VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")

# Ids are derived, never written out: a UUID literal padded with zeroes is a
# long digit run and the repo guard blocks those on sight. It cannot tell a
# demo id from an account number, and it is right not to try.
DEMO_NAMESPACE = uuid.UUID("da1ada1a-da1a-da1a-da1a-da1ada1ada1a")


def person_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"person:{slug}")


def idempotency_key(slug: str) -> str:
    """One stable key per write in this script.

    A half-finished run is the case that matters. Re-running then replays the
    writes that landed instead of doubling them, which is what the server-side
    `Idempotency-Key` enforcement is for. It is a second line of defence, not
    the first -- the group-exists check below is the first.
    """

    return str(uuid.uuid5(DEMO_NAMESPACE, f"write:{slug}"))


# Given names only. That is how a Vietnamese friend group actually labels its
# members, and it keeps the fixture from carrying anything that resembles a
# full identity.
MINH = person_id("minh")
TRANG = person_id("trang")
HAI = person_id("hai")
NGOC = person_id("ngoc")
DUC = person_id("duc")
LINH = person_id("linh")
QUAN = person_id("quan")

PEOPLE: list[tuple[uuid.UUID, str]] = [
    (MINH, "Minh"),
    (TRANG, "Trang"),
    (HAI, "Hải"),
    (NGOC, "Ngọc"),
    (DUC, "Đức"),
    (LINH, "Linh"),
    (QUAN, "Quân"),
]
NAME_OF = dict(PEOPLE)
EVERYONE = [pid for pid, _ in PEOPLE]

OWNER_ROLES = "group_admin,member,advancer,recipient,batch_owner"
MEMBER_ROLES = "group_admin,member"


class SeedFailed(Exception):
    """Raised with a message a human can act on, printed without a traceback."""


def psycopg_dsn(url: str) -> str:
    """SQLAlchemy spells the driver into the scheme; libpq does not accept it."""

    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def call(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    actor: uuid.UUID | None = None,
    roles: str | None = None,
    context_id: uuid.UUID | None = None,
    write_key: str | None = None,
) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if actor is not None:
        headers["X-Actor-ID"] = str(actor)
    if roles is not None:
        headers["X-Actor-Roles"] = roles
    if context_id is not None:
        headers["X-Actor-Contexts"] = str(context_id)
    if write_key is not None:
        headers["Idempotency-Key"] = write_key

    request = urllib.request.Request(
        f"{API_BASE}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        # The API's own error body says more than any message this script could
        # invent, so pass it through instead of summarising it.
        detail = exc.read().decode("utf-8", errors="replace")
        raise SeedFailed(f"{method} {path} -> HTTP {exc.code}\n{detail}") from exc
    except urllib.error.URLError as exc:
        raise SeedFailed(
            f"{method} {path} -> không nối được API: {exc.reason}"
        ) from exc
    return json.loads(payload) if payload else {}


def wait_for_api(timeout_s: float = 60.0) -> None:
    """Compose already gates on the healthcheck; this covers the script being
    run on its own against a stack somebody started by hand."""

    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{API_BASE}/healthz", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - any failure means "not yet"
            last_error = exc
        time.sleep(1)
    raise SeedFailed(f"API không trả lời /healthz sau {timeout_s:.0f}s: {last_error}")


def existing_group(connection: psycopg.Connection) -> uuid.UUID | None:
    row = connection.execute(
        "SELECT id FROM contexts WHERE display_name = %s LIMIT 1", (GROUP_NAME,)
    ).fetchone()
    return row[0] if row else None


def batch_count(connection: psycopg.Connection, context_id: uuid.UUID) -> int:
    return connection.execute(
        "SELECT COUNT(*) FROM collection_batches WHERE context_id = %s", (context_id,)
    ).fetchone()[0]


def check_complete(connection: psycopg.Connection, context_id: uuid.UUID) -> None:
    """Refuse to report on a dataset that was only half built.

    The group row is written near the start of the build, so "the group exists"
    means a run *started*, not that one finished. The difference is not
    hypothetical -- it happened on the first run of this script: `POST /batches`
    refused a past due date, the run died having already created the group, the
    members and two expenses, and a second run would have found the group,
    skipped the build, and printed a summary of a broken demo.

    That is the shape of failure this repository keeps finding behind green
    checkmarks, so it gets an error instead of a shrug.
    """

    found = batch_count(connection, context_id)
    expected = len(outings(datetime.now(UTC)))
    # Counted separately from the batches, and both must be complete.
    #
    # The trips arrived after the collection rounds did, so a group seeded by an
    # older copy of this script has all three batches and no `outings` rows at
    # all. Checking only the batches would call that dataset finished and hand
    # the demo an empty memory wall beside a group that has visibly been to Đà
    # Lạt twice -- the same "a run started, so it must have finished" mistake
    # this function was written for, one table over.
    trips = connection.execute(
        "SELECT COUNT(*) FROM outings WHERE context_id = %s", (context_id,)
    ).fetchone()[0]
    if found == expected and trips == expected:
        return
    raise SeedFailed(
        f"nhóm '{GROUP_NAME}' ({context_id}) mới dựng dở: có {found}/{expected} "
        f"đợt thu và {trips}/{expected} buổi đi chơi. Một lần chạy trước đã tạo "
        "nhóm rồi chết giữa chừng (hoặc chạy bằng bản script cũ chưa biết tới "
        "bảng `outings`), nên đây KHÔNG phải bộ dữ liệu demo dùng được.\n"
        "Không xoá nhóm đó bằng SQL được: `confirmed_allocations` là bảng "
        "append-only, trigger chặn cả DELETE — sổ cái đang làm đúng việc của "
        "nó. Ba đường đi được, rẻ nhất trước:\n"
        "  1. Giải phóng cái TÊN thay vì xoá dữ liệu — không mất dòng nào:\n"
        "     python3 scripts/reset_demo_group.py --yes   (chạy khô nếu bỏ --yes)\n"
        "     rồi `make demo`. Nó đổi tên nhóm cũ và xoá đúng các key\n"
        "     idempotency của chính fixture này, thứ đang làm lần seed thứ hai\n"
        "     trả 422 idempotency_key_reuse. Ảnh và dữ liệu lane khác còn nguyên.\n"
        "  2. Dựng bộ container riêng, database riêng, không đụng ai:\n"
        "     COMPOSE_PROJECT_NAME=demo MOBILE_API_PORT=8199 "
        "MOBILE_POSTGRES_PORT=5439 make demo\n"
        "  3. Hoặc `make clean` rồi `make demo` — nhưng clean XOÁ database "
        "dùng chung VÀ volume ảnh (seed không dựng lại ảnh được), hỏi cả đội trước."
    )


# --------------------------------------------------------------------------
# the outings
#
# Amounts are round because a demo audience reads them off a screen, with one
# deliberate exception: the morning coffee does not divide by six. That is the
# only place the largest-remainder rule becomes visible outside the golden
# corpus, and hiding it would make the product look like it never has to round.
# --------------------------------------------------------------------------

# Eight lines, four different subsets of the table. This is the bill the hero
# path photographs, and it sums to exactly 1.125.000đ -- the allocator refuses
# the expense outright (RECONCILIATION_MISMATCH) if the lines and the total
# disagree, so this arithmetic is enforced, not trusted.
HOTPOT_DINERS = [MINH, TRANG, HAI, NGOC, DUC, LINH]
DRINKERS = [MINH, HAI, DUC]
SOFT_DRINKERS = [TRANG, NGOC, LINH]
DESSERT = [TRANG, NGOC, LINH, DUC]

HOTPOT_ITEMS = [
    ("lau-thai", "Lẩu thái hải sản (2 nồi)", 360_000, HOTPOT_DINERS),
    ("bo-my", "Bò Mỹ 2 phần", 240_000, HOTPOT_DINERS),
    ("rau-nam", "Rau nấm thập cẩm", 120_000, HOTPOT_DINERS),
    ("mi-tom", "Mì tôm 6 vắt", 60_000, HOTPOT_DINERS),
    ("bia", "Bia 6 lon", 150_000, DRINKERS),
    ("nuoc-ngot", "Nước ngọt 3 lon", 45_000, SOFT_DRINKERS),
    ("kem", "Kem tráng miệng 4 phần", 100_000, DESSERT),
    ("khan-tra", "Khăn lạnh + trà đá", 50_000, HOTPOT_DINERS),
]
HOTPOT_TOTAL_VND = 1_125_000


def hotpot_items() -> list[dict]:
    return [
        {
            "item_id": item_id,
            "label": label,
            "amount_vnd": amount,
            "shared_by": [str(pid) for pid in shared_by],
        }
        for item_id, label, amount, shared_by in HOTPOT_ITEMS
    ]


def outings(now: datetime) -> list[dict]:
    """The three outings, newest last.

    `days_ago` is relative so the demo never shows a date from before the
    machine was set up, and `settle` says how much of each round the recipient
    has confirmed.

    Every `due_in_days` is positive, including June's. That is not sloppiness:
    `POST /batches` refuses a `due_at` that is not in the future
    (`due_at_not_future`, service.py), and it is right to -- opening a
    collection round that is already overdue would mark everybody late the
    instant it was sent. So what a past outing means here is "the dinner was in
    June, the round was opened now, and it has since been paid in full". The
    expense dates are genuinely backdated; only the due dates cannot be.
    """

    return [
        {
            "slug": "thang-6",
            "label": "Chuyến Đà Lạt tháng 6",
            "days_ago": 75,
            "due_in_days": 2,
            # `nights` backdates `starts_on`; the expenses land on `ends_on`.
            # Two nights, which is what the homestay line above was paid for.
            "nights": 2,
            "budget_per_person_vnd": 900_000,
            "stops": [
                {
                    "at": "07:30",
                    "label": "Xe khách Sài Gòn – Đà Lạt",
                    "place_name": None,
                },
                {
                    "at": "14:00",
                    "label": "Nhận phòng",
                    "place_name": "Homestay Cỏ Hồng",
                },
                {"at": "19:00", "label": "Ăn tối", "place_name": "Tiệm Nướng Xóm Lèo"},
            ],
            "expenses": [
                {
                    "slug": "homestay",
                    "description": "Homestay Đà Lạt · 2 đêm",
                    "paid_by": MINH,
                    "participants": EVERYONE,
                    "total_amount_vnd": 2_800_000,
                    "items": [],
                },
                {
                    "slug": "ve-xe",
                    "description": "Vé xe khách Sài Gòn – Đà Lạt",
                    "paid_by": TRANG,
                    "participants": EVERYONE,
                    "total_amount_vnd": 1_400_000,
                    "items": [],
                },
            ],
            # Settled: everybody paid, the recipients confirmed in full. This
            # outing exists so the history has something finished in it.
            "settle": "all",
        },
        {
            "slug": "thang-8",
            "label": "Chuyến Đà Lạt tháng 8",
            "days_ago": 12,
            "due_in_days": 3,
            "nights": 1,
            "budget_per_person_vnd": 600_000,
            "stops": [
                {"at": "08:00", "label": "Cà phê sáng", "place_name": "Mê Linh Coffee"},
                {"at": "11:30", "label": "Săn mây", "place_name": "Cầu Đất"},
                {"at": "18:30", "label": "Lẩu nấm", "place_name": "Lẩu Nấm Ba Toa"},
            ],
            "expenses": [
                {
                    "slug": "lau-nam",
                    "description": "Lẩu nấm Đà Lạt · hoá đơn 8 món",
                    "paid_by": HAI,
                    "participants": HOTPOT_DINERS,
                    "total_amount_vnd": HOTPOT_TOTAL_VND,
                    "items": hotpot_items(),
                },
                {
                    "slug": "ca-phe",
                    "description": "Cà phê sáng Mê Linh",
                    "paid_by": HAI,
                    "participants": HOTPOT_DINERS,
                    # 500.000 over six does not divide. Deliberate.
                    "total_amount_vnd": 500_000,
                    "items": [],
                },
            ],
            # Mid-collection: two senders have settled, one has sent part of
            # what they owe, the rest have not moved.
            "settle": "partial",
        },
        {
            "slug": "bbq",
            "label": "Bữa nướng cuối tuần",
            "days_ago": 2,
            "due_in_days": 5,
            # A single evening, so the trip is one day long: `starts_on` and
            # `ends_on` are the same date. The recap has to handle that -- a
            # `starts_on < ends_on` assumption would drop this one silently.
            "nights": 0,
            "budget_per_person_vnd": 200_000,
            "stops": [
                {"at": "17:00", "label": "Đi chợ", "place_name": None},
                {"at": "19:00", "label": "Nướng sân thượng", "place_name": None},
            ],
            "expenses": [
                {
                    "slug": "bbq",
                    "description": "Nướng BBQ sân thượng",
                    "paid_by": MINH,
                    "participants": [MINH, TRANG, HAI, NGOC, DUC],
                    "total_amount_vnd": 960_000,
                    "items": [],
                },
            ],
            # Just published. Nobody has paid, which is what a freshly sent
            # collection round actually looks like.
            "settle": "none",
        },
    ]


# --------------------------------------------------------------------------
# building
# --------------------------------------------------------------------------


def register_people() -> None:
    for pid, name in PEOPLE:
        call(
            "PUT",
            f"/people/{pid}",
            body={"display_name": name},
            actor=pid,
            roles=MEMBER_ROLES,
            write_key=idempotency_key(f"person:{pid}"),
        )


def create_group() -> uuid.UUID:
    group = call(
        "POST",
        "/contexts",
        body={"display_name": GROUP_NAME},
        actor=MINH,
        roles=OWNER_ROLES,
        write_key=idempotency_key("context"),
    )
    context_id = uuid.UUID(group["id"])

    for pid, _ in PEOPLE:
        if pid == MINH:
            continue  # the creator is already in.
        invite = call(
            "POST",
            f"/contexts/{context_id}/members",
            body={"person_id": str(pid)},
            actor=MINH,
            roles=OWNER_ROLES,
            context_id=context_id,
            write_key=idempotency_key(f"invite:{pid}"),
        )
        # Being added to a group is something that happens to you; accepting is
        # the invitee's own action, so it goes out under their id.
        call(
            "POST",
            f"/memberships/{invite['id']}/accept",
            actor=pid,
            roles=MEMBER_ROLES,
            context_id=context_id,
            write_key=idempotency_key(f"accept:{pid}"),
        )
    return context_id


def record_expense(context_id: uuid.UUID, spec: dict, occurred_at: datetime) -> str:
    """Propose, then confirm the allocation the API answered with.

    `expected_allocations` is echoed straight back from the proposal on
    purpose. It is a concurrency check -- "split it the way you just told me,
    or refuse" -- and the moment this script computes its own number to put
    there, it has become a second splitter.
    """

    payer = spec["paid_by"]
    proposal = call(
        "POST",
        "/expenses",
        body={
            "context_id": str(context_id),
            "description": spec["description"],
            "recorded_by_id": str(payer),
            "paid_by_id": str(payer),
            "verification_scope": "items_reviewed" if spec["items"] else "totals_only",
            "occurred_at": occurred_at.isoformat(),
            "participants": [str(pid) for pid in spec["participants"]],
            "total_amount_vnd": spec["total_amount_vnd"],
            "items": spec["items"],
            "surcharges": [],
            "discounts": [],
        },
        write_key=idempotency_key(f"expense:{spec['slug']}"),
    )
    confirmation = call(
        "POST",
        f"/expenses/{proposal['expense_id']}/confirm",
        body={
            "proposal": proposal["proposal"],
            "expected_allocations": proposal["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
        actor=payer,
        roles=OWNER_ROLES,
        context_id=context_id,
        write_key=idempotency_key(f"confirm:{spec['slug']}"),
    )
    return confirmation["expense_version_id"]


def collect(context_id: uuid.UUID, outing: dict, version_ids: list[str], now: datetime):
    """Freeze one outing into its own batch and publish it.

    The version ids are passed explicitly. Left to default, `POST /batches`
    sweeps up every outstanding expense in the group, and the three outings
    would collapse into one batch -- which is exactly what a history is not.
    """

    batch = call(
        "POST",
        "/batches",
        body={
            "context_id": str(context_id),
            "expense_version_ids": version_ids,
            "due_at": (now + timedelta(days=outing["due_in_days"])).isoformat(),
        },
        actor=MINH,
        roles=OWNER_ROLES,
        context_id=context_id,
        write_key=idempotency_key(f"batch:{outing['slug']}"),
    )
    published = call(
        "POST",
        f"/batches/{batch['batch_id']}/publish",
        body={
            "delivery_method": "personal_link",
            "guest_link_expires_at": (now + timedelta(days=30)).isoformat(),
        },
        actor=MINH,
        roles=OWNER_ROLES,
        context_id=context_id,
        write_key=idempotency_key(f"publish:{outing['slug']}"),
    )
    return batch, published


def confirm_receipts(context_id: uuid.UUID, outing: dict, batch: dict) -> None:
    """Confirm receipt as the recipient, for as many obligations as the outing
    says have been paid.

    Sorted by sender, never by obligation id. Obligation ids are `uuid4`, so
    ordering by them picks a different subset of people on every build -- the
    first two runs of this script had Trang owing 453.666đ and then 192.000đ
    for the same fixture. Sender ids are derived with `uuid5`, so this ordering
    is the same on every machine, and the demo owes the same money twice.
    """

    mode = outing["settle"]
    if mode == "none":
        return

    obligations = sorted(
        batch["obligations"], key=lambda o: (o["sender_id"], o["recipient_id"])
    )
    for index, obligation in enumerate(obligations):
        amount = obligation["amount_vnd"]
        if mode == "partial":
            if index >= 3:
                continue  # untouched: still outstanding.
            if index == 2:
                # A real part-payment, not a rounding artefact: half, floored
                # to whole dong, and never zero.
                amount = max(1, amount // 2)
        call(
            "POST",
            f"/obligations/{obligation['obligation_id']}/confirm-receipt",
            body={
                "amount_vnd": amount,
                "idempotency_key": idempotency_key(
                    f"receipt:{obligation['obligation_id']}"
                ),
            },
            actor=uuid.UUID(obligation["recipient_id"]),
            roles=OWNER_ROLES,
            context_id=context_id,
            write_key=idempotency_key(f"receipt-call:{obligation['obligation_id']}"),
        )


def record_outing(context_id: uuid.UUID, outing: dict, occurred_at: datetime) -> None:
    """Create the `outings` row and its timeline for one past trip.

    Until this existed the three "outings" in this file were only a way of
    grouping expenses into separate batches -- the word appeared in the script
    and nowhere in the database. F13/F15 gave trips a table, and the memory wall
    (F30) reads it, so a demo without these rows shows an empty wall next to a
    group that has visibly been to Đà Lạt twice.

    The dates are Vietnam's calendar days, taken from the same instant the
    expenses are backdated to. Using the UTC date instead would put a trip on
    the wrong day for seven hours out of every twenty-four, and `GET
    /contexts/{id}/recap` matches spending to a trip by exactly these days --
    so the bug would show up as a trip that cost nothing, on some runs only.
    """

    on_day = occurred_at.astimezone(VIETNAM).date()
    created = call(
        "POST",
        f"/contexts/{context_id}/outings",
        body={
            "title": outing["label"],
            "starts_on": (on_day - timedelta(days=outing["nights"])).isoformat(),
            "ends_on": on_day.isoformat(),
            "headcount": len(PEOPLE),
            "budget_per_person_vnd": outing["budget_per_person_vnd"],
        },
        actor=MINH,
        roles=OWNER_ROLES,
        context_id=context_id,
        write_key=idempotency_key(f"outing:{outing['slug']}"),
    )
    call(
        "PUT",
        f"/outings/{created['id']}/timeline",
        body={"stops": outing["stops"]},
        actor=MINH,
        roles=OWNER_ROLES,
        context_id=context_id,
        write_key=idempotency_key(f"timeline:{outing['slug']}"),
    )


def build(now: datetime) -> tuple[uuid.UUID, list[str]]:
    register_people()
    context_id = create_group()

    guest_paths: list[str] = []
    for outing in outings(now):
        occurred_at = now - timedelta(days=outing["days_ago"])
        record_outing(context_id, outing, occurred_at)
        version_ids = [
            record_expense(context_id, spec, occurred_at) for spec in outing["expenses"]
        ]
        batch, published = collect(context_id, outing, version_ids, now)
        confirm_receipts(context_id, outing, batch)
        for link in published["guest_links"]:
            who = NAME_OF.get(uuid.UUID(link["sender_id"]), link["sender_id"])
            guest_paths.append(f"{link['path']}  ({who} · {outing['label']})")

    return context_id, guest_paths


# --------------------------------------------------------------------------
# reporting -- read back, do not replay what we think we wrote
#
# Everything printed below is fetched again from Postgres and from the API
# after the writes. A summary assembled from the script's own in-memory
# results would print the same happy numbers whether or not a single row
# landed, which is the exact failure this repository keeps finding in green
# checkmarks.
# --------------------------------------------------------------------------


def report(
    connection: psycopg.Connection, context_id: uuid.UUID, guest_paths: list[str]
) -> int:
    members = connection.execute(
        "SELECT COUNT(*) FROM memberships WHERE context_id = %s AND state = 'active'",
        (context_id,),
    ).fetchone()[0]
    expenses = connection.execute(
        "SELECT COUNT(*) FROM expenses WHERE context_id = %s", (context_id,)
    ).fetchone()[0]
    batch_rows = connection.execute(
        "SELECT id, status, created_at FROM collection_batches "
        "WHERE context_id = %s ORDER BY created_at",
        (context_id,),
    ).fetchall()

    print(f"Nhóm demo    {GROUP_NAME}  ({context_id})")
    print(
        f"  thành viên   {members} người · khoản chi {expenses} · đợt thu "
        f"{len(batch_rows)}"
    )

    # Law 2, checked on the rows that were just written rather than assumed
    # from the fact that the API answered 201. Every confirmed expense version
    # must have its allocations sum to its own total, to the dong.
    drift = connection.execute(
        "SELECT v.id, v.total_amount_vnd, COALESCE(SUM(a.amount_vnd), 0) "
        "FROM expense_versions v "
        "JOIN expenses e ON e.id = v.expense_id "
        "LEFT JOIN confirmed_allocations a ON a.expense_version_id = v.id "
        "WHERE e.context_id = %s "
        "GROUP BY v.id, v.total_amount_vnd "
        "HAVING COALESCE(SUM(a.amount_vnd), 0) <> v.total_amount_vnd",
        (context_id,),
    ).fetchall()
    if drift:
        print("  TIỀN SAI — Σ phân bổ không bằng tổng khoản chi:")
        for version_id, total, allocated in drift:
            print(f"    {version_id}  tổng {total}  phân bổ {allocated}")
        return 1
    print("  luật tiền   Σ phân bổ = tổng khoản chi ở mọi phiên bản (kiểm trên DB)")

    # How much of each obligation has actually been confirmed, read from the
    # receipt ledger. The collection board reports a status but not a confirmed
    # amount, so a partially paid obligation would otherwise be counted at its
    # full value -- which is the cache-as-truth mistake law 3 forbids.
    confirmed_vnd = dict(
        connection.execute(
            "SELECT r.obligation_id, SUM(r.amount_vnd) FROM receipt_confirmations r "
            "JOIN collection_obligations o ON o.id = r.obligation_id "
            "JOIN collection_batch_versions v ON v.id = o.batch_version_id "
            "JOIN collection_batches b ON b.id = v.batch_id "
            "WHERE b.context_id = %s GROUP BY r.obligation_id",
            (context_id,),
        ).fetchall()
    )

    owed: dict[uuid.UUID, int] = {}
    statuses: dict[str, int] = {}

    for batch_id, status, _created in batch_rows:
        board = call(
            "GET",
            f"/batches/{batch_id}/obligations",
            actor=MINH,
            roles=OWNER_ROLES,
            context_id=context_id,
        )
        for obligation in board["obligations"]:
            state = obligation["obligation_status"]
            statuses[state] = statuses.get(state, 0) + 1
            paid = confirmed_vnd.get(uuid.UUID(obligation["obligation_id"]), 0)
            remaining = obligation["amount_vnd"] - paid
            if remaining > 0:
                sender = uuid.UUID(obligation["sender_id"])
                owed[sender] = owed.get(sender, 0) + remaining
        print(f"  đợt {batch_id}  {status}  {len(board['obligations'])} nghĩa vụ")

    # Counted, not listed: `guest_links` persists a SHA-256 digest and never the
    # token, so a link that was not printed at publish time cannot be recovered
    # from here by anybody -- this script included. That is the capability
    # behaving correctly, not a gap to work around.
    live_links = connection.execute(
        "SELECT COUNT(*) FROM guest_links g "
        "JOIN collection_envelopes e ON e.id = g.envelope_id "
        "JOIN collection_batch_versions v ON v.id = e.batch_version_id "
        "JOIN collection_batches b ON b.id = v.batch_id "
        "WHERE b.context_id = %s AND g.status = 'active'",
        (context_id,),
    ).fetchone()[0]

    print(
        "  trạng thái   " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items()))
    )
    print("  còn nợ (nghĩa vụ trừ số đã xác nhận nhận được, tính từ sổ):")
    if not owed:
        print("    — không ai còn nợ. Dữ liệu demo lẽ ra phải có số dư khác 0.")
        return 1
    for pid, amount in sorted(owed.items(), key=lambda kv: -kv[1]):
        print(f"    {NAME_OF.get(pid, pid):<8} {amount:,}đ".replace(",", "."))

    print(f"  trang khách  {live_links} link còn sống")
    if guest_paths:
        for path in guest_paths:
            print(f"    {path}")
        print("Ghép với địa chỉ `make smoke` in ra để mở trang khách trên trình duyệt.")
    else:
        print(
            "    Token chỉ tồn tại trong câu trả lời của publish — DB chỉ giữ digest,"
        )
        print("    nên lần chạy này không in lại được link của lần trước. Cần link mới")
        print("    thì xoay link cho người đó, hoặc `make clean` rồi `make demo` lại.")
    return 0


def main() -> int:
    if not DATABASE_URL:
        raise SeedFailed(
            "Thiếu MOBILE_DATABASE_URL. Chạy qua `make demo`, đừng gọi tay."
        )

    wait_for_api()
    now = datetime.now(UTC)

    with psycopg.connect(psycopg_dsn(DATABASE_URL), autocommit=True) as connection:
        context_id = existing_group(connection)
        guest_paths: list[str] = []
        if context_id is None:
            context_id, guest_paths = build(now)
            print("Đã dựng dữ liệu demo.")
        else:
            check_complete(connection, context_id)
            print("Dữ liệu demo đã có sẵn — không dựng lại, chỉ đọc lại và in ra.")
        return report(connection, context_id, guest_paths)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SeedFailed as failure:
        # A traceback here would only point at this script's own plumbing; the
        # message is the part that says which call refused and why.
        print(f"seed demo thất bại: {failure}", file=sys.stderr)
        sys.exit(1)
