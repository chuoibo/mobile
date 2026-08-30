"""QA probe (qa-tt-0031): does the rewritten get_repository still roll back?

The PR replaces `with factory.begin() as session:` -- a context manager that
rolled back on any exception -- with a hand-written try/except/else/finally.
No test in the PR exercises the failure branch, so this probe drives it on real
PostgreSQL: a route writes a row and then raises. The row must not survive.

Run from services/api with MOBILE_DATABASE_URL pointing at a migrated schema.
"""

from __future__ import annotations

import os
import sys
import uuid

import anyio
import httpx
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text

from app.api.deps import get_repository
from app.api.unit_of_work import install_commit_before_response
from app.db.session import get_engine, get_session_factory


def _build_app() -> FastAPI:
    application = FastAPI()

    @application.post("/qa-write-then-raise/{person_id}")
    async def write_then_raise(person_id: uuid.UUID, repo=Depends(get_repository)):
        repo.session.execute(
            text("insert into people (id, display_name) values (:id, :name)"),
            {"id": person_id, "name": "phai bi cuon lai"},
        )
        raise HTTPException(status_code=409, detail="co tinh hong sau khi ghi")

    @application.post("/qa-write-then-crash/{person_id}")
    async def write_then_crash(person_id: uuid.UUID, repo=Depends(get_repository)):
        repo.session.execute(
            text("insert into people (id, display_name) values (:id, :name)"),
            {"id": person_id, "name": "phai bi cuon lai"},
        )
        raise RuntimeError("loi khong duoc xu ly sau khi ghi")

    @application.post("/qa-write-ok/{person_id}")
    async def write_ok(person_id: uuid.UUID, repo=Depends(get_repository)):
        repo.session.execute(
            text("insert into people (id, display_name) values (:id, :name)"),
            {"id": person_id, "name": "phai con lai"},
        )
        return {"status": "created"}

    install_commit_before_response(application)
    return application


def _count(engine, person_id: uuid.UUID) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text("select count(*) from people where id = :id"), {"id": person_id}
        ).scalar_one()


def main() -> int:
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    engine = get_engine()
    app = _build_app()
    failures = []

    cases = [
        ("HTTPException 409 sau khi ghi", "/qa-write-then-raise", 409, 0),
        ("RuntimeError 500 sau khi ghi", "/qa-write-then-crash", None, 0),
        ("duong hanh phuc", "/qa-write-ok", 200, 1),
    ]

    async def exchange(path: str, person_id: uuid.UUID) -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post(f"{path}/{person_id}")

    for label, path, want_status, want_rows in cases:
        person_id = uuid.uuid4()
        response = anyio.run(exchange, path, person_id)
        rows = _count(engine, person_id)
        status_ok = want_status is None or response.status_code == want_status
        rows_ok = rows == want_rows
        verdict = "DAT" if (status_ok and rows_ok) else "HONG"
        if verdict == "HONG":
            failures.append(label)
        print(
            f"  {verdict}  {label}: status={response.status_code} "
            f"hang con lai={rows} (mong doi {want_rows})"
        )
        with engine.begin() as connection:
            connection.execute(
                text("delete from people where id = :id"), {"id": person_id}
            )

    print()
    if failures:
        print(f"KET QUA: HONG — {len(failures)} ca: {', '.join(failures)}")
        return 1
    print(
        "KET QUA: DAT — ghi roi loi thi khong hang nao sot lai, duong hanh phuc van commit"
    )
    return 0


if __name__ == "__main__":
    if not os.environ.get("MOBILE_DATABASE_URL"):
        print("can MOBILE_DATABASE_URL", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main())
