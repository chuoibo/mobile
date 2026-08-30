"""Who may ask where the faces are, over real HTTP against real PostgreSQL.

F22 detection, the half of ADR-0011 that carries no identity. A rectangle is
not a biometric, so this feature has no consent question -- but it is still
derived from a photograph of real people, and "you may not see this picture"
has to mean "you may not see anything computed from it either". A route that
answered a stranger with the count and position of the faces in a group's
dinner photo would have leaked the shape of the evening while never returning
a pixel.

Why every assertion here counts records
---------------------------------------
`assert response.status_code == 404` passes against a 404 whose body is empty
and against a 404 that carries the whole detection. ADR-0011 requires the
count, so each refusal below asserts what the body does **not** contain as well
as what the status says, and the positive control asserts a specific non-zero
number so a "refuse everybody" bug cannot make the file green.

The detector is a fixed stub. What is under test is the door, and a case that
also depended on OpenCV's opinion of a generated PNG would go red for reasons
that have nothing to do with access control. That the shipped cascade actually
finds faces is a different claim, measured in
`tests/live/test_face_detection_local.py`.
"""

from __future__ import annotations

import io
import uuid

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.deps import get_face_detector, get_photo_storage, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)
from app.media.face_detection import Detection, PixelBox
from app.media.storage import PhotoStorage

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

# Three faces, at known places, so the positive control can assert a number
# rather than "something came back".
STUB_BOXES = (
    PixelBox(x=10, y=10, width=40, height=40),
    PixelBox(x=100, y=12, width=40, height=40),
    PixelBox(x=55, y=90, width=40, height=40),
)


class StubDetector:
    """A fixed answer, and a record of whether it was reached at all.

    `calls` is the assertion that matters for the refusals: a route that
    refuses *after* running the cascade has already spent the CPU, and on the
    guest path it would also have read another group's photograph off disk.
    """

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, image: bytes) -> Detection:
        del image
        self.calls += 1
        return Detection(boxes=STUB_BOXES, image_width=200, image_height=200)


def _png(width: int = 200, height: int = 200) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (180, 140, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def detector() -> StubDetector:
    return StubDetector()


@pytest.fixture
def app(postgres_session: Session, detector, tmp_path, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    storage = PhotoStorage(tmp_path)
    application = create_app()
    application.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(
        postgres_session
    )
    application.dependency_overrides[get_photo_storage] = lambda: storage
    application.dependency_overrides[get_face_detector] = lambda: detector
    return application


def _request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    return anyio.run(send)


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    # Deliberately over-credentialled. If this door opens it must not be
    # because the caller was missing a role.
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, owner: Person, name: str) -> Context:
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
    session.add(context)
    session.flush()
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=owner.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.ADMIN,
            joined_at=NOW,
        )
    )
    session.flush()
    return context


def _join(
    session: Session,
    context: Context,
    person: Person,
    state: MembershipState = MembershipState.ACTIVE,
) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=person.id,
            state=state,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    session.flush()


def _upload(app, context_id: uuid.UUID, actor_id: uuid.UUID) -> uuid.UUID:
    response = _request(
        app,
        "POST",
        f"/contexts/{context_id}/photos",
        headers=_headers(actor_id),
        files={"file": ("toi-thu-bay.png", _png(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


@pytest.fixture
def scene(app, postgres_session):
    """One group with a photo, one member, and one stranger outside it."""

    owner = _person(postgres_session, "Chủ nhóm")
    member = _person(postgres_session, "Thành viên")
    stranger = _person(postgres_session, "Người ngoài")
    context = _context(postgres_session, owner, "Nhóm ăn tối")
    _join(postgres_session, context, member)
    photo_id = _upload(app, context.id, owner.id)
    return {
        "owner": owner,
        "member": member,
        "stranger": stranger,
        "context": context,
        "photo_id": photo_id,
    }


def _boxes_path(context_id: uuid.UUID, photo_id: uuid.UUID) -> str:
    return f"/contexts/{context_id}/photos/{photo_id}/face-boxes"


# --- the positive control -------------------------------------------------
#
# Without this, "refuse everybody" would make every case below pass.


def test_a_member_gets_every_box_the_detector_found(app, scene, detector):
    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
        headers=_headers(scene["member"].id),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["boxes"]) == len(STUB_BOXES) == 3
    assert detector.calls == 1


def test_the_answer_carries_geometry_and_no_name(app, scene):
    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
        headers=_headers(scene["member"].id),
    )

    body = response.json()
    assert set(body) == {"photo_id", "boxes"}
    for box in body["boxes"]:
        assert set(box) == {"box_key", "x", "y", "width", "height"}

    # Nobody's id appears anywhere in the payload -- not the uploader's, not
    # the caller's, not a member's. Checked against the serialized bytes so a
    # nested field cannot hide from a key-by-key walk.
    raw = response.text
    for person in (scene["owner"], scene["member"], scene["stranger"]):
        assert str(person.id) not in raw


# --- the refusals, each asserting the record count ------------------------


def test_a_stranger_gets_no_boxes_at_all(app, scene, detector):
    """The failure this route exists to not have.

    A count and a layout of the faces in a group's dinner photo is a
    description of the evening, returned to somebody who may not see the
    picture it came from.
    """

    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
        headers=_headers(scene["stranger"].id),
    )

    assert response.status_code == 403
    body = response.json()
    assert "boxes" not in body
    # The count, not only the status: a 403 carrying the detection would pass
    # a status-only assertion.
    assert "face-1" not in response.text
    # And the cascade never ran, so the photograph was never read off disk.
    assert detector.calls == 0


def test_an_invited_person_is_not_yet_a_member(app, scene, postgres_session, detector):
    """The state that looks live: a row exists, `left_at` is NULL.

    An `is_member` that asked only "is there a membership row" answers yes
    here, and the `left` case below cannot catch that mistake.
    """

    invited = _person(postgres_session, "Được mời")
    _join(postgres_session, scene["context"], invited, MembershipState.INVITED)

    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
        headers=_headers(invited.id),
    )

    assert response.status_code == 403
    assert "boxes" not in response.json()
    assert detector.calls == 0


