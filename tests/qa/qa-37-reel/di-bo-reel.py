"""Walk F37 `GET /contexts/{cid}/albums/{oid}/reel` against a LIVE API.

Every tier the branch ships fakes one side: `tests/api/` fakes the repository,
`tests/domain/` has no HTTP at all, and the postgres tier has no ASGI app in
front of the SQL.  This file drives the real uvicorn on a real PostgreSQL, so
the questions it answers are the ones no green tier above it can:

* does a member of group A get a body from group B, in any shape;
* does the reel actually choose photographs, or answer with an empty list;
* how many requests does the live ceiling admit, and over what window;
* do the URLs the reel hands out stay behind the photo route's own gate.

Usage: REEL_API=http://127.0.0.1:PORT python3 di-bo-reel.py
"""

from __future__ import annotations

import datetime
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("REEL_API", "http://127.0.0.1:8000").rstrip("/")

# The machine running this has a proxy that swallows loopback for both curl and
# Chrome; an opener with no proxy handler is the python-side of that fix.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

FAILURES: list[str] = []
NOTES: list[str] = []


def call(
    method: str,
    path: str,
    *,
    actor: str | None = None,
    roles: str = "member",
    contexts: str | None = None,
    body: dict | None = None,
    raw: tuple[bytes, str] | None = None,
) -> tuple[int, bytes, dict]:
    headers: dict[str, str] = {}
    if actor:
        headers["X-Actor-ID"] = actor
        headers["X-Actor-Roles"] = roles
        if contexts is not None:
            headers["X-Actor-Contexts"] = contexts
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if raw is not None:
        data, headers["Content-Type"] = raw
    request = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method
    )
    try:
        with _OPENER.open(request, timeout=90) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)


def js(payload: bytes) -> dict:
    try:
        return json.loads(payload)
    except Exception:
        return {}


def check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAILURES.append(f"{name}: {detail}")
    return ok


def person(phone: str, name: str) -> str:
    status, payload, _ = call("POST", "/identity/person-id", body={"phone": phone})
    assert status == 200, (status, payload[:300])
    person_id = js(payload)["person_id"]
    status, payload, _ = call(
        "PUT", f"/people/{person_id}", actor=person_id, body={"display_name": name}
    )
    assert status in (200, 201), (status, payload[:300])
    return person_id


