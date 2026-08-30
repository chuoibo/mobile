"""Bill drafts against the real database, where the constraints actually live.

The fake repository in `tests/api/conftest.py` can be taught to say anything.
It cannot be taught to reject a row, which is the whole point of the
`decision_matches_source` check constraint: "confirmed" is supposed to mean a
named person decided at a known moment, and if that rule lives only in Python
then one `UPDATE` that forgets two columns turns every AI guess into a
confirmed charge. So the test that matters here does not go through the
repository at all -- it tries to write the bad row directly and expects
PostgreSQL to refuse.

Read-backs use a SEPARATE connection on purpose. A session that has written but
not committed happily reads its own uncommitted rows, so asserting through the
writing session proves the object graph in memory and nothing about what
survives. That failure mode is invisible to both the fake and a shared-session
live client.

Note for whoever adds cases here: `tests/postgres` shares one schema for the
whole session, so never assert "this table has exactly N rows".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.repository import RepositoryConflict, SqlAlchemyApiRepository
from app.db.models import BillItemShare, BillShareSource
from app.domain.allocator import allocate
from app.domain.bill import allocator_input_from_bill

from .conftest import seed_context

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)
LATER = datetime(2030, 8, 29, 10, 30, tzinfo=UTC)


def _items(an: uuid.UUID, binh: uuid.UUID) -> list[dict]:
    """Two lines with different amounts. Equal amounts would let an even split
    and a per-item split agree, and then the projection could be wrong without
    any assertion here noticing."""

    return [
        {
            "item_key": "i1",
            "name": "Phở bò",
            "quantity": 1,
            "unit_price_vnd": 65000,
            "line_total_vnd": 65000,
            "position": 0,
            "suggested_participant_ids": [an],
        },
        {
            "item_key": "i2",
            "name": "Bún chả",
            "quantity": 1,
            "unit_price_vnd": 70000,
            "line_total_vnd": 70000,
            "position": 1,
            "suggested_participant_ids": [binh],
        },
    ]


def _create_bill(session: Session, an: uuid.UUID, binh: uuid.UUID, **overrides):
    repository = SqlAlchemyApiRepository(session)
    payload = {
        "context_id": uuid.uuid4(),
        "created_by_id": an,
        "printed_total_vnd": 135000,
        "items_total_vnd": 135000,
        "confidence": 88,
        "needs_review": False,
        "items": _items(an, binh),
        "surcharges": [],
        "discounts": [],
        "now": NOW,
    }
    payload.update(overrides)
    payload["context_id"] = seed_context(session, payload["context_id"])
    return repository.create_bill(**payload)


@pytest.fixture
def people() -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), uuid.uuid4()


def _committed(postgres_engine: Engine, session: Session):
    """Commit, then hand back a brand-new session so the next read crosses a
    real connection boundary rather than the writer's own transaction."""

    session.commit()
    return Session(postgres_engine, expire_on_commit=False)


class TestWhatSurvivesACommit:
    def test_a_suggested_assignment_reads_back_as_a_suggestion(
        self, postgres_engine: Engine, postgres_session: Session, people
    ):
        an, binh = people
        bill = _create_bill(postgres_session, an, binh)

        with _committed(postgres_engine, postgres_session) as reader:
            stored = SqlAlchemyApiRepository(reader).get_bill(bill.id)

        assert [item.item_key for item in stored.items] == ["i1", "i2"]
        for item in stored.items:
            for share in item.shares:
                assert share.source == "ai_suggested"
                assert share.decided_by_id is None
                assert share.decided_at is None

    def test_confirming_records_who_decided_and_when(
        self, postgres_engine: Engine, postgres_session: Session, people
    ):
        an, binh = people
        bill = _create_bill(postgres_session, an, binh)

        SqlAlchemyApiRepository(postgres_session).confirm_bill_assignments(
            bill_id=bill.id,
            assignments=[
                {"item_key": "i1", "participant_ids": [an]},
                {"item_key": "i2", "participant_ids": [binh]},
            ],
            decided_by_id=an,
            now=LATER,
        )

        with _committed(postgres_engine, postgres_session) as reader:
            stored = SqlAlchemyApiRepository(reader).get_bill(bill.id)

        for item in stored.items:
            for share in item.shares:
                assert share.source == "confirmed"
                assert share.decided_by_id == an
                assert share.decided_at is not None

    def test_a_correction_replaces_the_guess_rather_than_joining_it(
        self, postgres_engine: Engine, postgres_session: Session, people
    ):
        """If the old suggested row survived alongside the correction, the line
        would look shared by two people and charge each of them half."""

        an, binh = people
        bill = _create_bill(postgres_session, an, binh)

        SqlAlchemyApiRepository(postgres_session).confirm_bill_assignments(
            bill_id=bill.id,
            assignments=[{"item_key": "i1", "participant_ids": [binh]}],
            decided_by_id=an,
            now=LATER,
        )

        with _committed(postgres_engine, postgres_session) as reader:
            stored = SqlAlchemyApiRepository(reader).get_bill(bill.id)

        first = next(item for item in stored.items if item.item_key == "i1")
        assert [share.participant_id for share in first.shares] == [binh]
        second = next(item for item in stored.items if item.item_key == "i2")
        assert [share.source for share in second.shares] == ["ai_suggested"]


