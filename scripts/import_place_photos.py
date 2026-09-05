#!/usr/bin/env python3
"""Fill `place_photos` from Wikimedia Commons (M12, ADR-0017).

    python3 scripts/import_place_photos.py --destination d-da-lat
    python3 scripts/import_place_photos.py --all --moi-noi 2
    python3 scripts/import_place_photos.py --destination d-da-lat --offline mau.json

What goes out to Commons: the coordinates of a place already published in
OpenStreetMap, and nothing else. No user data, no identifiers, no positions
belonging to anybody. What comes back is a picture and the four facts that make
it usable -- licence, author, source page, and the image itself.

This script is the only thing in the product allowed to call Commons; nothing
serving a request does, and `tests/test_only_the_importer_talks_out.py` keeps it
that way.

Only real venues. Rows with `source='seed'` are the synthetic catalogue, and a
real photograph under an invented business name is a lie in the shape of a
photograph even when the credit beside it is correct.

Refusal is the default. A file whose licence is not on the allowlist in
`app/places/wikimedia.py`, or whose author or source page cannot be read, is
skipped and counted. It is never imported with «Unknown» in an attribution
field: that looks like attribution and satisfies nobody's licence.

Idempotent on `(place_id, source_url)`: a second run adds only what is new.
Bytes go through the same sanitiser as user photographs (re-encode, EXIF gone)
and into `PhotoStorage`. No image bytes ever enter Git.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from app.db.models import Place, PlacePhoto  # noqa: E402
from app.media.images import ImageRejected, sanitize_image  # noqa: E402
from app.media.storage import PhotoStorage, new_storage_key  # noqa: E402
from app.places.wikimedia import anh_tu_imageinfo, truy_van_gan_diem  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

COMMONS_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "RuDi-photo-import/1.0 (+https://github.com/chuoibo/ru-di-app)"
BAN_KINH_M = 250
NGHI_GIUA_HAI_LAN_S = 1.0
CO_TOI_DA_BYTE = 4_000_000


def _database_url() -> str:
    url = os.environ.get("MOBILE_DATABASE_URL", "").strip()
    if not url:
        sys.exit("MOBILE_DATABASE_URL chưa đặt.")
    return url


def _hoi_commons(lat: float, lng: float, so_luong: int) -> Any:
    """One Commons call, or None. A failure here is a place without pictures,
    never a failed import: the catalogue is the product, the photographs are a
    garnish, and one flaky call must not cost the run."""

    url = f"{COMMONS_URL}?{truy_van_gan_diem(lat, lng, BAN_KINH_M, so_luong)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:  # noqa: S310
            return json.loads(answer.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"  commons không trả lời ({type(error).__name__})", file=sys.stderr)
        return None


def _tai_anh(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:  # noqa: S310
            return answer.read(CO_TOI_DA_BYTE + 1)
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"  tải ảnh hỏng ({type(error).__name__})", file=sys.stderr)
        return None


def nhap_cho_mot_dia_diem(
    session: Session,
    storage: PhotoStorage,
    place: Place,
    payload: Any,
    moi_noi: int,
    kho: bool,
) -> tuple[int, int]:
    """(số ảnh đã thêm, số file bị bỏ vì không đọc được xuất xứ)."""

    ung_vien = anh_tu_imageinfo(payload)
    da_co = {
        row.source_url
        for row in session.scalars(
            select(PlacePhoto).where(PlacePhoto.place_id == place.id)
        )
    }
    them = 0
    for thu_tu, anh in enumerate(ung_vien):
        if them >= moi_noi:
            break
        if anh["source_url"] in da_co:
            continue
        if kho:
            them += 1
            continue
        raw = _tai_anh(anh["url"])
        if raw is None or len(raw) > CO_TOI_DA_BYTE:
            continue
        try:
            sach = sanitize_image(raw)
        except ImageRejected as error:
            print(f"  ảnh bị từ chối ({error.args[0]})", file=sys.stderr)
            continue
        key = new_storage_key()
        storage.write(key, sach.data)
        session.add(
            PlacePhoto(
                place_id=place.id,
                storage_key=key,
                content_type=sach.content_type,
                byte_size=len(sach.data),
                width=sach.width,
                height=sach.height,
                author=anh["author"],
                license=anh["license"],
                source_url=anh["source_url"],
                title=anh["title"],
                sort_order=thu_tu,
            )
        )
        them += 1
    # Files Commons had but nobody could attribute. Counted, because «không có
    # ảnh nào» and «có sáu ảnh mà không ai nói ai chụp» là hai sự thật khác nhau.
    bo = max(
        0, len(((payload or {}).get("query") or {}).get("pages") or {}) - len(ung_vien)
    )
    return them, bo


def cau_dia_diem_that(destination: str | None):
    """Những địa điểm được phép gắn ảnh: chỗ CÓ THẬT.

    Dòng `seed` là 12 địa điểm tổng hợp -- `app/places/catalog.py` tự nói «no
    real business is being described» -- và toạ độ của chúng tuy hợp lý nhưng
    không trỏ vào cơ sở nào. Geosearch quanh một toạ độ như thế vẫn trả về ảnh
    thật của khu phố ấy, và một tấm ảnh thật đứng dưới tên một quán không tồn
    tại là đúng thứ lời nói dối bằng hình mà ADR-0017 §4 bác bỏ -- credit đầy
    đủ tới đâu cũng không cứu được, vì cái sai nằm ở cái tên chứ không ở tấm
    ảnh. Lượt nhập đầu tiên trên máy đã gắn ảnh vào cả 12 dòng ấy trước khi
    hàm này tồn tại.
    """

    cau = select(Place).where(Place.source != "seed").order_by(Place.id)
    if destination:
        cau = cau.where(Place.destination_id == destination)
    return cau


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", help="chỉ điểm đến này")
    parser.add_argument("--all", action="store_true", help="mọi điểm đến")
    parser.add_argument("--moi-noi", type=int, default=2, help="tối đa mấy ảnh một chỗ")
    parser.add_argument(
        "--offline", help="đọc một payload Commons đã lưu, không gọi mạng"
    )
    parser.add_argument("--dry-run", action="store_true", help="không ghi gì")
    args = parser.parse_args()

    if not args.all and not args.destination:
        parser.error("cần --destination hoặc --all")

    engine = create_engine(_database_url(), future=True)
    storage = PhotoStorage()
    payload_kho = json.loads(Path(args.offline).read_text()) if args.offline else None

    tong_them = tong_bo = tong_cho = 0
    with Session(engine) as session:
        places = list(session.scalars(cau_dia_diem_that(args.destination)))
        for place in places:
            payload = (
                payload_kho
                if payload_kho is not None
                else _hoi_commons(place.lat, place.lng, max(args.moi_noi * 3, 6))
            )
            if payload is None:
                continue
            them, bo = nhap_cho_mot_dia_diem(
                session, storage, place, payload, args.moi_noi, args.dry_run
            )
            tong_them += them
            tong_bo += bo
            tong_cho += 1 if them else 0
            if payload_kho is None:
                time.sleep(NGHI_GIUA_HAI_LAN_S)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    print(
        f"{len(places)} địa điểm đã hỏi · {tong_cho} chỗ có ảnh · {tong_them} ảnh "
        f"{'sẽ' if args.dry_run else 'đã'} nhập · {tong_bo} file bỏ vì không đọc được xuất xứ"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
