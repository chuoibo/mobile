"""Does the walk in this folder actually have teeth, and where?

`di-bo-f42-thu-hoi-va-anh.py` is a BLACK-BOX walk: it talks HTTP and cannot see
which layer answered. That makes one thing it says easy to over-read. So this
table mutates the product one place at a time, restarts the server, and records
what the walk does.

Two kinds of row, and the difference is the point:

  * Rows that widen BOTH spellings of a rule (domain + SQL) must turn the walk
    RED. If they do not, the walk is decoration.
  * Rows that widen ONLY the SQL spelling must leave the walk GREEN -- because
    `ApiService` re-checks every row against `post_audience.can_read` before
    serialising. A green here is not a miss; it is the defence-in-depth claim
    in #308's description being true at the HTTP surface. Attribution per layer
    is qa-tt-0029's table, not this one.

M0 is a control: it reorders SQL disjuncts without changing meaning and MUST
stay green. Without it, every red below only proves the walk reacts to "somebody
edited a file".

Run: python3 tests/qa/qa-tt-0032/bang-dot-bien.py
"""

from __future__ import annotations

import os
import pathlib
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[3]
API = REPO / "services" / "api"
WALK = REPO / "tests" / "qa" / "qa-tt-0032" / "di-bo-f42-thu-hoi-va-anh.py"

PORT = 8154
BASE = f"http://127.0.0.1:{PORT}"
DB = "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/qa_tt_0032"
MEDIA = "/tmp/qa-tt-0032-media-mut"

DOMAIN = API / "app" / "domain" / "post_audience.py"
REPOSITORY = API / "app" / "api" / "repository.py"
SERVICE = API / "app" / "api" / "service.py"
IMAGES = API / "app" / "media" / "images.py"

# --- the exact fragments each mutation rewrites ---------------------------

FRIEND_DOMAIN_OLD = """    if audience == "friends":
        return is_friend"""
FRIEND_DOMAIN_NEW = """    if audience == "friends":
        return True"""

GROUP_DOMAIN_OLD = (
    """        return post.get("context_id") is not None and is_group_member"""
)
GROUP_DOMAIN_NEW = """        return post.get("context_id") is not None"""

ACCEPTED_SQL_OLD = """                FriendRequest.state == FriendRequestState.ACCEPTED,
                or_(
                    and_(
                        FriendRequest.requester_id == reader_id,
                        FriendRequest.addressee_id == Post.author_id,
                    ),"""
ACCEPTED_SQL_NEW = """                or_(
                    and_(
                        FriendRequest.requester_id == reader_id,
                        FriendRequest.addressee_id == Post.author_id,
                    ),"""

# M0's control: same two disjuncts, opposite order. Identical truth table.
REORDER_OLD = """                or_(
                    and_(
                        FriendRequest.requester_id == reader_id,
                        FriendRequest.addressee_id == Post.author_id,
                    ),
                    and_(
                        FriendRequest.addressee_id == reader_id,
                        FriendRequest.requester_id == Post.author_id,
                    ),
                ),"""
REORDER_NEW = """                or_(
                    and_(
                        FriendRequest.addressee_id == reader_id,
                        FriendRequest.requester_id == Post.author_id,
                    ),
                    and_(
                        FriendRequest.requester_id == reader_id,
                        FriendRequest.addressee_id == Post.author_id,
                    ),
                ),"""

ACTIVE_SQL_OLD = """                Membership.person_id == reader_id,
                Membership.state == MembershipState.ACTIVE,
                Membership.left_at.is_(None),"""
ACTIVE_SQL_NEW = """                Membership.person_id == reader_id,"""

PHOTO_GATE_OLD = """        _require_permission(
            "view_group_memories",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        record = self.repository.get_context_image(context_id, image_id)"""
PHOTO_GATE_NEW = (
    """        record = self.repository.get_context_image(context_id, image_id)"""
)

SANITIZE_OLD = """    output = io.BytesIO()
    if clean.mode == "RGBA":"""
SANITIZE_NEW = """    return SanitizedImage(
        data=raw, content_type="image/jpeg", width=width, height=height
    )
    output = io.BytesIO()
    if clean.mode == "RGBA":"""

