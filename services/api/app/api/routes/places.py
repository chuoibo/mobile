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

import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.api.deps import Actor, get_actor
from app.api.schemas import MoneyVnd
from app.api.search_rate_limit import FixedWindowLimiter
from app.domain.place_search import PlaceSearchError, ground_search
from app.places.catalog import CATEGORIES, GROUP, PLACES, GroupProfile
from app.places.reasons import (
    PlaceReason,
    ReasonRow,
    gemini_reasons,
    ungrounded_numbers,
)
from app.places.scoring import score_place
from app.places.search import MAX_QUERY_CHARS, echoes_the_query, gemini_search

logger = logging.getLogger(__name__)

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
    price_min_vnd: MoneyVnd
    price_max_vnd: MoneyVnd
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
    budget_per_person_vnd: MoneyVnd
    likes: list[str]
    max_distance_km: float
    when: str


class PlacesResponse(BaseModel):
    places: list[Place]
    categories: list[Category]
    group: GroupSummary


class Understood(BaseModel):
    """What the model took the sentence to mean, in closed vocabularies only.

    Sent so the screen can show its reading back and be told it is wrong. Every
    field is either a number the server has re-typed or a token drawn from the
    catalogue: there is no free text here, so this cannot become a second place
    for model prose to reach a card without a label.
    """

    budget_per_person_vnd: MoneyVnd | None
    group_size: int | None
    max_distance_km: float | None
    categories: list[str]
    traits: list[str]


class PlaceSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)

    @field_validator("query")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        """Refused here, so no prompt is ever built from an empty search.

        A whitespace-only query passes `min_length` and would otherwise cost a
        model call to be told nothing.
        """

        trimmed = value.strip()
        if not trimmed:
            raise ValueError("query must not be blank")
        return trimmed


class PlaceSearchResponse(BaseModel):
    """`source` is a claim about the whole answer, not about one card.

    `none` means no model answer survived, and the honest rendering is an empty
    list with a message saying so. `match.source` on each card is the narrower
    claim about who wrote that one sentence.
    """

    query: str
    understood: Understood | None
    places: list[Place]
    source: Literal["ai", "none"]
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


def get_search_rate_limiter(request: Request) -> FixedWindowLimiter:
    """Seam for tests, resolving the one object `create_app` built.

    Read off the application rather than constructed here: a limiter built per
    request counts to one and forgets, which is a limiter-shaped object that
    limits nothing.
    """

    return request.app.state.search_limiter


def get_place_searcher():
    """Seam for tests, and deliberately not memoised like the reason writer.

    A reason is a pure function of a fixed catalogue and a fixed group, so
    caching it is free. A search is a function of what somebody typed, and a
    cache keyed on that is a cache of other people's sentences sitting in
    process memory for no gain.
    """

    return gemini_search


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


