"""`source="group"` is a claim about a person, and nobody was checking it.

The fourth instance of the shape `rd-qa-40` (#254) audited, and the one its own
case 11 recorded as still open after `#235`, `#247`, `#260` and `rd-be-26`
closed the other three: proving the CALLER may act here says nothing about the
person the caller NAMES.

`create_outing_invite` proves the actor is a member of the outing's group and
then writes `request.person_id` into `invited_person_id` untouched. The field
`source` carries three values and they do not mean the same thing:

  ``link``    names nobody; the token is the capability.
  ``friend``  deliberately names somebody OUTSIDE the group -- that is what
              inviting a friend to an outing *is*, so a roster check here would
              delete the feature.
  ``group``   asserts the invitee is already in the group. Nothing verified the
              assertion.

So the gate has to be exactly as narrow as the claim. A blanket roster check on
`person_id` would be wrong in a way the audit's other three holes were not, and
that asymmetry is why this case carries a control that must stay green: a
`friend` invite naming a non-member is the ordinary path and must still be
accepted.

Why it mattered while nothing read it: `outing_invites` is not yet redeemed
into a grant by any screen, so this was a sleeping hole rather than a live one
-- the class of bug that is harmless until the day a feature switches on. The
audit wrote it down so it would not be rediscovered from scratch that day. This
file is that day, arriving early on purpose.

The second refusal here is about a person who does not exist at all. A
`person_id` naming nobody used to reach the INSERT and surface as an
`IntegrityError` from `fk_outing_invites_person` -- a 500, which tells the
caller nothing and pages whoever is on call. `invite_context_member` (the
audit's case 9) already answers that with `_require_registered_person`; this
path is its sibling and had simply never been given the same answer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import OutingCreateRequest, OutingInviteCreateRequest
from app.api.service import ApiService
from app.db.models import Context, Membership, MembershipRole, MembershipState, Person

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)
ROLES = frozenset({"member", "advancer", "recipient", "batch_owner", "group_admin"})

# Well-formed and deliberately unknown: a valid UUID is not evidence of a
# person, and a person is not evidence of a member.
NOBODY = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e000001a")


def _person(session, name):
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session, owner_id, name="Nhóm"):
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner_id)
    session.add(context)
    session.flush()
    return context.id


def _member(
    session,
    context_id,
    person_id,
    role=MembershipRole.MEMBER,
    state=MembershipState.ACTIVE,
    left_at=None,
):
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context_id,
            person_id=person_id,
            state=state,
            joined_at=NOW if state is MembershipState.ACTIVE else None,
            left_at=left_at,
            role=role,
        )
    )
    session.flush()


def _actor(person_id, context_id):
    return Actor(id=person_id, roles=ROLES, context_ids=frozenset({context_id}))


@pytest.fixture
def standing(postgres_session):
    """One group with one admin, plus an outing to invite people to."""

    session = postgres_session
    service = ApiService(SqlAlchemyApiRepository(session))
    nam = _person(session, "Nam")
    group = _context(session, nam.id)
    _member(session, group, nam.id, role=MembershipRole.ADMIN)
    outing = service.create_outing(
        group,
        OutingCreateRequest(
            title="Đi chơi",
            starts_on=NOW.date(),
            ends_on=(NOW + timedelta(days=1)).date(),
            headcount=3,
            budget_per_person_vnd=100_000,
        ),
        _actor(nam.id, group),
    )
    return service, session, group, nam, outing


@pytest.mark.postgres
def test_a_group_invite_may_not_name_somebody_from_another_group(standing):
    """The hole itself: `source="group"` about a person in a different group."""

    service, session, group, nam, outing = standing
    outsider = _person(session, "Người nhóm khác")
    elsewhere = _context(session, outsider.id, "Nhóm khác")
    _member(session, elsewhere, outsider.id)

    with pytest.raises(ApiProblem) as refused:
        service.create_outing_invite(
            outing.id,
            OutingInviteCreateRequest(source="group", person_id=outsider.id),
            _actor(nam.id, group),
        )

    assert refused.value.status_code == 422
    assert refused.value.code == "participant_not_in_context"


@pytest.mark.postgres
@pytest.mark.parametrize(
    "state,left_at",
    [
        (MembershipState.INVITED, None),
        # `state` and `left_at` are not independent -- the schema's
        # `ck_memberships_left_state_matches_timestamp` refuses an ACTIVE row
        # carrying a departure date, which is a constraint the fake repository
        # has no way to express.
        (MembershipState.LEFT, NOW),
    ],
    ids=["invited, never accepted", "left the group"],
)
def test_a_group_invite_reads_active_membership_not_merely_a_row(
    standing, state, left_at
):
    """A membership ROW is not membership.

    `source="group"` claims present tense. Somebody who was asked and never
    answered, or who has left, is not in the group now -- and the roster the
    guard reads is the same `state == "active"` set every other money path
    reads, so these two cannot drift apart from the expense gate.
    """

    service, session, group, nam, outing = standing
    lapsed = _person(session, "Người đã rời")
    _member(session, group, lapsed.id, state=state, left_at=left_at)

    with pytest.raises(ApiProblem) as refused:
        service.create_outing_invite(
            outing.id,
            OutingInviteCreateRequest(source="group", person_id=lapsed.id),
            _actor(nam.id, group),
        )

    assert refused.value.status_code == 422
    assert refused.value.code == "participant_not_in_context"


@pytest.mark.postgres
def test_a_friend_invite_to_somebody_outside_the_group_is_still_accepted(standing):
    """The control. This one must stay green, and it is why the gate is narrow.

    Inviting somebody who is NOT in the group is the entire purpose of a friend
    invite. A guard that refused here would pass every "refuses a stranger"
    case above while deleting the feature -- red for the wrong reason reads
    exactly like red for the right one.
    """

    service, session, group, nam, outing = standing
    friend = _person(session, "Bạn ngoài nhóm")

    invite = service.create_outing_invite(
        outing.id,
        OutingInviteCreateRequest(source="friend", person_id=friend.id),
        _actor(nam.id, group),
    )
    session.flush()

    assert invite.invited_person_id == friend.id


@pytest.mark.postgres
def test_a_group_invite_naming_an_actual_member_is_still_accepted(standing):
    """The other half of the control: the ordinary case must survive."""

    service, session, group, nam, outing = standing
    member = _person(session, "Thành viên")
    _member(session, group, member.id)

    invite = service.create_outing_invite(
        outing.id,
        OutingInviteCreateRequest(source="group", person_id=member.id),
        _actor(nam.id, group),
    )
    session.flush()

    assert invite.invited_person_id == member.id


@pytest.mark.postgres
@pytest.mark.parametrize("source", ["group", "friend"])
def test_a_person_id_naming_nobody_is_refused_not_a_500(standing, source):
    """A UUID that names no person must not reach the foreign key.

    Before this, the row hit `fk_outing_invites_person` and came back as an
    `IntegrityError` -- a 500 the caller can do nothing with, on a path where
    the honest answer is "there is no such person". Both sources are checked:
    `friend` is exempt from the roster, not from existing.

    The code is `_require_registered_person`'s own, not a new one minted here.
    `invite_context_member` already answers this question and answering it a
    second way would give the same fact two names -- which is how the two
    copies of a rule in `#132` drifted apart.
    """

    service, _session, group, nam, outing = standing

    with pytest.raises(ApiProblem) as refused:
        service.create_outing_invite(
            outing.id,
            OutingInviteCreateRequest(source=source, person_id=NOBODY),
            _actor(nam.id, group),
        )

    assert refused.value.status_code == 409
    assert refused.value.code == "person_not_registered"