# --- the table ------------------------------------------------------------
# (id, description, want, [(path, old, new), ...])
ROWS = [
    (
        "M0",
        "DOI CHUNG sql: dao thu tu hai nhanh OR, GIU NGUYEN nghia",
        "GREEN",
        [(REPOSITORY, REORDER_OLD, REORDER_NEW)],
    ),
    (
        "M1",
        "domain: audience friends bo qua is_friend (CHI tang domain)",
        "RED",
        [(DOMAIN, FRIEND_DOMAIN_OLD, FRIEND_DOMAIN_NEW)],
    ),
    (
        "M2",
        "sql: bo state==ACCEPTED (CHI tang sql) -> service phai bat lai",
        "GREEN",
        [(REPOSITORY, ACCEPTED_SQL_OLD, ACCEPTED_SQL_NEW)],
    ),
    (
        "M3",
        "CA HAI ban sao luat friends bi noi ra",
        "RED",
        [
            (DOMAIN, FRIEND_DOMAIN_OLD, FRIEND_DOMAIN_NEW),
            (REPOSITORY, ACCEPTED_SQL_OLD, ACCEPTED_SQL_NEW),
        ],
    ),
    (
        "M4",
        "CA HAI ban sao luat group: roi nhom van doc duoc",
        "RED",
        [
            (DOMAIN, GROUP_DOMAIN_OLD, GROUP_DOMAIN_NEW),
            (REPOSITORY, ACTIVE_SQL_OLD, ACTIVE_SQL_NEW),
        ],
    ),
    (
        "M5",
        "media: sanitize_image tra ve dung byte da nhan (khong tuoc EXIF)",
        "RED",
        [(IMAGES, SANITIZE_OLD, SANITIZE_NEW)],
    ),
    (
        "M6",
        "service: read_context_photo thoi hoi tu cach thanh vien",
        "RED",
        [(SERVICE, PHOTO_GATE_OLD, PHOTO_GATE_NEW)],
    ),
]


def wait_ready(proc: subprocess.Popen, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{BASE}/healthz", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def run_walk() -> tuple[str, str]:
    """Start a server on the CURRENT tree, run the walk, return (verdict, tail)."""
    env = {
        **os.environ,
        "MOBILE_DATABASE_URL": DB,
        "MOBILE_MEDIA_ROOT": MEDIA,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=API,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    try:
        if not wait_ready(proc):
            return "NOSERVER", "server khong len duoc (co the do chinh dot bien)"
        done = subprocess.run(
            [sys.executable, str(WALK), BASE],
            capture_output=True,
            text=True,
            timeout=420,
        )
        fails = [ln for ln in done.stdout.splitlines() if ln.strip().startswith("FAIL")]
        total = [ln for ln in done.stdout.splitlines() if ln.startswith("== TONG")]
        verdict = "GREEN" if done.returncode == 0 else "RED"
        tail = (total[-1] if total else "").strip()
        if fails:
            tail += " | dau tien: " + fails[0].strip()[:110]
        return verdict, tail
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=15)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass


def main() -> int:
    # Read every file ONCE, up front, and hold the originals in RAM. Anchors are
    # checked for uniqueness before anything is written: a fragment that matches
    # twice would patch a copy nobody is looking at and report a false GREEN.
    originals = {
        p: p.read_text()
        for p in {path for _, _, _, edits in ROWS for path, _, _ in edits}
    }
    for rid, _, _, edits in ROWS:
        for path, old, _ in edits:
            n = originals[path].count(old)
            if n != 1:
                print(f"NEO HONG: {rid} khop {n} lan trong {path.name}, can dung 1")
                return 2
    print("moc dot bien: moi neo khop dung 1 lan\n")

    print("== goc (khong dot bien) ==")
    base_verdict, base_tail = run_walk()
    print(f"  baseline: {base_verdict}  {base_tail}")
    if base_verdict != "GREEN":
        print("  cay goc da do -> khong doc duoc bang nao ben duoi. Dung.")
        return 2

    results = []
    try:
        for rid, desc, want, edits in ROWS:
            for path, old, new in edits:
                path.write_text(originals[path].replace(old, new, 1))
            # A row touching two files must apply both before the walk runs.
            for path, old, new in edits:
                assert new in path.read_text(), f"{rid}: khong ghi duoc {path.name}"
            got, tail = run_walk()
            ok = "DAT" if got == want else "**LOT**"
            print(f"  {rid} {got:8s} (muon {want:5s}) {ok}  {desc}")
            if tail:
                print(f"       {tail}")
            results.append((rid, desc, want, got, ok))
            for path in {p for p, _, _ in edits}:
                path.write_text(originals[path])
    finally:
        for path, text in originals.items():
            path.write_text(text)

    print("\n== bang ==")
    print(f"  {'id':4s} {'muon':6s} {'duoc':6s} {'':8s} mo ta")
    for rid, desc, want, got, ok in results:
        print(f"  {rid:4s} {want:6s} {got:6s} {ok:8s} {desc}")
    escaped = [r for r in results if r[4] != "DAT"]
    print(f"\n  {len(results)} dot bien, {len(escaped)} lot")
    return 1 if escaped else 0


if __name__ == "__main__":
    sys.exit(main())
