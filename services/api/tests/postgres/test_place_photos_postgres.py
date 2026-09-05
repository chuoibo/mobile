"""Licensed place photographs on a real database (M12, ADR-0017).

What only PostgreSQL can show: the CHECK that refuses a row which cannot name
its author, licence and source; the unique that makes a second import a no-op
instead of a second copy; the foreign key to a catalogue row; and the route
serving bytes with a public cache header, since these pictures are public in a
way group photographs never are.
"""

from __future__ import annotations

import importlib.util
import pathlib
import uuid

import anyio
import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_photo_storage, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import Destination, Place, PlacePhoto
from app.media.storage import PhotoStorage

pytestmark = pytest.mark.postgres


def _importer():
    """Load `scripts/import_place_photos.py` as a module.

    By path because it is a script, not a package -- and it is worth the
    awkwardness: the rule about which places may carry a photograph is a claim
    about rows, so the test that proves it has to run the importer's own query
    against real rows, not read the file and hope."""

    duong = (
        pathlib.Path(__file__).resolve().parents[4]
        / "scripts"
        / "import_place_photos.py"
    )
    spec = importlib.util.spec_from_file_location("import_place_photos", duong)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOT_ANH_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff03000006"
    "0005a3b7c1000000004945454e44ae426082"
)


def _app(session: Session, storage: PhotoStorage):
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    app.dependency_overrides[get_photo_storage] = lambda: storage
    return app


def _get(app, path: str):
    async def go():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.get(path)

    return anyio.run(go)


def _diem_den(session: Session) -> str:
    """A destination for the place to belong to: `places.destination_id` is
    NOT NULL, because a place nobody can say the city of is not a place this
    catalogue can serve (M10)."""

    row = Destination(
        id=f"d-thu-{uuid.uuid4().hex[:8]}",
        name="Thành phố thử",
        lat=11.94,
        lng=108.44,
        bbox_south=11.9,
        bbox_west=108.4,
        bbox_north=12.0,
        bbox_east=108.5,
    )
    session.add(row)
    session.flush()
    return row.id


def _place(session: Session) -> Place:
    row = Place(
        id=f"p-anh-{uuid.uuid4().hex[:8]}",
        destination_id=_diem_den(session),
        name="Quán thử",
        category="cafe",
        kinds=["Cà phê"],
        traits=[],
        lat=11.94,
        lng=108.44,
        source="seed",
    )
    session.add(row)
    session.flush()
    return row


def _photo(place_id: str, **overrides) -> PlacePhoto:
    truong = {
        "id": uuid.uuid4(),
        "place_id": place_id,
        "storage_key": uuid.uuid4().hex,
        "content_type": "image/png",
        "byte_size": len(MOT_ANH_PNG),
        "width": 1,
        "height": 1,
        "author": "Nguyễn A",
        "license": "CC BY-SA 4.0",
        "source_url": f"https://commons.wikimedia.org/wiki/File:{uuid.uuid4().hex}",
        "title": None,
        "sort_order": 0,
    }
    truong.update(overrides)
    return PlacePhoto(**truong)


def test_a_photograph_that_cannot_name_its_source_is_refused(postgres_session):
    """The rule ADR-0017 promises, in the one place that cannot be bypassed.

    Filtering on the way out would have been easier and is exactly what gets
    forgotten: one new read path, one screen, and an unattributed picture is
    on somebody's phone.
    """

    place = _place(postgres_session)
    for truong in ({"author": "   "}, {"license": ""}, {"source_url": " "}):
        with pytest.raises(IntegrityError):
            postgres_session.add(_photo(place.id, **truong))
            postgres_session.flush()
        postgres_session.rollback()
        place = _place(postgres_session)


def test_the_same_file_cannot_be_imported_twice(postgres_session):
    place = _place(postgres_session)
    url = "https://commons.wikimedia.org/wiki/File:Same"
    postgres_session.add(_photo(place.id, source_url=url))
    postgres_session.flush()
    postgres_session.add(_photo(place.id, source_url=url))
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_a_photograph_needs_a_place_that_exists(postgres_session):
    postgres_session.add(_photo("p-khong-co-that"))
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_the_gallery_and_the_bytes_come_back_over_http(postgres_session, tmp_path):
    place = _place(postgres_session)
    storage = PhotoStorage(tmp_path)
    photo = _photo(place.id)
    storage.write(photo.storage_key, MOT_ANH_PNG)
    postgres_session.add(photo)
    postgres_session.flush()

    app = _app(postgres_session, storage)
    gallery = _get(app, f"/places/{place.id}/photos")
    assert gallery.status_code == 200, gallery.text
    body = gallery.json()
    assert [row["author"] for row in body["photos"]] == ["Nguyễn A"]

    bytes_response = _get(app, body["photos"][0]["url"])
    assert bytes_response.status_code == 200, bytes_response.text
    assert bytes_response.content == MOT_ANH_PNG
    assert bytes_response.headers["content-type"] == "image/png"
    # Public, unlike a group's photograph: this is a licensed picture of a
    # public place, and saying so in the header is how a proxy knows too.
    assert "public" in bytes_response.headers["cache-control"]


def test_the_bytes_route_needs_no_session(postgres_session, tmp_path):
    """A licensed photograph of a public place is public. What a session would
    gate here is a picture anybody may look at, while doing nothing about the
    private half -- group photographs, which live in another table entirely."""

    place = _place(postgres_session)
    storage = PhotoStorage(tmp_path)
    photo = _photo(place.id)
    storage.write(photo.storage_key, MOT_ANH_PNG)
    postgres_session.add(photo)
    postgres_session.flush()
    app = _app(postgres_session, storage)
    assert _get(app, f"/places/{place.id}/photos/{photo.id}").status_code == 200


def test_a_synthetic_place_never_gets_a_real_photograph(postgres_session):
    """The 12 seed rows describe no real business, so a real photograph under
    one of their names is a lie in the shape of a photograph -- correct credit
    and all (ADR-0017 §4).

    Found on a machine, not in review: the first import run attached Wikimedia
    photographs of Đà Lạt to every one of those rows, because geosearch around
    a plausible coordinate returns real pictures of that street."""

    diem_den = _diem_den(postgres_session)
    chung = {
        "destination_id": diem_den,
        "name": "Quán thử",
        "category": "cafe",
        "kinds": ["Cà phê"],
        "traits": [],
        "lat": 11.94,
        "lng": 108.44,
    }
    bia = Place(id=f"p-seed-{uuid.uuid4().hex[:8]}", source="seed", **chung)
    that = Place(
        id=f"p-osm-{uuid.uuid4().hex[:8]}",
        source="osm",
        license="ODbL-1.0",
        source_ref=f"node/{uuid.uuid4().int % 10**7}",
        **chung,
    )
    postgres_session.add_all([bia, that])
    postgres_session.flush()

    duoc = list(postgres_session.scalars(_importer().cau_dia_diem_that(diem_den)))
    ids = {row.id for row in duoc}
    assert that.id in ids, "chỗ nhập từ OSM là chỗ có thật, phải được gắn ảnh"
    assert bia.id not in ids, "dòng seed là chỗ bịa, không được gắn ảnh thật"
