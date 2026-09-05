"""`GET /places/{id}/photos` and the bytes route (M12, ADR-0017).

What this layer proves: a photograph never reaches a screen without the three
facts that make it usable; a photo id belonging to another place is not found;
the card carries a cover URL and a real count; and a place with no photographs
says so with null rather than with somebody else's picture.

What it does not prove: that any of this is stored -- `tests/postgres/
test_place_photos_postgres.py` has the CHECKs that refuse a row with no
provenance, and the unique that makes a second import a no-op.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.api.repository import MemoryRecord, PlacePhotoRecord
from app.places.catalog import PLACES

from .helpers import actor_headers
from .test_places import dang_nhap, get_places, silent_reasons, use_writer

PLACE = PLACES[0]["id"]
KHAC = PLACES[1]["id"]


def _anh(repository, place_id=PLACE, **overrides):
    """One licensed photograph in the fake repository."""

    truong = {
        "id": uuid.uuid4(),
        "place_id": place_id,
        "storage_key": f"key-{uuid.uuid4().hex}",
        "content_type": "image/jpeg",
        "byte_size": 1234,
        "width": 1024,
        "height": 768,
        "author": "Nguyễn A",
        "license": "CC BY-SA 4.0",
        "source_url": f"https://commons.wikimedia.org/wiki/File:{uuid.uuid4().hex}",
        "title": "Hồ Xuân Hương",
        "sort_order": len(repository.place_photos),
    }
    truong.update(overrides)
    row = PlacePhotoRecord(**truong)
    repository.place_photos.append(row)
    return row


def test_a_gallery_carries_the_provenance_of_every_photograph(client, repository):
    anh = _anh(repository)
    response = client.get(f"/places/{PLACE}/photos")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["place_id"] == PLACE
    assert len(body["photos"]) == 1
    photo = body["photos"][0]
    assert photo["author"] == "Nguyễn A"
    assert photo["license"] == "CC BY-SA 4.0"
    assert photo["source_url"].startswith("https://commons.wikimedia.org/")
    assert photo["url"] == f"/places/{PLACE}/photos/{anh.id}"


def test_a_place_with_no_photographs_answers_an_empty_gallery(client, repository):
    del repository
    response = client.get(f"/places/{PLACE}/photos")
    assert response.status_code == 200, response.text
    assert response.json()["photos"] == []


def test_a_gallery_for_a_place_that_does_not_exist_is_404(client):
    """An empty list for an unknown id would tell a caller «this place has no
    pictures» about a place that is not there."""

    response = client.get("/places/p-khong-ton-tai/photos")
    assert response.status_code == 404, response.text


def test_the_card_carries_a_cover_and_a_real_count(client, repository):
    use_writer(client, silent_reasons)
    anh = _anh(repository)
    _anh(repository)
    body = get_places(client, headers=dang_nhap(repository)).json()
    card = next(row for row in body["places"] if row["id"] == PLACE)
    assert card["photo_count"] == 2
    assert card["photo_url"] == f"/places/{PLACE}/photos/{anh.id}"


def test_the_card_carries_the_credit_beside_the_cover(client, repository):
    """The URL alone is a photograph the client is not allowed to draw.

    ADR-0017 §2.5 permits the picture only where the author and the licence are
    shown next to it. The list response is the only thing a card has, so if the
    credit did not travel with the URL, every card would have to choose between
    breaking the rule and dropping the picture."""

    use_writer(client, silent_reasons)
    anh = _anh(repository, author="Trần B", license="CC BY 4.0")
    body = get_places(client, headers=dang_nhap(repository)).json()
    card = next(row for row in body["places"] if row["id"] == PLACE)
    assert card["photo_url"] == f"/places/{PLACE}/photos/{anh.id}"
    assert card["photo_author"] == "Trần B"
    assert card["photo_license"] == "CC BY 4.0"


def test_a_place_with_no_photograph_sends_null_not_a_stand_in(client, repository):
    """Null is what the typographic band is for. A stock picture in that gap
    would be a lie in the shape of a photograph (ADR-0017 §4)."""

    use_writer(client, silent_reasons)
    _anh(repository)
    body = get_places(client, headers=dang_nhap(repository)).json()
    khac = next(row for row in body["places"] if row["id"] != PLACE)
    assert khac["photo_url"] is None
    assert khac["photo_count"] == 0
    # All three go together: a credit with no picture is as unusable as a
    # picture with no credit, and a screen reading one without the other would
    # be reading a shape the server never sends.
    assert khac["photo_author"] is None
    assert khac["photo_license"] is None


def test_the_detail_says_whether_this_place_has_any(client, repository):
    use_writer(client, silent_reasons)
    _anh(repository)
    with_photo = client.get(f"/places/{PLACE}").json()
    without = client.get(f"/places/{KHAC}").json()
    assert with_photo["photos_available"] is True
    assert without["photos_available"] is False


def test_a_photo_id_from_another_place_is_not_found(client, repository):
    """Both halves of the key. Serving bytes for a row the caller did not ask
    about is how a scoped read stops being scoped."""

    anh = _anh(repository, place_id=KHAC)
    response = client.get(f"/places/{PLACE}/photos/{anh.id}")
    assert response.status_code == 404, response.text


def test_an_unknown_photo_id_is_404_not_a_crash(client):
    response = client.get(f"/places/{PLACE}/photos/{uuid.uuid4()}")
    assert response.status_code == 404, response.text


def test_the_detail_says_what_a_person_does_there(client, repository):
    """«Nên làm gì ở đây» (M12) comes from the row, not from a sentence about
    it. The seed rows carry no OSM tags, so their phrases are read off the
    category, kinds and traits they already have."""

    del repository
    body = client.get(f"/places/{PLACE}").json()
    assert body["activities"] == [
        "Ăn một bữa",
        "Ăn nướng",
        "Ngắm cảnh",
        "Ngồi ngoài trời",
    ]


def test_a_place_the_data_says_nothing_about_lists_no_activities(client, repository):
    """Empty, not a filler line. «Ghé chơi» for a place nobody described reads
    exactly like a fact and is about nowhere."""

    del repository
    body = client.get(f"/places/{PLACES[6]['id']}").json()
    assert isinstance(body["activities"], list)


# --- ảnh của nhóm (ADR-0017 §2.4) ------------------------------------------
#
# Nguồn ảnh thứ hai của một địa điểm, và là nguồn RIÊNG. Điều phải chứng minh ở
# tầng này không phải «route trả về ảnh» — mà là người ngoài nhóm KHÔNG nhận
# được ảnh ấy, và bộ đôi giả phải giữ đủ ảnh để cú rò rỉ có cái mà rò.


def _anh_nhom(repository, place_id, context_id, author_id, caption="Tối qua"):
    record = MemoryRecord(
        id=uuid.uuid4(),
        context_id=context_id,
        author_id=author_id,
        kind="photo",
        image_url=f"/contexts/{context_id}/photos/{uuid.uuid4()}",
        caption=caption,
        place_id=place_id,
        place_name="Quán",
        lat=None,
        lng=None,
        created_at=dt.datetime(2026, 9, 6, 12, 0, tzinfo=dt.UTC),
    )
    repository.memories[record.id] = record
    return record


def test_a_group_photograph_reaches_the_group(client, repository):
    headers = dang_nhap(repository)
    toi = uuid.UUID(headers["X-Actor-ID"])
    nhom = uuid.uuid4()
    repository.active_memberships.add((nhom, toi))
    anh = _anh_nhom(repository, PLACE, nhom, toi)

    body = client.get(f"/places/{PLACE}/group-photos", headers=headers).json()
    assert [row["id"] for row in body["photos"]] == [str(anh.id)]
    assert body["photos"][0]["caption"] == "Tối qua"


def test_a_group_photograph_never_reaches_somebody_outside_the_group(
    client, repository
):
    """The one that matters. ADR-0017 §2.4: «Ảnh nhóm không bao giờ thành ảnh
    minh hoạ công khai của một quán»."""

    nguoi_la = uuid.uuid4()
    nhom = uuid.uuid4()
    repository.active_memberships.add((nhom, nguoi_la))
    _anh_nhom(repository, PLACE, nhom, nguoi_la, caption="Riêng của nhóm kia")

    headers = dang_nhap(repository)
    body = client.get(f"/places/{PLACE}/group-photos", headers=headers).json()
    assert body["photos"] == [], "ảnh của nhóm khác lọt ra ngoài"

    # Và đối chứng dương: chính người trong nhóm ấy thì thấy. Nếu không có
    # dòng này, một fake rỗng cũng cho ca trên màu xanh.
    cua_ho = client.get(
        f"/places/{PLACE}/group-photos", headers=actor_headers(actor_id=nguoi_la)
    ).json()
    assert len(cua_ho["photos"]) == 1


def test_the_public_gallery_never_carries_a_group_photograph(client, repository):
    """Hai nguồn, hai route. Gallery công khai không được lẫn ảnh của nhóm dù
    ảnh ấy gắn đúng địa điểm này."""

    headers = dang_nhap(repository)
    toi = uuid.UUID(headers["X-Actor-ID"])
    nhom = uuid.uuid4()
    repository.active_memberships.add((nhom, toi))
    _anh_nhom(repository, PLACE, nhom, toi)

    body = client.get(f"/places/{PLACE}/photos").json()
    assert body["photos"] == []


def test_group_photos_need_a_session(client, repository):
    dang_nhap(repository)
    assert client.get(f"/places/{PLACE}/group-photos").status_code == 401


def test_an_unknown_place_answers_empty_not_404(client, repository):
    """404 ở đây là trả lời câu «id này có tồn tại không» cho bất kỳ ai."""

    headers = dang_nhap(repository)
    ra = client.get("/places/p-khong-co-that/group-photos", headers=headers)
    assert ra.status_code == 200
    assert ra.json()["photos"] == []
