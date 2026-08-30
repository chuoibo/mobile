"""The ninth model door, and the first one that spends no paid quota.

`POST /contexts/{id}/photos/{id}/face-boxes` runs a Haar cascade in this
process. No API key is spent, which is exactly the argument somebody will make
for leaving it unmetered -- and it is wrong. What this window protects is the
box: `detectMultiScale` over a multi-megapixel photograph holds a threadpool
worker for tens to hundreds of milliseconds, and the caller has already passed
membership. A member looping this route is the cheapest denial of service in
the product, and the threads it starves are the ones the money routes need.

The case this file exists for beyond the ceiling itself is
`test_the_ninth_window_does_not_share_a_window_with_the_eighth`. Eight doors
already meter, and the cheapest way to "add" a ninth is to hand it an object
that already existed. Every ceiling assertion survives that -- each route alone
still stops somewhere -- while a burst of face detection silently consumes the
allowance for reading the group's chat.

What this file does NOT prove: that 30 is the right number, or that it survives
a second replica. The window is per process and in memory, so two API replicas
mean twice the ceiling and a restart forgives everyone. A blast-radius cap for
a single-box demo, not a quota -- the same limitation its sibling files state.
"""

from __future__ import annotations

import uuid

import pytest

from app.api.deps import get_face_detector, get_photo_storage, get_repository
from app.api.main import create_app
from app.api.routes.faces import get_face_detection_limiter
from app.api.search_rate_limit import (
    FACE_DETECTION_LIMIT_PER_WINDOW,
    FixedWindowLimiter,
)
from app.media.face_detection import Detection, PixelBox

from .conftest import ASGITestClient

CONTEXT_ID = uuid.UUID("1aa00000-aaaa-4aaa-8aaa-0000a0000022")
PHOTO_ID = uuid.UUID("2bb00000-bbbb-4bbb-8bbb-0000b0000022")
MEMBER_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000022")
OTHER_MEMBER_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000022")

HEADERS = {"X-Actor-ID": str(MEMBER_ID), "X-Actor-Roles": "member"}
PATH = f"/contexts/{CONTEXT_ID}/photos/{PHOTO_ID}/face-boxes"


class StubImage:
    storage_key = "0123456789abcdef0123456789abcdef"
    content_type = "image/png"


class StubRepository:
    """Enough of the protocol for this route, and nothing else.

    Everybody who asks is a member, so no case here can go green because the
    request was refused before reaching the detector -- which is the failure
    that would make an app with no ceiling at all look metered.
    """

    def is_member(self, context_id, person_id):
        del context_id, person_id
        return True

    def get_context_image(self, context_id, image_id):
        del context_id, image_id
        return StubImage()


class StubStorage:
    def read(self, key):
        del key
        return b"not-a-real-png-the-detector-is-stubbed-too"


class CountingDetector:
    """Records how often the cascade was actually reached."""

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, image: bytes) -> Detection:
        del image
        self.calls += 1
        return Detection(
            boxes=(PixelBox(x=10, y=10, width=20, height=20),),
            image_width=100,
            image_height=100,
        )


@pytest.fixture
def detector() -> CountingDetector:
    return CountingDetector()


@pytest.fixture
def client(detector, monkeypatch):
    import anyio

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: StubRepository()
    app.dependency_overrides[get_photo_storage] = lambda: StubStorage()
    app.dependency_overrides[get_face_detector] = lambda: detector
    return ASGITestClient(app)


@pytest.fixture
def metered(client):
    """A small ceiling so a burst is a handful of requests, not thirty."""

    limiter = FixedWindowLimiter(
        limit=3,
        window_seconds=60,
        code="face_detection_rate_limited",
        message="Quá nhiều lượt tìm khuôn mặt trong ảnh.",
    )
    client.app.dependency_overrides[get_face_detection_limiter] = lambda: limiter
    return limiter


def test_below_the_ceiling_every_request_reaches_the_detector(
    client, metered, detector
):
    """The control. Without it "refuse everything" would pass the file."""

    for _ in range(3):
        assert client.post(PATH, headers=HEADERS).status_code == 200

    assert detector.calls == 3


def test_a_burst_from_one_person_is_cut_off(client, metered):
    for _ in range(3):
        assert client.post(PATH, headers=HEADERS).status_code == 200

    assert client.post(PATH, headers=HEADERS).status_code == 429


def test_the_refused_request_never_runs_the_cascade(client, metered, detector):
    """A 429 raised after the CPU was spent is a limiter in name only."""

    for _ in range(3):
        client.post(PATH, headers=HEADERS)
    before = detector.calls

    assert client.post(PATH, headers=HEADERS).status_code == 429
    assert detector.calls == before


def test_a_refusal_names_this_route_and_not_a_neighbour(client, metered):
    for _ in range(3):
        client.post(PATH, headers=HEADERS)

    body = client.post(PATH, headers=HEADERS).json()

    assert body["code"] == "face_detection_rate_limited"
    # Naming the wrong feature tells a person to stop doing something they
    # were not doing. This class had the search wording hardcoded once.
    assert "khuôn mặt" in body["detail"]


