"""rd-be-11: the service refuses an expired link on its own authority.

`bug-151046` (#132) put the same predicate in two places -- `ApiService` reads
the invite unlocked and checks it, then `SqlAlchemyApiRepository` re-checks it
while holding `FOR UPDATE`. That redundancy is deliberate (the unlocked read is
a TOCTOU window), but it makes the enforcement invisible to mutation testing:
neutering either copy alone leaves the end-to-end suite fully green, because the
surviving copy still refuses the link.

A gate nobody can see erode is a gate that will erode. This file pins the
*service* copy by handing it a repository that would happily redeem an expired
link, so the only thing standing between the token and a membership is the check
on the service side.

The companion pin for the repository copy is
``tests/postgres/test_outing_invite_lifetime_postgres.py::
test_the_repository_refuses_an_expired_link_even_when_nothing_checked_first``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta

import pytest

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import (
    MembershipRecord,
    OutingInviteRecord,
    OutingRecord,
)
from app.api.service import OUTING_INVITE_TTL, ApiService, token_digest

from tests.api.conftest import SeedCatalogueReads

NOW = datetime(2026, 8, 29, 9, 0, tzinfo=UTC)
TOKEN = "link-da-phat-tu-doi-nao"


@dataclass
class PermissiveInviteRepository(SeedCatalogueReads):
    """Every method the redeem path touches, and no refusals anywhere.

    Deliberately *not* a subclass of the shared ``FakeRepository``: that fake
    carries a third copy of the expiry predicate, so inheriting from it would
    mean the test could pass on the fake's check rather than the service's --
    exactly the confusion this file exists to remove.
    """

    invite: OutingInviteRecord
    outing: OutingRecord
    accept_calls: list[uuid.UUID] = field(default_factory=list)
    membership_calls: list[uuid.UUID] = field(default_factory=list)

    def get_outing_invite_by_digest(self, digest):
        return self.invite if digest == token_digest(TOKEN) else None

    def get_outing(self, outing_id):
        return self.outing if outing_id == self.outing.id else None

    def accept_outing_invite(self, *, invite_id, accepted_by_id, now):
        # No expiry check on purpose: the repository copy is pinned by its own
        # live case. If control ever reaches here, the service let it through.
        self.accept_calls.append(invite_id)
        return replace(self.invite, accepted_at=now, accepted_by_id=accepted_by_id)

    def ensure_invited_membership(
        self, *, context_id, person_id, invited_by_id, origin, now
    ):
        self.membership_calls.append(person_id)
        return MembershipRecord(
            id=uuid.uuid4(),
            context_id=context_id,
            person_id=person_id,
            display_name="Hà",
            state="invited",
            role="member",
            origin=origin,
            invited_by_id=invited_by_id,
            joined_at=None,
            left_at=None,
            created_at=now,
        )


def _scene(*, expires_at: datetime) -> PermissiveInviteRepository:
    outing_id, context_id, owner_id = (uuid.uuid4() for _ in range(3))
    return PermissiveInviteRepository(
        invite=OutingInviteRecord(
            id=uuid.uuid4(),
            outing_id=outing_id,
            source="link",
            invited_person_id=None,
            invited_by_id=owner_id,
            accepted_at=None,
            accepted_by_id=None,
            created_at=expires_at - OUTING_INVITE_TTL,
            expires_at=expires_at,
            revoked_at=None,
        ),
        outing=OutingRecord(
            id=outing_id,
            context_id=context_id,
            created_by_id=owner_id,
            title="Đà Lạt 2 ngày",
            starts_on=date(2026, 9, 5),
            ends_on=date(2026, 9, 6),
            headcount=4,
            budget_per_person_vnd=2_500_000,
            created_at=expires_at - OUTING_INVITE_TTL,
            stops=(),
        ),
    )


def _holder() -> Actor:
    return Actor(id=uuid.uuid4(), roles=frozenset({"member"}), context_ids=frozenset())


def test_the_service_refuses_an_expired_link_without_asking_the_repository(
    monkeypatch: pytest.MonkeyPatch,
):
    """Neuter the repository's guard and the service must still say no.

    Asserting the 404 alone would not distinguish "the service refused" from
    "something downstream refused". The load-bearing assertion is that the
    repository was never asked: a refusal that still reached the write path
    would be a refusal that depends on somebody else remembering the rule.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    repository = _scene(expires_at=NOW - timedelta(seconds=1))
    service = ApiService(repository)

    with pytest.raises(ApiProblem) as raised:
        service.accept_outing_invite(TOKEN, _holder())

    assert raised.value.status_code == 404, raised.value.status_code
    assert raised.value.code == "invite_not_found", raised.value.code
    assert repository.accept_calls == [], (
        "Service đã gọi xuống repository với link quá hạn -- vế kiểm ở service "
        "không chặn, nó chỉ đang dựa vào tầng dưới."
    )
    assert repository.membership_calls == [], (
        "Link quá hạn bị từ chối nhưng vẫn tạo membership"
    )


def test_the_service_still_redeems_a_link_inside_its_window(
    monkeypatch: pytest.MonkeyPatch,
):
    """The other half of the gate: refusing everything must not read as green.

    Without this, changing the comparison to always-expired would leave the
    file above passing and prove nothing about which links survive.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    repository = _scene(expires_at=NOW + timedelta(seconds=1))
    service = ApiService(repository)
    holder = _holder()

    response = service.accept_outing_invite(TOKEN, holder)

    assert repository.accept_calls == [repository.invite.id]
    assert response.membership_state == "invited", (
        "Link hợp lệ phải dừng ở INVITED, không tự lên ACTIVE (bug-141903)"
    )
    assert repository.membership_calls == [holder.id]