class TestTheDatabaseEnforcesTheDistinction:
    def test_a_confirmed_share_with_nobody_responsible_is_refused(
        self, postgres_session: Session, people
    ):
        """The acceptance criterion "an AI assignment carries a suggested flag,
        distinct from a confirmed one" proved at the only layer that cannot be
        bypassed. This writes the row directly -- a repository that got the
        rule right would hide a database that got it wrong."""

        an, binh = people
        bill = _create_bill(postgres_session, an, binh)
        item_id = postgres_session.scalar(
            text(
                "SELECT id FROM bill_items WHERE bill_id = :bill_id AND item_key = 'i1'"
            ),
            {"bill_id": bill.id},
        )

        postgres_session.add(
            BillItemShare(
                bill_item_id=item_id,
                participant_id=binh,
                source=BillShareSource.CONFIRMED,
                decided_by_id=None,
                decided_at=None,
            )
        )

        with pytest.raises(IntegrityError):
            postgres_session.flush()
        postgres_session.rollback()

    def test_a_suggestion_carrying_a_decider_is_refused(
        self, postgres_session: Session, people
    ):
        """The constraint has to bite both ways. A guess that names a decider
        is a confirmed charge wearing a suggestion's label."""

        an, binh = people
        bill = _create_bill(postgres_session, an, binh)
        item_id = postgres_session.scalar(
            text(
                "SELECT id FROM bill_items WHERE bill_id = :bill_id AND item_key = 'i1'"
            ),
            {"bill_id": bill.id},
        )

        postgres_session.add(
            BillItemShare(
                bill_item_id=item_id,
                participant_id=binh,
                source=BillShareSource.AI_SUGGESTED,
                decided_by_id=an,
                decided_at=LATER,
            )
        )

        with pytest.raises(IntegrityError):
            postgres_session.flush()
        postgres_session.rollback()

    def test_one_person_cannot_be_assigned_the_same_dish_twice(
        self, postgres_session: Session, people
    ):
        """A duplicate row would give one person two shares of one line, and
        the allocator would read that as two eaters."""

        an, binh = people
        bill = _create_bill(postgres_session, an, binh)
        item_id = postgres_session.scalar(
            text(
                "SELECT id FROM bill_items WHERE bill_id = :bill_id AND item_key = 'i1'"
            ),
            {"bill_id": bill.id},
        )

        postgres_session.add(
            BillItemShare(
                bill_item_id=item_id,
                participant_id=an,
                source=BillShareSource.AI_SUGGESTED,
                decided_by_id=None,
                decided_at=None,
            )
        )

        with pytest.raises(IntegrityError):
            postgres_session.flush()
        postgres_session.rollback()


class TestRefusals:
    def test_assigning_a_dish_the_bill_does_not_have_is_refused(
        self, postgres_session: Session, people
    ):
        an, binh = people
        bill = _create_bill(postgres_session, an, binh)

        with pytest.raises(RepositoryConflict):
            SqlAlchemyApiRepository(postgres_session).confirm_bill_assignments(
                bill_id=bill.id,
                assignments=[{"item_key": "khong-ton-tai", "participant_ids": [an]}],
                decided_by_id=an,
                now=LATER,
            )

    def test_confirming_a_bill_that_does_not_exist_is_refused(
        self, postgres_session: Session
    ):
        with pytest.raises(RepositoryConflict):
            SqlAlchemyApiRepository(postgres_session).confirm_bill_assignments(
                bill_id=uuid.uuid4(),
                assignments=[],
                decided_by_id=uuid.uuid4(),
                now=LATER,
            )


class TestTheWholePath:
    def test_a_stored_bill_projects_onto_the_allocator_and_sums_to_the_paper(
        self, postgres_engine: Engine, postgres_session: Session, people
    ):
        """Scan -> store -> confirm -> project -> allocate, across a real
        commit. Money law 2 is checked against the number printed on the
        paper, not against a total this test computed for itself."""

        an, binh = people
        bill = _create_bill(postgres_session, an, binh)
        SqlAlchemyApiRepository(postgres_session).confirm_bill_assignments(
            bill_id=bill.id,
            assignments=[
                {"item_key": "i1", "participant_ids": [an]},
                {"item_key": "i2", "participant_ids": [binh]},
            ],
            decided_by_id=an,
            now=LATER,
        )

        with _committed(postgres_engine, postgres_session) as reader:
            stored = SqlAlchemyApiRepository(reader).get_bill(bill.id)

        projection = allocator_input_from_bill(
            {
                "participants": [str(an), str(binh)],
                "printed_total_vnd": stored.printed_total_vnd,
                "items": [
                    {
                        "item_key": item.item_key,
                        "amount_vnd": item.line_total_vnd,
                        "shares": [
                            {
                                "participant_id": str(share.participant_id),
                                "source": share.source,
                            }
                            for share in item.shares
                        ],
                    }
                    for item in stored.items
                ],
                "surcharges": [],
                "discounts": [],
                "advancer_id": str(an),
            }
        )

        assert projection["assignment_state"] == "confirmed"
        result = allocate(projection["expense"])

        assert result["allocations"][str(an)] == 65000
        assert result["allocations"][str(binh)] == 70000
        assert sum(result["allocations"].values()) == stored.printed_total_vnd