def jpeg_with_gps() -> bytes:
    """A real JPEG carrying GPS + camera EXIF, so stripping is observable."""

    from PIL import Image

    image = Image.new("RGB", (640, 480), (200, 120, 90))
    for x in range(0, 640, 40):
        for y in range(0, 480, 40):
            if (x // 40 + y // 40) % 2:
                for dx in range(40):
                    for dy in range(40):
                        image.putpixel((x + dx, y + dy), (30, 60, 140))
    exif = Image.Exif()
    exif[0x010F] = "QA-CANARY-MAKE"  # Make
    exif[0x0110] = "QA-CANARY-MODEL"  # Model
    exif[0x9286] = "QA-CANARY-EXIF"  # UserComment, via the Exif IFD
    exif[0x8825] = {  # GPS IFD: Da Lat, to the second
        1: "N",
        2: (11.0, 56.0, 0.0),
        3: "E",
        4: (108.0, 26.0, 0.0),
    }
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def multipart(
    field: str, filename: str, content: bytes, ctype: str
) -> tuple[bytes, str]:
    boundary = "----qa37reel" + uuid.uuid4().hex
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {ctype}\r\n\r\n".encode(),
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def make_group(owner: str, name: str) -> str:
    status, payload, _ = call(
        "POST",
        "/contexts",
        actor=owner,
        roles="group_admin",
        body={"display_name": name},
    )
    assert status in (200, 201), (status, payload[:300])
    return js(payload)["id"]


def add_member(context_id: str, admin: str, who: str) -> None:
    status, payload, _ = call(
        "POST",
        f"/contexts/{context_id}/members",
        actor=admin,
        roles="group_admin",
        contexts=context_id,
        body={"person_id": who},
    )
    assert status in (200, 201), (status, payload[:300])
    membership = js(payload).get("id")
    if membership:
        call(
            "POST", f"/memberships/{membership}/accept", actor=who, contexts=context_id
        )


def make_outing(context_id: str, actor: str, title: str, day: str) -> str:
    status, payload, _ = call(
        "POST",
        f"/contexts/{context_id}/outings",
        actor=actor,
        roles="group_admin",
        contexts=context_id,
        body={
            "title": title,
            "starts_on": day,
            "ends_on": day,
            "headcount": 4,
            "budget_per_person_vnd": 200000,
        },
    )
    assert status in (200, 201), (status, payload[:400])
    return js(payload)["id"]


def post_memory(context_id: str, actor: str, image_url: str, caption: str) -> str:
    status, payload, _ = call(
        "POST",
        f"/contexts/{context_id}/memories",
        actor=actor,
        contexts=context_id,
        body={"image_url": image_url, "caption": caption},
    )
    assert status in (200, 201), (status, payload[:400])
    return js(payload)["id"]


def upload(context_id: str, actor: str, content: bytes) -> str:
    data, ctype = multipart("file", "anh.jpg", content, "image/jpeg")
    status, payload, _ = call(
        "POST",
        f"/contexts/{context_id}/photos",
        actor=actor,
        contexts=context_id,
        raw=(data, ctype),
    )
    assert status in (200, 201), (status, payload[:400])
    return js(payload)["url"]


def main() -> int:
    today = time.strftime("%Y-%m-%d")
    tag = uuid.uuid4().hex[:6]
    # Vietnamese mobile shape, digits only: 0 + 9 digits.
    stem = f"{uuid.uuid4().int % 1000000:06d}"

    an = person(f"090{stem}1", "An")
    binh = person(f"091{stem}2", "Binh")
    ke_la = person(f"093{stem}3", "Ke La")

    group_a = make_group(an, f"Nhom A {tag}")
    group_b = make_group(binh, f"Nhom B {tag}")
    add_member(group_a, an, binh) if False else None  # A and B stay disjoint

    outing_a = make_outing(group_a, an, "Chuyen A: Da Lat", today)
    outing_b = make_outing(group_b, binh, "Chuyen B: BI MAT NHOM B", today)
    # A trip claims memories by DATE, not by a foreign key (see the docstring of
    # `list_outing_memories`).  An "empty" outing on today's date would quietly
    # inherit the three photographs below and spend a real model call per
    # request; a past week is the only way to get a genuinely empty trip.
    long_ago = (
        datetime.date.fromisoformat(today) - datetime.timedelta(days=40)
    ).isoformat()
    outing_a_empty = make_outing(group_a, an, "Chuyen A rong", long_ago)

    print(
        f"\n== bo du lieu ==\nA ctx={group_a} outing={outing_a}\nB ctx={group_b} outing={outing_b}\n"
    )

    # --- group A gets three photographs with EXIF baked in -------------------
    raw = jpeg_with_gps()
    urls = []
    memory_ids = []
    captions = [
        "Ca nhom cuoi vo bung o doc Prenn",
        "Binh minh tren Langbiang, lanh cong ca tay",
        "To bun bo goc pho ai cung khen",
    ]
    for caption in captions:
        url = upload(group_a, an, raw)
        urls.append(url)
        memory_ids.append(post_memory(group_a, an, url, caption))

    url_b = upload(group_b, binh, raw)
    memory_b = post_memory(group_b, binh, url_b, "BI MAT NHOM B khong ai duoc thay")

    # --- 1. the happy path: does it actually pick photographs ---------------
    status, payload, _ = call(
        "GET", f"/contexts/{group_a}/albums/{outing_a}/reel", actor=an, contexts=group_a
    )
    reel = js(payload)
    print("\n-- thuoc phim cua A --")
    print(json.dumps(reel, ensure_ascii=False, indent=2)[:1400])
    check(
        "A doc duoc thuoc phim cua chinh minh: 200", status == 200, f"status={status}"
    )
    check(
        "thuoc phim CHON duoc anh that (picks > 0, source=ai)",
        bool(reel.get("picks"))
        and reel.get("source") == "ai"
        and reel.get("reeled") is True,
        f"reeled={reel.get('reeled')} source={reel.get('source')} reason={reel.get('reason')} picks={len(reel.get('picks') or [])}",
    )
    picked_ids = {p["memory_id"] for p in reel.get("picks", [])}
    check(
        "moi pick tro ve dung ky uc cua nhom A",
        picked_ids <= set(memory_ids),
        f"picked={picked_ids} offered={set(memory_ids)}",
    )
    check(
        "moi pick co image_url do MAY CHU gan, va co note",
        all(p.get("image_url") and p.get("note") for p in reel.get("picks", [])),
        json.dumps(reel.get("picks", [])[:1], ensure_ascii=False)[:300],
    )
    check(
        "considered_count = so anh may chu thuc su doc",
        reel.get("considered_count") == len(memory_ids),
        f"considered={reel.get('considered_count')} that={len(memory_ids)}",
    )

    # --- 2. cross-group: the lying intruder --------------------------------
    real_403 = call(
        "GET",
        f"/contexts/{group_b}/albums/{outing_b}/reel",
        actor=an,
        contexts=group_b,  # A LIES: claims membership of B in the header
    )
    fake_uuid = str(uuid.uuid4())
    fake_403 = call(
        "GET",
        f"/contexts/{group_b}/albums/{fake_uuid}/reel",
        actor=an,
        contexts=group_b,
    )
    ghost_ctx = str(uuid.uuid4())
    ghost_403 = call(
        "GET",
        f"/contexts/{ghost_ctx}/albums/{fake_uuid}/reel",
        actor=an,
        contexts=ghost_ctx,
    )
    print("\n-- 403 cua ke noi doi --")
    print("outing THAT cua B  :", real_403[0], real_403[1][:200])
    print("outing BIA cua B   :", fake_403[0], fake_403[1][:200])
    print("context BIA hoan toan:", ghost_403[0], ghost_403[1][:200])
    check(
        "nguoi nhom A noi doi header van bi 403 o nhom B",
        real_403[0] == 403,
        f"status={real_403[0]} body={real_403[1][:200]!r}",
    )
    check(
        "403 cua outing THAT giong HET 403 cua outing BIA (khong phai may do id)",
        real_403[1] == fake_403[1] and real_403[0] == fake_403[0],
        f"that={real_403[1][:120]!r} bia={fake_403[1][:120]!r}",
    )
    check(
        "403 cua context co that giong HET 403 cua context bia",
        real_403[1] == ghost_403[1],
        f"that={real_403[1][:120]!r} ma={ghost_403[1][:120]!r}",
    )
    leak_needles = ["BI MAT NHOM B", memory_b, url_b, "Nhom B"]
    blob = (real_403[1] + fake_403[1] + ghost_403[1]).decode("utf-8", "replace")
    check(
        "than 403 khong chua BAT KY dau vet nao cua nhom B",
        not any(needle in blob for needle in leak_needles),
        blob[:300],
    )

    # negative control: the needles ARE findable when the caller is allowed
    status_b, payload_b, _ = call(
        "GET",
        f"/contexts/{group_b}/albums/{outing_b}/reel",
        actor=binh,
        contexts=group_b,
    )
    control_blob = payload_b.decode("utf-8", "replace")
    check(
        "DOI CHUNG: chinh chu nhom B THAY duoc du lieu cua minh (neu khong, phep do tren la rong)",
        status_b == 200
        and ("BI MAT NHOM B" in control_blob or memory_b in control_blob),
        f"status={status_b} body={control_blob[:250]}",
    )

    # --- 3. outing of another group through MY own context ------------------
    status_x, payload_x, _ = call(
        "GET", f"/contexts/{group_a}/albums/{outing_b}/reel", actor=an, contexts=group_a
    )
    check(
        "outing cua nhom B qua context cua nhom A -> 404, khong ro ri",
        status_x == 404 and "BI MAT NHOM B" not in payload_x.decode("utf-8", "replace"),
        f"status={status_x} body={payload_x[:200]!r}",
    )

    # --- 4. total stranger --------------------------------------------------
    status_s, payload_s, _ = call(
        "GET",
        f"/contexts/{group_a}/albums/{outing_a}/reel",
        actor=ke_la,
        contexts=group_a,
    )
    check(
        "nguoi la hoan toan -> 403",
        status_s == 403,
        f"status={status_s} {payload_s[:150]!r}",
    )

    # --- 5. empty state -----------------------------------------------------
    status_e, payload_e, _ = call(
        "GET",
        f"/contexts/{group_a}/albums/{outing_a_empty}/reel",
        actor=an,
        contexts=group_a,
    )
    empty = js(payload_e)
    print("\n-- trang thai rong --")
    print(status_e, json.dumps(empty, ensure_ascii=False))
    check(
        "chuyen di khong co anh -> 200 va reason=no_memories, KHONG 404",
        status_e == 200
        and empty.get("reason") == "no_memories"
        and empty.get("picks") == [],
        f"status={status_e} body={payload_e[:250]!r}",
    )
    check(
        "trang thai rong khong lo gi ve nhom",
        empty.get("title") is None and empty.get("considered_count") == 0,
        json.dumps(empty, ensure_ascii=False),
    )

    # --- 6. EXIF + photo URL authorisation ---------------------------------
    first_url = (
        reel.get("picks", [{}])[0].get("image_url") if reel.get("picks") else urls[0]
    )
    status_p, blob_p, headers_p = call("GET", first_url, actor=an, contexts=group_a)
    check("chu anh tai duoc anh: 200", status_p == 200, f"status={status_p}")
    check(
        "anh da bi TUOC EXIF (khong con GPS / Make / UserComment canary)",
        b"QA-CANARY-EXIF" not in blob_p
        and b"QA-CANARY-MAKE" not in blob_p
        and b"Exif\x00\x00" not in blob_p,
        f"len={len(blob_p)} co_exif_marker={b'Exif' in blob_p}",
    )
    check(
        "DOI CHUNG: file goc THAT SU co canary (neu khong, phep do EXIF la rong)",
        b"QA-CANARY-EXIF" in raw and b"QA-CANARY-MAKE" in raw,
        f"anh goc {len(raw)} byte, co Exif marker={b'Exif' in raw}",
    )
    status_n, blob_n, _ = call("GET", first_url, actor=ke_la, contexts=group_a)
    check(
        "nguoi ngoai nhom KHONG tai duoc URL anh trong thuoc phim",
        status_n in (403, 404) and b"JFIF" not in blob_n[:64],
        f"status={status_n} len={len(blob_n)}",
    )
    status_no, blob_no, _ = call("GET", first_url)
    check(
        "khong co danh tinh -> khong tai duoc anh",
        status_no in (401, 403, 422) and b"JFIF" not in blob_no[:64],
        f"status={status_no} len={len(blob_no)}",
    )

    # --- 6b. the guest surface never reaches this route ---------------------
    guest_token = "qa37" + uuid.uuid4().hex
    st_g, bd_g, _ = call(
        "GET", f"/contexts/{group_a}/albums/{outing_a}/reel", actor=guest_token
    )
    check(
        "token kieu khach lam X-Actor-ID -> khong doc duoc thuoc phim",
        st_g in (403, 404, 422) and b"note" not in bd_g,
        f"status={st_g} body={bd_g[:160]!r}",
    )
    st_gp, bd_gp, _ = call("GET", f"/g/{guest_token}")
    check(
        "trang khach /g/<token> khong he nhac toi thuoc phim",
        b"reel" not in bd_gp.lower() and b"thuoc phim" not in bd_gp.lower(),
        f"status={st_gp} len={len(bd_gp)}",
    )

    # --- 7. the live ceiling, measured on the empty outing -----------------
    # `limiter.check` runs in the route BEFORE the service, so an outing with
    # no memories charges the window without spending a model call.
    hammer = person(f"097{stem}4", "Nguoi Go Cua")
    add_member(group_a, an, hammer)
    admitted = 0
    refused_status = None
    refused_body = b""
    started = time.monotonic()
    for _ in range(45):
        st, bd, _ = call(
            "GET",
            f"/contexts/{group_a}/albums/{outing_a_empty}/reel",
            actor=hammer,
            contexts=group_a,
        )
        if st == 200:
            admitted += 1
            continue
        refused_status, refused_body = st, bd
        break
    elapsed = time.monotonic() - started
    print(
        f"\n-- tran nhip --\nadmitted={admitted} roi {refused_status} sau {elapsed:.1f}s",
        flush=True,
    )
    print("than 429:", refused_body[:250])
    check(
        "tran nhip chan that su tren app that",
        refused_status == 429,
        f"sau {admitted} luot ma van chua bi chan (status={refused_status})",
    )
    check(
        "tran dung 30 luot / cua so",
        admitted == 30,
        f"admitted={admitted}",
    )
    check(
        "ma loi 429 la reel_rate_limited (khong muon ten cua cua khac)",
        js(refused_body).get("code") == "reel_rate_limited",
        refused_body[:200].decode("utf-8", "replace"),
    )
    # An independent budget: the hammered actor must not have spent anyone else's.
    st_other, _, _ = call(
        "GET",
        f"/contexts/{group_a}/albums/{outing_a_empty}/reel",
        actor=an,
        contexts=group_a,
    )
    check(
        "actor khac VAN qua duoc sau khi mot actor bi chan (ngan sach theo nguoi)",
        st_other == 200,
        f"status={st_other}",
    )
    st_door, _, _ = call(
        "GET", f"/contexts/{group_a}/albums/{outing_a}", actor=hammer, contexts=group_a
    )
    check(
        "cua khac (album F36) van mo cho chinh actor da bi chan o reel",
        st_door == 200,
        f"status={st_door}",
    )
    NOTES.append(
        f"cua so do duoc: {admitted} luot trong {elapsed:.1f}s roi 429; "
        "hang so khai bao REEL_WINDOW_SECONDS=60"
    )

    print("\n==================== TONG KET ====================")
    for note in NOTES:
        print("ghi chu:", note)
    if FAILURES:
        print(f"\nFAIL: {len(FAILURES)} phep kiem hong")
        for failure in FAILURES:
            print("  -", failure)
        return 1
    print("\nTat ca phep kiem live DAT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
