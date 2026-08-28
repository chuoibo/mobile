"""`GET /places` -- the catalogue behind the Khám phá tab (rd-be-05).

Read-only, and the only route in this service that is not about money. It sits
here rather than in `service.py` because there is no aggregate, no ledger entry
and no repository call: seed rows in, scored rows out.

The contract in one sentence: **a card never shows a number without showing
where the number came from, and never shows the words AI MATCH unless a model
actually answered for that card.** `match.factors` carries the arithmetic,
`match.source` carries the provenance, and `match.verdict` carries the model's
own conclusion -- including the conclusion that the place does not suit the
group, which the screen has to be able to say.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.places.catalog import CATEGORIES, GROUP, PLACES, GroupProfile
from app.places.reasons import PlaceReason, ReasonRow, gemini_reasons
from app.places.scoring import score_place

router = APIRouter(tags=["places"])


class MatchFactor(BaseModel):
    label: str
    detail: str


class Match(BaseModel):
    score: int
    reason: str
    #: `ai` is a claim about who wrote `reason`, and the app prints the words
    #: AI MATCH on exactly this value. `none` means the score stands alone.
    source: Literal["ai", "none"]
    #: The model's own answer, absent when it did not give one. Not derived
    #: from `score`: the two are computed independently and are allowed to
    #: disagree, which is the only way a disagreement can ever be noticed.
    verdict: Literal["hop", "tam", "khong-hop"] | None
    factors: list[MatchFactor]


class GroupFit(BaseModel):
    min_people: int
    max_people: int
    relation: str


class Place(BaseModel):
    id: str
    name: str
    category: str
    kinds: list[str]
    rating: float
    rating_count: int
    distance_km: float
    #: Integer đồng, both ends. Money law 1 does not stop at the ledger: a
    #: price band that leaves this service fractional means a float reached a
    #: money value somewhere upstream.
    price_min_vnd: int
    price_max_vnd: int
    address: str
    open_now: bool
    open_hours: str
    travel_minutes: int
    photo_count: int
    traits: list[str]
    group_fit: GroupFit | None
    flag: Literal["new", "hot"] | None
    lat: float
    lng: float
    match: Match


class Category(BaseModel):
    id: str
    label: str


class GroupSummary(BaseModel):
    """The profile every score is relative to, sent so the badge is falsifiable.

    A percentage whose basis is not stated cannot be argued with, and a number
    nobody can argue with is decoration. This is the basis.
    """

    size: int
    age_range: str
    budget_per_person_vnd: int
    likes: list[str]
    max_distance_km: float
    when: str


class PlacesResponse(BaseModel):
    places: list[Place]
    categories: list[Category]
    group: GroupSummary


# ---------------------------------------------------------------------------
# Reason writer: injected, memoised, and allowed to fail
# ---------------------------------------------------------------------------

_reason_cache: dict[str, PlaceReason] = {}


def cached_gemini_reasons(rows: list[ReasonRow]) -> dict[str, PlaceReason]:
    """Call Gemini once per place per process, not once per pull-to-refresh.

    The seed catalogue and the group profile are both fixed, so a reason is a
    pure function of data that does not change while the process lives. Caching
    it keeps a demo from spending a model call -- and two seconds of someone's
    attention -- every time a tab is opened.

    A row that failed last time is retried: the cache stores successes only, so
    a Gemini blip during startup does not leave the catalogue permanently
    unlabelled.
    """

    missing = [row for row in rows if row.place["id"] not in _reason_cache]
    if missing:
        _reason_cache.update(gemini_reasons(missing, GROUP))
    return {
        row.place["id"]: _reason_cache[row.place["id"]]
        for row in rows
        if row.place["id"] in _reason_cache
    }


def get_reason_writer():
    """Seam for tests. Overridden with a writer that never opens a socket."""

    return cached_gemini_reasons


# ---------------------------------------------------------------------------


def _fallback_reason(place: dict[str, Any], group: GroupProfile) -> str:
    """What a card says when no model answered for it.

    Assembled from the same figures the factor lines carry, so it is checkable
    against the row -- but it is a template, it is not a judgement, and it is
    served under `source: "none"` so nothing on screen calls it AI. This is the
    honest version of the canned sentence the deleted stub server used to
    serve under an `ai` label.
    """

    low = place["price_min_vnd"] // 1000
    high = place["price_max_vnd"] // 1000
    band = f"{low}k" if low == high else f"{low}–{high}k"
    return (
        f"Khoảng {band}/người, cách {place['distance_km']}km. "
        f"Điểm dưới đây do máy tính từ ngân sách, sở thích và khoảng cách của nhóm; "
        f"chưa có nhận xét của AI cho chỗ này."
    )


def _matches(text: str, place: dict[str, Any]) -> bool:
    needle = text.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        [place["name"], place["address"], *place["kinds"], *place["traits"]]
    ).lower()
    return needle in haystack


@router.get("/places", response_model=PlacesResponse)
def list_places(
    reason_writer: Annotated[Any, Depends(get_reason_writer)],
    context_id: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> PlacesResponse:
    """Score the seed catalogue against the group, then ask the model about it.

    `context_id` is accepted and not yet used: the group profile is seed data
    for the vertical slice. It is in the signature because the app already
    sends it and because the seam for reading a real group belongs here rather
    than in a later rewrite of the client.

    An unknown `category` yields an empty list and a 200, not a 404. The app
    reads 404 on this path as "the route does not exist yet" and shows a screen
    saying so, which would be false.
    """

    del context_id

    selected = [
        place
        for place in PLACES
        if (category is None or place["category"] == category)
        and _matches(q or "", place)
    ]

    rows = [ReasonRow(place=place) for place in selected]
    # Never lets a model outage become a 500 on a read-only catalogue.
    try:
        written = reason_writer(rows) if rows else {}
    except Exception:  # noqa: BLE001
        written = {}

    out: list[Place] = []
    for place in selected:
        score, factors = score_place(place, GROUP)
        reason = written.get(place["id"])
        out.append(
            Place(
                **{key: value for key, value in place.items()},
                match=Match(
                    score=score,
                    reason=reason.reason if reason else _fallback_reason(place, GROUP),
                    source="ai" if reason else "none",
                    verdict=reason.verdict if reason else None,
                    factors=[MatchFactor(**factor) for factor in factors],
                ),
            )
        )

    # Best first, ties broken by rating so two renders of the same data do not
    # shuffle under someone's thumb.
    out.sort(key=lambda place: (-place.match.score, -place.rating, place.id))

    return PlacesResponse(
        places=out,
        categories=[Category(**category_row) for category_row in CATEGORIES],
        group=GroupSummary(**GROUP),
    )
