"""PR #301 (F31/F33/F36) -- what a refusal actually carries, and the shelf's cover.

`test_group_intelligence_postgres.py` already proves the strangers are refused.
This file exists because of *how* it proves it: every refusal there is checked
with a needle -- `assert "BBQ" not in response.text`, `assert "Đà Lạt" not in
response.text`. A needle answers "is this one string absent", which is a
weaker question than the one the gate has to survive:

  * it is green when the fixture never wrote the needle in the first place,
  * it is green on a body that leaked a hundred rows and merely spelled the
    category differently, and
  * it says nothing at all about the fields the needle does not name --
    `checkin_count`, `split_total_vnd`, `photo_count`, a cover's `image_url`.

So the refusals below are checked structurally instead: a refused body must
carry the two keys of an error and **zero records at any depth**. That is the
assertion the shape of the response cannot satisfy by accident.

Three things here are not covered anywhere else in the suite:

1. **The header does not decide.** `X-Actor-Contexts` is a claim a client
   chooses. Every refusal below is re-run by a caller who names the victim
   group in that header, because "the gate reads `is_member` and not the
   header" is a property of the running code, not of the code review that
   observed it.

2. **The shelf's cover.** The overlap case is proved on
   `GET /contexts/{id}/albums/{outing_id}` and not on the shelf, and the shelf
   builds a cover through the same `_album_of`. One gate with two call sites is
   how a check gets removed from the half nobody tested.

3. **A reader who belongs to both groups.** A refusal test whose reader belongs
   to only one group passes even when the filter is keyed on the *reader*
   rather than on the context in the path.

Uses `flush`, never `commit`, for the reason the neighbouring file gives: this
directory's schema is shared and row-counting tests elsewhere go red if rows
from here survive.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from .test_group_intelligence_postgres import (
    GRILL,
    PLAY,
    _checkin,
    _Client,
    _group,
    _headers,
    _http,
    _join,
    _outing,
    _person,
    _photo,
    _say,
)

pytestmark = pytest.mark.postgres


def _records(payload) -> int:
    """How many rows of anybody's data a body carries, at any depth.

    Counting rather than string-matching is the whole point of this file. A
    refusal has to carry zero, and `zero` is a claim about every list in the
    body -- including ones added by a field somebody writes next month, which
    a hand-written list of field names would not cover.
    """

    if isinstance(payload, dict):
        return sum(_records(value) for value in payload.values())
    if isinstance(payload, list):
        return len(payload) + sum(_records(item) for item in payload)
    return 0


def _assert_is_a_bare_refusal(response, *, status: int) -> None:
    """A refusal carries an error and nothing else.

    `set(body) == {"code", "detail"}` is deliberately an equality and not a
    subset check: the failure this guards is a handler that returns the real
    payload *alongside* an error code, which a subset check would wave through.
    """

    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "detail"}, body
    assert _records(body) == 0, body


def _claiming(person_id: uuid.UUID, context_id: uuid.UUID) -> dict[str, str]:
    """Headers that assert membership of `context_id` without holding a row.

    This is the forged half of `X-Actor-ID` / `X-Actor-Contexts`: the gateway
    that is supposed to assert these does not exist in this slice, so a client
    can put whatever it likes here. `deps.py` says so in as many words. What
    must hold is that the value changes nothing.
    """

    return _headers(person_id) | {"X-Actor-Contexts": str(context_id)}


# --------------------------------------------------------------------------
# 1. A refusal carries no records -- on every one of the four endpoints
# --------------------------------------------------------------------------


class TestARefusalCarriesNoRecords:
    """Each case pairs the refusal with the member who may read it.

    Without the paired 200 the refusal is satisfied by a route that is broken
    for everybody -- a 500, an unregistered router, a typo in the path.
    """

    def test_the_profile_of_another_group_is_refused_and_empty(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        mine, owner = _group(postgres_session, "Nhóm mình")
        for _ in range(4):
            _checkin(postgres_session, theirs, their_owner, GRILL)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            refused = client.get(
                f"/contexts/{theirs.id}/preference-profile",
                headers=_claiming(owner.id, theirs.id),
            )
            allowed = client.get(
                f"/contexts/{theirs.id}/preference-profile",
                headers=_headers(their_owner.id),
            )

        _assert_is_a_bare_refusal(refused, status=403)
        assert allowed.status_code == 200
        # The positive control has to be non-trivial: a profile with zero
        # check-ins would make "the refusal carried no records" vacuous.
        assert allowed.json()["checkin_count"] == 4
        assert _records(allowed.json()) > 0
        del mine

    def test_the_contextual_card_of_another_group_is_refused_and_empty(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        mine, owner = _group(postgres_session, "Nhóm mình")
        _say(postgres_session, theirs, their_owner, "tối nay đi đâu")
        _say(postgres_session, theirs, their_owner, "chán quá")

        seen: list[dict] = []

        def _suggester(digest, places):
            del places
            seen.append(digest)
            return None

        app = _http(postgres_session, monkeypatch, suggester=_suggester)
        with _Client(app) as client:
            refused = client.get(
                f"/contexts/{theirs.id}/contextual-suggestion",
                headers=_claiming(owner.id, theirs.id),
            )
            allowed = client.get(
                f"/contexts/{theirs.id}/contextual-suggestion",
                headers=_headers(their_owner.id),
            )

        _assert_is_a_bare_refusal(refused, status=403)
        assert allowed.status_code == 200
        # The refusal must also cost nothing: a gate that runs *after* the
        # model call has already spent the shared key on a group the caller
        # may not read, and has already put their sentences in a prompt.
        assert len(seen) == 1, "the model was reached on the refused request too"
        assert seen[0]["message_count"] == 2
        del mine

    def test_the_shelf_of_another_group_is_refused_and_empty(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        mine, owner = _group(postgres_session, "Nhóm mình")
        _outing(postgres_session, theirs, their_owner, "Chuyến của họ")
        _photo(postgres_session, theirs, their_owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            refused = client.get(
                f"/contexts/{theirs.id}/albums",
                headers=_claiming(owner.id, theirs.id),
            )
            allowed = client.get(
                f"/contexts/{theirs.id}/albums", headers=_headers(their_owner.id)
            )

        _assert_is_a_bare_refusal(refused, status=403)
        assert allowed.status_code == 200
        assert len(allowed.json()["albums"]) == 1
        assert allowed.json()["albums"][0]["cover"] is not None
        del mine

    def test_the_album_of_another_group_is_refused_and_empty(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        mine, owner = _group(postgres_session, "Nhóm mình")
        their_trip = _outing(postgres_session, theirs, their_owner, "Chuyến của họ")
        _photo(postgres_session, theirs, their_owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            refused = client.get(
                f"/contexts/{theirs.id}/albums/{their_trip.id}",
                headers=_claiming(owner.id, theirs.id),
            )
            allowed = client.get(
                f"/contexts/{theirs.id}/albums/{their_trip.id}",
                headers=_headers(their_owner.id),
            )

        _assert_is_a_bare_refusal(refused, status=403)
        assert allowed.status_code == 200
        assert len(allowed.json()["photos"]) == 1


# --------------------------------------------------------------------------
# 2. The shelf's cover -- the untested call site of the album gate
# --------------------------------------------------------------------------


class TestTheShelfCoverIsThisGroupsOwnPhotograph:
    def test_an_overlapping_trip_next_door_does_not_supply_the_cover(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The overlap case, on the shelf rather than on one album.

        `_album_of` is reached from both `trip_album` and `list_trip_albums`,
        and only the first has this test next door. The shelf is the worse
        surface to lose: it renders a cover for *every* trip in one response,
        so a missing `Memory.context_id == Outing.context_id` shows up here as
        a wall of somebody else's photographs rather than as one album.

        The reader is ACTIVE in both groups on purpose. A reader who belonged
        to only one would pass this test even if the join were keyed on the
        reader's memberships instead of on the outing's context.
        """

        mine, owner = _group(postgres_session, "Nhóm mình")
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        _join(postgres_session, theirs, owner)

        _outing(postgres_session, mine, owner, "Chuyến của mình")
        _outing(postgres_session, theirs, their_owner, "Cùng ngày")

        # Theirs is written last, so it is the newest row in the date window
        # the two trips share -- i.e. the one a context-blind `order_by
        # created_at desc` would hand back as *the cover*.
        mine_photo = _photo(postgres_session, mine, owner)
        theirs_photo = _photo(postgres_session, theirs, their_owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            response = client.get(
                f"/contexts/{mine.id}/albums", headers=_headers(owner.id)
            )

        assert response.status_code == 200
        albums = response.json()["albums"]
        assert len(albums) == 1
        assert albums[0]["cover"]["image_url"] == mine_photo.image_url
        assert albums[0]["photo_count"] == 1
        assert theirs_photo.image_url not in response.text

    def test_a_shelf_reports_only_the_photographs_of_its_own_group(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """`photo_count` is a number on a screen, so a leak here is silent.

        The cover proves *which* photograph came back. The count proves how
        many were assembled, which is the half a cover assertion cannot see:
        an album that picked the right cover out of eleven foreign candidates
        still tells the group it has eleven photographs.
        """

        mine, owner = _group(postgres_session, "Nhóm mình")
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        _join(postgres_session, theirs, owner)

        _outing(postgres_session, mine, owner, "Chuyến của mình")
        _outing(postgres_session, theirs, their_owner, "Cùng ngày")

        _photo(postgres_session, mine, owner)
        for _ in range(10):
            _photo(postgres_session, theirs, their_owner)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{mine.id}/albums", headers=_headers(owner.id)
            ).json()

        assert body["albums"][0]["photo_count"] == 1
        assert body["albums"][0]["checkin_count"] == 0

    def test_the_profile_of_a_reader_in_both_groups_stays_on_the_path_group(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The same shape for F31, against the *other* group's check-ins.

        The neighbouring file proves this with the reader's own group in the
        path. This is the mirror: the group in the path is the one the reader
        joined second, and its profile must be built from its own rows.
        """

        mine, owner = _group(postgres_session, "Nhóm mình")
        theirs, their_owner = _group(postgres_session, "Nhóm khác")
        _join(postgres_session, theirs, owner)

        for _ in range(7):
            _checkin(postgres_session, mine, owner, GRILL)
        _checkin(postgres_session, theirs, their_owner, PLAY)

        with _Client(_http(postgres_session, monkeypatch)) as client:
            body = client.get(
                f"/contexts/{theirs.id}/preference-profile",
                headers=_headers(owner.id),
            ).json()

        assert body["checkin_count"] == 1
        # "activity", not "food": the seven grills belong to the other group.
        # The section name is the product's, read off a passing run rather
        # than guessed -- the count above is what carries the claim.
        assert [row["section"] for row in body["sections"]] == ["activity"]


# --------------------------------------------------------------------------
# 3. A person with no membership row anywhere
# --------------------------------------------------------------------------


class TestTheHeaderIsNotTheGate:
    @pytest.mark.parametrize(
        "path",
        [
            "preference-profile",
            "contextual-suggestion",
            "albums",
        ],
    )
    def test_naming_the_group_in_a_header_grants_nothing(
        self,
        postgres_session: Session,
        monkeypatch: pytest.MonkeyPatch,
        path: str,
    ):
        """A stranger who claims the group in `X-Actor-Contexts` is still out.

        The claim is the cheapest attack available against this slice, because
        the gateway that would make the header trustworthy is not built yet.
        `is_member` is what refuses; this asserts that it is what runs.
        """

        context, owner = _group(postgres_session, "Team Đà Lạt")
        _checkin(postgres_session, context, owner, GRILL)
        _outing(postgres_session, context, owner, "Đà Lạt")
        _photo(postgres_session, context, owner)
        _say(postgres_session, context, owner, "bí mật của nhóm này")
        stranger = _person(postgres_session, "Người lạ")

        app = _http(
            postgres_session, monkeypatch, suggester=lambda digest, places: None
        )
        with _Client(app) as client:
            refused = client.get(
                f"/contexts/{context.id}/{path}",
                headers=_claiming(stranger.id, context.id),
            )
            allowed = client.get(
                f"/contexts/{context.id}/{path}", headers=_headers(owner.id)
            )

        _assert_is_a_bare_refusal(refused, status=403)
        assert allowed.status_code == 200