def test_the_cut_off_is_per_person_not_a_switch_that_silences_the_group(
    client, metered
):
    for _ in range(3):
        client.post(PATH, headers=HEADERS)
    assert client.post(PATH, headers=HEADERS).status_code == 429

    other = {"X-Actor-ID": str(OTHER_MEMBER_ID), "X-Actor-Roles": "member"}
    assert client.post(PATH, headers=other).status_code == 200


def test_the_shipped_route_meters_without_any_test_installing_a_limiter(client):
    """The ceiling is a property of the app, not of this file's fixtures.

    Every case above overrides the limiter, so all of them would pass against
    a route that `create_app` wired to nothing.
    """

    for _ in range(FACE_DETECTION_LIMIT_PER_WINDOW):
        assert client.post(PATH, headers=HEADERS).status_code == 200

    assert client.post(PATH, headers=HEADERS).status_code == 429


def test_each_application_carries_its_own_face_window(client):
    """A module-level limiter makes a suite's colour depend on its order."""

    other = create_app()

    assert (
        client.app.state.face_detection_limiter
        is not other.state.face_detection_limiter
    )


def test_the_ninth_window_does_not_share_a_window_with_the_eighth(client):
    """F22 detection and the F33 chat card must not spend each other's budget.

    Spelled out as a spend rather than an identity comparison, because `is not`
    passes for two limiters that happen to be distinct objects while sharing a
    counter through some third thing. Here the ninth door is driven to its
    ceiling and the eighth is asked whether it noticed.
    """

    state = client.app.state
    face = state.face_detection_limiter
    contextual = state.contextual_suggestion_limiter

    for _ in range(FACE_DETECTION_LIMIT_PER_WINDOW):
        face.check(MEMBER_ID)
    with pytest.raises(Exception) as refused:
        face.check(MEMBER_ID)
    assert getattr(refused.value, "status_code", None) == 429

    # The eighth window, for the same person, is untouched.
    contextual.check(MEMBER_ID)
    assert contextual.tracked() == 1


def _state_windows(app) -> dict[str, FixedWindowLimiter]:
    """Every limiter `create_app` hung on the application, found by walking it.

    Starlette keeps `app.state` in a private `_state` dict, so `vars(app.state)`
    returns the wrapper rather than the contents -- an easy way to write a gate
    that inspects nothing and passes. The first draft of this file did exactly
    that and reported zero windows as a clean sweep.
    """

    inner = vars(app.state).get("_state", {})
    assert inner, "app.state exposed no contents -- this walk is measuring nothing"
    return {
        name: value
        for name, value in inner.items()
        if isinstance(value, FixedWindowLimiter)
    }


def test_every_window_the_app_builds_is_a_distinct_object(client):
    """Discovered from `app.state`, never listed by hand.

    Its ancestors in `test_companion_rate_limit.py` and
    `test_contextual_suggestion_rate_limit.py` enumerate the limiters they know
    about and assert a count. That shape is green by construction for any route
    added afterwards -- it is how F33 shipped unmetered, and adding this window
    would not have moved either of them.

    No absolute count here, deliberately. `#297` adds a window for
    `GET /places` on a branch this one has not merged, so a `== 9` would go red
    the day that lands, for a reason having nothing to do with F22 -- the
    two-green-PRs-one-red-main shape this repo has already paid for once. The
    property that matters is aliasing, and aliasing is countable without
    knowing how many doors exist.
    """

    windows = _state_windows(client.app)

    assert "face_detection_limiter" in windows, sorted(windows)
    assert len({id(limiter) for limiter in windows.values()}) == len(windows), (
        "two routes are sharing one counter: " + repr(sorted(windows))
    )


def test_every_route_that_depends_on_a_limiter_has_one_of_its_own(client):
    """The other half: a window nobody uses is not a metered route.

    Walks the route table for dependencies that resolve a `FixedWindowLimiter`
    off `app.state`, so a route wired to a *different* route's window fails
    here even though both objects exist and both look wired.
    """

    from fastapi.routing import APIRoute

    class FakeRequest:
        """Just enough of `Request` for a `request.app.state.x` getter."""

        def __init__(self, app):
            self.app = app

    resolved: dict[str, int] = {}
    for route in client.app.routes:
        if not isinstance(route, APIRoute):
            continue
        for dependency in route.dependant.dependencies:
            call = dependency.call
            if call is None or not getattr(call, "__name__", "").endswith("_limiter"):
                continue
            limiter = call(FakeRequest(client.app))
            assert isinstance(limiter, FixedWindowLimiter)
            resolved[f"{route.path}:{call.__name__}"] = id(limiter)

    assert resolved, "no route resolves a limiter -- the walk found nothing"
    assert any("face-boxes" in key for key in resolved), (
        "the F22 route resolves no limiter: " + repr(sorted(resolved))
    )
    # One counter per metered route. A shared id means one route's burst
    # refuses another route's caller.
    assert len(set(resolved.values())) == len(resolved), repr(resolved)
