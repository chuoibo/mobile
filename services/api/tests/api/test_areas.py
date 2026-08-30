"""`GET /areas` -- the districts the meeting-point route will accept.

What this tier proves: that the list a picker offers and the list
`POST /contexts/{id}/meet` validates against are the *same* list, because they
come from the same module. That is the whole reason the route exists.

What it does not prove: that any screen calls it. `scripts/check_api_contract.py`
answers that, and it reads the tree rather than this file.
"""

from __future__ import annotations

from app.places.areas import AREAS

from .helpers import ADVANCER_ID, CONTEXT_ID


def test_every_known_area_is_offered(client):
    response = client.get("/areas")
    assert response.status_code == 200, response.text
    body = response.json()

    assert [row["id"] for row in body] == [area["id"] for area in AREAS]
    for row, area in zip(body, AREAS, strict=True):
        assert row["label"] == area["label"]
        # The centroid ships because every kilometre in a meeting-point answer
        # is measured from it. A fairness number whose basis is not disclosed
        # cannot be argued with.
        assert row["lat"] == area["lat"]
        assert row["lng"] == area["lng"]


def test_the_ids_offered_are_ids_meet_accepts(client):
    """The drift this route exists to prevent, asserted rather than described.

    A picker offering an id the meeting route rejects looks to a person like a
    form refusing a perfectly reasonable answer, and nothing in either half
    would go red on its own.
    """

    offered = [row["id"] for row in client.get("/areas").json()]
    assert len(offered) >= 2

    response = client.post(
        f"/contexts/{CONTEXT_ID}/meet",
        json={"from_areas": offered[:2]},
        headers={"X-Actor-ID": str(ADVANCER_ID)},
    )
    # Membership is a separate question and this actor may well fail it. What
    # must not happen is 422: that would mean the ids this route published are
    # ids the other route does not know.
    assert response.status_code != 422, response.text


def test_the_catalogue_carries_no_group_and_no_person(client):
    """Ungated, so the answer must contain nothing that gating would protect."""

    body = client.get("/areas").json()
    allowed = {"id", "label", "lat", "lng"}
    for row in body:
        assert set(row) == allowed, f"trường lạ trong /areas: {set(row) - allowed}"


def test_no_actor_header_is_still_answered(client):
    """The one route in this module that does not need an actor.

    Asserted rather than assumed: if it ever starts requiring one, the picker
    on a screen that has not identified anybody yet goes blank, and the symptom
    is a district list that silently fails to load.
    """

    assert client.get("/areas").status_code == 200
