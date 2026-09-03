#!/usr/bin/env python3
"""Mint the first session on a host, out of band.

## Why this exists

ADR-0014 closes a loop that would otherwise close on itself. In `prod` a
session comes from a named invitation, a named invitation is issued by a member
holding a session, and on a fresh host nobody holds one. Every HTTP route is
correctly shut, and the product cannot be entered at all.

This script is the one door outside HTTP. Its authorization is possession of
the database URL, which is the strongest credential in the system already --
so this adds no attack surface that a person with `psql` did not have.

## What it does

Creates, if missing: a person, a group, and that person's ACTIVE `admin`
membership. Then mints a session for them and prints the raw token exactly
once. From there the ordinary flow works: this person names other people
(`PUT /people/{id}`), creates a trip, and invites them
(`POST /outings/{id}/invites`), and each of those invitations is exchanged for
a session at `POST /sessions`.

## What it deliberately does not do

* It does not turn the auth mode off. A host that needs a session gets a
  session; it does not get a window during which headers are trusted.
* It stores no raw token. The row holds a SHA-256 digest, exactly like every
  other bearer capability in this schema.
* It is not idempotent about the *token*: run it twice and the person has two
  live sessions, because that is what signing in on a second device means.
  Re-running does not duplicate the person, the group, or the membership.

The token it prints is a credential. It belongs in a password manager or in the
operator's own hands, not in a ticket, a chat message, or a commit.
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import (  # noqa: E402
    AccountSession,
    Context,
    Membership,
    MembershipOrigin,
    MembershipRole,
    MembershipState,
    Person,
)
from app.db.session import DEFAULT_DATABASE_URL  # noqa: E402

#: Shorter than the API's own thirty days on purpose. This one is typed in by
#: hand on a laptop and is meant to be traded for the ordinary flow quickly; a
#: month-long credential printed to a terminal is a month-long credential
#: sitting in somebody's scrollback.
GENESIS_SESSION_TTL = timedelta(days=7)


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _ensure_person(
    session: Session, person_id: uuid.UUID | None, display_name: str
) -> Person:
    if person_id is not None:
        existing = session.get(Person, person_id)
        if existing is not None:
            return existing
        person = Person(id=person_id, display_name=display_name)
    else:
        person = Person(id=uuid.uuid4(), display_name=display_name)
    session.add(person)
    session.flush()
    return person


def _ensure_group(session: Session, name: str, owner: Person) -> Context:
    existing = session.scalar(
        select(Context).where(Context.display_name == name).limit(1)
    )
    if existing is not None:
        return existing
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
    session.add(context)
    session.flush()
    return context


def _ensure_admin_membership(
    session: Session, context: Context, person: Person, now: datetime
) -> Membership:
    existing = session.scalar(
        select(Membership)
        .where(
            Membership.context_id == context.id,
            Membership.person_id == person.id,
            Membership.left_at.is_(None),
        )
        .limit(1)
    )
    if existing is not None:
        # Promote rather than duplicate: a half-seeded host is the case this
        # script is most often run against.
        existing.state = MembershipState.ACTIVE
        existing.role = MembershipRole.ADMIN
        if existing.joined_at is None:
            existing.joined_at = now
        session.flush()
        return existing

    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=person.id,
        state=MembershipState.ACTIVE,
        role=MembershipRole.ADMIN,
        # Nobody invited the first person. `named` is the closest true thing:
        # an operator chose them, which is a person's decision, not a
        # forwarded link.
        origin=MembershipOrigin.NAMED,
        invited_by_id=person.id,
        joined_at=now,
    )
    session.add(membership)
    session.flush()
    return membership


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Tạo phiên đầu tiên trên một host (ADR-0014)."
    )
    parser.add_argument("--display-name", required=True, help="Tên người dùng đầu tiên")
    parser.add_argument("--group", required=True, help="Tên nhóm đầu tiên")
    parser.add_argument(
        "--person-id",
        type=uuid.UUID,
        default=None,
        help="UUID người đã mint sẵn (bỏ trống thì script tự sinh)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "In một dòng JSON thay vì văn bản cho người đọc. Dùng cho harness "
            "(scripts/e2e_slice.sh); token vẫn chỉ hiện một lần."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=f"Mặc định lấy MOBILE_DATABASE_URL, rồi tới {DEFAULT_DATABASE_URL}",
    )
    args = parser.parse_args(argv)

    import os

    database_url = (
        args.database_url
        or os.environ.get("MOBILE_DATABASE_URL")
        or DEFAULT_DATABASE_URL
    )

    engine = create_engine(database_url, pool_pre_ping=True)
    now = datetime.now(UTC)
    raw_token = secrets.token_urlsafe(32)

    with Session(engine) as session, session.begin():
        person = _ensure_person(session, args.person_id, args.display_name)
        context = _ensure_group(session, args.group, person)
        _ensure_admin_membership(session, context, person, now)
        session.add(
            AccountSession(
                id=uuid.uuid4(),
                person_id=person.id,
                token_digest=_digest(raw_token),
                issued_from_invite_id=None,
                created_at=now,
                expires_at=now + GENESIS_SESSION_TTL,
            )
        )
        person_id = person.id
        context_id = context.id

    engine.dispose()

    if args.json:
        # One line, so a caller can read it without parsing prose. The token is
        # in here for the same reason it is in the text below: this is the one
        # moment it exists outside the digest.
        import json

        print(
            json.dumps(
                {
                    "person_id": str(person_id),
                    "context_id": str(context_id),
                    "token": raw_token,
                    "expires_at": (now + GENESIS_SESSION_TTL).isoformat(),
                }
            )
        )
        return 0

    print(f"person_id : {person_id}")
    print(f"context_id: {context_id}")
    print(f"hết hạn   : {(now + GENESIS_SESSION_TTL).isoformat()}")
    print()
    print("Bearer token (chỉ hiện MỘT lần, không lưu ở đâu khác):")
    print(raw_token)
    print()
    print("Dùng thử:")
    print(f'  curl -H "Authorization: Bearer {raw_token}" \\')
    print(f"       http://localhost:8000/contexts/{context_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
