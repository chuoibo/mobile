#!/usr/bin/env python3
"""Fill the `places` table from OpenStreetMap (M9, ADR-0017).

    python3 scripts/import_osm_places.py --all
    python3 scripts/import_osm_places.py --destination d-da-lat
    python3 scripts/import_osm_places.py --destination d-da-lat --offline mau.json

What goes out to Overpass: a bounding box and a list of tags. No user data, no
coordinates belonging to anybody, no identifiers. What comes back does not
enter Git -- it goes into the database, which is where real venue data belongs
(charter). This script is the only thing in the product allowed to call
Overpass; nothing serving a request does.

Idempotent by `source_ref`: a second run updates the rows it already wrote and
inserts the ones that are new. Rows a person's data points at (a saved place,
an outing stop) keep their ids, because the id is derived from the OSM id.

Attribution is not optional. ODbL requires it, so every row carries
`license = 'ODbL-1.0'` and the database refuses an `osm` row without one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from app.db.models import Destination, Place  # noqa: E402
from app.places.destinations_vn import DESTINATIONS_VN, DESTINATION_BY_ID  # noqa: E402
from app.places.osm import overpass_query, rows_from_payload  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "RuDi-catalogue-import/1.0 (+https://github.com/chuoibo/ru-di-app)"
PAUSE_BETWEEN_DESTINATIONS_S = 5.0


def _database_url() -> str:
    url = os.environ.get("MOBILE_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit(
            "MOBILE_DATABASE_URL chưa đặt. Ví dụ:\n"
            "  MOBILE_DATABASE_URL='postgresql+psycopg://mobile:...@localhost:5432/mobile'"
        )
    return url


def fetch_overpass(query: str, *, timeout_s: int = 180) -> dict[str, Any]:
    """One POST to Overpass. Raises on anything that is not a JSON answer."""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return json.load(response)


def upsert_destinations(
    session: Session, rows: list[dict[str, Any]]
) -> tuple[int, int]:
    them = doi = 0
    for row in rows:
        existing = session.get(Destination, row["id"])
        if existing is None:
            session.add(Destination(**row))
            them += 1
            continue
        changed = False
        for key, value in row.items():
            if key == "id":
                continue
            if getattr(existing, key) != value:
                setattr(existing, key, value)
                changed = True
        doi += 1 if changed else 0
    session.flush()
    return them, doi


def upsert_places(session: Session, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Insert new rows, refresh the ones already imported. Never deletes.

    Deleting is deliberately out of scope: a place somebody saved or put in a
    timeline must not vanish because a mapper retagged it this week. A place
    that closes is a later decision, with a `closed_at` and a screen that says
    so -- not a silent DELETE.
    """
    them = doi = 0
    for row in rows:
        existing = session.scalar(
            select(Place).where(
                Place.source == row["source"], Place.source_ref == row["source_ref"]
            )
        )
        if existing is None:
            session.add(Place(**row))
            them += 1
            continue
        changed = False
        for key, value in row.items():
            # The id stays whatever it was: things point at it.
            if key in {"id", "source", "source_ref"}:
                continue
            if getattr(existing, key) != value:
                setattr(existing, key, value)
                changed = True
        doi += 1 if changed else 0
    session.flush()
    return them, doi


def import_destination(
    session: Session,
    destination: dict[str, Any],
    *,
    limit_per_category: int,
    offline: Path | None,
) -> tuple[int, int, int]:
    if offline is not None:
        payload = json.loads(offline.read_text(encoding="utf-8"))
    else:
        payload = fetch_overpass(
            overpass_query(
                south=destination["bbox_south"],
                west=destination["bbox_west"],
                north=destination["bbox_north"],
                east=destination["bbox_east"],
            )
        )
    rows = rows_from_payload(
        payload,
        destination_id=destination["id"],
        fallback_city=destination["name"],
        limit_per_category=limit_per_category,
    )
    them, doi = upsert_places(session, rows)
    return len(rows), them, doi


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", help="id một điểm đến, ví dụ d-da-lat")
    parser.add_argument("--all", action="store_true", help="nhập mọi điểm đến")
    parser.add_argument(
        "--limit-per-category",
        type=int,
        default=40,
        help="trần số địa điểm mỗi danh mục cho một điểm đến (mặc định 40)",
    )
    parser.add_argument(
        "--offline",
        type=Path,
        help="đọc một file JSON Overpass đã lưu thay vì gọi mạng (dùng cho test)",
    )
    parser.add_argument("--dry-run", action="store_true", help="không ghi database")
    args = parser.parse_args(argv)

    if not args.all and not args.destination:
        parser.error("cần --all hoặc --destination")
    if args.offline is not None and args.all:
        parser.error("--offline chỉ dùng với một --destination")

    targets = (
        DESTINATIONS_VN if args.all else [DESTINATION_BY_ID.get(args.destination or "")]
    )
    if any(t is None for t in targets):
        parser.error(f"không biết điểm đến {args.destination!r}")

    engine = create_engine(_database_url())
    with Session(engine) as session:
        them_dd, doi_dd = upsert_destinations(session, DESTINATIONS_VN)
        print(f"điểm đến: thêm {them_dd}, cập nhật {doi_dd}")
        tong_them = tong_doi = tong_doc = 0
        for index, destination in enumerate(targets):
            assert destination is not None
            if index > 0 and args.offline is None:
                time.sleep(PAUSE_BETWEEN_DESTINATIONS_S)
            try:
                doc, them, doi = import_destination(
                    session,
                    destination,
                    limit_per_category=args.limit_per_category,
                    offline=args.offline,
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                print(
                    f"  {destination['id']}: KHÔNG ĐỌC ĐƯỢC ({type(error).__name__})",
                    file=sys.stderr,
                )
                continue
            tong_doc += doc
            tong_them += them
            tong_doi += doi
            print(f"  {destination['id']}: đọc {doc}, thêm {them}, cập nhật {doi}")
        if args.dry_run:
            session.rollback()
            print("dry-run: đã bỏ mọi thay đổi")
        else:
            session.commit()
        print(f"tổng: đọc {tong_doc}, thêm {tong_them}, cập nhật {tong_doi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
