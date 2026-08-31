#!/usr/bin/env python3
"""Mutation battery for the four-way control probe added by PR #411.

## Why this exists

`tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py` answers a real
question well: it separates "the caller is not a member, so 403 is correct"
from "a member is being refused, which is a defect". Its own conclusion line
is strong -- "San pham khong hong o quyen" -- and it exits 0 to say so.

A probe that prints that sentence is only worth its exit code if it would
print something else when the gate IS broken. Nothing in the repository runs
this probe (it has no `test_` prefix, so pytest does not collect it, and no
gate script names it), so its exit code is read by people, not by CI. That
makes "does it bite" a question someone has to answer by hand. This is that
answer.

## What it mutates, and why that is the right target

All three routes under test (F43 map, F44 heatmap, F45 meet) reach exactly one
predicate -- `SqlAlchemyApiRepository.is_member` -- through
`_require_permission("view_...", ...)`. Mutating that function is mutating the
precise thing the probe claims to have measured, so a surviving mutant is a
statement about the probe and not about where the mutation happened to land.

`is_member` asks three separate things, and they can break independently:

    Membership.context_id == context_id    # right group
    Membership.person_id  == person_id     # right person
    Membership.state == ACTIVE             # membership still live
    Membership.left_at.is_(None)           # ...and not left
    (no role predicate at all)             # member and admin are equal here

The probe's directions are `member x pinned id`, `member x real group`, and
`stranger x real group`, where the stranger is a uuid that was NEVER a member.
So the probe exercises the first pair of predicates and nothing else.

## Measured result (qa-tt-0053, on the merge tree of #411 with main@6def9a1)

    M0 baseline                        exit 0   (a) not broken   <- reproduces PR
    M1 gate wide open (always True)    exit 1   KILLED  -- direction C notices
    M2 gate slammed shut (always False) exit 1  KILLED  -- direction B notices
    M3 only admins get in              exit 0   SURVIVED
    M4 people who LEFT keep access     exit 0   SURVIVED

M3 and M4 print the identical "San pham khong hong o quyen" line. Under M3 six
of the seven members of the seeded group are locked out of all three routes;
under M4 somebody removed from a group keeps reading its map and heatmap. The
probe cannot see either, because direction [B] picks its actor with
`order by c.created_at desc, m.role limit 1`, which lands on the group's only
admin, and because no direction uses a membership that is not ACTIVE.

This does not make the PR's conclusion wrong -- M0 reproduces it, and M1/M2
show the two directions that answer the question it asked really do work. It
narrows what the probe may be quoted for later: it proves the gate honours
membership, not that it honours revocation or that it treats roles equally.

## Running it

Needs a disposable stack -- it edits `repository.py` in the working tree and
restarts an API against your database. Never point it at the shared 8099 stack.

    scripts/e2e_slice.sh --keep          # note the API url and the dsn it prints
    python3 scripts/reset_demo_group.py --dsn "$DSN" --yes
    MOBILE_SEED_API_BASE_URL=$API MOBILE_DATABASE_URL=$DSN \
        python3 scripts/seed_demo_data.py
    python3 tests/qa/qa-tt-0053-dot-bien-411/dot_bien_cong_thanh_vien.py \
        --dsn "$DSN" --port 45170

`repository.py` is restored in a `finally`, and the script refuses to start if
the file does not contain exactly one copy of the expected original body -- a
half-applied mutation left behind in a shared worktree is worse than no
measurement.
"""

from __future__ import annotations

import argparse
import os
import signal
import pathlib
import subprocess
import sys
import time
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[3]
TARGET = REPO / "services/api/app/api/repository.py"
PROBE = REPO / "tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py"

GOC = """    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return (
            self.session.scalar(
                select(Membership.id)
                .where(
                    Membership.context_id == context_id,
                    Membership.person_id == person_id,
                    Membership.state == MembershipState.ACTIVE,
                    Membership.left_at.is_(None),
                )
                .limit(1)
            )
            is not None
        )
"""

