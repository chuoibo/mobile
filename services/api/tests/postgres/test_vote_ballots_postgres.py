"""#133 · `uq_vote_ballots_one_per_person` is the only thing holding one-person-one-ballot.

`VoteBallot`'s docstring already says it out loud:

    The unique constraint is the authority for one-person-one-ballot even
    under concurrent requests; tallying never depends on an in-memory check.

Until this file existed, nothing checked that claim. Loosening the constraint to
`("vote_id", "voter_id", "option_id")` -- still a perfectly legal schema, and
exactly the shape somebody would reach for to let a person "vote for several
options" -- left the whole suite green.

What the constraint is actually load-bearing for:

`SqlAlchemyApiRepository.upsert_ballot` is a read-then-write. It does lock the
`votes` row with `SELECT ... FOR UPDATE` before touching ballots, so today's two
concurrent voters queue up rather than racing -- `test_one_person_racing_...`
below measures that rather than assuming it. But the lock is an implementation
detail of one method; the constraint is the invariant. Anyone who drops the
`FOR UPDATE` (it serialises *every* voter on a vote, so it is a tempting
throughput fix) is left with only the constraint between them and two rows.

And a second row is not a cosmetic defect. `app.domain.vote.tally` raises
`DUPLICATE_BALLOT` the moment it sees one voter twice, and every read of the
result goes through it -- so one leaked row does not corrupt a single response,
it makes that vote permanently unreadable for the whole group.

These cases are live because the property lives in PostgreSQL. The fake
repository in `tests/api/conftest.py` cannot refuse a duplicate INSERT; asking
it to would be asking a dict to be a database.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
    Vote,
    VoteBallot,
    VoteOption,
)
from app.domain.vote import VoteError, tally

NOW = datetime(2030, 8, 30, 12, tzinfo=UTC)

# A thread that blocks on a row lock forever must fail the run, not hang it.
JOIN_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class VoteFixture:
    """Ids only: the threads below each open their own Session, and ORM objects
    do not cross session boundaries."""

    context_id: uuid.UUID
    vote_id: uuid.UUID
    first_option_id: uuid.UUID
    second_option_id: uuid.UUID
    voter_id: uuid.UUID
    other_voter_id: uuid.UUID


@pytest.fixture
def open_vote(postgres_engine: Engine) -> Iterator[VoteFixture]:
    """One open vote with two options and two members, committed for real.

    These cases commit, so teardown deletes exactly the rows they created.
    `tests/postgres` share ONE schema and a stray row makes a row-counting case
    in another file red -- so no `delete(Table)` without a WHERE here.
    """
    fixture = VoteFixture(
        context_id=uuid.uuid4(),
        vote_id=uuid.uuid4(),
        first_option_id=uuid.uuid4(),
        second_option_id=uuid.uuid4(),
        voter_id=uuid.uuid4(),
        other_voter_id=uuid.uuid4(),
    )
    people_ids = (fixture.voter_id, fixture.other_voter_id)

    with Session(postgres_engine) as setup:
        setup.add_all(
            [
                Person(id=fixture.voter_id, display_name="Người bỏ phiếu"),
                Person(id=fixture.other_voter_id, display_name="Người thứ hai"),
            ]
        )
        setup.flush()
        setup.add(
            Context(
                id=fixture.context_id,
                display_name="Nhóm bình chọn",
                created_by_id=fixture.voter_id,
            )
        )
        setup.flush()
        setup.add_all(
            [
                Membership(
                    id=uuid.uuid4(),
                    context_id=fixture.context_id,
                    person_id=person_id,
                    state=MembershipState.ACTIVE,
                    role=MembershipRole.MEMBER,
                    joined_at=NOW,
                )
                for person_id in people_ids
            ]
        )
        setup.add(
            Vote(
                id=fixture.vote_id,
                context_id=fixture.context_id,
                created_by_id=fixture.voter_id,
                question="Ăn ở đâu?",
                created_at=NOW,
            )
        )
        setup.flush()
        setup.add_all(
            [
                VoteOption(
                    id=fixture.first_option_id,
                    vote_id=fixture.vote_id,
                    position=0,
                    label="Quán A",
                ),
                VoteOption(
                    id=fixture.second_option_id,
                    vote_id=fixture.vote_id,
                    position=1,
                    label="Quán B",
                ),
            ]
        )
        setup.commit()

    try:
        yield fixture
    finally:
        with Session(postgres_engine) as cleanup:
            # Fail fast instead of hanging. These cases deliberately leave
            # uncommitted writes around, and an uncommitted writer still holds
            # row locks until it rolls back -- so a case that forgets to close
            # its own session would block this DELETE forever and the run would
            # die on the outer `timeout`, 900 seconds later, saying nothing
            # about which case did it. Ten seconds and a named error instead.
            cleanup.execute(text("SET LOCAL lock_timeout = '10s'"))
            cleanup.execute(
                delete(VoteBallot).where(VoteBallot.vote_id == fixture.vote_id)
            )
            cleanup.execute(
                delete(VoteOption).where(VoteOption.vote_id == fixture.vote_id)
            )
            cleanup.execute(delete(Vote).where(Vote.id == fixture.vote_id))
            cleanup.execute(
                delete(Membership).where(Membership.context_id == fixture.context_id)
            )
            cleanup.execute(delete(Context).where(Context.id == fixture.context_id))
            cleanup.execute(delete(Person).where(Person.id.in_(people_ids)))
            cleanup.commit()


def _ballot_count(session: Session, fixture: VoteFixture) -> int:
    """Count only this vote's ballots -- never the whole table, which belongs to
    every other file sharing this schema too."""
    return session.scalar(
        select(func.count())
        .select_from(VoteBallot)
        .where(VoteBallot.vote_id == fixture.vote_id)
    )


def _read_the_result(session: Session, fixture: VoteFixture) -> dict:
    """The read path a group member hits, through the same pure tally the API
    uses -- so a leaked duplicate surfaces here exactly as it would in a
    response."""
    options = session.scalars(
        select(VoteOption).where(VoteOption.vote_id == fixture.vote_id)
    ).all()
    ballots = session.scalars(
        select(VoteBallot)
        .where(VoteBallot.vote_id == fixture.vote_id)
        .order_by(VoteBallot.created_at, VoteBallot.id)
    ).all()
    return tally(
        [
            {"id": option.id, "position": option.position, "label": option.label}
            for option in options
        ],
        [
            {"voter_id": ballot.voter_id, "option_id": ballot.option_id}
            for ballot in ballots
        ],
    )


def test_database_refuses_a_second_ballot_from_the_same_voter(
    postgres_engine: Engine, open_vote: VoteFixture
) -> None:
    """The one case that goes red when the constraint stops covering
    (vote_id, voter_id).

    It inserts straight through the ORM rather than through `upsert_ballot`,
    on purpose: `upsert_ballot` reads first and would UPDATE the existing row,
    so routing through it would prove the read worked, not that the database
    refuses. The row is written the way a lost race would write it.

    The session is opened here rather than taken from the `postgres_session`
    fixture so it closes -- and drops its row locks -- BEFORE `open_vote` tears
    down. Fixtures finalise in reverse setup order, so a session held by an
    outer fixture is still holding locks while the cleanup DELETE runs, and the
    two wait on each other.
    """
    with Session(postgres_engine) as session:
        session.add(
            VoteBallot(
                id=uuid.uuid4(),
                vote_id=open_vote.vote_id,
                option_id=open_vote.first_option_id,
                voter_id=open_vote.voter_id,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()

        session.add(
            VoteBallot(
                id=uuid.uuid4(),
                vote_id=open_vote.vote_id,
                # A different option: the duplicate this rejects is "one person,
                # two ballots", not "the identical row twice". A constraint
                # widened to (vote_id, voter_id, option_id) accepts this and
                # stays legal SQL.
                option_id=open_vote.second_option_id,
                voter_id=open_vote.voter_id,
                created_at=NOW,
                updated_at=NOW,
            )
        )

        with pytest.raises(IntegrityError) as refused:
            session.flush()

        assert "uq_vote_ballots_one_per_person" in str(refused.value)
        session.rollback()


def test_a_leaked_duplicate_makes_the_result_permanently_unreadable(
    postgres_engine: Engine, open_vote: VoteFixture
) -> None:
    """Why the constraint is worth a live case: this is the damage it prevents.

    The two rows are forced in with the constraint dropped for this transaction
    only, so the case can describe the consequence without needing a way to
    actually beat the constraint.

    Nothing here is committed, and the DROP is inside the transaction, so the
    constraint comes back on rollback -- including if this process is killed,
    since PostgreSQL rolls back on disconnect. That matters more than usual:
    `tests/postgres` share ONE schema, so a leaked DROP would silently disarm
    this property for every other file in the run.
    """
    with Session(postgres_engine) as session:
        session.execute(
            # DEFERRABLE would be cleaner, but the constraint is not declared
            # deferrable. DDL is transactional in PostgreSQL, so dropping it
            # here rolls back with everything else.
            text(
                "ALTER TABLE vote_ballots "
                "DROP CONSTRAINT uq_vote_ballots_one_per_person"
            )
        )
        session.add_all(
            [
                VoteBallot(
                    id=uuid.uuid4(),
                    vote_id=open_vote.vote_id,
                    option_id=option_id,
                    voter_id=open_vote.voter_id,
                    created_at=NOW,
                    updated_at=NOW,
                )
                for option_id in (open_vote.first_option_id, open_vote.second_option_id)
            ]
        )
        session.flush()

        with pytest.raises(VoteError) as blown_up:
            _read_the_result(session, open_vote)

        assert blown_up.value.code == "DUPLICATE_BALLOT"
        session.rollback()

    # The DROP must not have escaped this case's transaction.
    #
    # Scoped to current_schema(): `pg_constraint` spans the whole database, and
    # this machine holds leftover `repository_it_*` schemas from earlier runs,
    # each with a constraint of the same name. Counting across all of them
    # answered 2 and said nothing about the schema under test.
    with Session(postgres_engine) as check:
        surviving = check.scalar(
            text(
                "SELECT count(*) FROM pg_constraint c "
                "JOIN pg_namespace n ON n.oid = c.connamespace "
                "WHERE c.conname = 'uq_vote_ballots_one_per_person' "
                "AND n.nspname = current_schema()"
            )
        )
    assert surviving == 1


def _cast_a_ballot(
    engine: Engine,
    fixture: VoteFixture,
    *,
    voter_id: uuid.UUID,
    option_id: uuid.UUID,
    ready: threading.Barrier,
    failures: list[BaseException],
) -> None:
    """One request's worth of work: its own session, its own transaction, its
    own commit -- the shape two separate HTTP requests actually have."""
    try:
        ready.wait(timeout=JOIN_TIMEOUT_SECONDS)
        with Session(engine) as session:
            repository = SqlAlchemyApiRepository(session)
            repository.upsert_ballot(
                vote_id=fixture.vote_id,
                option_id=option_id,
                voter_id=voter_id,
                now=NOW,
            )
            session.commit()
    except BaseException as error:  # noqa: BLE001 - reported by the main thread
        failures.append(error)


def _run_together(threads: list[threading.Thread]) -> None:
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)
    still_running = [thread.name for thread in threads if thread.is_alive()]
    assert not still_running, (
        f"thread(s) {still_running} never finished within {JOIN_TIMEOUT_SECONDS}s "
        "-- a row lock is held across requests"
    )


def test_two_people_voting_at_once_both_land_and_the_result_reads(
    postgres_engine: Engine, open_vote: VoteFixture
) -> None:
    """The legitimate race. `upsert_ballot` takes `FOR UPDATE` on the shared
    `votes` row, so two different voters serialise on it -- this proves that
    queue lets both through and does not deadlock or drop one.
    """
    ready = threading.Barrier(2)
    failures: list[BaseException] = []
    threads = [
        threading.Thread(
            target=_cast_a_ballot,
            args=(postgres_engine, open_vote),
            kwargs={
                "voter_id": voter_id,
                "option_id": option_id,
                "ready": ready,
                "failures": failures,
            },
            name=f"voter-{index}",
        )
        for index, (voter_id, option_id) in enumerate(
            [
                (open_vote.voter_id, open_vote.first_option_id),
                (open_vote.other_voter_id, open_vote.second_option_id),
            ]
        )
    ]

    _run_together(threads)

    assert failures == []
    with Session(postgres_engine) as reader:
        assert _ballot_count(reader, open_vote) == 2
        result = _read_the_result(reader, open_vote)
    assert result["counts"][open_vote.first_option_id] == 1
    assert result["counts"][open_vote.second_option_id] == 1


def test_one_person_racing_themselves_still_leaves_exactly_one_ballot(
    postgres_engine: Engine, open_vote: VoteFixture
) -> None:
    """One person, two simultaneous requests -- a double-tap on a slow phone.

    The assertion is the invariant, not the mechanism: whether the second
    request queues behind the `FOR UPDATE` and updates, or races through and is
    refused by the constraint, the group must end up with one ballot and a
    readable result. That keeps the case honest if the locking is ever changed.
    """
    ready = threading.Barrier(2)
    failures: list[BaseException] = []
    threads = [
        threading.Thread(
            target=_cast_a_ballot,
            args=(postgres_engine, open_vote),
            kwargs={
                "voter_id": open_vote.voter_id,
                "option_id": option_id,
                "ready": ready,
                "failures": failures,
            },
            name=f"double-tap-{index}",
        )
        for index, option_id in enumerate(
            [open_vote.first_option_id, open_vote.second_option_id]
        )
    ]

    _run_together(threads)

    unexpected = [error for error in failures if not isinstance(error, IntegrityError)]
    assert unexpected == [], f"unexpected failures: {unexpected}"

    with Session(postgres_engine) as reader:
        assert _ballot_count(reader, open_vote) == 1
        # Must not raise DUPLICATE_BALLOT: the vote is still readable.
        result = _read_the_result(reader, open_vote)
    assert sum(result["counts"].values()) == 1
