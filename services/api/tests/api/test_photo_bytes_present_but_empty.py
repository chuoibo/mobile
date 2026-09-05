"""Bytes that are gone and bytes that are empty must answer the same way.

## What this file locks down

`qa2-062305` (#434) walked the two routes that hand image bytes to a client
through eight ways the picture behind a record can be missing or wrong, and
found one pair that disagreed for no reason a caller could act on:

  B  the row is there, the file was deleted   -> ``404``, a refusal
  D  the row is there, the file is 0 bytes    -> ``200``, ``image/jpeg``, no body

Both mean the same thing to whoever asked: the ledger lists a photograph and
storage cannot produce it. ``200`` with an empty body is not a thinner answer
than ``404``, it is a **wrong** one -- it says "here is your picture" and then
hands over nothing. The client measurement in that PR followed it the rest of
the way: `taiAnhCoQuyen` treats every 2xx as success, mints a ``blob:`` URL over
zero bytes, the browser fires ``error``, and the screen falls back to the same
placeholder it shows for a group that has no photos at all. No message, no
retry, no log line -- on either side. That silence is the defect; the status
code is only where it starts.

The decision recorded on #434 was to make D answer exactly what B answers.

## Why each case asserts "same as B" rather than a literal code string

The two routes do not share a not-found code: photos raise `photo_not_found`,
avatars raise `avatar_not_found`. Pinning both to one literal would give the
avatar route a code its own B condition does not use, splitting D from B on that
route -- which is the exact shape the decision removes. So every case asserts
that D is indistinguishable from B **on its own route**: same status, same body,
byte for byte. That is the property that was decided, stated as an assertion
instead of as two hard-coded strings that can drift apart later.

## Why H is here

Without the healthy control, a stack that answers 404 to everything -- a broken
fixture, a route that never gets reached, a permission gate closing early --
passes B and D and proves nothing at all.

## Why the route list is derived from the tree, not typed out here

`ROUTES` below is checked against a list built by walking the AST of
`app/api/routes/` for `Response(content=...)`, which is the same unit qa2 used
to find that there are exactly two such routes. A hand-written list cannot
notice a third byte-serving route being added next month; a derived one goes red
and names the function nobody covered. Counting by a shape the code cannot
rename is the lesson #437 paid for tonight.

## What this file does NOT prove

Nothing here says a *user* can reach condition D. #434 measured that separately
and found they cannot: every input the upload door accepts lands more than zero
bytes on disk, and a write killed halfway under a real ``RLIMIT_FSIZE`` ceiling
leaves nothing behind at all. D arrives from outside the product -- a restore
that stopped early, a copied volume, a filesystem that lost a tail. The reason
to answer it correctly is that the product cannot tell which of those happened,
not that a caller can cause it.

Condition E -- a file with the wrong number of bytes in it, junk rather than an
image -- is deliberately **not** asserted here. It still answers ``200``. No
decision has been made about it, and inventing one inside a regression file is
how a gate ends up enforcing something nobody agreed to.
"""

from __future__ import annotations

import ast
import pathlib
import uuid

import pytest

from app.api.deps import get_photo_storage, get_repository
from app.api.main import create_app
from app.media.storage import PhotoStorage

from .conftest import SeedCatalogueReads, ASGITestClient

CONTEXT_ID = uuid.UUID("1aa00000-aaaa-4aaa-8aaa-0000a0000434")
PHOTO_ID = uuid.UUID("2bb00000-bbbb-4bbb-8bbb-0000b0000434")
#: A catalogue key, not a UUID: place ids are text (M9).
PLACE_ID = "p-tiem-nuong-xom-lao"
MEMBER_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000434")
SUBJECT_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000434")

STORAGE_KEY = "0123456789abcdef0123456789abcdef"
HEALTHY_BYTES = b"\xff\xd8\xff\xe0" + b"pretend-this-decodes" * 8
HEADERS = {"X-Actor-ID": str(MEMBER_ID), "X-Actor-Roles": "member"}

ROUTES_DIR = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "routes"


class StoredImage:
    """The record the ledger keeps, including the size it believes is on disk."""

    storage_key = STORAGE_KEY
    content_type = "image/jpeg"
    byte_size = len(HEALTHY_BYTES)


class StubRepository(SeedCatalogueReads):
    """Everyone asking is a member, so no case can go green on a refusal.

    A permission answer arriving before the storage read would satisfy every
    404 assertion here while proving nothing about the bytes, which is why the
    positive control matters as much as the two failure rows.
    """

    def is_member(self, context_id, person_id):
        del context_id, person_id
        return True

    def shares_active_context(self, actor_id, person_id):
        del actor_id, person_id
        return True

    def get_context_image(self, context_id, image_id):
        del context_id, image_id
        return StoredImage()

    def get_latest_avatar(self, person_id):
        del person_id
        return StoredImage()

    def get_place_photo(self, place_id, photo_id):
        """A licensed place photograph whose file storage cannot produce (M12).

        The third byte-serving route joined the product with the same two
        conditions as the first two: the row is there and the file is gone, or
        the row is there and the file is empty. Nothing about the picture being
        public changes what «here is your picture» over zero bytes does to the
        screen that receives it.
        """
        del place_id, photo_id
        return StoredImage()


