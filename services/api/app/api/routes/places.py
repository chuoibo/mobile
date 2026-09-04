"""`GET /places` -- the catalogue behind the Khám phá tab (rd-be-05).

Read-only, and the only route in this service that is not about money. Since
M9 (ADR-0017) the rows come from the `places` table through the repository
instead of from a module constant, because real venue data may not live in
Git; the scoring, the grounding and the card shape did not change with them.

The contract in one sentence: **a card never shows a number without showing
where the number came from, and never shows the words AI MATCH unless a model
actually answered for that card.** `match.factors` carries the arithmetic,
`match.source` carries the provenance, and `match.verdict` carries the model's
own conclusion -- including the conclusion that the place does not suit the
group, which the screen has to be able to say.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.api.deps import Actor, get_actor, get_repository
from app.api.errors import ApiProblem
from app.api.repository import ApiRepository, DestinationRecord
from app.api.schemas import MoneyVnd
from app.api.search_rate_limit import FixedWindowLimiter
from app.api.service import ApiService
from app.domain.place_search import PlaceSearchError, ground_search
from app.places.areas import haversine_km
from app.places.catalog import CATEGORIES, GROUP, GroupProfile
from app.places.prompt_safety import safe_places
from app.places.reasons import (
    PlaceReason,
    ReasonRow,
    gemini_reasons,
    ungrounded_numbers,
)
from app.places.scoring import score_place
from app.places.search import MAX_QUERY_CHARS, echoes_the_query, gemini_search

logger = logging.getLogger(__name__)

# How far «you are here» is allowed to reach. Beyond it the answer is «RuDi
# chưa biết chỗ bạn đang đứng», not the least-wrong city in the table: a
# suggestion two provinces away is worse than admitting the gap. Chosen to be
# generous enough that a caller on the edge of a city still matches it and
# small enough that two neighbouring destinations never both claim somebody.
NEAR_LIMIT_KM = 60.0

# How many places one read may ask the model about. A destination can hold a
# hundred imported rows and a reader looks at the first handful; the rest get
# the server's own template sentence, which is what an unanswered row gets
# anyway. Twelve because the seed catalogue is twelve: every existing test that
# expects a reason for every seed row still gets one.
MAX_REASON_ROWS = 12

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
    """One card. Since M9 most of it is optional, and that is the honest shape.

    OpenStreetMap gives a name, a point and a kind. It does not give a rating,
    a price band, opening hours or how long it takes to get there. Those fields
    are `None` for an imported place and the screen says «chưa có» -- a card
    that filled them with plausible numbers would be inventing facts about a
    business that exists. The twelve invented seed rows still carry all of
    them, which is why the types are optional rather than gone.
    """

    id: str
    name: str
    category: str
    kinds: list[str]
    rating: float | None
    rating_count: int | None
    distance_km: float | None
    #: Integer đồng, both ends. Money law 1 does not stop at the ledger: a
    #: price band that leaves this service fractional means a float reached a
    #: money value somewhere upstream.
    price_min_vnd: MoneyVnd | None
    price_max_vnd: MoneyVnd | None
    address: str | None
    #: `None` means «nobody told us», which is not the same as «closed».
    open_now: bool | None
    open_hours: str | None
    travel_minutes: int | None
    photo_count: int
    traits: list[str]
    group_fit: GroupFit | None
    flag: Literal["new", "hot"] | None
    lat: float
    lng: float
    #: Where the row came from, so a screen can name its source. ODbL requires
    #: attribution for `osm`, and a reader deserves it for anything else.
    source: Literal["seed", "osm", "curated"] = "seed"
    license: str | None = None
    match: Match


class Review(BaseModel):
    author: str
    rating: float
    body: str


class PlaceDetail(Place):
    """F10. One place, everything the detail screen draws.

    Extends `Place` rather than restating it so the two screens cannot drift:
    the grid card and the detail header read the same `match` block, computed by
    the same `_card`. A separate model here would be a second place for a score
    to be calculated, which is how one dinner ends up showing two numbers.

    `description` and `reviews` are the only additions, and they are the only
    two fields the list omits. Both live on the row now (M9): the twelve seed
    rows carry the prose `app/places/details.py` was written for, and an
    imported place carries none and says so with null rather than borrowing
    somebody else's description.

    Photos are represented by `photo_count`, inherited from `Place`, and there
    is deliberately no `photos` array: this product has no image store for
    venues, and a list of invented URLs would render as broken frames on the
    screen most likely to be opened first. `photos_available` says so out loud
    rather than leaving a client to infer it from an empty list.
    """

    description: str | None
    reviews: list[Review]
    photos_available: bool


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


class DestinationSummary(BaseModel):
    """One place people travel to, as a row the picker draws (M10)."""

    id: str
    name: str
    province: str | None
    blurb: str | None
    lat: float
    lng: float
    #: Straight-line kilometres from a caller who sent coordinates, else null.
    #: Rounded to one decimal: the number is «which city am I in», and any more
    #: precision would be repeating back a position we promised not to keep.
    distance_km: float | None = None


class DestinationsResponse(BaseModel):
    destinations: list[DestinationSummary]
    #: Present only when the caller sent coordinates: the nearest destination,
    #: or null when the nearest one is further away than `NEAR_LIMIT_KM`.
    #: Null is «bạn đang ở ngoài vùng RuDi biết», which the screen must say
    #: rather than silently choosing a city hundreds of kilometres away.
    nearest: DestinationSummary | None = None


class PlacesResponse(BaseModel):
    places: list[Place]
    categories: list[Category]
    group: GroupSummary
    #: Which destination these places are from. Always present: a catalogue
    #: spanning fifteen cities cannot be shown as one list, so the route always
    #: picks one, and saying which is how the screen can name it and let
    #: somebody change it.
    destination: DestinationSummary


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

# How long a row the model would not answer is left alone before asking again.
# One minute, matching the windows in `app/api/search_rate_limit.py`, and the
# same trade for the same reason: long enough that a permanently unanswerable
# row costs a call a minute instead of a call a request, short enough that a
# model outage clears within a minute of the model coming back.
REASON_RETRY_COOLDOWN_SECONDS = 60


class CachedReasonWriter:
    """Call Gemini once per place, not once per *failed* place per request.

    The seed catalogue and the group profile are both fixed, so a reason is a
    pure function of data that does not change while the process lives. Caching
    it keeps a demo from spending a model call -- and two seconds of someone's
    attention -- every time a tab is opened.

    A row that failed is still retried, because the alternative is worse: a
    Gemini blip during startup must not leave the catalogue permanently
    unlabelled. What changed is *how often*. Caching successes only made "asked
    and got nothing" indistinguishable from "never asked", so a row the model
    will not answer was re-asked on every single request, for the life of the
    process. Three files had already written the old bound down as a safety
    property -- "one call per place per process" -- and used it to argue this
    route needed no ceiling. Measured on `d4bf672`: true when every row
    answers, and false the moment one does not, at 25 model calls for 25
    requests.

    That is not an outage-only path. `parse_reasons` drops a reason whose
    figures are not grounded in the place record, deliberately, and
    `tests/places/test_reasons_batch_robustness.py` measured roughly one first
    load in ten arriving with reasons missing. One ungrounded row in a
    twelve-place catalogue re-armed the whole batch every time.

    It matters here more than it would elsewhere because `GET /places` is the
    only model-spending route in this service with no actor at all: the five
    metered routes key their window on one and `POST /places/search` has
    required one since rd-be-13. An unbounded retry behind an anonymous GET is
    a `while true; do curl; done` pointed at the shared, paid key.

    The ceiling is per place per cooldown, including across threads. The lock
    is dropped before the model call -- holding it across a network round trip
    would serialise every browse behind one -- so the first version of this
    fix bounded requests *in sequence* and nothing else: measured on 78b8148,
    twenty callers in sequence bought one model call and twenty callers at the
    same time bought twenty. Sync routes run in a threadpool, so concurrent is
    what a browser fleet, or `-P 20` on the `while true; do curl; done` this
    docstring uses as its threat, gets for free. `_asking` is what closes it.

    Refusal degrades rather than raising. A suppressed row loses its AI label
    for a minute; the rows that did answer keep theirs, and the route keeps
    serving scores -- which is what `list_places` already does when the writer
    fails outright.

    A caller that arrives while another thread is mid-question degrades the
    same way, and this is a real cost, not a free win: on a cold catalogue,
    nineteen of twenty simultaneous first loads render without AI labels
    rather than waiting on the one call in flight. That is the deliberate
    trade -- the alternative is every browse request queued behind a two
    second model round trip, which is the thing the lock is dropped to avoid.
    The next request after it lands is served from `_answered`.

    Instance state, not module state, and for the reason `build_search_limiter`
    gives at length in the same codebase: a process-wide dict outlives the app
    that owns it, so a suite sharing one has a colour that depends on execution
    order. `create_app` builds one; production builds the app once, so
    production still has exactly one.
    """

    def __init__(
        self,
        *,
        writer: Callable[[list[ReasonRow], GroupProfile], dict[str, PlaceReason]] = (
            gemini_reasons
        ),
        group: GroupProfile = GROUP,
        cooldown_seconds: int = REASON_RETRY_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._writer = writer
        self._group = group
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._answered: dict[str, PlaceReason] = {}
        # Place id -> when we last asked and were given nothing. Successes are
        # never in here; an entry is the record that makes a refusal different
        # from a question nobody has asked yet.
        self._refused_at: dict[str, float] = {}
        # Place ids with a model call in flight right now. The lock is dropped
        # before that call on purpose, so without this set two threads both
        # find a row missing and both pay for it: the ceiling would be one
        # call per place per *serial* request, and `curl -P 20` at the
        # anonymous GET would buy twenty. Nothing above records an in-flight
        # question, because a question nobody has finished asking is neither
        # answered nor refused.
        self._asking: set[str] = set()
        # Sync routes run in a threadpool, so two concurrent browsers are two
        # real threads reading and writing these dicts.
        self._lock = threading.Lock()

    def __call__(self, rows: list[ReasonRow]) -> dict[str, PlaceReason]:
        now = self._clock()
        with self._lock:
            missing = [
                row
                for row in rows
                if row.place["id"] not in self._answered
                and row.place["id"] not in self._asking
                and self._may_ask(row.place["id"], now)
            ]
            self._asking.update(row.place["id"] for row in missing)

        if missing:
            # Outside the lock: this is the network call, and holding a lock
            # across it would serialise every browse request behind one model
            # round trip.
            fresh: dict[str, PlaceReason] = {}
            try:
                fresh = self._writer(missing, self._group)
            finally:
                # `finally`, not the success path. A writer that raises has
                # still spent the call, so its rows go on the cooldown like
                # any other row the model gave nothing for -- `fresh` is still
                # empty, so the loop below records them all as refused. And
                # they must be released from `_asking` either way, or a single
                # raise makes them unaskable for the life of the process: a
                # tombstone, which is the failure the cooldown exists to
                # avoid. `gemini_reasons` documents that it never raises, but
                # the writer is an injected seam and `list_places` wraps the
                # call in `except Exception`, so a raising one degrades in
                # silence.
                with self._lock:
                    self._answered.update(fresh)
                    for row in missing:
                        place_id = row.place["id"]
                        if place_id in fresh:
                            self._refused_at.pop(place_id, None)
                        else:
                            self._refused_at[place_id] = now
                    self._asking.difference_update(row.place["id"] for row in missing)

        with self._lock:
            return {
                row.place["id"]: self._answered[row.place["id"]]
                for row in rows
                if row.place["id"] in self._answered
            }

    def _may_ask(self, place_id: str, now: float) -> bool:
        """Caller holds the lock."""

        refused_at = self._refused_at.get(place_id)
        return refused_at is None or now - refused_at >= self._cooldown_seconds


def get_reason_writer(request: Request):
    """Seam for tests, resolving the one object `create_app` built.

    Read off the application for the same reason `get_search_rate_limiter` is:
    a writer built per request remembers nothing, which is a cache-shaped
    object that caches nothing and a cooldown that never cools.
    """

    return request.app.state.reason_writer


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

    manh: list[str] = []
    low = place.get("price_min_vnd")
    high = place.get("price_max_vnd")
    if low is not None and high is not None:
        low_k, high_k = low // 1000, high // 1000
        band = f"{low_k}k" if low_k == high_k else f"{low_k}–{high_k}k"
        manh.append(f"Khoảng {band}/người")
    if place.get("distance_km") is not None:
        manh.append(f"cách {place['distance_km']}km")
    # An imported place may have none of these, and the sentence has to work
    # without them rather than printing «Khoảng Nonek/người, cách Nonekm».
    dau = ", ".join(manh) + ". " if manh else "Chưa có giá và khoảng cách cho chỗ này. "
    return (
        f"{dau}"
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


def _destination_summary(
    row: DestinationRecord, distance_km: float | None = None
) -> DestinationSummary:
    return DestinationSummary(
        id=row.id,
        name=row.name,
        province=row.province,
        blurb=row.blurb,
        lat=row.lat,
        lng=row.lng,
        distance_km=distance_km,
    )


@router.get("/destinations", response_model=DestinationsResponse)
def list_destinations(
    repository: Annotated[ApiRepository, Depends(get_repository)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> DestinationsResponse:
    """Where RuDi knows places, and which one the caller is standing in (M10).

    `lat`/`lng` are used **inside this call and nowhere else** (ADR-0018): no
    column stores them, no cache holds them, no log line prints them, and the
    response does not echo them back. What comes back is a city name and a
    rounded distance -- the answer to «which city am I in», which is the only
    question the product asked.

    Sending only one of the two is a caller bug rather than a half-answer, so
    it is a 422: a screen that asked for a position and got half of one should
    say so rather than quietly show a list ordered by nothing.

    The nearest destination is `null` when the closest one is beyond
    `NEAR_LIMIT_KM`. Somebody in Cà Mau is not «in Cần Thơ» because Cần Thơ is
    the closest row we happen to have.
    """

    if (lat is None) != (lng is None):
        raise ApiProblem(
            422, "coordinates_incomplete", "Cần cả lat và lng, hoặc không gửi gì."
        )

    rows = repository.list_destinations()
    if lat is None or lng is None:
        return DestinationsResponse(
            destinations=[_destination_summary(row) for row in rows], nearest=None
        )

    khoang_cach = [(haversine_km(lat, lng, row.lat, row.lng), row) for row in rows]
    khoang_cach.sort(key=lambda pair: (pair[0], pair[1].id))
    gan_nhat = None
    if khoang_cach and khoang_cach[0][0] <= NEAR_LIMIT_KM:
        gan_nhat = _destination_summary(khoang_cach[0][1], round(khoang_cach[0][0], 1))
    return DestinationsResponse(
        destinations=[
            _destination_summary(row, round(km, 1)) for km, row in khoang_cach
        ],
        nearest=gan_nhat,
    )


@router.get("/places", response_model=PlacesResponse)
def list_places(
    reason_writer: Annotated[Any, Depends(get_reason_writer)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    context_id: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    destination: Annotated[str | None, Query()] = None,
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

    service = ApiService(repository)
    # One city at a time (M10). A catalogue that spans fifteen destinations is
    # not a list; asking for «places» without saying where is a question with
    # no answer, so the route picks the first destination and says which one it
    # picked rather than serving two thousand rows or an empty screen.
    diem_den = service.destination_or_default(destination)
    if diem_den is None:
        raise ApiProblem(
            404, "destination_not_found", "Không có điểm đến nào với mã này."
        )

    selected = [
        place
        for place in service.place_rows(destination_id=diem_den.id)
        if (category is None or place["category"] == category)
        and _matches(q or "", place)
    ]

    # Only rows that are safe to show a model (M9, ADR-0017). A place whose
    # name or traits talk to the model is dropped from the prompt, not quoted
    # more carefully: it still appears on screen, with no AI sentence.
    #
    # And only the top of the list (M10). A destination can hold a hundred
    # imported places; asking the model about all of them would put fifteen
    # kilobytes of catalogue in one prompt on every read, to write sentences
    # for cards nobody scrolls to. The rows chosen are the ones the reader sees
    # first, ranked by the same arithmetic that orders the screen -- so the cap
    # never silently drops a card that would have been at the top.
    xep = sorted(
        safe_places(selected),
        key=lambda place: (-score_place(place, GROUP)[0], place["id"]),
    )
    rows = [ReasonRow(place=place) for place in xep[:MAX_REASON_ROWS]]
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
    # `open_now` and `rating` are nullable since M9: OpenStreetMap gives
    # neither. An unknown door is not an open one (it sorts with the closed
    # tier rather than ahead of a place known to be open), and an unrated place
    # sorts after a rated one at equal score instead of being ranked as zero.
    out.sort(
        key=lambda place: (
            place.open_now is not True,
            -place.match.score,
            -(place.rating if place.rating is not None else -1.0),
            place.id,
        )
    )

    return PlacesResponse(
        places=out,
        categories=[Category(**category_row) for category_row in CATEGORIES],
        group=GroupSummary(**GROUP),
        destination=_destination_summary(diem_den),
    )


@router.get(
    "/places/{place_id}",
    response_model=PlaceDetail,
    responses={404: {"description": "Không có địa điểm nào với mã này."}},
)
def get_place(
    place_id: str,
    reason_writer: Annotated[Any, Depends(get_reason_writer)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> PlaceDetail:
    """F10 -- one place, scored by the same arithmetic the grid used.

    404 here and 200-with-an-empty-list on `GET /places` are not inconsistent.
    A category nobody has used yet is a real query with an empty answer; a place
    id that resolves to nothing is a request for a specific row that does not
    exist, and answering it with a blank screen would leave a caller unable to
    tell "no such place" from "this place has no details".

    Declared above `POST /places/search` and does not shadow it. Starlette scans
    routes in order, and a route whose path matches but whose method does not is
    a *partial* match: it is remembered as a candidate 405 and the scan
    continues, so the later full match still wins. `GET /places/search` has no
    full match anywhere and lands here as `place_id="search"`, answering 404 --
    the right answer for a path with no GET. The wiring test pins both.

    No actor. The catalogue is the same public rows for everybody, this
    handler reads no group data and takes no identity, so there is nothing here
    to authorise -- exactly the position `GET /places` is in. The metering
    argument that put `get_actor` on `/places/search` does not apply either: a
    reason is memoised per place per process, so a loop against this route costs
    one model call in total, not one per request.
    """

    place = ApiService(repository).place_row(place_id)
    if place is None:
        raise ApiProblem(404, "place_not_found", "Không tìm thấy địa điểm này.")

    # Same failure posture as the list: a model outage must not turn a
    # read-only catalogue row into a 500.
    try:
        written = reason_writer([ReasonRow(place=place)])
    except Exception:  # noqa: BLE001
        written = {}
    reason = written.get(place["id"])

    card = _card(
        place,
        reason.reason if reason else None,
        reason.verdict if reason else None,
    )
    return PlaceDetail(
        **card.model_dump(),
        description=place.get("description"),
        reviews=list(place.get("reviews") or []),
        photos_available=False,
    )


@router.post("/places/search", response_model=PlaceSearchResponse)
def search_places(
    request: PlaceSearchRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_search_rate_limiter)],
    place_searcher: Annotated[Any, Depends(get_place_searcher)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
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

    rows = safe_places(ApiService(repository).place_rows())
    try:
        raw = place_searcher(query, rows)
    except Exception as error:  # noqa: BLE001 - a search box must not 500 on this
        logger.warning("place search: searcher failed (%s)", type(error).__name__)
        return unavailable
    if raw is None:
        return unavailable

    try:
        grounded = ground_search(raw, rows, CATEGORIES)
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
            logger.warning(
                "place search: dropped ungrounded reason for %s", place["id"]
            )
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
