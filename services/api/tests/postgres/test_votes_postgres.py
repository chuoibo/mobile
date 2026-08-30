"""F17 voting proved against real PostgreSQL over real HTTP.

The domain tally can prove that counts and ties are calculated correctly, and
a fake repository can prove that an endpoint calls a method. Neither can see
the database boundaries this feature depends on:

1. **One person has one row, even after changing their mind.** The second
   ballot is an update protected by ``UNIQUE(vote_id, voter_id)``, not another
   item appended to a Python list. Only the real table can prove that a 200
   replacement still leaves exactly one ballot row.
2. **Context and option ids cannot cross group or vote boundaries.** An outing
   from another context and an option from another vote are both valid UUIDs.
   PostgreSQL foreign keys and scoped queries must still refuse the join rather
   than leak one group's plan into another group's result.
3. **A social choice has no financial side effect.** A complete vote lifecycle
   is measured against every money table, and SQLAlchemy metadata is inspected
   for forbidden foreign keys. A dict-backed fake cannot reveal an accidental
   trigger, write, or schema relationship to the ledger.

Uses ``flush``, never ``commit``: ``postgres_session`` rolls back per test and
the schema is shared with row-counting tests in this directory.
"""

from __future__ import annotations

import uuid
from datetime import date

import anyio
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.base import Base
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Outing,
    Person,
    Vote,
    VoteBallot,
    VoteOption,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

QUESTION = "Tối nay cả nhóm ăn ở đâu?"
OPTIONS = [
    {"label": "Pizza", "place_name": "Pizza 4P's"},
    {"label": "Cơm nhà", "place_name": "Bếp Mẹ Ỉn"},
    {"label": "Gỏi Thái", "place_name": "Som Tum Thai"},
]

MONEY_TABLE_NAMES = (
    "expenses",
    "confirmed_allocations",
    "collection_obligations",
    "collection_batches",
    "payment_reports",
    "receipt_confirmations",
)

VOTE_RESPONSE_FIELDS = {
    "id",
    "context_id",
    "outing_id",
    "created_by_id",
    "question",
    "created_at",
    "closed_at",
    "is_closed",
    "options",
    "total_ballots",
    "leading_option_ids",
    "is_tie",
    "decided_option_id",
    "my_option_id",
}
OPTION_RESPONSE_FIELDS = {
    "id",
    "position",
    "label",
    "place_name",
    "ballot_count",
}
BALLOT_RESPONSE_FIELDS = {
    "vote_id",
    "option_id",
    "voter_id",
    "created_at",
    "updated_at",
    "replaced_previous_ballot",
}


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    # Both roles on purpose. A header is a claim, not a proof: membership is
    # what decides, never the role string a caller typed.
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, owner: Person, name: str) -> Context:
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
    session.add(context)
    session.flush()
    return context


def _join(
    session: Session,
    context: Context,
    person: Person,
    *,
    state: MembershipState = MembershipState.ACTIVE,
    left_at=None,
) -> Membership:
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=person.id,
        state=state,
        role=MembershipRole.MEMBER,
        joined_at=NOW,
        left_at=left_at,
    )
    session.add(membership)
    session.flush()
    return membership


def _group(session: Session) -> tuple[Context, Person, Person]:
    """One group with one member, and one person who is not in it."""
    owner = _person(session, "Minh Anh")
    outsider = _person(session, "Người lạ")
    context = _context(session, owner, "Team Đà Lạt")
    _join(session, context, owner)
    return context, owner, outsider


def _request(app, method: str, path: str, actor: Person, json: dict | None = None):
    async def exchange():
        async with _client(app) as client:
            kwargs = {"headers": _headers(actor.id)}
            if json is not None:
                kwargs["json"] = json
            return await client.request(method, path, **kwargs)

    return anyio.run(exchange)


def _payload(**overrides) -> dict:
    body = {
        "question": QUESTION,
        "options": [dict(option) for option in OPTIONS],
        "outing_id": None,
    }
    body.update(overrides)
    return body


