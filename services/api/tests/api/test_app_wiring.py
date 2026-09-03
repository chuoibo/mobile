"""What ``create_app`` is responsible for: every router, and both middlewares.

Four branches grew a layer of this function at the same time -- the people
router, the idempotency middleware, the CORS middleware, and ``POST
/receipts/scan``, the step that turns a photograph of a bill into items. All
four edit the same twenty lines, so all four conflict with each other, and a
conflict resolved by keeping the wrong side is silent in a way no other test in
this suite catches: a router that stops being registered takes its own tests
down with it, and every remaining file still passes.

That is not hypothetical. ``/receipts/scan`` was written, reviewed, and then
absent from ``main`` -- the camera could take the photo and the model could read
it, with nothing in between. This file is the inventory to re-read whenever
those twenty lines are touched.

It asserts wiring, and only wiring. Whether each route behaves correctly is the
business of the file named after it.
"""

from __future__ import annotations

from contextlib import contextmanager

import anyio
import pytest

from app.api.cors import PreflightNoContentCORSMiddleware
from app.api.idempotency import IDEMPOTENCY_HEADER, REPLAY_HEADER, IdempotencyMiddleware
from app.api.main import create_app

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID, png_bytes
from .test_idempotency import InMemoryIdempotencyStore

# Every step the PoC demo walks, in order, plus the two reads it needs on the
# way. Written out as data rather than derived from the app, because deriving
# the expectation from the thing under test is how an empty list passes.
DEMO_PATH_ROUTES = {
    ("POST", "/contexts"),
    ("POST", "/contexts/{context_id}/members"),
    ("POST", "/memberships/{membership_id}/accept"),
    ("PUT", "/people/{person_id}"),
    ("POST", "/receipts/scan"),
    ("POST", "/expenses"),
    ("POST", "/expenses/{expense_id}/confirm"),
    ("POST", "/batches"),
    ("POST", "/batches/{batch_id}/publish"),
    ("GET", "/batches/{batch_id}/obligations"),
    # The two `/bank-recipients` steps left with the payment rail: the demo
    # walks as far as telling each person their share, and no further.
    ("GET", "/g/{token}"),
    ("POST", "/g/{token}/da-chuyen"),
    ("POST", "/obligations/{obligation_id}/confirm-receipt"),
}

PNG = png_bytes()
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}
KEY = "5ca11111-bbbb-4bbb-8bbb-0000b0000001"


def registered(app) -> set[tuple[str, str]]:
    found = set()
    for route in app.routes:
        for method in getattr(route, "methods", None) or ():
            if method != "HEAD":
                found.add((method, route.path))
    return found


class StubReader:
    """Stands in for the vision backend; counts how often it was reached."""

    def __init__(self):
        self.calls = 0

    def read(self, image: bytes, mime_type: str) -> dict:
        del image, mime_type
        self.calls += 1
        return {
            "document_type": "receipt",
            "items": [
                {"name": "Pepsi", "quantity_text": "2", "line_total_text": "28.000"}
            ],
            "total_text": "28.000",
            "confidence": 0.9,
        }


class TestRoutersAreRegistered:
    def test_receipt_scan_exists(self):
        """The link between the camera and the split. Absent from main once."""

        assert ("POST", "/receipts/scan") in registered(create_app())

    def test_no_step_of_the_demo_path_is_missing(self):
        missing = DEMO_PATH_ROUTES - registered(create_app())
        assert missing == set()


class TestMiddlewareOrder:
    """Order is not cosmetic here, so it is asserted rather than assumed.

    ``add_middleware`` prepends, so index 0 is outermost. CORS has to stay
    there: the idempotency layer answers three refusals by itself, before any
    route runs, and an answer that leaves the CORS layer unentered carries no
    allow-origin header. The browser then discards a 409 that said exactly what
    the person needed to hear and reports an opaque network failure instead.
    """

    def test_cors_is_outermost(self):
        assert create_app().user_middleware[0].cls is PreflightNoContentCORSMiddleware

    def test_idempotency_is_inside_cors(self):
        stack = [entry.cls for entry in create_app().user_middleware]
        assert stack.index(IdempotencyMiddleware) > stack.index(
            PreflightNoContentCORSMiddleware
        )


@pytest.fixture
def store():
    return InMemoryIdempotencyStore()