def test_someone_who_left_keeps_no_working_endpoint(
    app, scene, postgres_session, detector
):
    former = _person(postgres_session, "Đã rời nhóm")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=scene["context"].id,
            person_id=former.id,
            state=MembershipState.LEFT,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
            left_at=NOW,
        )
    )
    postgres_session.flush()

    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
        headers=_headers(former.id),
    )

    assert response.status_code == 403
    assert "boxes" not in response.json()
    assert detector.calls == 0


def test_a_guest_holding_no_actor_header_gets_nothing(app, scene, detector):
    """The `/g/{token}` audience reaches this app with no `X-Actor-ID` at all.

    A guest page is served to somebody outside every group, so the guest's
    reachability of this route is the widest possible door. There is no header
    they can obtain by holding a link.
    """

    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
    )

    assert response.status_code == 401
    assert "boxes" not in response.json()
    assert "face-1" not in response.text
    assert detector.calls == 0


def test_a_guest_token_is_not_an_actor_id(app, scene, detector):
    """And a token in the header is a malformed id, not a weaker identity.

    422 rather than 401, which is `get_actor`'s existing answer for a header
    that is not a UUID -- recorded here as the behaviour it is, not asserted
    into a shape this file would prefer. What matters is identical either way:
    no detection crosses the boundary and the cascade never runs.
    """

    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
        headers={"X-Actor-ID": "guest-token-abc123", "X-Actor-Roles": "member"},
    )

    assert response.status_code == 422
    assert "boxes" not in response.json()
    assert "face-1" not in response.text
    assert detector.calls == 0


def test_the_face_route_is_not_a_wider_door_than_the_photo_itself(app, scene):
    """The property that makes reusing `view_group_memories` load-bearing.

    Whatever the answer is for the bytes must be the answer for anything
    derived from them. If these two ever disagree, the derived route has become
    a way around the one it was derived from -- the exact failure the album
    entry in `permissions.py` was written about.
    """

    for person in (scene["member"], scene["stranger"]):
        photo = _request(
            app,
            "GET",
            f"/contexts/{scene['context'].id}/photos/{scene['photo_id']}",
            headers=_headers(person.id),
        )
        boxes = _request(
            app,
            "POST",
            _boxes_path(scene["context"].id, scene["photo_id"]),
            headers=_headers(person.id),
        )

        assert (photo.status_code < 400) == (boxes.status_code < 400), (
            f"{person.display_name}: photo {photo.status_code} "
            f"vs boxes {boxes.status_code}"
        )


def test_a_photo_belonging_to_another_group_is_not_reachable_by_relabelling(
    app, scene, postgres_session, detector
):
    """Membership in *some* group is not membership in the one that owns it.

    The caller here is a real, active member of their own group and points the
    path at their own context id while naming the other group's photo.
    """

    outsider = _person(postgres_session, "Thành viên nhóm khác")
    other_context = _context(postgres_session, outsider, "Nhóm khác")

    response = _request(
        app,
        "POST",
        _boxes_path(other_context.id, scene["photo_id"]),
        headers=_headers(outsider.id),
    )

    assert response.status_code == 404
    assert "boxes" not in response.json()
    assert "face-1" not in response.text
    assert detector.calls == 0


def test_nothing_about_the_detection_is_written_down(app, scene, postgres_session):
    """No table gains a row, so there is nothing retained to withdraw.

    This is what lets F22 detection ship while ADR-0011's identity half waits
    for a decision: a feature that stores nothing has no consent lifecycle.
    Counted across every table rather than checked table by table, so a
    detection cache added later fails here without anyone remembering to
    extend a list.
    """

    from sqlalchemy import text

    def snapshot() -> dict[str, int]:
        names = postgres_session.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
        ).all()
        return {
            name: postgres_session.scalar(text(f'SELECT count(*) FROM "{name}"'))  # noqa: S608
            for name in names
        }

    before = snapshot()
    response = _request(
        app,
        "POST",
        _boxes_path(scene["context"].id, scene["photo_id"]),
        headers=_headers(scene["member"].id),
    )
    assert response.status_code == 200
    postgres_session.flush()

    assert snapshot() == before
