"""F31/F33/F36 against real PostgreSQL over real HTTP -- who may read what.

Three features, one gate, one file, because they share the argument. Each of
them turns a group's private rows into something *smaller* -- a score, a count,
a shelf of covers -- and the temptation each of them creates is to treat the
smaller thing as less private than the rows it came from. It is not. "This
group scores BBQ 0.91" is their eating habits; "18 ảnh, 3 triệu" is their trip
and their money.

## Why this cannot be a fake-repository test

Every claim below is a WHERE clause. `is_member` reads a membership row and its
ACTIVE state; `list_outing_memories` joins on the outing's own `context_id`. A
dict-backed fake round-trips a missing predicate exactly as cleanly as a
present one, so cross-group leakage is invisible to a fake by construction --
the argument `test_group_checkins_postgres.py` and `test_social_map_postgres.py`
both make, for the same reason.

## Why every refusal here is paired with a positive control

A test that only proves an outsider is refused stays green on an endpoint
broken for *everybody*: a 500, a typo in the path, a route never registered all
satisfy "the outsider did not get the data". So each refusal below is paired
with a member making the same request and getting it. The pair is the evidence;
either half alone is not.

Uses `flush`, never `commit`: `postgres_session` rolls back per test, and this
directory's schema is shared with row-counting tests that go red if rows from
here survive.
"""

from __future__ import annotations

import itertools
import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.deps import get_contextual_suggester, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Memory,
    MemoryKind,
    MemoryReaction,
    Message,
    MessageKind,
    Outing,
    Person,
)
from app.places.catalog import PLACES

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

GRILL = PLACES[0]
CAFE = next(place for place in PLACES if place["category"] == "cafe")
PLAY = next(place for place in PLACES if place["category"] == "vui-choi")

TRIP_START = NOW.date()
TRIP_END = TRIP_START + timedelta(days=2)


_tick = itertools.count(1)


def _moment():
    """A distinct, increasing timestamp per row.

    Every fixture row used to be written at exactly `NOW`, which made "newest
    first" a coin flip on the random uuid tiebreak -- an ordering assertion
    that passed or failed depending on which uuid4 came out larger. A frozen
    clock does not just make time-dependent tests weak; it makes ordering
    tests meaningless while they still look like they are checking order.
    """

    return NOW + timedelta(seconds=next(_tick))


def _http(session: Session, monkeypatch: pytest.MonkeyPatch, *, suggester=None):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    if suggester is not None:
        app.dependency_overrides[get_contextual_suggester] = lambda: suggester
    return app


class _Client:
    """Sync façade over the ASGI transport, one `anyio.run` per request.

    Same shape `test_social_map_postgres.py` uses and for the same reason:
    `ASGITransport` is async-only, and these tests are synchronous because the
    session fixture they share is.
    """

    def __init__(self, app):
        self._app = app

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def get(self, path: str, headers: dict[str, str] | None = None):
        async def go():
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.get(path, headers=headers)

        return anyio.run(go)


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    # Both roles on purpose. A header is a claim, not a proof: membership
    # decides, not the role string a client chose to send.
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _join(
    session: Session,
    context: Context,
    person: Person,
    state: MembershipState = MembershipState.ACTIVE,
) -> Membership:
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=person.id,
        state=state,
        role=MembershipRole.MEMBER,
        joined_at=NOW,
        # `ck_memberships_left_state_matches_timestamp` refuses a LEFT row with
        # no departure time; "left" and "left at an unknown moment" are not the
        # same fact.
        left_at=NOW if state is MembershipState.LEFT else None,
    )
    session.add(membership)
    session.flush()
    return membership


def _group(session: Session, name: str) -> tuple[Context, Person]:
    owner = _person(session, f"Chủ {name}")
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
    session.add(context)
    session.flush()
    _join(session, context, owner)
    return context, owner