def _card(
    place: dict[str, Any],
    reason: str | None,
    verdict: Literal["hop", "tam", "khong-hop"] | None,
) -> Place:
    """One card, scored once.

    Shared by browse and search on purpose rather than for tidiness: two call
    sites computing a score separately is how the same place ends up showing
    two different numbers on two screens for one group.

    `reason` and `verdict` are one claim, held here rather than at the call
    sites. Search used to pass `verdict=None` beside a sentence a model really
    wrote, and the pair `source: "ai"` + `verdict: null` renders as "AI MATCH
    95%" -- a percentage credited to a model that never gave an opinion, which
    is the exact lie the two fields exist to prevent. The app refuses a
    response containing either half of the pair, so half a pair is not a
    cosmetic defect: it costs the caller the whole screen.
    """

    # Either half missing drops both. A sentence with no conclusion behind it
    # is served under the server's own template, which is the honest label.
    if reason is None or verdict is None:
        reason = None
        verdict = None

    score, factors = score_place(place, GROUP)
    return Place(
        **{key: value for key, value in place.items()},
        match=Match(
            score=score,
            reason=reason if reason else _fallback_reason(place, GROUP),
            source="ai" if reason else "none",
            verdict=verdict,
            factors=[MatchFactor(**factor) for factor in factors],
        ),
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
        reason = written.get(place["id"])
        out.append(
            _card(
                place,
                reason.reason if reason else None,
                reason.verdict if reason else None,
            )
        )

    # Two tiers, not one weighted number. `open_now` decides the tier; the
    # score only decides the order inside a tier; rating breaks the remaining
    # ties so two renders of the same data do not shuffle under someone's thumb.
    #
    # `open_now` deliberately never reaches `score_place`. A shut door is not a
    # matter of degree: as a scoring term it would merely cost a place some
    # points, so a closed place could still out-argue an open one on budget and
    # distance and be recommended for tonight. As a tier it cannot. Keeping it
    # out of the arithmetic also leaves every hand-checked score in the suite
    # exactly where it was -- the ordering changed, no number did.
    out.sort(
        key=lambda place: (
            not place.open_now,
            -place.match.score,
            -place.rating,
            place.id,
        )
    )

    return PlacesResponse(
        places=out,
        categories=[Category(**category_row) for category_row in CATEGORIES],
        group=GroupSummary(**GROUP),
    )


@router.post("/places/search", response_model=PlaceSearchResponse)
def search_places(
    request: PlaceSearchRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_search_rate_limiter)],
    place_searcher: Annotated[Any, Depends(get_place_searcher)],
) -> PlaceSearchResponse:
    """F12 -- "quán nướng ngoài trời cho 6 người dưới 300k" becomes real places.

    The model reads the sentence and answers with identifiers. Everything a
    caller ends up looking at is assembled here from the seed catalogue, so a
    model that was confused, wrong, or doing what an injected instruction told
    it can still only pick rows that exist -- and if it picks one that does not,
    `ground_search` refuses the whole answer rather than serving the rest.

    Every failure lands on the same honest empty answer: 200, no places,
    `source: "none"`. There is deliberately no fallback to the keyword matching
    `GET /places` does, because a plausible list served while the feature is
    broken is a broken feature that nobody can see is broken.

    Signed in, and metered (rd-be-13). Unlike every other route here, `actor`
    authorises nothing: there is no aggregate to own and no row to hide, and
    QA established structurally at rd-qa-18 that this handler has no path to
    anybody else's data. What identity buys is a **meter**. The call costs
    real Gemini quota, and open and uncounted it could be drained by a loop --
    a failure that surfaces not as an alert but as search silently not working
    for everyone at once. `get_actor` stops the anonymous caller; the window
    stops the caller who merely invented a UUID, which in this slice is the
    same person one header later.
    """

    limiter.check(actor.id)

    query = request.query
    unavailable = PlaceSearchResponse(
        query=query,
        understood=None,
        places=[],
        source="none",
        group=GroupSummary(**GROUP),
    )

    try:
        raw = place_searcher(query)
    except Exception as error:  # noqa: BLE001 - a search box must not 500 on this
        logger.warning("place search: searcher failed (%s)", type(error).__name__)
        return unavailable
    if raw is None:
        return unavailable

    try:
        grounded = ground_search(raw, PLACES, CATEGORIES)
    except PlaceSearchError as error:
        # The code, never the answer. What provoked the refusal is model output
        # shaped by caller text, and neither belongs in a log line.
        logger.warning("place search: answer refused (%s)", error.code)
        return unavailable

    out: list[Place] = []
    for item in grounded["results"]:
        place = item["place"]
        reason = item["reason"]
        # Two reused gates, different blast radius, both per-row here because a
        # bad *sentence* about a real place is not a bad answer -- unlike a
        # place that does not exist, which `ground_search` already refused above.
        if reason is not None and ungrounded_numbers(reason, place, GROUP):
            logger.warning("place search: dropped ungrounded reason for %s", place["id"])
            reason = None
        if echoes_the_query(reason, query):
            logger.warning("place search: dropped echoed reason for %s", place["id"])
            reason = None
        # The model's own conclusion, asked for in the prompt and checked
        # against the closed set by `ground_search`. Passing `None` here is
        # what shipped `source: "ai"` beside `verdict: null` and cost the app
        # the whole response; `_card` now refuses to build that pair at all,
        # so a gate above that drops the sentence drops the verdict with it.
        out.append(_card(place, reason, item["verdict"]))

    # Not re-sorted. `GET /places` orders by open-now and score because it is a
    # catalogue; this is a search, and relevance to the sentence is the model's
    # answer, which sorting here would quietly discard.
    return PlaceSearchResponse(
        query=query,
        understood=Understood(**grounded["understood"]),
        places=out,
        source="ai",
        group=GroupSummary(**GROUP),
    )
