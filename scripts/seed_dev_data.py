#!/usr/bin/env python3
"""Fill a local development database with one synthetic collection round.

Runs inside the API image (see the `seed` service in docker-compose.yml): it
needs psycopg, which is a runtime dependency, and network access to the API.

There are two write paths on purpose.

* `people` and `bank_recipients` are written with SQL. No HTTP route creates
  either one yet, and inventing product surface inside a dev fixture is worse
  than admitting the gap. When the recipient-registration route lands, the
  bank block here should be deleted, not kept as a second way in.
* Everything else goes through the real HTTP API. That is the point: a seed
  that finished means the vertical slice answered for real, not that a script
  can run INSERT.

Re-running is a no-op. The demo group is looked up by display name first, so
`make up` twice does not create a second group or a second expense.

All data here is invented. Nothing in this file may ever be replaced with a
real name, a real account number, or a real amount -- it is committed to Git.
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

import psycopg

API_BASE = os.environ.get("MOBILE_SEED_API_BASE_URL", "http://api:8000").rstrip("/")
DATABASE_URL = os.environ.get("MOBILE_DATABASE_URL")

GROUP_NAME = "Nhóm mẫu (dữ liệu tổng hợp)"

# Ids must be stable so a second run recognises its own rows instead of piling
# up new ones. They are derived rather than written out: a UUID literal padded
# with zeroes is a long digit run, and the repo guard blocks those on sight --
# it cannot tell a demo id from an account number, and it is right not to try.
SEED_NAMESPACE = uuid.UUID("5eed5eed-5eed-5eed-5eed-5eed5eed5eed")
ADVANCER_ID = uuid.uuid5(SEED_NAMESPACE, "advancer")
SENDER_A_ID = uuid.uuid5(SEED_NAMESPACE, "sender-a")
SENDER_B_ID = uuid.uuid5(SEED_NAMESPACE, "sender-b")
BANK_ROW_ID = uuid.uuid5(SEED_NAMESPACE, "bank-recipient")

PEOPLE = [
    (ADVANCER_ID, "An (dữ liệu mẫu)"),
    (SENDER_A_ID, "Bình (dữ liệu mẫu)"),
    (SENDER_B_ID, "Chi (dữ liệu mẫu)"),
]

# 300000 over three people divides exactly, so the seed does not quietly depend
# on the rounding rule. A vector that exercises rounding belongs in the golden
# corpus, where somebody checked the answer by hand.
TOTAL_VND = 300_000

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

    request = urllib.request.Request(
        f"{API_BASE}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        # The API's own error body says more than any message this script
        # could invent, so pass it through instead of summarising it.
        detail = exc.read().decode("utf-8", errors="replace")
        raise SeedFailed(f"{method} {path} -> HTTP {exc.code}\n{detail}") from exc
    except urllib.error.URLError as exc:
        raise SeedFailed(
            f"{method} {path} -> không nối được API: {exc.reason}"
        ) from exc
    return json.loads(payload) if payload else {}


def wait_for_api(timeout_s: float = 60.0) -> None:
    """Compose already gates on the healthcheck; this covers `make seed` run
    on its own against a stack somebody started by hand."""

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


def write_rows_with_no_route(connection: psycopg.Connection) -> None:
    connection.execute(
        "INSERT INTO people (id, display_name) VALUES "
        "(%s, %s), (%s, %s), (%s, %s) ON CONFLICT (id) DO NOTHING",
        tuple(value for person in PEOPLE for value in person),
    )
    # No conflict target: the live-recipient constraint is a partial unique
    # index on recipient_id, so a second run can collide on a row id this
    # script never chose.
    connection.execute(
        "INSERT INTO bank_recipients "
        "(id, recipient_id, bank_bin, account_number, account_name,"
        " confirmed_by_recipient_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (
            BANK_ROW_ID,
            ADVANCER_ID,
            "970415",
            "SEEDACCOUNT0001",
            "TAI KHOAN MAU",
            datetime.now(UTC),
        ),
    )


def build_round() -> dict:
    now = datetime.now(UTC)

    group = call(
        "POST",
        "/contexts",
        body={"display_name": GROUP_NAME},
        actor=ADVANCER_ID,
        roles=OWNER_ROLES,
    )
    context_id = uuid.UUID(group["id"])

    for person_id in (SENDER_A_ID, SENDER_B_ID):
        invite = call(
            "POST",
            f"/contexts/{context_id}/members",
            body={"person_id": str(person_id)},
            actor=ADVANCER_ID,
            roles=OWNER_ROLES,
            context_id=context_id,
        )
        # Being added to a group is something that happens to you; accepting is
        # the invitee's own action, so it goes out under their id.
        call(
            "POST",
            f"/memberships/{invite['id']}/accept",
            actor=person_id,
            roles=MEMBER_ROLES,
            context_id=context_id,
        )

    proposal = call(
        "POST",
        "/expenses",
        body={
            "context_id": str(context_id),
            "description": "Bữa tối nhóm (dữ liệu mẫu)",
            "recorded_by_id": str(ADVANCER_ID),
            "paid_by_id": str(ADVANCER_ID),
            "verification_scope": "totals_only",
            "occurred_at": (now - timedelta(days=1)).isoformat(),
            "participants": [str(person_id) for person_id, _ in PEOPLE],
            "total_amount_vnd": TOTAL_VND,
            "items": [],
            "surcharges": [],
            "discounts": [],
        },
    )
    confirmation = call(
        "POST",
        f"/expenses/{proposal['expense_id']}/confirm",
        body={
            "proposal": proposal["proposal"],
            "expected_allocations": proposal["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
        actor=ADVANCER_ID,
        roles=OWNER_ROLES,
        context_id=context_id,
    )

    batch = call(
        "POST",
        "/batches",
        body={
            "context_id": str(context_id),
            "due_at": (now + timedelta(days=7)).isoformat(),
        },
        actor=ADVANCER_ID,
        roles=OWNER_ROLES,
        context_id=context_id,
    )
    published = call(
        "POST",
        f"/batches/{batch['batch_id']}/publish",
        body={
            "delivery_method": "personal_link",
            "guest_link_expires_at": (now + timedelta(days=30)).isoformat(),
        },
        actor=ADVANCER_ID,
        roles=OWNER_ROLES,
        context_id=context_id,
    )

    return {
        "context_id": context_id,
        "expense_version_id": confirmation["expense_version_id"],
        "allocations": confirmation["allocations"],
        "batch_id": batch["batch_id"],
        "guest_links": published["guest_links"],
    }


def main() -> int:
    if not DATABASE_URL:
        raise SeedFailed(
            "Thiếu MOBILE_DATABASE_URL. Chạy qua `make seed`, đừng gọi tay."
        )

    wait_for_api()

    with psycopg.connect(psycopg_dsn(DATABASE_URL), autocommit=True) as connection:
        already = existing_group(connection)
        if already is not None:
            print(f"Đã có dữ liệu mẫu (nhóm {already}) — không seed lại.")
            return 0
        write_rows_with_no_route(connection)

    result = build_round()

    print("Đã seed một đợt thu hoàn chỉnh:")
    print(f"  nhóm            {result['context_id']}")
    print(f"  đợt thu         {result['batch_id']}")
    print(f"  chia tiền       {result['allocations']}")
    for link in result["guest_links"]:
        amounts = ", ".join(f"{item['amount_vnd']}đ" for item in link["obligations"])
        print(f"  trang khách     {link['path']}  ({amounts})")
    print("Ghép với địa chỉ `make smoke` in ra để mở trang khách trên trình duyệt.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SeedFailed as failure:
        # A traceback here would only point at this script's own plumbing; the
        # message is the part that says which call refused and why.
        print(f"seed thất bại: {failure}", file=sys.stderr)
        sys.exit(1)