def _checkin(session: Session, context: Context, author: Person, place: dict) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MemoryKind.CHECKIN,
        place_id=place["id"],
        place_name=place["name"],
        lat=place["lat"],
        lng=place["lng"],
        created_at=_moment(),
    )
    session.add(memory)
    session.flush()
    return memory


def _photo(session: Session, context: Context, author: Person, *, at=None) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MemoryKind.PHOTO,
        image_url=f"/contexts/{context.id}/photos/{uuid.uuid4()}",
        caption=None,
        created_at=at or _moment(),
    )
    session.add(memory)
    session.flush()
    return memory


def _heart(session: Session, memory: Memory, person: Person) -> None:
    session.add(
        MemoryReaction(
            id=uuid.uuid4(),
            memory_id=memory.id,
            person_id=person.id,
            created_at=NOW,
        )
    )
    session.flush()


def _say(session: Session, context: Context, author: Person, body: str) -> Message:
    message = Message(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MessageKind.TEXT,
        body=body,
        created_at=_moment(),
    )
    session.add(message)
    session.flush()
    return message


def _outing(session: Session, context: Context, owner: Person, title: str) -> Outing:
    outing = Outing(
        id=uuid.uuid4(),
        context_id=context.id,
        created_by_id=owner.id,
        title=title,
        starts_on=TRIP_START,
        ends_on=TRIP_END,
        headcount=4,
        budget_per_person_vnd=500_000,
        created_at=NOW,
    )
    session.add(outing)
    session.flush()
    return outing


# --------------------------------------------------------------------------
# F31 -- the implicit profile
# --------------------------------------------------------------------------


class TestPreferenceProfilePermission:
    def test_a_member_reads_the_profile_of_their_own_group(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The positive control. Without it every refusal below is satisfied by
        a route that is broken for everybody."""

        context, owner = _group(postgres_session, "Team Đà Lạt")
        _checkin(postgres_session, context, owner, GRILL)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            response = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(owner.id),
            )

        assert response.status_code == 200
        body = response.json()
        assert body["has_profile"] is True
        assert body["checkin_count"] == 1

    def test_a_stranger_is_refused(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        _checkin(postgres_session, context, owner, GRILL)
        stranger = _person(postgres_session, "Người lạ")

        with _Client(_http(postgres_session, monkeypatch)) as client:
            response = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(stranger.id),
            )

        assert response.status_code == 403
        assert "BBQ" not in response.text

    @pytest.mark.parametrize(
        "state", [MembershipState.LEFT, MembershipState.INVITED]
    )
    def test_a_membership_row_that_is_not_active_is_not_membership(
        self,
        postgres_session: Session,
        monkeypatch: pytest.MonkeyPatch,
        state: MembershipState,
    ):
        """Someone who left, and someone merely invited, both have a membership
        row. Neither has an ACTIVE one, and the profile is a group's habits."""

        context, owner = _group(postgres_session, "Team Đà Lạt")
        _checkin(postgres_session, context, owner, GRILL)
        other = _person(postgres_session, "Người cũ")
        _join(postgres_session, context, other, state)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            response = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(other.id),
            )

        assert response.status_code == 403


