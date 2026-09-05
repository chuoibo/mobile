"""`GET /interests`, `PUT /people/me/interests`, and what `GET /people/me` says.

What this layer proves: the vocabulary is public and closed; a person's answers
round-trip through the profile route; unticking is how a taste is removed;
somebody else's profile never carries them. What it does not prove: the unique
index, the foreign key, or that the delete leaves the survivors' rows alone --
`tests/postgres/test_interests_postgres.py` does that against a real database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.repository import PersonRecord
from app.domain.interests import INTEREST_IDS

from .helpers import actor_headers

ME = uuid.UUID("aa11aa11-0a0a-4a0a-8a0a-0a0a0a0a0aa1")
MATE = uuid.UUID("bb11bb11-0b0b-4b0b-8b0b-0b0b0b0b0bb1")
T0 = datetime(2030, 9, 5, 9, tzinfo=UTC)


def _seed(repository):
    for pid, name in ((ME, "Tôi"), (MATE, "Đồng nhóm")):
        repository.people[pid] = PersonRecord(id=pid, display_name=name, created_at=T0)


def _as(pid):
    return actor_headers(actor_id=pid)


def test_the_vocabulary_is_public(client):
    """The personalization screen is drawn before there is a session; a route
    that required one could not answer the screen that needs it."""

    response = client.get("/interests")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [tag["id"] for tag in body["interests"]] == list(INTEREST_IDS)
    assert all(tag["label"].strip() for tag in body["interests"])
    assert [band["id"] for band in body["budget_bands"]] == [
        "tiet-kiem",
        "vua-phai",
        "thoai-mai",
    ]


def test_budget_bands_travel_as_two_integers(client):
    body = client.get("/interests").json()
    for band in body["budget_bands"]:
        assert isinstance(band["min_vnd"], int)
        assert band["max_vnd"] is None or isinstance(band["max_vnd"], int)
    # No midpoint on the wire: the arithmetic belongs to whoever does it.
    assert "midpoint_vnd" not in body["budget_bands"][0]


def test_answers_round_trip_through_the_profile(client, repository):
    _seed(repository)
    written = client.put(
        "/people/me/interests",
        json={"interests": ["cafe", "an-uong"], "budget_band": "vua-phai"},
        headers=_as(ME),
    )
    assert written.status_code == 200, written.text
    # Vocabulary order, not tap order.
    assert written.json() == {
        "interests": ["an-uong", "cafe"],
        "budget_band": "vua-phai",
    }

    profile = client.get("/people/me", headers=_as(ME)).json()
    assert profile["interests"] == ["an-uong", "cafe"]
    assert profile["budget_band"] == "vua-phai"


def test_unticking_removes_a_taste(client, repository):
    """The request is the whole answer, so a shorter list is a removal."""

    _seed(repository)
    client.put(
        "/people/me/interests",
        json={"interests": ["cafe", "an-uong", "game"]},
        headers=_as(ME),
    )
    client.put("/people/me/interests", json={"interests": ["cafe"]}, headers=_as(ME))
    assert client.get("/people/me", headers=_as(ME)).json()["interests"] == ["cafe"]


def test_choosing_nothing_is_a_supported_answer(client, repository):
    _seed(repository)
    response = client.put(
        "/people/me/interests", json={"interests": []}, headers=_as(ME)
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"interests": [], "budget_band": None}


def test_a_word_the_server_does_not_know_is_refused(client, repository):
    """Not dropped: a client shipping a chip the server never heard of would
    otherwise look like it worked, and the person would keep re-choosing it."""

    _seed(repository)
    response = client.put(
        "/people/me/interests",
        json={"interests": ["cafe", "du-thuyen"]},
        headers=_as(ME),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "interest_unknown"
    # And nothing was stored: the whole answer is refused, not the good half.
    assert client.get("/people/me", headers=_as(ME)).json()["interests"] == []


def test_the_refusal_does_not_echo_the_word_back(client, repository):
    _seed(repository)
    response = client.put(
        "/people/me/interests",
        json={"interests": ["<script>alert(1)</script>"]},
        headers=_as(ME),
    )
    assert response.status_code == 422
    assert "script" not in response.text


def test_an_unknown_budget_band_is_refused(client, repository):
    _seed(repository)
    response = client.put(
        "/people/me/interests",
        json={"interests": [], "budget_band": "sang-chanh"},
        headers=_as(ME),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "budget_band_unknown"


def test_a_skipped_budget_clears_a_previous_one(client, repository):
    """Changing your mind back to «rather not say» has to be possible; the
    alternative is a first answer nobody can take back."""

    _seed(repository)
    client.put(
        "/people/me/interests",
        json={"interests": [], "budget_band": "thoai-mai"},
        headers=_as(ME),
    )
    client.put("/people/me/interests", json={"interests": []}, headers=_as(ME))
    assert client.get("/people/me", headers=_as(ME)).json()["budget_band"] is None


def test_interests_are_not_part_of_anybody_elses_view(client, repository):
    """ADR-0019 §2.1: a person's tastes are theirs. The public profile does not
    carry them, and there is no route that reads another person's."""

    _seed(repository)
    repository.friend_edges[uuid.uuid4()] = {
        "requester_id": ME,
        "addressee_id": MATE,
        "state": "accepted",
        "created_at": T0,
        "decided_at": T0,
    }
    client.put(
        "/people/me/interests",
        json={"interests": ["nightlife"], "budget_band": "tiet-kiem"},
        headers=_as(ME),
    )
    seen = client.get(f"/people/{ME}", headers=_as(MATE))
    assert seen.status_code == 200, seen.text
    body = seen.json()
    assert "interests" not in body and "budget_band" not in body
    assert "nightlife" not in seen.text


def test_the_route_only_ever_writes_the_caller(client, repository):
    """No `person_id` in the path and none in the body: a field naming whose
    answers to write is a question no caller should be able to pose."""

    _seed(repository)
    response = client.put(
        "/people/me/interests",
        json={"interests": ["cafe"], "person_id": str(MATE)},
        headers=_as(ME),
    )
    assert response.status_code == 422, response.text
    assert client.get("/people/me", headers=_as(MATE)).json()["interests"] == []


def test_writing_needs_a_session(client, repository):
    _seed(repository)
    response = client.put("/people/me/interests", json={"interests": ["cafe"]})
    assert response.status_code == 401, response.text
