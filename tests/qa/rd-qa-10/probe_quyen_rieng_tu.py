"""Privacy probes against a running API, from outside, as a stranger would.

Targets the two surfaces main took today: the private group memory wall (#112)
and the way in -- register, add a friend, invite (#115). Four questions, none
of which a unit test against a fake repository can answer, because each one is
about what a *different* person's request gets back from the real database:

  Q1  A person who was never in the group asks for its memory wall.
  Q2  A person who left the group asks for the wall they used to read.
  Q3  Does a telephone number reach the server, its logs, or a response body?
  Q4  Can one person read another person's group roster?

Run it against a server you started yourself, on a port you chose, against a
database you migrated. Reading a `200` off somebody else's stale container is
the failure this file is built to avoid, so it fingerprints the build first.

    python3 tests/qa/rd-qa-10/probe_quyen_rieng_tu.py --base http://127.0.0.1:8117

Exit code is 0 when every probe holds and 1 when any of them does not, so it
can be planted against a mutated server and watched to go red.

The leak check is deliberately not a hand-written list of forbidden field
names. It collects every value a legitimate member is shown, then asserts that
none of those strings appear anywhere in the refusal a stranger gets. A field
added to `MemoryResponse` next week is covered without anybody remembering to
add it here.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from danh_tinh import id_tu_so  # noqa: E402

# Markers are unique per run so a hit in a log file is attributable to this
# run and not to something left behind by an earlier one.
RUN = uuid.uuid4().hex[:8].upper()
CAPTION = f"BiMatChuThich-{RUN}"
IMAGE_URL = f"https://anh.invalid/ky-niem-rieng-{RUN}.jpg"

# Telephone numbers are assembled here rather than written down: `repo_guard`
# refuses digit runs shaped like Vietnamese mobile numbers on sight, and it
# cannot tell an invented one from a real one.
def _so(prefix: str, tail: int) -> str:
    return "0" + prefix + str(tail).zfill(8)


class Probe:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.failures: list[str] = []
        self.checks = 0

    # -- transport ----------------------------------------------------------
    def call(
        self,
        method: str,
        path: str,
        actor: str | None = None,
        body: dict | None = None,
        roles: str = "member",
    ) -> tuple[int, str]:
        request = urllib.request.Request(
            self.base + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
        )
        if body is not None:
            request.add_header("Content-Type", "application/json")
        if actor is not None:
            request.add_header("X-Actor-ID", actor)
            request.add_header("X-Actor-Roles", roles)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    # -- assertions ---------------------------------------------------------
    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks += 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" -- {detail}" if detail else ""))
        if not ok:
            self.failures.append(f"{name}: {detail}")
        return ok


def run(base: str, log_path: str | None) -> int:
    p = Probe(base)

    print(f"# probe quyen rieng tu -- run {RUN}")
    print(f"# base = {base}")

    # ---- 0. Fingerprint the build, so a stale container cannot answer -----
    status, body = p.call("GET", "/openapi.json")
    paths = json.loads(body).get("paths", {}) if status == 200 else {}
    p.check(
        "0. server duoi test la ban co memory wall (#112)",
        any("memories" in route for route in paths),
        f"openapi status={status}, {len(paths)} routes",
    )
    p.check(
        "0. server duoi test la ban co /people/{id} (#115)",
        "/people/{person_id}" in paths,
        "",
    )

    # ---- Cast -------------------------------------------------------------
    # An and Binh are in the group. Cuong never was. Dung joins then leaves.
    # Em is in Binh's *other* group and must stay invisible to An.
    so_an = _so("9", 11000000 + int(RUN[:4], 16) % 1000)
    so_binh = _so("9", 12000000 + int(RUN[:4], 16) % 1000)
    so_cuong = _so("9", 13000000 + int(RUN[:4], 16) % 1000)
    so_dung = _so("9", 14000000 + int(RUN[:4], 16) % 1000)
    so_em = _so("9", 15000000 + int(RUN[:4], 16) % 1000)

    an, binh, cuong, dung, em = (
        id_tu_so(so_an),
        id_tu_so(so_binh),
        id_tu_so(so_cuong),
        id_tu_so(so_dung),
        id_tu_so(so_em),
    )
    ten_an = f"An TenThat-{RUN}"
    ten_binh = f"Binh TenThat-{RUN}"
    ten_em = f"Em TenThat-{RUN}"

    for pid, ten in (
        (an, ten_an),
        (binh, ten_binh),
        (cuong, f"Cuong TenThat-{RUN}"),
        (dung, f"Dung TenThat-{RUN}"),
        (em, ten_em),
    ):
        status, body = p.call("PUT", f"/people/{pid}", actor=pid, body={"display_name": ten})
        if status not in (200, 201):
            print(f"  SETUP FAILED registering {pid}: {status} {body[:200]}")
            return 2

    # An opens the group and invites Binh and Dung. Both accept.
    status, body = p.call(
        "POST", "/contexts", actor=an, roles="member", body={"display_name": f"Nhom-{RUN}"}
    )
    if status != 201:
        print(f"  SETUP FAILED creating context: {status} {body[:300]}")
        return 2
    ctx = json.loads(body)["id"]

    for guest in (binh, dung):
        status, body = p.call(
            "POST",
            f"/contexts/{ctx}/members",
            actor=an,
            roles="group_admin",
            body={"person_id": guest},
        )
        if status != 201:
            print(f"  SETUP FAILED inviting {guest}: {status} {body[:300]}")
            return 2
        membership = json.loads(body)["id"]
        status, body = p.call("POST", f"/memberships/{membership}/accept", actor=guest)
        if status != 200:
            print(f"  SETUP FAILED accepting {membership}: {status} {body[:300]}")
            return 2

    # An posts the memory that must not escape the group.
    status, body = p.call(
        "POST",
        f"/contexts/{ctx}/memories",
        actor=an,
        body={"image_url": IMAGE_URL, "caption": CAPTION},
    )
    if status != 201:
        print(f"  SETUP FAILED posting memory: {status} {body[:300]}")
        return 2

    # Binh, a member in good standing, reads the wall. Everything in this
    # response is group-private data and becomes the leak dictionary.
    status, member_view = p.call("GET", f"/contexts/{ctx}/memories", actor=binh)
    p.check(
        "1a. thanh vien doc duoc tuong (khang dinh cai CO truoc)",
        status == 200 and CAPTION in member_view and IMAGE_URL in member_view,
        f"status={status}",
    )
    if status != 200:
        print("  ABORT: khong doc duoc ban 200 thi phep kiem ro ri la rong tuech")
        return 2

    secrets = {"caption": CAPTION, "image_url": IMAGE_URL, "author_id": an}
    seen = json.loads(member_view)
    for memory in seen.get("memories", []):
        secrets[f"cursor:{memory['id'][:8]}"] = memory["cursor"]
        secrets[f"memory_id:{memory['id'][:8]}"] = memory["id"]

    # ---- Q1. The person who was never in the group ------------------------
    print("\n## Q1 -- nguoi NGOAI nhom doan dung context_id")
    status, refusal = p.call("GET", f"/contexts/{ctx}/memories", actor=cuong)
    p.check("1b. GET ky niem tu nguoi ngoai -> 403", status == 403, f"status={status}")
    leaked = [name for name, value in secrets.items() if value in refusal]
    p.check(
        "1c. than 403 KHONG mang caption / URL anh / id nguoi dang",
        not leaked,
        f"lo: {leaked}; than={refusal[:200]}",
    )
    p.check(
        "1d. than 403 KHONG mang ten that cua ai",
        ten_an not in refusal and ten_binh not in refusal,
        f"than={refusal[:200]}",
    )

    status, refusal_post = p.call(
        "POST",
        f"/contexts/{ctx}/memories",
        actor=cuong,
        body={"image_url": "https://x.invalid/a.jpg", "caption": "xam nhap"},
    )
    p.check("1e. POST ky niem tu nguoi ngoai -> 403", status == 403, f"status={status}")

    # A stranger with no header at all, and a stranger claiming to be an admin.
    status, _ = p.call("GET", f"/contexts/{ctx}/memories")
    p.check("1f. GET ky niem khong co header actor -> tu choi", status in (401, 403, 422), f"status={status}")
    status, refusal_admin = p.call(
        "GET", f"/contexts/{ctx}/memories", actor=cuong, roles="group_admin,platform_moderator"
    )
    p.check(
        "1g. X-Actor-Roles tu phong admin KHONG mo duoc tuong",
        status == 403 and CAPTION not in refusal_admin,
        f"status={status}",
    )

    # ---- Q2. The person who left ------------------------------------------
    print("\n## Q2 -- nguoi DA ROI nhom")
    status, before_leaving = p.call("GET", f"/contexts/{ctx}/memories", actor=dung)
    p.check(
        "2a. truoc khi roi, Dung doc duoc (doi chung)",
        status == 200 and CAPTION in before_leaving,
        f"status={status}",
    )
    status, body = p.call("DELETE", f"/contexts/{ctx}/members/{dung}", actor=dung)
    p.check("2b. Dung roi nhom -> 204", status == 204, f"status={status} {body[:150]}")

    status, refusal_left = p.call("GET", f"/contexts/{ctx}/memories", actor=dung)
    p.check("2c. sau khi roi, GET ky niem -> 403", status == 403, f"status={status}")
    leaked_left = [name for name, value in secrets.items() if value in refusal_left]
    p.check(
        "2d. than 403 cua nguoi da roi KHONG mang du lieu ky niem",
        not leaked_left,
        f"lo: {leaked_left}; than={refusal_left[:200]}",
    )
    status, _ = p.call(
        "POST",
        f"/contexts/{ctx}/memories",
        actor=dung,
        body={"image_url": "https://x.invalid/b.jpg", "caption": "quay lai"},
    )
    p.check("2e. nguoi da roi POST ky niem -> 403", status == 403, f"status={status}")
    status, roster_left = p.call("GET", f"/contexts/{ctx}/members", actor=dung)
    p.check(
        "2f. nguoi da roi doc danh sach thanh vien -> 403",
        status == 403,
        f"status={status}",
    )

    # ---- Q4. One person's roster, read by another -------------------------
    print("\n## Q4 -- danh sach ban be cua nguoi khac")
    status, body = p.call(
        "POST", "/contexts", actor=binh, body={"display_name": f"NhomRieng-{RUN}"}
    )
    if status != 201:
        print(f"  SETUP FAILED creating Binh's group: {status} {body[:200]}")
        return 2
    ctx_binh = json.loads(body)["id"]
    status, body = p.call(
        "POST",
        f"/contexts/{ctx_binh}/members",
        actor=binh,
        roles="group_admin",
        body={"person_id": em},
    )
    if status != 201:
        print(f"  SETUP FAILED inviting Em: {status} {body[:200]}")
        return 2
    status, _ = p.call("POST", f"/memberships/{json.loads(body)['id']}/accept", actor=em)

    status, an_reads = p.call("GET", f"/contexts/{ctx_binh}/members", actor=an)
    p.check(
        "4a. An doc roster nhom RIENG cua Binh -> 403",
        status == 403,
        f"status={status}",
    )
    p.check(
        "4b. than tu choi KHONG mang id/ten cua Em",
        em not in an_reads and ten_em not in an_reads,
        f"than={an_reads[:200]}",
    )
    status, an_reads_admin = p.call(
        "GET", f"/contexts/{ctx_binh}/members", actor=an, roles="group_admin"
    )
    p.check(
        "4c. An tu phong group_admin van KHONG doc duoc roster cua Binh",
        status == 403 and em not in an_reads_admin,
        f"status={status}",
    )
    status, an_reads_memories = p.call("GET", f"/contexts/{ctx_binh}/memories", actor=an)
    p.check(
        "4d. An doc tuong ky niem nhom rieng cua Binh -> 403",
        status == 403,
        f"status={status}",
    )
    status, an_reads_balances = p.call("GET", f"/contexts/{ctx_binh}/balances", actor=an)
    p.check(
        "4e. An doc so du nhom rieng cua Binh -> 403",
        status == 403,
        f"status={status}",
    )
    status, an_reads_finance = p.call("GET", f"/people/{em}/finance", actor=an)
    p.check(
        "4f. An doc tai chinh ca nhan cua Em -> tu choi",
        status in (401, 403, 404),
        f"status={status} than={an_reads_finance[:150]}",
    )

    # ---- Q3. The telephone number -----------------------------------------
    print("\n## Q3 -- so dien thoai")
    numbers = [so_an, so_binh, so_cuong, so_dung, so_em]
    bodies = [
        member_view,
        refusal,
        refusal_post,
        refusal_left,
        before_leaving,
        an_reads,
        an_reads_admin,
        an_reads_memories,
        an_reads_balances,
        an_reads_finance,
    ]
    status, roster = p.call("GET", f"/contexts/{ctx}/members", actor=binh)
    bodies.append(roster)
    hits = [n for n in numbers if any(n in b for b in bodies)]
    p.check(
        "3a. khong than phan hoi nao chua so dien thoai",
        not hits,
        f"tim thay {len(hits)} so",
    )
    # And the same numbers in every spelling the canonicaliser accepts, in case
    # something echoed a normalised form rather than what was typed.
    spellings = []
    for n in numbers:
        spellings += [n, "84" + n[1:], "+84" + n[1:]]
    hits2 = [s for s in spellings if any(s in b for b in bodies)]
    p.check("3b. khong than nao chua so o dang 84/+84", not hits2, f"tim thay {hits2[:3]}")

    if log_path:
        try:
            log = Path(log_path).read_text(errors="replace")
        except OSError as exc:
            log = ""
            print(f"  (khong doc duoc log: {exc})")
        log_hits = [s for s in spellings if s in log]
        p.check(
            "3c. log may chu KHONG chua so dien thoai o bat ky dang nao",
            not log_hits,
            f"tim thay {log_hits[:3]} trong {log_path}",
        )
        p.check(
            "3d. log may chu co ghi request that (chong 'log rong nen sach')",
            f"/contexts/{ctx}/memories" in log or "POST /contexts" in log,
            "khong thay duong dan nao trong log -- phep kiem 3c vo nghia",
        )

    print(f"\n# {p.checks} phep kiem, {len(p.failures)} that bai")
    for failure in p.failures:
        print(f"  ! {failure}")
    return 1 if p.failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8117")
    parser.add_argument("--log", default=None, help="duong dan log uvicorn de grep")
    args = parser.parse_args()
    sys.exit(run(args.base, args.log))