DOT_BIEN = {
    "M1 cong mo toang (luon True)": """    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return True
""",
    "M2 cong dong sap (luon False)": """    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return False
""",
    "M3 chi ADMIN vao duoc": """    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return (
            self.session.scalar(
                select(Membership.id)
                .where(
                    Membership.context_id == context_id,
                    Membership.person_id == person_id,
                    Membership.role == MembershipRole.ADMIN,
                    Membership.state == MembershipState.ACTIVE,
                    Membership.left_at.is_(None),
                )
                .limit(1)
            )
            is not None
        )
""",
    "M4 nguoi da ROI nhom van vao duoc": """    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return (
            self.session.scalar(
                select(Membership.id)
                .where(
                    Membership.context_id == context_id,
                    Membership.person_id == person_id,
                )
                .limit(1)
            )
            is not None
        )
""",
}


def doi_ma(moi: str) -> None:
    src = TARGET.read_text(encoding="utf-8")
    if src.count(GOC) != 1:
        sys.exit(
            "khong tim thay dung mot ban goc cua is_member trong "
            f"{TARGET} -- ham da doi, cap nhat GOC truoc khi tin bang duoi"
        )
    TARGET.write_text(src.replace(GOC, moi), encoding="utf-8")


def khoi_dong(dsn: str, port: int, media: str, key: str) -> subprocess.Popen:
    env = dict(os.environ)
    env.update(
        MOBILE_DATABASE_URL=dsn, MOBILE_MEDIA_ROOT=media, MOBILE_PERSON_ID_KEY=key
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO / "services/api",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    for _ in range(120):
        if proc.poll() is not None:
            print("uvicorn CHET khi khoi dong:")
            print(proc.stderr.read().decode()[-1500:])
            sys.exit(3)
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=2
            ) as resp:
                if resp.status == 200:
                    return proc
        except OSError:
            time.sleep(0.5)
    proc.send_signal(signal.SIGTERM)
    sys.exit("uvicorn khong len trong 60s")


def chay_probe(dsn: str, port: int) -> tuple[int, str]:
    env = dict(os.environ)
    env.update(
        MOBILE_SEED_API_BASE_URL=f"http://127.0.0.1:{port}", MOBILE_DATABASE_URL=dsn
    )
    done = subprocess.run(
        [sys.executable, str(PROBE)],
        env=env,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return done.returncode, done.stdout + done.stderr


def mot_luot(ten: str, ma: str | None, args) -> tuple[str, int, str]:
    if ma is not None:
        doi_ma(ma)
    proc = khoi_dong(args.dsn, args.port, args.media_root, args.person_key)
    try:
        code, out = chay_probe(args.dsn, args.port)
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    ket = [
        line.strip()
        for line in out.splitlines()
        if line.strip().startswith(("A  ", "B  ", "C  ", "=>"))
    ]
    return ten, code, " | ".join(ket)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("MOBILE_DATABASE_URL"))
    ap.add_argument("--port", type=int, default=45170)
    ap.add_argument("--media-root", default=os.environ.get("MOBILE_MEDIA_ROOT", "/tmp"))
    ap.add_argument("--person-key", default=os.environ.get("MOBILE_PERSON_ID_KEY", ""))
    args = ap.parse_args()
    if not args.dsn:
        sys.exit("can --dsn (hoac MOBILE_DATABASE_URL) tro vao mot stack dung mot lan")

    goc = TARGET.read_text(encoding="utf-8")
    bang = []
    try:
        bang.append(mot_luot("M0 NEN (khong doi gi)", None, args))
        for ten, ma in DOT_BIEN.items():
            TARGET.write_text(goc, encoding="utf-8")  # always mutate from clean
            bang.append(mot_luot(ten, ma, args))
    finally:
        TARGET.write_text(goc, encoding="utf-8")
        print("\n== da khoi phuc repository.py ==")

    print("\n" + "=" * 78)
    print(f"{'dot bien':<38} {'exit':<5} probe noi gi")
    print("=" * 78)
    song = 0
    for ten, code, ket in bang:
        if ten.startswith("M0"):
            dau = "NEN "
        elif code != 0:
            dau = "GIET"
        else:
            dau = "SONG"
            song += 1
        print(f"{ten:<38} {code:<5} {dau}")
        print(f"{'':38} {ket[:200]}")
    print(
        f"\n{song} dot bien SONG SOT -- moi cai la mot cau probe nay khong tra loi duoc."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