# Keyed by the route function name so the keys of this table ARE the coverage
# claim the derived-list case below checks. One source, not two.
#
# `not_found_code` is written out per route on purpose. It pins B, the reference
# answer -- and B has to be pinned to something outside itself, because "D says
# what B says" survives a change that moves BOTH of them onto the wrong code.
# Measured, not assumed: giving the avatar route `photo_not_found` left this
# file 5/5 green until this table started asserting the code as well.
ROUTES: dict[str, dict[str, str]] = {
    "read_context_photo": {
        "path": f"/contexts/{CONTEXT_ID}/photos/{PHOTO_ID}",
        "not_found_code": "photo_not_found",
    },
    "read_person_avatar": {
        "path": f"/people/{SUBJECT_ID}/avatar",
        "not_found_code": "avatar_not_found",
    },
    "read_place_photo": {
        "path": f"/places/{PLACE_ID}/photos/{PHOTO_ID}",
        "not_found_code": "photo_not_found",
    },
}


def _byte_serving_route_functions() -> dict[str, int]:
    """Every route function that hands raw bytes back to a caller.

    Walks for `Response(content=...)` under `app/api/routes/` -- the unit qa2
    used -- and maps each hit back to the enclosing function. Derived rather
    than typed so that route number three cannot arrive uncovered and silent.
    """

    found: dict[str, int] = {}
    for source_file in sorted(ROUTES_DIR.glob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                if not isinstance(inner.func, ast.Name) or inner.func.id != "Response":
                    continue
                if any(keyword.arg == "content" for keyword in inner.keywords):
                    found[node.name] = inner.lineno
    return found


@pytest.fixture
def storage(tmp_path) -> PhotoStorage:
    return PhotoStorage(tmp_path)


@pytest.fixture
def client(storage) -> ASGITestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: StubRepository()
    app.dependency_overrides[get_photo_storage] = lambda: storage
    return ASGITestClient(app)


def _stored_file(storage: PhotoStorage) -> pathlib.Path:
    return storage.root / STORAGE_KEY[:2] / STORAGE_KEY[2:4] / STORAGE_KEY


def test_the_covered_routes_are_the_ones_that_actually_serve_bytes():
    """The table above must match what the tree does, or coverage is a guess."""

    served = _byte_serving_route_functions()
    assert set(served) == set(ROUTES), (
        "Routes emitting `Response(content=...)` and the routes covered by this "
        f"file have drifted apart. Found in the tree: {sorted(served)}. Covered "
        f"here: {sorted(ROUTES)}. A new byte-serving route needs a row in "
        "ROUTES and a path to reach it -- deleting this assertion is not the fix."
    )


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_h_a_healthy_photo_still_arrives(client, storage, route):
    """The positive control: without it the two rows below prove nothing."""

    storage.write(STORAGE_KEY, HEALTHY_BYTES)

    response = client.get(ROUTES[route]["path"], headers=HEADERS)

    assert response.status_code == 200, response.text
    assert response.content == HEALTHY_BYTES


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_d_a_zero_byte_file_answers_exactly_what_a_missing_file_answers(
    client, storage, route
):
    """Condition D of #434, asserted against condition B on the same route."""

    path = ROUTES[route]["path"]

    # B first: the file storage lost entirely. This is the reference answer,
    # read from the running route rather than written down as a literal, so the
    # two conditions cannot drift apart in a later edit. Its code is pinned
    # separately -- see the note on ROUTES for the mutation that needed it.
    storage.write(STORAGE_KEY, HEALTHY_BYTES)
    _stored_file(storage).unlink()
    missing = client.get(path, headers=HEADERS)
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == ROUTES[route]["not_found_code"], missing.text

    # D: the file is present and empty. `write` is the product's own writer, so
    # this is a real zero-byte file on disk, not a stubbed `read` returning b"".
    storage.write(STORAGE_KEY, b"")
    assert _stored_file(storage).stat().st_size == 0

    empty = client.get(path, headers=HEADERS)

    assert empty.status_code == missing.status_code, (
        f"{route}: a zero-byte file answered {empty.status_code} where a deleted "
        f"file answers {missing.status_code}. Body was {empty.content!r}."
    )
    assert empty.content == missing.content, (
        f"{route}: a zero-byte file and a deleted file are the same situation "
        "for the caller, so they must be the same answer. Got "
        f"{empty.content!r} versus {missing.content!r}."
    )