@pytest.fixture
def scan_client(monkeypatch, store):
    """The scan route with the real middleware above it and no database.

    ``create_app()`` would reach for PostgreSQL the moment a key arrives, which
    is a fact about this route worth stating out loud: it stores nothing itself,
    but a caller that sends a key makes it a database-backed request.
    """

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    # The policy is read when the app is built, so a value left in the
    # developer's environment would otherwise decide what these tests assert.
    monkeypatch.delenv("MOBILE_CORS_ALLOW_ORIGINS", raising=False)

    @contextmanager
    def factory():
        yield store

    # Imported here rather than at the top on purpose. On a tree where the
    # receipts branch is missing, this file's job is to say which route is gone
    # in an assertion; a module-level import of something that branch added
    # would turn that into a collection error naming a symbol instead.
    from app.api.deps import get_receipt_reader

    app = create_app(idempotency_store_factory=factory)
    reader = StubReader()
    app.dependency_overrides[get_receipt_reader] = lambda: reader
    client = ASGITestClient(app)
    client.reader = reader
    return client


def scan(client, *, key=None, content=PNG):
    headers = dict(HEADERS)
    if key is not None:
        headers[IDEMPOTENCY_HEADER] = key
    return client.post(
        "/receipts/scan",
        files={"image": ("bill.png", content, "image/png")},
        headers=headers,
    )


class TestScanUnderTheIdempotencyLayer:
    """A multipart upload has to survive the layer that buffers and replays it.

    The middleware drains the request body to fingerprint it, then hands the
    bytes back to the route. Every other write route it wraps sends JSON; this
    is the only one that sends an image, and a body that does not survive that
    round trip fails as "no file uploaded" rather than as anything about
    idempotency.
    """

    def test_a_scan_without_a_key_is_untouched(self, scan_client):
        assert scan(scan_client).status_code == 200

    def test_a_scan_with_a_key_still_reads_the_image(self, scan_client):
        assert scan(scan_client, key=KEY).status_code == 200

    def test_the_key_is_actually_reserved(self, scan_client, store):
        scan(scan_client, key=KEY)
        assert len(store.reservations) == 1

    def test_a_byte_identical_retry_replays_instead_of_calling_the_model(
        self, scan_client
    ):
        """Same key, same bytes: the answer comes back without a second call.

        Built by hand rather than through ``files=``, because httpx picks a
        fresh random multipart boundary per request -- see the test below.
        """

        body = (
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="image"; filename="bill.png"\r\n'
            b"Content-Type: image/png\r\n\r\n" + PNG + b"\r\n--boundary--\r\n"
        )
        headers = {
            **HEADERS,
            IDEMPOTENCY_HEADER: KEY,
            "Content-Type": "multipart/form-data; boundary=boundary",
        }
        first = scan_client.post("/receipts/scan", content=body, headers=headers)
        second = scan_client.post("/receipts/scan", content=body, headers=headers)

        assert first.status_code == 200
        assert second.json() == first.json()
        assert second.headers[REPLAY_HEADER] == "true"
        assert scan_client.reader.calls == 1


class TestTheScanRouteIsReachableFromABrowser:
    """The preflight the web build sends before it uploads anything.

    Answered by the CORS layer ahead of routing, so this passes whether or not
    the route exists -- it is here for the other half of the same conflict. Drop
    ``install_cors`` while resolving it and the browser's preflight reaches the
    router, which answers 405 for a method it has no route for, and the
    photograph never leaves the phone.
    """

    def test_preflight_for_a_scan_is_allowed(self, scan_client):
        response = scan_client.request(
            "OPTIONS",
            "/receipts/scan",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-actor-id",
            },
        )

        assert response.status_code == 204
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:8080"
        )


class TestReencodedRetryIsRefused:
    """Re-uploading the same photo under the same key is a 422, not a replay.

    Not a defect in the middleware: it fingerprints the body, and a multipart
    body re-encoded by the client is genuinely different bytes -- httpx and
    every browser pick a random boundary each time. It is a constraint that
    lands on whoever wires the camera to this route, and it is pinned here so
    they meet it as a test rather than as a refusal in front of a person who
    just took a photograph.

    Two ways out, both on the client: reuse the encoded body verbatim on
    retry, or mint a fresh key when the photo is genuinely being sent again.
    """

    def test_same_key_with_a_reencoded_body_is_refused(self, scan_client):
        first = scan(scan_client, key=KEY)
        second = scan(scan_client, key=KEY)

        assert first.status_code == 200
        assert second.status_code == 422
        assert second.json()["code"] == "idempotency_key_reuse"
