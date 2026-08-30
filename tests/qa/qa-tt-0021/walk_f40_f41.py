"""QA live walk (qa-tt-0021) for F40 hearts / F41 comments, PR #283.

Real PostgreSQL, real `SqlAlchemyApiRepository`, real HTTP through the app.
Nothing is faked: the point is to hit the shapes a fake repository cannot see.

This is deliberately NOT a re-run of the PR's own suite. Each check writes a
violation the PR's tests either do not write, or write in an easier shape:

  A. cross-context escalation -- a member of group A puts THEIR OWN context in
     the path and group B's memory id in the same path. Permission passes (they
     really are a member of A); only the memory lookup's context scoping stands
     between them and another group's wall.
  B. the 403/404 oracle, from the outside, over four id combinations that must
     be indistinguishable.
  C. authorship, attacked through the query string and a spoofed body rather
     than through the body field the PR already forbids.
  D. one heart per person, driven CONCURRENTLY rather than sequentially.
  E. hearts and comments must not multiply each other (3 x 2 must not read 6).

Run from `services/api/`:
    MOBILE_TEST_DATABASE_URL=... python3 ../../tests/qa/qa-tt-0021/walk_f40_f41.py
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
from datetime import UTC, datetime

import anyio
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from app.api.deps import get_repository  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.api.repository import SqlAlchemyApiRepository  # noqa: E402
from app.db.models import (  # noqa: E402
    Context,
    Membership,
    MembershipState,
    Memory,
    Person,
)

URL = os.environ["MOBILE_TEST_DATABASE_URL"]
ENGINE = create_engine(URL, future=True)

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    RESULTS.append((ok, label, detail))
    print(
        f"  {'PASS' if ok else 'FAIL':4}  {label}"
        + (f"\n          {detail}" if detail else "")
    )


# --------------------------------------------------------------------------
# Seed: two groups, so "another group's wall" is a real place, not a fake id.
# --------------------------------------------------------------------------


def seed():
    ids = {
        k: uuid.uuid4()
        for k in (
            "ctx_a",
            "ctx_b",
            "amy",
            "ben",
            "gone",
            "asked",
            "outsider",
            "mem_a",
            "mem_b",
        )
    }
    now = datetime.now(UTC)
    with Session(ENGINE) as s:
        for key in ("amy", "ben", "gone", "asked", "outsider"):
            s.add(Person(id=ids[key], display_name=key.title(), created_at=now))
        s.flush()  # people before contexts: fk_contexts_created_by
        for key, title in (("ctx_a", "Nhom A"), ("ctx_b", "Nhom B")):
            s.add(
                Context(
                    id=ids[key],
                    display_name=title,
                    created_by_id=ids["amy"],
                    created_at=now,
                )
            )
        rows = [
            ("ctx_a", "amy", MembershipState.ACTIVE),
            ("ctx_a", "ben", MembershipState.ACTIVE),
            ("ctx_a", "gone", MembershipState.LEFT),
            ("ctx_a", "asked", MembershipState.INVITED),
            ("ctx_b", "ben", MembershipState.ACTIVE),
        ]
        for ctx, person, state in rows:
            # ck_memberships_left_state_matches_timestamp: LEFT needs left_at,
            # and a joined membership needs joined_at. The schema is stricter
            # than the model annotations suggest.
            s.add(
                Membership(
                    id=uuid.uuid4(),
                    context_id=ids[ctx],
                    person_id=ids[person],
                    role="member",
                    state=state,
                    created_at=now,
                    joined_at=now if state is not MembershipState.INVITED else None,
                    left_at=now if state is MembershipState.LEFT else None,
                )
            )
        # ck_memories_payload_matches_kind: kind 'photo' needs an image_url and
        # must carry NO place columns at all. (kind 'checkin' is the mirror.)
        s.add(
            Memory(
                id=ids["mem_a"],
                context_id=ids["ctx_a"],
                author_id=ids["amy"],
                image_url=f"/contexts/{ids['ctx_a']}/photos/{uuid.uuid4()}",
                caption="anh cua nhom A",
                created_at=now,
            )
        )
        s.add(
            Memory(
                id=ids["mem_b"],
                context_id=ids["ctx_b"],
                author_id=ids["ben"],
                image_url=f"/contexts/{ids['ctx_b']}/photos/{uuid.uuid4()}",
                caption="anh cua nhom B",
                created_at=now,
            )
        )
        s.commit()
    return ids


def app_factory():
    app = create_app()

    def repo():
        session = Session(ENGINE)
        try:
            yield SqlAlchemyApiRepository(session)
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[get_repository] = repo
    return app


def call(app, method, path, actor, *, claims=None, **kw):
    """Everybody -- outsiders included -- is handed the STRONGEST role set.

    If a refusal still lands, it landed because of the membership row in the
    database and not because the caller was short a header. `claims` fills
    `X-Actor-Contexts`, the gateway-copied claim that must not grant anything
    on its own (hole #253).
    """

    headers = {
        "X-Actor-ID": str(actor),
        "X-Actor-Roles": "member,group_admin",
    }
    if claims is not None:
        headers["X-Actor-Contexts"] = str(claims)

    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await c.request(method, path, headers=headers, **kw)

    return anyio.run(send)


def main() -> int:
    ids = seed()
    app = app_factory()
    A = ids["ctx_a"]
    MEM_A, MEM_B = ids["mem_a"], ids["mem_b"]
    amy, gone, asked, outsider = ids["amy"], ids["gone"], ids["asked"], ids["outsider"]

    print(
        "\nA. Cross-context escalation -- own context in the path, another group's memory id"
    )
    # Amy is a real ACTIVE member of A, so the permission check WILL pass.
    # Only the memory lookup's context scoping stands between her and B's wall.
    r = call(app, "POST", f"/contexts/{A}/memories/{MEM_B}/reactions", amy)
    check(
        r.status_code == 404,
        f"heart on B's memory via A's path -> {r.status_code} (want 404)",
    )
    r = call(
        app,
        "POST",
        f"/contexts/{A}/memories/{MEM_B}/comments",
        amy,
        json={"body": "xin chao nhom B"},
    )
    check(
        r.status_code == 404,
        f"comment on B's memory via A's path -> {r.status_code} (want 404)",
    )
    r = call(app, "GET", f"/contexts/{A}/memories/{MEM_B}/comments", amy)
    check(
        r.status_code == 404,
        f"read B's comments via A's path -> {r.status_code} (want 404)",
    )
    with Session(ENGINE) as s:
        n = s.execute(
            text("select count(*) from memory_reactions where memory_id = :m"),
            {"m": MEM_B},
        ).scalar()
        c = s.execute(
            text("select count(*) from memory_comments where memory_id = :m"),
            {"m": MEM_B},
        ).scalar()
    check(
        n == 0 and c == 0,
        f"nothing was written to B's wall (reactions={n}, comments={c})",
    )

    print(
        "\nB. The 403/404 oracle -- four combinations must be indistinguishable to an outsider"
    )
    fake_ctx, fake_mem = uuid.uuid4(), uuid.uuid4()
    combos = {
        "real ctx + real memory": (A, MEM_A),
        "real ctx + fake memory": (A, fake_mem),
        "fake ctx + real memory": (fake_ctx, MEM_A),
        "fake ctx + fake memory": (fake_ctx, fake_mem),
    }
    seen = {}
    for label, (c_id, m_id) in combos.items():
        r = call(app, "POST", f"/contexts/{c_id}/memories/{m_id}/reactions", outsider)
        seen[label] = (r.status_code, r.text)
        print(f"          {label:26} -> {r.status_code}")
    codes = {v[0] for v in seen.values()}
    bodies = {v[1] for v in seen.values()}
    check(codes == {403}, f"outsider gets one single code for all four: {codes}")
    check(len(bodies) == 1, f"and one single body ({len(bodies)} distinct)")

    print(
        "\n   And an X-Actor-Contexts claim naming the group must grant nothing (#253)"
    )
    r = call(
        app, "POST", f"/contexts/{A}/memories/{MEM_A}/reactions", outsider, claims=A
    )
    check(
        r.status_code == 403,
        f"outsider claiming membership of A in the header -> {r.status_code} (want 403)",
    )

    print("\n   Same oracle for the two states that DO have a membership row")
    for who, label in ((gone, "LEFT"), (asked, "INVITED")):
        r = call(app, "POST", f"/contexts/{A}/memories/{MEM_A}/reactions", who)
        check(
            r.status_code == 403,
            f"{label} member is refused -> {r.status_code} (want 403)",
        )

    print(
        "\nC. Authorship -- attacked through the query string, not the forbidden body field"
    )
    r = call(
        app,
        "POST",
        f"/contexts/{A}/memories/{MEM_A}/reactions?person_id={outsider}",
        amy,
    )
    ok_code = r.status_code == 201
    with Session(ENGINE) as s:
        owner = (
            s.execute(
                text("select person_id from memory_reactions where memory_id=:m"),
                {"m": MEM_A},
            )
            .scalars()
            .all()
        )
    check(
        ok_code and owner == [amy],
        f"query-string person_id ignored; heart belongs to the caller (rows={owner})",
    )
    # BEN comments, not Amy. MEM_A is AMY's photo, so "file the comment under
    # the caller" and "file it under the photo's author" give the same row when
    # the commenter owns the picture -- the case reads green either way and
    # proves nothing. Ben is the cheapest way to make the two answers differ.
    ben_id = ids["ben"]
    r = call(
        app,
        "POST",
        f"/contexts/{A}/memories/{MEM_A}/comments?author_id={outsider}",
        ben_id,
        json={"body": "anh dep qua Amy oi"},
    )
    with Session(ENGINE) as s:
        authors = (
            s.execute(
                text("select author_id from memory_comments where memory_id=:m"),
                {"m": MEM_A},
            )
            .scalars()
            .all()
        )
    check(
        r.status_code == 201 and authors == [ben_id],
        f"comment on ANOTHER person's photo is filed under the caller, not the "
        f"photo owner (rows={authors}, amy={amy}, ben={ben_id})",
    )

    print("\nD. One heart per person -- driven CONCURRENTLY, not sequentially")
    with Session(ENGINE) as s:
        s.execute(text("delete from memory_reactions where memory_id=:m"), {"m": MEM_A})
        s.commit()
    codes_out: list[int] = []
    lock = threading.Lock()

    def tap():
        r = call(
            app_factory(), "POST", f"/contexts/{A}/memories/{MEM_A}/reactions", amy
        )
        with lock:
            codes_out.append(r.status_code)

    threads = [threading.Thread(target=tap) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with Session(ENGINE) as s:
        rows = s.execute(
            text(
                "select count(*) from memory_reactions where memory_id=:m and person_id=:p"
            ),
            {"m": MEM_A, "p": amy},
        ).scalar()
    check(
        rows == 1,
        f"8 simultaneous taps left exactly one row (rows={rows}, codes={sorted(codes_out)})",
    )
    check(
        codes_out.count(201) == 1,
        f"exactly one tap was told it won (201 count={codes_out.count(201)})",
    )

    print(
        "\nE. Hearts and comments must not multiply each other (3 hearts x 2 comments != 6)"
    )
    with Session(ENGINE) as s:
        s.execute(text("delete from memory_reactions where memory_id=:m"), {"m": MEM_A})
        s.execute(text("delete from memory_comments where memory_id=:m"), {"m": MEM_A})
        s.commit()
    ben = ids["ben"]
    call(app, "POST", f"/contexts/{A}/memories/{MEM_A}/reactions", amy)
    call(app, "POST", f"/contexts/{A}/memories/{MEM_A}/reactions", ben)
    for i in range(2):
        call(
            app,
            "POST",
            f"/contexts/{A}/memories/{MEM_A}/comments",
            amy,
            json={"body": f"binh luan {i}"},
        )
    r = call(app, "GET", f"/contexts/{A}/memories", amy)
    row = next(m for m in r.json()["memories"] if m["id"] == str(MEM_A))
    check(
        row["reaction_count"] == 2 and row["comment_count"] == 2,
        f"2 hearts x 2 comments reads 2/2, not 4/4 "
        f"(reaction_count={row['reaction_count']}, comment_count={row['comment_count']})",
    )
    check(
        row["viewer_has_reacted"] is True,
        "viewer_has_reacted is true for a reader who did react",
    )
    r_ben = call(app, "GET", f"/contexts/{A}/memories", ben)
    row_ben = next(m for m in r_ben.json()["memories"] if m["id"] == str(MEM_A))
    check(row_ben["viewer_has_reacted"] is True, "and true for Ben, who also reacted")

    failed = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(main())
