"""Probe server for PR #301: real uvicorn, real Postgres, real routes.

Only the network boundary to Gemini is patched -- `suggestion_gemini._post`.
It counts calls and KEEPS EVERY PROMPT, so the "nobody is named" claim can be
checked against what would actually leave the process, not against a docstring.
Everything above it (prompt assembly, the digest, the limiter, permissions,
the repository) is the shipped code.
"""

from __future__ import annotations

import os
import sys
import threading
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "api"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.api.suggestion_gemini as sg  # noqa: E402
from app.api.deps import get_repository  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.api.repository import SqlAlchemyApiRepository  # noqa: E402
from app.db.models import (  # noqa: E402
    Context,
    Memory,
    MemoryKind,
    Membership,
    MembershipRole,
    MembershipState,
    Message,
    MessageKind,
    Outing,
    Person,
)
from app.places.catalog import PLACES  # noqa: E402

from datetime import date, timedelta

TRIP_START = date(2026, 8, 1)
TRIP_END = TRIP_START + timedelta(days=2)

URL = os.environ["QA28_DB"]
engine = create_engine(URL, future=True)

CALLS = {"n": 0}
PROMPTS: list[str] = []
_lock = threading.Lock()

_real_post = sg._post


def _counting_post(prompt: str, api_key: str) -> str | None:
    """Stand in for the round trip, and remember exactly what was going to be sent."""

    with _lock:
        CALLS["n"] += 1
        PROMPTS.append(prompt)
    return (
        '{"headline":"Đi ăn lẩu đi","reason":"Cả nhóm đang than đói","place_id":"%s"}'
        % (PLACES[0]["id"],)
    )


sg._post = _counting_post

IDS: dict[str, str] = {}


def seed() -> None:
    with Session(engine) as s:
        owner = Person(id=uuid.uuid4(), display_name="Trần Bảo Khánh")
        friend = Person(id=uuid.uuid4(), display_name="Nguyễn Thu Hà")
        outsider = Person(id=uuid.uuid4(), display_name="Người Ngoài")
        s.add_all([owner, friend, outsider])
        s.flush()

        ctx = Context(
            id=uuid.uuid4(), display_name="Hội bạn thân", created_by_id=owner.id
        )
        other_ctx = Context(
            id=uuid.uuid4(), display_name="Nhóm khác", created_by_id=outsider.id
        )
        s.add_all([ctx, other_ctx])
        s.flush()

        for person, context in ((owner, ctx), (friend, ctx), (outsider, other_ctx)):
            s.add(
                Membership(
                    id=uuid.uuid4(),
                    context_id=context.id,
                    person_id=person.id,
                    state=MembershipState.ACTIVE,
                    role=MembershipRole.MEMBER,
                    joined_at=sg_now(),
                )
            )
        s.flush()

        # Conversation: two human turns plus one ai_card and one image, which
        # the digest is supposed to drop.
        for kind, body, card, author in (
            (MessageKind.TEXT, "Đói quá mọi người ơi", None, owner),
            (MessageKind.TEXT, "Tối nay ăn gì đây", None, friend),
            (
                MessageKind.AI_CARD,
                None,
                {"headline": "CANARY_AI_CARD", "reason": "thẻ cũ của trợ lý"},
                owner,
            ),
        ):
            s.add(
                Message(
                    id=uuid.uuid4(),
                    context_id=ctx.id,
                    author_id=author.id,
                    kind=kind,
                    body=body,
                    card=card,
                    created_at=sg_now(),
                )
            )
        s.flush()

        # Check-ins so the preference profile has something to derive from.
        for place in (PLACES[0], PLACES[0]):
            s.add(
                Memory(
                    id=uuid.uuid4(),
                    context_id=ctx.id,
                    author_id=owner.id,
                    kind=MemoryKind.CHECKIN,
                    place_id=place["id"],
                    place_name=place["name"],
                    lat=place["lat"],
                    lng=place["lng"],
                    created_at=sg_now(),
                )
            )

        outing = Outing(
            id=uuid.uuid4(),
            context_id=ctx.id,
            title="Đà Lạt",
            created_by_id=owner.id,
            starts_on=TRIP_START,
            ends_on=TRIP_END,
            headcount=3,
            budget_per_person_vnd=500_000,
        )
        other_outing = Outing(
            id=uuid.uuid4(),
            context_id=other_ctx.id,
            title="Chuyến của nhóm khác",
            created_by_id=outsider.id,
            starts_on=TRIP_START,
            ends_on=TRIP_END,
            headcount=3,
            budget_per_person_vnd=500_000,
        )
        s.add_all([outing, other_outing])
        s.commit()

        IDS.update(
            ctx=str(ctx.id),
            other_ctx=str(other_ctx.id),
            owner=str(owner.id),
            friend=str(friend.id),
            outsider=str(outsider.id),
            outing=str(outing.id),
            other_outing=str(other_outing.id),
        )


def sg_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


seed()

application = create_app()
_session = Session(engine)
application.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(
    _session
)


@application.get("/__probe")
def probe() -> dict:
    with _lock:
        return {"MODEL_CALLS": CALLS["n"], "prompts": list(PROMPTS), "ids": IDS}


@application.post("/__reset")
def reset() -> dict:
    with _lock:
        CALLS["n"] = 0
        PROMPTS.clear()
    return {"ok": True}