class TestPreferenceProfileIsDerived:
    def test_a_new_checkin_moves_the_profile_with_no_refresh_of_any_kind(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Invariant 3 for F31, measured rather than asserted in a docstring.

        This is the test that a stored profile column would fail: it writes a
        check-in and re-reads, and nothing in between recomputes anything. A
        cached profile would answer the first shape twice, and the screen would
        be wrong in a way that has no receipt for anybody to notice it by.
        """

        context, owner = _group(postgres_session, "Team Đà Lạt")
        _checkin(postgres_session, context, owner, GRILL)

        app = _http(postgres_session, monkeypatch)
        with _Client(app) as client:
            before = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(owner.id),
            ).json()

            _checkin(postgres_session, context, owner, CAFE)
            _checkin(postgres_session, context, owner, CAFE)

            after = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(owner.id),
            ).json()

        assert before["checkin_count"] == 1
        assert after["checkin_count"] == 3
        assert [row["section"] for row in before["sections"]] == ["food"]
        assert {row["section"] for row in after["sections"]} == {"food", "activity"}

    def test_two_reads_of_unchanged_rows_agree(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Recomputed does not mean unstable. If the same rows produced two
        different profiles, "derive it every time" would be worse than a cache
        rather than better."""

        context, owner = _group(postgres_session, "Team Đà Lạt")
        for place in (GRILL, CAFE, PLAY):
            _checkin(postgres_session, context, owner, place)

        app = _http(postgres_session, monkeypatch)
        with _Client(app) as client:
            first = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(owner.id),
            ).json()
            second = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(owner.id),
            ).json()

        assert first == second

    def test_a_group_that_has_been_nowhere_says_so(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Nhóm mới")
        _photo(postgres_session, context, owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers=_headers(owner.id),
            ).json()

        # A photograph is not evidence of a taste.
        assert body["has_profile"] is False
        assert body["reason"] == "no_behaviour"
        assert body["sections"] == []


class TestPreferenceProfileIsOneGroupsOwn:
    def test_another_groups_checkins_never_reach_this_profile(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The predicate under test is `list_memories`' `context_id` filter.

        The two groups share a member here on purpose: a filter keyed on the
        *reader* instead of on the context would pass a test where the reader
        belonged to only one of them.
        """

        mine, owner = _group(postgres_session, "Nhóm mình")
        theirs, _ = _group(postgres_session, "Nhóm khác")
        _join(postgres_session, theirs, owner)

        _checkin(postgres_session, mine, owner, GRILL)
        for _ in range(9):
            _checkin(postgres_session, theirs, owner, PLAY)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{mine.id}/preference-profile", headers=_headers(owner.id)
            ).json()

        assert body["checkin_count"] == 1
        assert [row["section"] for row in body["sections"]] == ["food"]


# --------------------------------------------------------------------------
# F33 -- the contextual card
# --------------------------------------------------------------------------


def _refusing_suggester(digest, places):
    """Records what the service handed the model, and declines to answer."""

    _refusing_suggester.seen = digest
    del places
    return None


class TestContextualSuggestionPermission:
    def test_a_member_gets_an_answer(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        _say(postgres_session, context, owner, "Chán quá")
        _say(postgres_session, context, owner, "Đi đâu không?")

        app = _http(
            postgres_session, monkeypatch, suggester=lambda digest, places: None
        )
        with _Client(app) as client:
            response = client.get(
                f"/contexts/{context.id}/contextual-suggestion",
                headers=_headers(owner.id),
            )

        assert response.status_code == 200
        # The model declined, so the card declines. There is deliberately no
        # written-in fallback: a plausible card served while the backend is
        # down is a broken feature nobody can see is broken.
        assert response.json()["reason"] == "unavailable"
        assert response.json()["suggested"] is False

    def test_a_stranger_is_refused_and_sees_no_part_of_the_conversation(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        _say(postgres_session, context, owner, "bí mật của nhóm này")
        _say(postgres_session, context, owner, "đừng kể ai")
        stranger = _person(postgres_session, "Người lạ")

        app = _http(
            postgres_session, monkeypatch, suggester=lambda digest, places: None
        )
        with _Client(app) as client:
            response = client.get(
                f"/contexts/{context.id}/contextual-suggestion",
                headers=_headers(stranger.id),
            )

        assert response.status_code == 403
        assert "bí mật" not in response.text
        assert "đừng kể ai" not in response.text

    @pytest.mark.parametrize(
        "state", [MembershipState.LEFT, MembershipState.INVITED]
    )
    def test_only_an_active_member_may_read_a_card_built_from_the_chat(
        self,
        postgres_session: Session,
        monkeypatch: pytest.MonkeyPatch,
        state: MembershipState,
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        _say(postgres_session, context, owner, "Chán quá")
        _say(postgres_session, context, owner, "Đi đâu không?")
        other = _person(postgres_session, "Chưa vào")
        _join(postgres_session, context, other, state)

        app = _http(
            postgres_session, monkeypatch, suggester=lambda digest, places: None
        )
        with _Client(app) as client:
            response = client.get(
                f"/contexts/{context.id}/contextual-suggestion",
                headers=_headers(other.id),
            )

        assert response.status_code == 403


class TestContextualSuggestionEvidence:
    def test_the_response_carries_counts_and_not_the_conversation(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        friend = _person(postgres_session, "Kiệt")
        _join(postgres_session, context, friend)
        _say(postgres_session, context, owner, "chuyện riêng của tụi mình")
        _say(postgres_session, context, friend, "ừ đừng đăng lên đâu")

        app = _http(
            postgres_session, monkeypatch, suggester=lambda digest, places: None
        )
        with _Client(app) as client:
            response = client.get(
                f"/contexts/{context.id}/contextual-suggestion",
                headers=_headers(owner.id),
            )

        body = response.json()
        assert body["basis"] == {
            "message_count": 2,
            "speaker_count": 2,
            "member_count": 2,
        }
        assert "chuyện riêng" not in response.text
        assert str(owner.id) not in response.text

    def test_the_model_is_handed_the_lines_and_never_an_identity(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The conversation reaching the model *is* the feature. That it
        reaches the model without names attached is the constraint."""

        context, owner = _group(postgres_session, "Team Đà Lạt")
        _say(postgres_session, context, owner, "Chán quá")
        _say(postgres_session, context, owner, "Đi đâu không?")

        app = _http(postgres_session, monkeypatch, suggester=_refusing_suggester)
        with _Client(app) as client:
            client.get(
                f"/contexts/{context.id}/contextual-suggestion",
                headers=_headers(owner.id),
            )

        seen = _refusing_suggester.seen
        assert seen["recent_lines"] == ["Chán quá", "Đi đâu không?"]
        assert "author_id" not in seen
        assert str(owner.id) not in repr(seen)

    def test_a_silent_group_is_not_interrupted(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        _say(postgres_session, context, owner, "Chào cả nhà")

        def _never_called(digest, places):
            raise AssertionError("the model must not be called for a silent group")

        app = _http(postgres_session, monkeypatch, suggester=_never_called)
        with _Client(app) as client:
            body = client.get(
                f"/contexts/{context.id}/contextual-suggestion",
                headers=_headers(owner.id),
            ).json()

        assert body["reason"] == "no_conversation"
        assert body["suggested"] is False

    def test_another_groups_chat_is_not_read_into_this_card(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        mine, owner = _group(postgres_session, "Nhóm mình")
        theirs, _ = _group(postgres_session, "Nhóm khác")
        _join(postgres_session, theirs, owner)
        _say(postgres_session, theirs, owner, "câu của nhóm khác")
        _say(postgres_session, theirs, owner, "câu thứ hai của nhóm khác")

        app = _http(postgres_session, monkeypatch, suggester=_refusing_suggester)
        with _Client(app) as client:
            body = client.get(
                f"/contexts/{mine.id}/contextual-suggestion",
                headers=_headers(owner.id),
            ).json()

        assert body["basis"]["message_count"] == 0
        assert body["reason"] == "no_conversation"


# --------------------------------------------------------------------------
# F36 -- trip albums
# --------------------------------------------------------------------------


class TestTripAlbumPermission:
    def test_a_member_reads_the_album(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        outing = _outing(postgres_session, context, owner, "Đà Lạt")
        photo = _photo(postgres_session, context, owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            response = client.get(
                f"/contexts/{context.id}/albums/{outing.id}",
                headers=_headers(owner.id),
            )

        assert response.status_code == 200
        body = response.json()
        assert body["photo_count"] == 1
        assert body["photos"][0]["image_url"] == photo.image_url

    def test_a_stranger_is_refused_the_album(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        outing = _outing(postgres_session, context, owner, "Đà Lạt")
        _photo(postgres_session, context, owner)
        stranger = _person(postgres_session, "Người lạ")

        with _Client(_http(postgres_session, monkeypatch)) as client:
            response = client.get(
                f"/contexts/{context.id}/albums/{outing.id}",
                headers=_headers(stranger.id),
            )

        assert response.status_code == 403
        assert "/photos/" not in response.text

    def test_a_stranger_cannot_tell_a_real_trip_from_an_invented_one(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """403 before the lookup, so the pair is not an oracle.

        Reversed, a stranger walking ids would learn which of them name real
        trips from the difference between 404 and 403 -- the shape QA measured
        at #193 and the reason `context_id` is in this path at all.
        """

        context, owner = _group(postgres_session, "Team Đà Lạt")
        real = _outing(postgres_session, context, owner, "Đà Lạt")
        stranger = _person(postgres_session, "Người lạ")

        with _Client(_http(postgres_session, monkeypatch)) as client:
            existing = client.get(
                f"/contexts/{context.id}/albums/{real.id}",
                headers=_headers(stranger.id),
            )
            invented = client.get(
                f"/contexts/{context.id}/albums/{uuid.uuid4()}",
                headers=_headers(stranger.id),
            )

        assert existing.status_code == invented.status_code == 403
        assert existing.json() == invented.json()


    def test_a_stranger_is_refused_the_shelf(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The shelf is a second call site of the same gate.

        Tested separately because "one gate, two call sites" is how a
        permission check gets removed from the half nobody wrote a test for --
        and the shelf leaks a trip title, its dates, its money and a cover
        photograph, which is most of what the detail route would have leaked.
        """

        context, owner = _group(postgres_session, "Team Đà Lạt")
        _outing(postgres_session, context, owner, "Đà Lạt")
        _photo(postgres_session, context, owner)
        stranger = _person(postgres_session, "Người lạ")

        with _Client(_http(postgres_session, monkeypatch)) as client:
            refused = client.get(
                f"/contexts/{context.id}/albums", headers=_headers(stranger.id)
            )
            allowed = client.get(
                f"/contexts/{context.id}/albums", headers=_headers(owner.id)
            )

        assert refused.status_code == 403
        assert "Đà Lạt" not in refused.text
        assert "/photos/" not in refused.text
        # The positive control, in the same test: without it the assertion
        # above is satisfied by a shelf that is broken for everybody.
        assert allowed.status_code == 200
        assert len(allowed.json()["albums"]) == 1


class TestAlbumIsNotAWayAroundThePhotoGate:
    def test_a_member_of_one_group_cannot_read_another_groups_album(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The reader is a real, ACTIVE member -- of the wrong group.

        This is the failure the feature invites: keyed on `outing_id` alone the
        membership check passes on the caller's own context and then happily
        assembles somebody else's photographs. The 404 is the outing failing to
        belong to the context in the path.
        """

        mine, owner = _group(postgres_session, "Nhóm mình")
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        their_trip = _outing(postgres_session, theirs, their_owner, "Chuyến của họ")
        _photo(postgres_session, theirs, their_owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            response = client.get(
                f"/contexts/{mine.id}/albums/{their_trip.id}",
                headers=_headers(owner.id),
            )

        assert response.status_code == 404
        assert "/photos/" not in response.text

    def test_an_overlapping_trip_next_door_does_not_pull_in_its_photographs(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The window is a date range, and dates are not scoped to anybody.

        Without `Memory.context_id == Outing.context_id` in the join, every
        group whose trip overlapped these days would have its photographs
        assembled into this album -- the album becoming the way around the one
        gate the photo route has.
        """

        mine, owner = _group(postgres_session, "Nhóm mình")
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        my_trip = _outing(postgres_session, mine, owner, "Chuyến của mình")
        _outing(postgres_session, theirs, their_owner, "Cùng ngày")

        mine_photo = _photo(postgres_session, mine, owner)
        theirs_photo = _photo(postgres_session, theirs, their_owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{mine.id}/albums/{my_trip.id}", headers=_headers(owner.id)
            ).json()

        urls = [photo["image_url"] for photo in body["photos"]]
        assert urls == [mine_photo.image_url]
        assert theirs_photo.image_url not in response_text(body)

    def test_the_album_serves_the_walls_own_media_path_and_mints_no_other(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """An album entry must be fetchable only through the photo route.

        A second media path would be a second door to the same files, and the
        second door is the one nobody remembers to lock.
        """

        context, owner = _group(postgres_session, "Team Đà Lạt")
        outing = _outing(postgres_session, context, owner, "Đà Lạt")
        photo = _photo(postgres_session, context, owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{context.id}/albums/{outing.id}",
                headers=_headers(owner.id),
            ).json()

        url = body["photos"][0]["image_url"]
        assert url == photo.image_url
        assert url.startswith(f"/contexts/{context.id}/photos/")


class TestAlbumAgreesWithTheRecap:
    def test_album_photo_count_equals_the_recap_memory_count(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """One window, two screens, one number.

        `list_outing_memories` and `group_recap`'s `memory_count` are two
        copies of one date predicate. If they drift, the recap says "18 ảnh"
        over an album listing 17 and neither screen is obviously the wrong one.
        """

        context, owner = _group(postgres_session, "Team Đà Lạt")
        outing = _outing(postgres_session, context, owner, "Đà Lạt")
        for _ in range(3):
            _photo(postgres_session, context, owner)
        _checkin(postgres_session, context, owner, GRILL)
        # Outside the trip's days: counted by neither.
        _photo(
            postgres_session,
            context,
            owner,
            at=NOW + timedelta(days=30),
        )

        with _Client(_http(postgres_session, monkeypatch)) as client:
            album = client.get(
                f"/contexts/{context.id}/albums/{outing.id}",
                headers=_headers(owner.id),
            ).json()
            recap = client.get(
                f"/contexts/{context.id}/recap", headers=_headers(owner.id)
            ).json()

        row = next(
            entry
            for entry in recap["outings"] + recap["in_progress"]
            if entry["outing_id"] == str(outing.id)
        )
        assert album["photo_count"] + album["checkin_count"] == row["memory_count"]
        assert album["photo_count"] == 3
        assert album["checkin_count"] == 1

    def test_the_shelf_and_the_album_report_the_same_trip(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        outing = _outing(postgres_session, context, owner, "Đà Lạt")
        _photo(postgres_session, context, owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            shelf = client.get(
                f"/contexts/{context.id}/albums", headers=_headers(owner.id)
            ).json()
            album = client.get(
                f"/contexts/{context.id}/albums/{outing.id}",
                headers=_headers(owner.id),
            ).json()

        assert len(shelf["albums"]) == 1
        summary = shelf["albums"][0]
        assert summary["photo_count"] == album["photo_count"]
        assert summary["split_total_vnd"] == album["split_total_vnd"]
        assert summary["cover"]["image_url"] == album["photos"][0]["image_url"]

    def test_a_shelf_is_empty_for_a_group_with_no_trips(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Nhóm mới")

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{context.id}/albums", headers=_headers(owner.id)
            ).json()

        assert body["albums"] == []


class TestHighlightsAreTheGroupsOwnJudgement:
    def test_highlights_follow_the_hearts_the_group_left(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        context, owner = _group(postgres_session, "Team Đà Lạt")
        friend = _person(postgres_session, "Kiệt")
        _join(postgres_session, context, friend)
        outing = _outing(postgres_session, context, owner, "Đà Lạt")

        quiet = _photo(postgres_session, context, owner)
        loved = _photo(postgres_session, context, owner)
        _heart(postgres_session, loved, owner)
        _heart(postgres_session, loved, friend)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{context.id}/albums/{outing.id}",
                headers=_headers(owner.id),
            ).json()

        assert [row["memory_id"] for row in body["highlights"]] == [str(loved.id)]
        assert str(quiet.id) not in [row["memory_id"] for row in body["highlights"]]


def response_text(body: dict) -> str:
    import json

    return json.dumps(body)
