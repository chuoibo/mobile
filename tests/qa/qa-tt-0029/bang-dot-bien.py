"""Does #308's own suite have teeth? One mutation per layer, one at a time.

Mutating both spellings of the F42 rule at once hides the layer that has no
gate behind the layer that does. So every row here touches exactly ONE of:

    domain      app/domain/post_audience.py          -- the rule as logic
    sql         SqlAlchemyApiRepository._readable_by  -- the rule as a WHERE
    service     ApiService.read_post / list_*         -- where the rule is run

M0 is the control: it reorders the OR disjuncts, which does not change what
the clause selects. It must stay GREEN. A table where every row is red cannot
tell "the gate has teeth" from "the tests notice that somebody edited a file".

Run from the repo root with a live PostgreSQL:
    MOBILE_TEST_DATABASE_URL=... python3 tests/qa/qa-tt-0029/bang-dot-bien.py
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
API = ROOT / "services" / "api"
DOMAIN = API / "app" / "domain" / "post_audience.py"
REPO = API / "app" / "api" / "repository.py"
SERVICE = API / "app" / "api" / "service.py"

LAYERS = {
    "domain": "tests/domain/test_post_audience.py",
    "api": "tests/api/test_posts_audience.py",
    "postgres": "tests/postgres/test_posts_postgres.py",
}

# (id, file, old, new, expectation)  -- expectation is what a gate WITH teeth
# should do: "RED" somewhere, or "GREEN" for the semantics-preserving control.
MUTANTS = [
    (
        "M0 doi thu tu cac nhanh OR (GIU nguyen nghia)",
        REPO,
        """        return or_(
            Post.author_id == reader_id,
            Post.audience == PostAudience.PUBLIC,
            and_(Post.audience == PostAudience.FRIENDS, friendship),
            and_(
                Post.audience == PostAudience.GROUP,
                Post.context_id.is_not(None),
                membership,
            ),
        )""",
        """        return or_(
            and_(
                Post.audience == PostAudience.GROUP,
                Post.context_id.is_not(None),
                membership,
            ),
            and_(Post.audience == PostAudience.FRIENDS, friendship),
            Post.audience == PostAudience.PUBLIC,
            Post.author_id == reader_id,
        )""",
        "GREEN",
    ),
    (
        "M1 domain: only_me roi xuong True",
        DOMAIN,
        """    # `only_me`, and it reached here, so the reader is not the author.
    return False""",
        """    # `only_me`, and it reached here, so the reader is not the author.
    return True""",
        "RED",
    ),
    (
        "M2 sql: only_me tro thanh mot nhanh OR (chi tang SQL)",
        REPO,
        "            Post.audience == PostAudience.PUBLIC,\n"
        "            and_(Post.audience == PostAudience.FRIENDS, friendship),",
        "            Post.audience == PostAudience.PUBLIC,\n"
        "            Post.audience == PostAudience.ONLY_ME,\n"
        "            and_(Post.audience == PostAudience.FRIENDS, friendship),",
        "RED",
    ),
    (
        "M3 sql: bo dieu kien ACCEPTED — loi moi CHUA tra loi cung la ban",
        REPO,
        "            .where(\n"
        "                FriendRequest.state == FriendRequestState.ACCEPTED,\n"
        "                or_(",
        "            .where(\n                or_(",
        "RED",
    ),
    (
        "M4 sql: bo dieu kien ACTIVE — nguoi MOI CHUA nhan cung doc duoc",
        REPO,
        "                Membership.context_id == Post.context_id,\n"
        "                Membership.person_id == reader_id,\n"
        "                Membership.state == MembershipState.ACTIVE,\n"
        "                Membership.left_at.is_(None),",
        "                Membership.context_id == Post.context_id,\n"
        "                Membership.person_id == reader_id,",
        "RED",
    ),
    (
        "M5 domain: audience la nhom thi bo qua tu cach thanh vien",
        DOMAIN,
        '        return post.get("context_id") is not None and is_group_member',
        '        return post.get("context_id") is not None',
        "RED",
    ),
    (
        "M6 domain: audience la khong ro thi cho doc (fail open)",
        DOMAIN,
        "    if audience not in AUDIENCES:\n"
        "        # Fail closed, the same way `can_view_history` does. An audience string",
        "    if audience not in AUDIENCES:\n"
        "        return True\n"
        "        # Fail closed, the same way `can_view_history` does. An audience string",
        "RED",
    ),
    # Two list call sites, two chances to forget the filter. `_readable_by`
    # being one function does not make it one gate: a gate is only as wide as
    # the set of places that call it, so each call site gets its own row.
    (
        "M7a sql: feed (list_posts_visible_to) bo mat bo loc",
        REPO,
        "            select(Post)\n"
        "            .where(self._readable_by(reader_id))\n"
        "            .order_by(Post.created_at.desc(), Post.id.desc())",
        "            select(Post)\n"
        "            .order_by(Post.created_at.desc(), Post.id.desc())",
        "RED",
    ),
    (
        "M7b sql: tuong (list_person_posts_visible_to) bo mat bo loc",
        REPO,
        "            select(Post)\n"
        "            .where(Post.author_id == person_id, self._readable_by(reader_id))",
        "            select(Post)\n            .where(Post.author_id == person_id)",
        "RED",
    ),
    (
        "M8 domain: bo chan only_me mang theo context_id",
        DOMAIN,
        '        raise AudienceError("CONTEXT_NOT_ADDRESSABLE")',
        "        pass",
        "RED",
    ),
]


def run(paths: list[str]) -> tuple[str, str]:
    env = dict(os.environ)
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q", "-p", "no:randomly", "-x"],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    summary = tail[-1] if tail else "(khong co output)"
    return ("RED" if proc.returncode != 0 else "GREEN"), summary


backups: dict[pathlib.Path, str] = {}
stash = tempfile.mkdtemp(prefix="qa0029-mutants-")
for f in (DOMAIN, REPO, SERVICE):
    backups[f] = f.read_text()
    shutil.copy2(f, pathlib.Path(stash) / f.name)


def restore() -> None:
    for f, text in backups.items():
        f.write_text(text)


print("== phep do goc: ba tang phai XANH truoc khi dot bien co nghia ==")
rows = []
for layer, path in LAYERS.items():
    verdict, summary = run([path])
    print(f"  {layer:9} {verdict:5}  {summary}")
    if verdict != "GREEN":
        print("  !! cay goc khong xanh -- dung, moi so do sau day vo nghia")
        restore()
        sys.exit(2)

print()
print(f"{'dot bien':58} {'muon':6} {'domain':7} {'api':7} {'postgres':8} {'ket luan'}")
bad = 0
for label, target, old, new, want in MUTANTS:
    if old not in backups[target]:
        print(f"{label:58} NEO TRUOT -- chuoi khong co trong {target.name}")
        bad += 1
        continue
    if backups[target].count(old) != 1:
        print(
            f"{label:58} NEO TRUNG {backups[target].count(old)} lan trong {target.name}"
        )
        bad += 1
        continue
    target.write_text(backups[target].replace(old, new, 1))
    got = {}
    for layer, path in LAYERS.items():
        got[layer], _ = run([path])
    restore()
    if want == "GREEN":
        ok = all(v == "GREEN" for v in got.values())
    else:
        ok = any(v == "RED" for v in got.values())
    if not ok:
        bad += 1
    print(
        f"{label:58} {want:6} {got['domain']:7} {got['api']:7} {got['postgres']:8} "
        f"{'DAT' if ok else '>>> LO HONG'}"
    )

restore()
print(f"\n== {len(MUTANTS)} dot bien, {bad} khong dat ==")
print(f"(ban goc cua ba file luu tai {stash} phong khi khoi phuc that bai)")
sys.exit(1 if bad else 0)
