"""Every write path in `service.py` that takes a person's identity from its caller.

The shape being audited, stated once: **proving the CALLER may act here says
nothing about the people the caller NAMES.** `_require_permission` answers the
first question. Only `_require_participants_are_members` answers the second, and
it is called from exactly two places.

It has gone wrong twice, both times found after the merge:

* #235 -- `confirm_expense` took `proposal.participants` from the body. The
  three money rules in `CLAUDE.md` stayed green the whole time, because they are
  arithmetic and the arithmetic was right; only the people were wrong.
* #247 -- `PUT /bills/{id}/assignments` had the same hole on the route the demo
  actually walks. Two outsider UUIDs came back 200 with full amounts stored.

Both were found by grepping for the word `participants`, which is why this file
does not grep. The inventory below is derived from the schemas: every field in
`app/api/schemas.py` annotated `UUID` or `list[UUID]` that names a person, plus
every `person_id` path parameter, matched to the service method that writes it.

Each case answers the three questions this audit asks:

  1. Are the NAMED people checked -- not the caller?
  2. If not, what is written and who reads it?
  3. Is there a gate that goes red when the check is removed?

Cases marked `xfail(strict=True)` are question 3 answered "no gate exists". They
are strict on purpose: the marker is the second half of the fix, and a repair
that leaves it in place turns XPASS into a red gate that names itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import (
    BankRecipientRequest,
    BillCreateRequest,
    BillItemCreateRequest,
    ExpenseConfirmationRequest,
    ExpenseInput,
    MemberRoleRequest,
    OutingCreateRequest,
    OutingInviteCreateRequest,
)
from app.api.service import ApiService
from app.db.models import Context, Membership, MembershipRole, MembershipState, Person

# Well-formed and deliberately unknown. A valid UUID is not evidence of a
# person, and a person is not evidence of a member -- those are three different
# facts and this file keeps them apart.
STRANGER = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e0000009")

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)
ROLES = frozenset({"member", "advancer", "recipient", "batch_owner", "group_admin"})


# --- fake-repository tier: HTTP <-> domain orchestration ---------------------
#
# Imported here rather than at module scope in `conftest.py` so the names read
# where they are used. `helpers` is the backend suite's own file: this lane
# borrows it instead of minting a second cast of characters whose membership
# facts could drift from the ones every other API test assumes.
from rd_qa_40_api_fixtures.helpers import (  # noqa: E402
    ADVANCER_ID,
    CONTEXT_ID,
    SENDER_ID,
    actor_headers,
    expense_payload,
)


def _propose(client, payload):
    response = client.post("/expenses", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _confirm(client, proposed, *, acknowledge=False):
    return client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=actor_headers(),
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": proposed["allocation"]["allocations"],
            "acknowledge_as_advancer": acknowledge,
        },
    )


# --- 1. ExpenseInput.participants -- GATED at #235 --------------------------


def test_participants_from_the_body_are_checked_against_the_roster(client, repository):
    """The gate #235 installed. Re-asserted here so the table has a control row.

    Without a case that passes, a file of failures cannot tell "no gate exists"
    from "the harness is broken".
    """
    payload = expense_payload(participants=[ADVANCER_ID, STRANGER])
    response = _confirm(client, _propose(client, payload), acknowledge=True)

    assert response.status_code == 422
    assert response.json()["code"] == "participant_not_in_context"
    assert repository.confirmed == {}


# --- 2. ExpenseItemInput.shared_by -- held by the DOMAIN, not by a gate ------


def test_shared_by_is_refused_by_the_allocator_not_by_a_membership_check(client):
    """A blank cell in the table that is NOT a hole -- the layer below holds it.

    `allocator.py` requires `shared_by` to be a subset of `participants`
    (`UNKNOWN_PARTICIPANT`), and `participants` is checked against the roster by
    the case above. So a stranger in `shared_by` is refused twice over and
    `service.py` needs no third check. Recorded explicitly because #129 nearly
    booked an equivalent mutation as a missing gate.
    """
    payload = expense_payload(participants=[SENDER_ID, ADVANCER_ID])
    payload["items"] = [
        {
            "item_id": "i1",
            "label": "Phở",
            "amount_vnd": 82_000,
            "shared_by": [str(STRANGER)],
        }
    ]
    response = client.post("/expenses", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "UNKNOWN_PARTICIPANT"


# --- 3. ExpenseConfirmationRequest.expected_allocations ---------------------


def test_expected_allocations_cannot_smuggle_a_name_past_the_roster(client, repository):
    """The dict KEYS are person ids too, and they are written verbatim.

    `save_expense_confirmation(allocations=request.expected_allocations)` stores
    what the body sent, not what the allocator computed. Nothing here checks
    membership -- but the equality against the recomputed proposal refuses any
    key the allocator did not produce, and the allocator only produces
    participants. Another blank cell that is a real defence, one layer over.
    """
    proposed = _propose(client, expense_payload(participants=[SENDER_ID, ADVANCER_ID]))
    smuggled = dict(proposed["allocation"]["allocations"])
    victim = next(iter(smuggled))
    smuggled[str(STRANGER)] = smuggled.pop(victim)

    response = client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=actor_headers(),
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": smuggled,
            "acknowledge_as_advancer": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "proposal_changed"
    assert repository.confirmed == {}


# --- 4. ExpenseInput.paid_by_id -- NO GATE ----------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "rd-qa-40 hole 1: confirm_expense never checks paid_by_id against the "
        "roster. Remove this marker as the second half of the fix."
    ),
)
def test_paid_by_id_from_the_body_must_be_a_member(client, repository):
    """The third instance of the #235 pattern, and the one that moves money.

    `paid_by_id` becomes `advancer_id` for the allocator, is stored as
    `ExpenseVersion.paid_by_id`, and `create_batch` hands it to
    `obligations_from_allocations` as the RECIPIENT of every obligation the
    expense produces. So naming an outsider here does not merely mislabel a
    receipt: it redirects the whole collection round.

    `acknowledge_as_advancer` looks like it covers this and does not. It is
    `False` by default, and the predicate it proves (`actor.id == paid_by_id`)
    is only evaluated when the flag is set -- so the check is opt-in by the
    caller who would be evading it.
    """
    payload = expense_payload(participants=[SENDER_ID, ADVANCER_ID])
    payload["paid_by_id"] = str(STRANGER)

    response = _confirm(client, _propose(client, payload))

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "participant_not_in_context"
    assert repository.confirmed == {}


# --- 5. ExpenseInput.recorded_by_id -- NO GATE ------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "rd-qa-40 hole 2: confirm_expense never checks recorded_by_id. Remove "
        "this marker as the second half of the fix."
    ),
)
def test_recorded_by_id_from_the_body_must_be_a_member(client, repository):
    """Not money -- a name, printed to somebody outside the group.

    `ExpenseVersion.recorded_by_id` is read back by `guest_envelope` and joined
    against `people` to fill `recorded_by_display_name`. A guest link is a
    bearer capability held by whoever is being asked for money, so this prints
    a chosen person's display name to a reader who is not in the group and may
    not be in the product. The live case in this directory shows it landing on
    the page.
    """
    payload = expense_payload(participants=[SENDER_ID, ADVANCER_ID])
    payload["recorded_by_id"] = str(STRANGER)

    response = _confirm(client, _propose(client, payload), acknowledge=True)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "participant_not_in_context"
    assert repository.confirmed == {}


# --- 6. BillItemCreateRequest.suggested_participant_ids -- NO GATE ----------


def _create_bill(client, suggested):
    return client.post(
        "/bills",
        headers=actor_headers(),
        json={
            "context_id": str(CONTEXT_ID),
            "printed_total_vnd": 82_000,
            "items_total_vnd": 82_000,
            "confidence": 90,
            "needs_review": False,
            "items": [
                {
                    "item_key": "i1",
                    "name": "Phở",
                    "quantity": 1,
                    "unit_price_vnd": 82_000,
                    "line_total_vnd": 82_000,
                    "suggested_participant_ids": [str(value) for value in suggested],
                }
            ],
            "surcharges": [],
            "discounts": [],
        },
    )


def test_create_bill_accepts_a_bill_whose_suggestions_are_all_members(client):
    """The control row for the case below."""
    response = _create_bill(client, [ADVANCER_ID])

    assert response.status_code == 201, response.text
    shares = response.json()["items"][0]["shares"]
    assert [share["participant_id"] for share in shares] == [str(ADVANCER_ID)]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "rd-qa-40 hole 3: POST /bills writes suggested_participant_ids with no "
        "roster check -- the same hole #247 closed on the sibling route. "
        "Remove this marker as the second half of the fix."
    ),
)
def test_suggested_participant_ids_must_be_members(client):
    """#247 gated `PUT /bills/{id}/assignments`. Nothing gated `POST /bills`.

    The stored row is a `bill_item_shares` row with `source="ai_suggested"`,
    which every group member reads back from `GET /bills/{id}`. It also poisons
    the split: `split_bill` builds its participant list from the ACTIVE ROSTER
    and then asks the allocator to honour the stored shares, so a share naming
    a non-member is `UNKNOWN_PARTICIPANT` and the bill cannot be split at all.
    """
    response = _create_bill(client, [ADVANCER_ID, STRANGER])

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "participant_not_in_context"


# --- 7. BillAssignment.participant_ids -- GATED at #247 ---------------------


def test_assignment_participant_ids_are_checked_against_the_roster(client):
    """The gate #247 installed. Control row, same reason as case 1."""
    created = _create_bill(client, [ADVANCER_ID])
    assert created.status_code == 201, created.text

    response = client.put(
        f"/bills/{created.json()['id']}/assignments",
        headers=actor_headers(),
        json={
            "assignments": [
                {"item_key": "i1", "participant_ids": [str(ADVANCER_ID), str(STRANGER)]}
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "participant_not_in_context"


# --- 8. BankRecipientRequest.recipient_id -- GATED --------------------------


def test_bank_recipient_id_from_the_body_must_be_the_caller(client):
    """The one field where the check is identity, not membership, and it holds.

    Spec 9.2 with no admin exception. Worth a row because it is the single
    highest-value field in the inventory: it decides where a whole collection
    round lands.
    """
    response = client.post(
        "/bank-recipients",
        headers=actor_headers(),
        json={
            "recipient_id": str(STRANGER),
            "bank_bin": "970415",
            "account_number": "0000000000TEST",
            "account_name": "NGUOI LA",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


# --- 9. MembershipInviteRequest.person_id -- GATED (registration, not roster)


def test_invite_person_id_must_at_least_be_a_registered_person(client):
    """Membership is the wrong question here -- an invitee is by definition not
    a member yet. `_require_registered_person` asks the question that does
    apply, and refuses before the foreign key would.
    """
    response = client.post(
        f"/contexts/{CONTEXT_ID}/members",
        headers=actor_headers(roles="member,group_admin"),
        json={"person_id": str(STRANGER)},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "person_not_registered"


# --- 10. FriendRequestCreate.addressee_id -- GATED --------------------------


def test_friend_request_addressee_must_exist(client):
    """Also not a membership question: a friend request crosses groups by
    design. Existence is the predicate that applies, and it is checked.
    """
    response = client.post(
        "/friends/requests",
        headers=actor_headers(),
        json={"addressee_id": str(STRANGER)},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "person_not_found"


# --- live tier: the rows the fake repository cannot answer -------------------
#
# The fake holds memberships as a set of UUID pairs and has no `membership_role`
# and no `create_outing` at all, so three rows of the table are unreachable
# there. Two of them turn out to be defended by the layer BELOW the service --
# which is exactly the kind of cell that must not be written up as a hole.


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
            # Stays None for an invitation nobody accepted: the row records
            # that they were asked, not that they arrived.
            joined_at=NOW if state is MembershipState.ACTIVE else None,
            left_at=left_at,
            role=role,
        )
    )
    session.flush()


def _actor(person_id, context_id):
    return Actor(id=person_id, roles=ROLES, context_ids=frozenset({context_id}))


@pytest.mark.postgres
@pytest.mark.parametrize(
    "standing",
    ["no membership row at all", "invited, never accepted", "left the group"],
)
def test_live_member_role_cannot_be_set_on_a_non_member(postgres_session, standing):
    """`set_context_member_role` never checks the path `person_id`. Not a hole.

    `set_membership_role` selects `FOR UPDATE` on `state == ACTIVE AND left_at
    IS NULL`, so a person the group does not contain matches no row and the
    service turns the `None` into 404. The check exists -- it is written as SQL
    rather than as a guard call, and the fake tier cannot show it at all
    because the fake has no `membership_role` method to be asked.

    Three standings, not one, and the reason is measured rather than tidy. With
    only the first case, deleting BOTH filters from that `WHERE` left this file
    green: a person with no row is refused by the `person_id` clause no matter
    what else the query says. That version of the test would have recorded
    "defended one layer down" while proving nothing about which layer. `INVITED`
    is the case that pins `state`; `LEFT` pins `left_at`.

    `INVITED` is also the one that matters in the product: `models.py` says
    being added to a group is something that happens to you, so a role change
    landing on a boundary somebody has not agreed to cross is a permission
    written against a person who never said yes.
    """
    session = postgres_session
    service = ApiService(SqlAlchemyApiRepository(session))
    nam = _person(session, "Nam")
    outsider = _person(session, "Người ngoài")
    group = _context(session, nam.id)
    _member(session, group, nam.id, role=MembershipRole.ADMIN)

    if standing == "invited, never accepted":
        _member(session, group, outsider.id, state=MembershipState.INVITED)
    elif standing == "left the group":
        _member(session, group, outsider.id, state=MembershipState.LEFT, left_at=NOW)

    with pytest.raises(ApiProblem) as refused:
        service.set_context_member_role(
            group,
            outsider.id,
            MemberRoleRequest(role="admin"),
            _actor(nam.id, group),
        )

    assert refused.value.status_code == 404
    assert refused.value.code == "membership_not_found"


@pytest.mark.postgres
@pytest.mark.xfail(
    strict=True,
    reason=(
        "rd-qa-40 hole 1, live tier. Remove this marker as the second half of the fix."
    ),
)
def test_live_paid_by_outsider_must_not_reach_the_ledger(postgres_session):
    """Hole 1 on the real database, where the money actually lands.

    Measured on clean `main` at dbc1e35 before this file existed: the confirm
    returns 201, `create_batch` freezes, and the board comes back as two
    obligations of 40_000 each whose `recipient_id` is the outsider -- summing
    to exactly the 80_000 bill. Money rule 2 holds the whole way through, which
    is why no arithmetic gate can see this. The person who really paid appears
    as a SENDER.

    The refusal asserted below is what should happen instead.
    """
    session = postgres_session
    repository = SqlAlchemyApiRepository(session)
    service = ApiService(repository)

    nam = _person(session, "Nam")
    binh = _person(session, "Bình")
    outsider = _person(session, "Người nhóm khác")
    group = _context(session, nam.id, "Nhóm ăn tối")
    _member(session, group, nam.id, role=MembershipRole.ADMIN)
    _member(session, group, binh.id)
    elsewhere = _context(session, outsider.id, "Nhóm khác")
    _member(session, elsewhere, outsider.id)

    # Their own account, set by themselves -- the one part of this that is
    # entirely legitimate, and what makes the batch freeze instead of stalling
    # on `recipient_setup_incomplete`.
    service.set_bank_recipient(
        BankRecipientRequest(
            recipient_id=outsider.id,
            bank_bin="970415",
            account_number="0000000000TEST",
            account_name="NGUOI NGOAI",
        ),
        _actor(outsider.id, elsewhere),
    )
    session.flush()

    expense_id = repository.create_expense(group).id
    with pytest.raises(ApiProblem) as refused:
        service.confirm_expense(
            expense_id,
            ExpenseConfirmationRequest(
                proposal=ExpenseInput(
                    context_id=group,
                    description="Lẩu nấm",
                    recorded_by_id=nam.id,
                    paid_by_id=outsider.id,
                    verification_scope="totals_only",
                    occurred_at=NOW,
                    participants=sorted(
                        [nam.id, binh.id], key=lambda value: value.bytes
                    ),
                    total_amount_vnd=80_000,
                    items=[],
                    surcharges=[],
                    discounts=[],
                ),
                expected_allocations={nam.id: 40_000, binh.id: 40_000},
                acknowledge_as_advancer=False,
            ),
            _actor(nam.id, group),
        )

    assert refused.value.status_code == 422
    assert refused.value.code == "participant_not_in_context"


@pytest.mark.postgres
@pytest.mark.xfail(
    strict=True,
    reason=(
        "rd-qa-40 hole 2, live tier. Remove this marker as the second half of the fix."
    ),
)
def test_live_recorded_by_outsider_must_not_reach_the_guest_page(postgres_session):
    """Hole 2's privacy half, on the page a non-member actually reads.

    Measured on clean `main` at dbc1e35: `recorded_by_display_name` on every
    published guest envelope came back as the chosen outsider's display name,
    verbatim. A guest link is a bearer capability held by whoever is being
    asked for money -- often somebody outside the product entirely -- so this
    hands a chosen person's name to a reader who was never in the group.
    """
    session = postgres_session
    repository = SqlAlchemyApiRepository(session)
    service = ApiService(repository)

    nam = _person(session, "Nam")
    binh = _person(session, "Bình")
    elsewhere_name = "TEN CUA NGUOI NHOM KHAC"
    outsider = _person(session, elsewhere_name)
    group = _context(session, nam.id, "Nhóm ăn tối")
    _member(session, group, nam.id, role=MembershipRole.ADMIN)
    _member(session, group, binh.id)
    other = _context(session, outsider.id, "Nhóm khác")
    _member(session, other, outsider.id)

    service.set_bank_recipient(
        BankRecipientRequest(
            recipient_id=nam.id,
            bank_bin="970415",
            account_number="0000000000TEST",
            account_name="NAM",
        ),
        _actor(nam.id, group),
    )
    session.flush()

    expense_id = repository.create_expense(group).id
    with pytest.raises(ApiProblem) as refused:
        service.confirm_expense(
            expense_id,
            ExpenseConfirmationRequest(
                proposal=ExpenseInput(
                    context_id=group,
                    description="Lẩu nấm",
                    recorded_by_id=outsider.id,
                    paid_by_id=nam.id,
                    verification_scope="totals_only",
                    occurred_at=NOW,
                    participants=sorted(
                        [nam.id, binh.id], key=lambda value: value.bytes
                    ),
                    total_amount_vnd=80_000,
                    items=[],
                    surcharges=[],
                    discounts=[],
                ),
                expected_allocations={nam.id: 40_000, binh.id: 40_000},
                acknowledge_as_advancer=True,
            ),
            _actor(nam.id, group),
        )

    assert refused.value.status_code == 422
    assert refused.value.code == "participant_not_in_context"


@pytest.mark.postgres
@pytest.mark.xfail(
    strict=True,
    reason=(
        "rd-qa-40 hole 3, live tier. Remove this marker as the second half of the fix."
    ),
)
def test_live_bill_suggestion_of_a_non_member_is_refused(postgres_session):
    """Hole 3 on the real database, and why it kills the demo path.

    Measured on clean `main` at dbc1e35: `POST /bills` stored the outsider as a
    `bill_item_shares` row with `source="ai_suggested"`, and then
    `POST /bills/{id}/split` came back 422 `UNKNOWN_PARTICIPANT` -- because
    `split_bill` builds its participant list from the ACTIVE ROSTER and then
    asks the allocator to honour the stored shares.

    Confirming assignments does not clear it: `confirm_bill_assignments`
    deletes existing shares only for the item_keys the request names, so an
    item nobody re-assigns keeps its stranger share. Re-measured on the same
    tree -- after confirming the other item, split was still 422. The screen
    has no reason to re-touch an item that already looks assigned, so from the
    group's side the bill is simply stuck: scan -> assign -> split, the exact
    path the demo walks, dead with no way out inside the product.
    """
    session = postgres_session
    service = ApiService(SqlAlchemyApiRepository(session))
    nam = _person(session, "Nam")
    binh = _person(session, "Bình")
    outsider = _person(session, "Người ngoài nhóm")
    group = _context(session, nam.id)
    _member(session, group, nam.id, role=MembershipRole.ADMIN)
    _member(session, group, binh.id)
    actor = _actor(nam.id, group)

    with pytest.raises(ApiProblem) as refused:
        service.create_bill(
            BillCreateRequest(
                context_id=group,
                printed_total_vnd=100_000,
                items_total_vnd=100_000,
                confidence=90,
                needs_review=False,
                items=[
                    BillItemCreateRequest(
                        item_key="i1",
                        name="Phở",
                        quantity=1,
                        unit_price_vnd=50_000,
                        line_total_vnd=50_000,
                        suggested_participant_ids=[outsider.id],
                    ),
                    BillItemCreateRequest(
                        item_key="i2",
                        name="Bún",
                        quantity=1,
                        unit_price_vnd=50_000,
                        line_total_vnd=50_000,
                        suggested_participant_ids=[nam.id],
                    ),
                ],
                surcharges=[],
                discounts=[],
            ),
            actor,
        )

    assert refused.value.status_code == 422
    assert refused.value.code == "participant_not_in_context"


@pytest.mark.postgres
def test_live_outing_invite_takes_a_person_id_the_group_does_not_contain(
    postgres_session,
):
    """`source` claims provenance and nothing verifies the claim.

    `source="group"` asserts the invitee is in the group. The service reads the
    field, writes `invited_person_id`, and never asks. Nothing reads a named
    invite into a grant *yet*, so this is a sleeping hole rather than a live
    one -- recorded so it is not discovered again the day a screen starts
    reading `outing_invites`.

    The neighbouring case, a UUID naming nobody, is held by
    `fk_outing_invites_person` -- but as an IntegrityError, so it surfaces as a
    500 rather than a refusal the caller can act on.
    """
    session = postgres_session
    service = ApiService(SqlAlchemyApiRepository(session))
    nam = _person(session, "Nam")
    outsider = _person(session, "Người nhóm khác")
    group = _context(session, nam.id)
    _member(session, group, nam.id, role=MembershipRole.ADMIN)
    elsewhere = _context(session, outsider.id, "Nhóm khác")
    _member(session, elsewhere, outsider.id)

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
    invite = service.create_outing_invite(
        outing.id,
        OutingInviteCreateRequest(source="group", person_id=outsider.id),
        _actor(nam.id, group),
    )
    session.flush()

    assert invite.invited_person_id == outsider.id