def _make_vote(app, creator: Person, context: Context, **overrides) -> dict:
    response = _request(
        app,
        "POST",
        f"/contexts/{context.id}/votes",
        creator,
        _payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _read_vote(app, reader: Person, vote_id: str):
    return _request(app, "GET", f"/votes/{vote_id}", reader)


def _cast_ballot(app, voter: Person, vote_id: str, option_id: str):
    return _request(
        app,
        "POST",
        f"/votes/{vote_id}/ballots",
        voter,
        {"option_id": option_id},
    )


def _close_vote(app, actor: Person, vote_id: str):
    return _request(app, "POST", f"/votes/{vote_id}/close", actor)


def _outing(
    session: Session,
    context: Context,
    creator: Person,
    *,
    title: str = "Đà Lạt cuối tuần",
) -> Outing:
    outing = Outing(
        id=uuid.uuid4(),
        context_id=context.id,
        created_by_id=creator.id,
        title=title,
        starts_on=date(2030, 10, 17),
        ends_on=date(2030, 10, 19),
        headcount=8,
        budget_per_person_vnd=2_500_000,
    )
    session.add(outing)
    session.flush()
    return outing


def _add_members(session: Session, context: Context, *names: str) -> list[Person]:
    members = []
    for name in names:
        member = _person(session, name)
        _join(session, context, member)
        members.append(member)
    return members


def _assert_problem(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code, response.text
    assert response.json()["code"] == code


def _ballot_row_count(
    session: Session, vote_id: str, voter_id: uuid.UUID | None = None
) -> int:
    statement = (
        select(func.count())
        .select_from(VoteBallot)
        .where(VoteBallot.vote_id == uuid.UUID(vote_id))
    )
    if voter_id is not None:
        statement = statement.where(VoteBallot.voter_id == voter_id)
    count = session.scalar(statement)
    assert count is not None
    return count


def _money_row_counts(session: Session) -> dict[str, int]:
    session.flush()
    counts = {}
    for table_name in MONEY_TABLE_NAMES:
        table = Base.metadata.tables[table_name]
        count = session.scalar(select(func.count()).select_from(table))
        assert count is not None
        counts[table_name] = count
    return counts


def test_a_member_creates_three_options_and_reads_them_back_in_sent_order(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    created = _request(
        app,
        "POST",
        f"/contexts/{context.id}/votes",
        owner,
        _payload(),
    )

    assert created.status_code == 201, created.text
    created_body = created.json()
    assert set(created_body) == VOTE_RESPONSE_FIELDS
    assert created_body["context_id"] == str(context.id)
    assert created_body["created_by_id"] == str(owner.id)
    assert created_body["outing_id"] is None
    assert created_body["question"] == QUESTION
    assert [option["position"] for option in created_body["options"]] == [0, 1, 2]
    assert [option["label"] for option in created_body["options"]] == [
        option["label"] for option in OPTIONS
    ]
    assert [option["place_name"] for option in created_body["options"]] == [
        option["place_name"] for option in OPTIONS
    ]
    assert all(
        set(option) == OPTION_RESPONSE_FIELDS for option in created_body["options"]
    )

    reread = _read_vote(app, owner, created_body["id"])

    assert reread.status_code == 200, reread.text
    reread_body = reread.json()
    assert reread_body["id"] == created_body["id"]
    assert [option["position"] for option in reread_body["options"]] == [0, 1, 2]
    assert [option["id"] for option in reread_body["options"]] == [
        option["id"] for option in created_body["options"]
    ]


def test_a_vote_attached_to_an_outing_reads_back_its_outing_id(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    outing = _outing(postgres_session, context, owner)
    app = _http(postgres_session, monkeypatch)

    created = _make_vote(app, owner, context, outing_id=str(outing.id))
    reread = _read_vote(app, owner, created["id"])

    assert reread.status_code == 200, reread.text
    assert reread.json()["outing_id"] == str(outing.id)


def test_an_outing_from_another_group_is_rejected_without_cross_group_link(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A valid outing UUID must not become a cross-group existence oracle.

    The actor deliberately belongs to both groups, so a generic membership
    check cannot catch the mistake. The vote-to-outing context comparison must.
    """
    context, owner, _ = _group(postgres_session)
    other_context = _context(postgres_session, owner, "Team Sa Pa")
    _join(postgres_session, other_context, owner)
    other_outing = _outing(
        postgres_session,
        other_context,
        owner,
        title="Sa Pa mù sương",
    )
    app = _http(postgres_session, monkeypatch)

    response = _request(
        app,
        "POST",
        f"/contexts/{context.id}/votes",
        owner,
        _payload(outing_id=str(other_outing.id)),
    )

    _assert_problem(response, 422, "outing_not_in_context")


def test_a_missing_outing_is_reported_as_not_found(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    response = _request(
        app,
        "POST",
        f"/contexts/{context.id}/votes",
        owner,
        _payload(outing_id=str(uuid.uuid4())),
    )

    _assert_problem(response, 404, "outing_not_found")


def test_a_missing_vote_is_reported_as_not_found(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The result route has its own stable missing-resource code."""
    _, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    response = _read_vote(app, owner, str(uuid.uuid4()))

    _assert_problem(response, 404, "vote_not_found")


def test_seven_members_produce_the_spec_four_two_one_result(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """F17's exact example must survive HTTP, SQL persistence, and projection."""
    context, owner, _ = _group(postgres_session)
    others = _add_members(
        postgres_session,
        context,
        "Bình",
        "Chi",
        "Dũng",
        "Em",
        "Phúc",
        "Giang",
    )
    voters = [owner, *others]
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    option_ids = [option["id"] for option in vote["options"]]
    choices = [
        option_ids[0],
        option_ids[0],
        option_ids[0],
        option_ids[0],
        option_ids[1],
        option_ids[1],
        option_ids[2],
    ]

    responses = [
        _cast_ballot(app, voter, vote["id"], choice)
        for voter, choice in zip(voters, choices, strict=True)
    ]
    result = _read_vote(app, owner, vote["id"])

    assert [response.status_code for response in responses] == [200] * 7
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["total_ballots"] == 7
    assert [option["ballot_count"] for option in body["options"]] == [4, 2, 1]
    assert body["leading_option_ids"] == [option_ids[0]]
    assert body["is_tie"] is False
    assert body["decided_option_id"] == option_ids[0]


def test_a_two_two_tie_decides_nothing_and_orders_both_leaders_by_position(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The machine must expose the deadlock, never pick the first option."""
    context, owner, _ = _group(postgres_session)
    others = _add_members(postgres_session, context, "Bình", "Chi", "Dũng")
    voters = [owner, *others]
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    option_ids = [option["id"] for option in vote["options"]]

    for voter, option_id in zip(
        voters,
        [option_ids[0], option_ids[1], option_ids[0], option_ids[1]],
        strict=True,
    ):
        response = _cast_ballot(app, voter, vote["id"], option_id)
        assert response.status_code == 200, response.text

    result = _read_vote(app, owner, vote["id"])

    assert result.status_code == 200, result.text
    body = result.json()
    assert [option["ballot_count"] for option in body["options"]] == [2, 2, 0]
    assert body["leading_option_ids"] == option_ids[:2]
    assert body["is_tie"] is True
    assert body["decided_option_id"] is None
    assert body["decided_option_id"] not in option_ids


def test_a_three_way_tie_decides_nothing_and_lists_all_leaders(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    others = _add_members(postgres_session, context, "Bình", "Chi")
    voters = [owner, *others]
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    option_ids = [option["id"] for option in vote["options"]]

    for voter, option_id in zip(voters, option_ids, strict=True):
        response = _cast_ballot(app, voter, vote["id"], option_id)
        assert response.status_code == 200, response.text

    result = _read_vote(app, owner, vote["id"])

    assert result.status_code == 200, result.text
    body = result.json()
    assert [option["ballot_count"] for option in body["options"]] == [1, 1, 1]
    assert body["leading_option_ids"] == option_ids
    assert body["is_tie"] is True
    assert body["decided_option_id"] is None


def test_an_unanswered_vote_has_zero_counts_and_no_leader(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Zero-all means unanswered, not a tie among every listed option."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)

    result = _read_vote(app, owner, vote["id"])

    assert result.status_code == 200, result.text
    body = result.json()
    assert body["total_ballots"] == 0
    assert [option["ballot_count"] for option in body["options"]] == [0, 0, 0]
    assert body["leading_option_ids"] == []
    assert body["is_tie"] is False
    assert body["decided_option_id"] is None


def test_one_person_replaces_their_ballot_without_creating_a_second_row(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Both requests are successful, but the unique row is the actual guarantee.

    A fake that overwrites a dict key would pass the response assertions without
    proving ``UNIQUE(vote_id, voter_id)`` exists in PostgreSQL.
    """
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    first_option_id = vote["options"][0]["id"]
    second_option_id = vote["options"][1]["id"]

    first = _cast_ballot(app, owner, vote["id"], first_option_id)
    second = _cast_ballot(app, owner, vote["id"], second_option_id)
    result = _read_vote(app, owner, vote["id"])

    assert first.status_code == 200, first.text
    assert set(first.json()) == BALLOT_RESPONSE_FIELDS
    assert first.json()["voter_id"] == str(owner.id)
    assert first.json()["replaced_previous_ballot"] is False
    assert second.status_code == 200, second.text
    assert set(second.json()) == BALLOT_RESPONSE_FIELDS
    assert second.json()["option_id"] == second_option_id
    assert second.json()["replaced_previous_ballot"] is True
    assert _ballot_row_count(postgres_session, vote["id"], owner.id) == 1
    assert result.status_code == 200, result.text
    assert result.json()["total_ballots"] == 1
    assert result.json()["my_option_id"] == second_option_id


def test_changing_a_ballot_decrements_the_old_count_and_increments_the_new_count(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Checking only the new count misses an implementation that counts twice."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    first_option_id = vote["options"][0]["id"]
    second_option_id = vote["options"][1]["id"]

    first = _cast_ballot(app, owner, vote["id"], first_option_id)
    before = _read_vote(app, owner, vote["id"])
    changed = _cast_ballot(app, owner, vote["id"], second_option_id)
    after = _read_vote(app, owner, vote["id"])

    assert first.status_code == 200, first.text
    assert before.status_code == 200, before.text
    assert [option["ballot_count"] for option in before.json()["options"]] == [
        1,
        0,
        0,
    ]
    assert changed.status_code == 200, changed.text
    assert after.status_code == 200, after.text
    assert [option["ballot_count"] for option in after.json()["options"]] == [
        0,
        1,
        0,
    ]
    assert after.json()["total_ballots"] == 1


def test_closing_a_vote_blocks_ballots_without_changing_stored_ballot_count(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    [other] = _add_members(postgres_session, context, "Bình")
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    first_option_id = vote["options"][0]["id"]
    second_option_id = vote["options"][1]["id"]
    initial_ballot = _cast_ballot(app, owner, vote["id"], first_option_id)
    assert initial_ballot.status_code == 200, initial_ballot.text

    closed = _close_vote(app, owner, vote["id"])
    before_count = _ballot_row_count(postgres_session, vote["id"])
    refused = _cast_ballot(app, other, vote["id"], second_option_id)
    after_count = _ballot_row_count(postgres_session, vote["id"])

    assert closed.status_code == 200, closed.text
    assert closed.json()["is_closed"] is True
    assert closed.json()["closed_at"] is not None
    _assert_problem(refused, 409, "vote_closed")
    assert before_count == 1
    assert after_count == before_count


def test_closing_an_already_closed_vote_is_rejected(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)

    first = _close_vote(app, owner, vote["id"])
    second = _close_vote(app, owner, vote["id"])

    assert first.status_code == 200, first.text
    _assert_problem(second, 409, "vote_already_closed")


def test_a_member_who_did_not_create_the_vote_cannot_close_it(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Membership grants participation, not ownership of the close action.

    The forged group-admin role in the header must not widen that ownership.
    """
    context, owner, _ = _group(postgres_session)
    [other] = _add_members(postgres_session, context, "Bình")
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)

    refused = _close_vote(app, other, vote["id"])

    assert refused.status_code == 403, refused.text


def test_a_closed_vote_remains_readable_as_a_result(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Closing freezes a result; it does not delete or hide the group record."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    option_id = vote["options"][0]["id"]
    ballot = _cast_ballot(app, owner, vote["id"], option_id)
    assert ballot.status_code == 200, ballot.text
    closed = _close_vote(app, owner, vote["id"])
    assert closed.status_code == 200, closed.text

    reread = _read_vote(app, owner, vote["id"])

    assert reread.status_code == 200, reread.text
    body = reread.json()
    assert body["id"] == vote["id"]
    assert body["is_closed"] is True
    assert body["closed_at"] is not None
    assert body["total_ballots"] == 1
    assert body["decided_option_id"] == option_id


def test_a_stranger_can_neither_create_read_nor_ballot(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, outsider = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    option_id = vote["options"][0]["id"]

    create = _request(
        app,
        "POST",
        f"/contexts/{context.id}/votes",
        outsider,
        _payload(question="Bình chọn của người lạ"),
    )
    read = _read_vote(app, outsider, vote["id"])
    ballot = _cast_ballot(app, outsider, vote["id"], option_id)

    assert create.status_code == 403, create.text
    assert read.status_code == 403, read.text
    assert ballot.status_code == 403, ballot.text
    assert QUESTION not in read.text
    assert QUESTION not in ballot.text


def test_a_former_member_loses_read_and_ballot_access(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A historical membership row is not current authorization.

    This catches a repository check that asks only whether any row exists and
    ignores the linked ``left`` state and ``left_at`` timestamp.
    """
    context, owner, _ = _group(postgres_session)
    former = _person(postgres_session, "Quang Huy")
    membership = _join(postgres_session, context, former)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    membership.state = MembershipState.LEFT
    membership.left_at = NOW
    postgres_session.flush()

    read = _read_vote(app, former, vote["id"])
    ballot = _cast_ballot(app, former, vote["id"], vote["options"][0]["id"])

    assert read.status_code == 403, read.text
    assert ballot.status_code == 403, ballot.text


def test_a_vote_from_another_group_never_appears_in_this_contexts_list(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Membership in both groups prevents permission checks masking a bad WHERE."""
    context, owner, _ = _group(postgres_session)
    other_context = _context(postgres_session, owner, "Team Sa Pa")
    _join(postgres_session, other_context, owner)
    app = _http(postgres_session, monkeypatch)
    this_vote = _make_vote(app, owner, context, question="Ăn tối ở đâu?")
    other_vote = _make_vote(app, owner, other_context, question="Đi Sa Pa ở đâu?")

    listed = _request(app, "GET", f"/contexts/{context.id}/votes", owner)

    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["context_id"] == str(context.id)
    assert [vote["id"] for vote in body["votes"]] == [this_vote["id"]]
    assert other_vote["id"] not in listed.text
    assert other_vote["question"] not in listed.text


def test_an_outsider_cannot_list_a_groups_votes(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The guard on the list route, measured by tripping it.

    Every sibling read route in this API has a test that watches it refuse a
    stranger. This one did not: across the whole suite ``GET /contexts/{id}/
    votes`` had only ever answered 200, so the ``is_group_member`` check in
    ``list_context_votes`` was load-bearing and unheld. Deleting it left the
    suite green while the questions a group is deciding on -- and the place
    names in them -- became readable by anyone who could name the context.
    """
    context, owner, outsider = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context, question="Ăn tối ở đâu?")

    listed = _request(app, "GET", f"/contexts/{context.id}/votes", outsider)

    assert listed.status_code == 403, listed.text
    assert vote["question"] not in listed.text
    assert OPTIONS[0]["place_name"] not in listed.text


def test_someone_who_left_stops_listing_the_groups_votes(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A historical membership row is not current authorization.

    Separate from the outsider case because it fails differently: this one
    survives a guard that asks only whether a membership row exists.
    """
    context, owner, _ = _group(postgres_session)
    former = _person(postgres_session, "Quang Huy")
    membership = _join(postgres_session, context, former)
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context, question="Ăn tối ở đâu?")
    membership.state = MembershipState.LEFT
    membership.left_at = NOW
    postgres_session.flush()

    listed = _request(app, "GET", f"/contexts/{context.id}/votes", former)

    assert listed.status_code == 403, listed.text
    assert vote["question"] not in listed.text


def test_an_option_from_another_vote_is_rejected_as_unknown(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A real option UUID is still invalid outside the vote that owns it."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    first_vote = _make_vote(app, owner, context, question="Ăn ở đâu?")
    other_vote = _make_vote(app, owner, context, question="Uống ở đâu?")
    foreign_option_id = other_vote["options"][0]["id"]

    response = _cast_ballot(app, owner, first_vote["id"], foreign_option_id)

    _assert_problem(response, 422, "unknown_option")
    assert _ballot_row_count(postgres_session, first_vote["id"], owner.id) == 0


def test_each_member_reads_only_their_own_selected_option_id(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    [other] = _add_members(postgres_session, context, "Bình")
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    owner_option_id = vote["options"][0]["id"]
    other_option_id = vote["options"][1]["id"]
    owner_ballot = _cast_ballot(app, owner, vote["id"], owner_option_id)
    other_ballot = _cast_ballot(app, other, vote["id"], other_option_id)
    assert owner_ballot.status_code == 200, owner_ballot.text
    assert other_ballot.status_code == 200, other_ballot.text

    owner_result = _read_vote(app, owner, vote["id"])
    other_result = _read_vote(app, other, vote["id"])

    assert owner_result.status_code == 200, owner_result.text
    assert other_result.status_code == 200, other_result.text
    assert owner_result.json()["my_option_id"] == owner_option_id
    assert owner_result.json()["my_option_id"] != other_option_id
    assert other_result.json()["my_option_id"] == other_option_id
    assert other_result.json()["my_option_id"] != owner_option_id


def test_vote_results_never_expose_the_identity_of_a_voter(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """F17 publishes counts, not a roster of who chose which option.

    The voter is deliberately not the creator, because ``created_by_id`` is a
    legitimate public field and would otherwise make an id absence check
    meaningless.
    """
    context, owner, _ = _group(postgres_session)
    [voter] = _add_members(postgres_session, context, "Bình")
    app = _http(postgres_session, monkeypatch)
    vote = _make_vote(app, owner, context)
    ballot = _cast_ballot(app, voter, vote["id"], vote["options"][0]["id"])
    assert ballot.status_code == 200, ballot.text

    result = _read_vote(app, owner, vote["id"])

    assert result.status_code == 200, result.text
    assert "voter_id" not in result.text
    assert str(voter.id) not in result.text


def test_vote_creation_rejects_invalid_option_counts_and_blank_questions(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    too_many_options = [
        {"label": f"Lựa chọn {position}", "place_name": None} for position in range(21)
    ]
    invalid_payloads = [
        _payload(options=[OPTIONS[0]]),
        _payload(options=[]),
        _payload(question=""),
        _payload(question="   "),
        _payload(options=too_many_options),
    ]

    responses = [
        _request(
            app,
            "POST",
            f"/contexts/{context.id}/votes",
            owner,
            payload,
        )
        for payload in invalid_payloads
    ]

    assert [response.status_code for response in responses] == [422] * 5


def test_a_vote_lifecycle_never_changes_any_money_table(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Spec 8.8 makes changing who owes whom a consensual social change.

    A poll is not that consent. Creating, casting, replacing, and closing a
    vote therefore must not create, update, or delete anybody's expense,
    allocation, collection obligation, batch, payment report, or receipt
    confirmation.
    """
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    before = _money_row_counts(postgres_session)

    vote = _make_vote(app, owner, context)
    first_option_id = vote["options"][0]["id"]
    second_option_id = vote["options"][1]["id"]
    first_ballot = _cast_ballot(app, owner, vote["id"], first_option_id)
    replacement = _cast_ballot(app, owner, vote["id"], second_option_id)
    closed = _close_vote(app, owner, vote["id"])

    assert first_ballot.status_code == 200, first_ballot.text
    assert replacement.status_code == 200, replacement.text
    assert closed.status_code == 200, closed.text
    after = _money_row_counts(postgres_session)
    for table_name in MONEY_TABLE_NAMES:
        assert after[table_name] == before[table_name], table_name


def test_vote_tables_have_no_foreign_key_into_money_tables():
    """Catch a future vote-to-money coupling before it bypasses an ADR.

    A developer may add a relationship without changing any lifecycle query,
    so row counts alone are insufficient. The schema itself must keep all
    three voting tables disconnected from the six financial tables.
    """
    vote_tables = (Vote.__table__, VoteOption.__table__, VoteBallot.__table__)
    assert {table.name for table in vote_tables} == {
        "votes",
        "vote_options",
        "vote_ballots",
    }

    money_table_names = set(MONEY_TABLE_NAMES)
    for table in vote_tables:
        forbidden_targets = {
            foreign_key.column.table.name
            for foreign_key in table.foreign_keys
            if foreign_key.column.table.name in money_table_names
        }
        assert forbidden_targets == set(), table.name
