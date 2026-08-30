"""F45 meet-in-the-middle, built so the server never learns who is where.

The spec draws this feature as a table of people and their districts:

    Kiet  -> Thu Duc     Nam  -> District 7
    Huy   -> District 1  Linh -> Binh Thanh

That table is the private part. A server that holds it holds a live map of
where four named people are, which is a different and much heavier kind of data
than anything else in this product -- `OutingStopCheckin` refuses to store a
single coordinate against a person for exactly this reason, and it would be odd
to refuse one and then accept four.

## So the request carries areas, and not people

`rank_meeting_points` takes a list of *areas*. Not a list of members with areas
attached; not member ids at all. The mapping from a person to an area stays on
the phone that knows it, and the server receives an unlabelled multiset.

Two things follow, and both are the point:

* There is no field in which a caller could name somebody else, so the whole
  class of bug that cost this product seven money gates -- taking an identity
  from a request body -- cannot be spelled here.
* The answer cannot leak person-to-area, because the function never received
  it. This is a stronger guarantee than "we are careful not to return it": it
  is not returned because it does not exist in this process.

## The two-area case, stated rather than hidden

With two areas the midpoint is invertible: knowing one origin and the result
gives the other. That is real, and it is *not* a disclosure by this endpoint --
the areas came from the caller, so the caller already had both. The server tells
them nothing they did not just say. What would be a disclosure is a stored
person-to-area table that a second member could query, and there is none.

The honest limit lives in the client instead: a screen that collects areas from
four members and shows the result to all four has told each of them roughly
where the others are, and it should say so before collecting. That is a consent
question about the screen, not an authorisation question about the route.

## Fair means minimax, and says so

Ranking by *total* travel sends everyone to whichever district most of the group
already lives in, which is the opposite of meeting in the middle: it optimises
the majority's convenience and hands the whole cost to the person furthest out.
So the primary key is the **worst** journey anybody makes, and total distance
only breaks ties. `spread_km` ships too, so "relatively balanced" is a number
the screen can show rather than an adjective it has to be trusted on.
"""

from __future__ import annotations

from typing import Any

from app.places.areas import Area, area_summary, haversine_km

__all__ = ["MIN_ORIGIN_AREAS", "MAX_ORIGIN_AREAS", "rank_meeting_points"]

#: One area is not a meeting, it is a destination, and the fair answer would be
#: "where you already are". Refused at the edge so the screen has to ask a
#: second person before it can show anything.
MIN_ORIGIN_AREAS = 2

#: A ceiling on work per request. Twelve is above any plausible friend group and
#: keeps a single call from turning into an unbounded distance matrix.
MAX_ORIGIN_AREAS = 12


def rank_meeting_points(
    origins: list[Area],
    places: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Catalogue places ordered by how evenly everybody has to travel.

    `origins` may repeat: three friends in District 1 send that district three
    times. Repeats change the answer far less than one might expect, and it is
    worth being exact about why rather than implying otherwise.

    The primary key is the worst single journey, and duplicating an origin does
    not change a maximum. So multiplicity moves the result only through the
    `total_km` tie-break, and only when two candidates are level on the worst
    journey. That is the correct reading of "cân bằng": a meeting point is
    balanced when nobody is stranded, not when the largest faction is closest.
    Weighting by headcount is the utilitarian answer, and it reliably sends
    everybody to whichever district the majority already lives in.

    It also happens to be the better privacy posture. Because the answer is
    almost invariant to how many people share an origin, it discloses very
    little about the composition of the group -- two friends and six friends
    starting from the same pair of districts get much the same recommendation.
    `test_meeting.py` pins both halves: the invariance, and the tie-break where
    multiplicity does bite.

    Every returned row carries `travel`, the distance from each origin area.
    That is safe for the reason in the module docstring: the areas are the
    caller's own input, echoed back with arithmetic attached. It carries no
    member, because no member was ever supplied.
    """

    ranked: list[dict[str, Any]] = []
    for place in places:
        legs = [
            haversine_km(area["lat"], area["lng"], float(place["lat"]), float(place["lng"]))
            for area in origins
        ]
        if not legs:
            continue
        worst = max(legs)
        ranked.append(
            {
                "place_id": place["id"],
                "place_name": place["name"],
                "category": place["category"],
                "address": place["address"],
                "lat": float(place["lat"]),
                "lng": float(place["lng"]),
                "fairness": {
                    # Rounded for the wire only. The ordering below uses the
                    # unrounded values, so two places that round to the same
                    # tenth of a kilometre still sort deterministically.
                    "worst_km": round(worst, 2),
                    "total_km": round(sum(legs), 2),
                    "spread_km": round(worst - min(legs), 2),
                },
                "travel": [
                    {**area_summary(area), "km": round(leg, 2)}
                    for area, leg in zip(origins, legs, strict=True)
                ],
                "_sort": (worst, sum(legs), place["id"]),
            }
        )

    ranked.sort(key=lambda row: row["_sort"])
    for row in ranked:
        del row["_sort"]
    return ranked[:limit]
