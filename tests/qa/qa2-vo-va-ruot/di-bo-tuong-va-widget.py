"""Walk F35 (memory wall) and F38 (home-screen widget) against a LIVE API.

## Why this file exists

A QA report of mine (`docs/claude/2026-08-31/qa2-042742-do-lai-47-tren-880cd6d.md`)
filed F35 and F38 as "the shell is all I can prove", on the reasoning that the
guts need photographs and that putting photographs into a group would break
CLAUDE.md's rule about real data. That reasoning was wrong, and this file is the
correction.

The rule forbids *real* bill images and *real* people. It does not forbid a
group having photographs at all. `tests/qa/qa-37-reel/di-bo-reel.py` had already
shown the way a year of QA reports missed: generate a checkerboard JPEG in
memory, upload it through the same multipart route the app uses, and the group
now has photographs that belong to nobody. `MOBILE_MEDIA_ROOT` on a provisioned
stack points at a temp directory, so the bytes never come near the repository.

So the honest label for these two rows was never "cannot be measured". It was
"nobody has measured it". This file measures it.

## What it asks that no green tier above it can

`tests/api/` runs on a fake repository, which stores an `image_url` as a string
and is therefore incapable of noticing that the string points at nothing. That
is exactly the failure a user sees as a wall of broken thumbnails. The only way
to catch it is to fetch every URL the wall hands out and confirm bytes come
back that decode as an image of the size that went in.

* does the wall return the rows, newest first, with usable `image_url`s;
* does each of those URLs actually serve a decodable image, or just 404;
* does the widget switch off "no photographs yet" once photographs exist;
* does the widget hand out the NEWEST photograph rather than an arbitrary one;
* does any of it leak across groups.

Usage: WALL_API=http://127.0.0.1:PORT python3 di-bo-tuong-va-widget.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("WALL_API", "http://127.0.0.1:8000").rstrip("/")

# Same reason as the reel probe: this machine's proxy swallows loopback.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

FAILURES: list[str] = []


def call(
    method: str,
    path: str,
    *,
    actor: str | None = None,
    roles: str = "member",
    contexts: str | None = None,
    body: dict | None = None,
    raw: tuple[bytes, str] | None = None,
) -> tuple[int, bytes]:
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
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def js(payload: bytes) -> dict:
    try:
        return json.loads(payload)
    except Exception:
        return {}


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")
    return ok


def photo_bytes(tag: int) -> bytes:
    """A synthetic JPEG. No camera took it and no person is in it.

    The band of `tag`-coloured pixels down the left edge makes each upload
    distinguishable from the others after a round trip, so "the widget served
    the newest photo" is checkable by content and not only by a URL string.
    """

    from PIL import Image

    image = Image.new("RGB", (320, 240), (240, 240, 240))
    for x in range(0, 320, 32):
        for y in range(0, 240, 32):
            if (x // 32 + y // 32) % 2:
                for dx in range(min(32, 320 - x)):
                    for dy in range(min(32, 240 - y)):
                        image.putpixel((x + dx, y + dy), (40, 90, 160))
    for x in range(8):
        for y in range(240):
            image.putpixel((x, y), (tag * 40 % 256, 20, 20))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def multipart(content: bytes) -> tuple[bytes, str]:
    boundary = "----qa2wall" + uuid.uuid4().hex
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="anh.jpg"\r\n',
            b"Content-Type: image/jpeg\r\n\r\n",
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def person(phone: str, name: str) -> str:
    status, payload = call("POST", "/identity/person-id", body={"phone": phone})
    assert status == 200, (status, payload[:300])
    person_id = js(payload)["person_id"]
    status, payload = call(
        "PUT", f"/people/{person_id}", actor=person_id, body={"display_name": name}
    )
    assert status in (200, 201), (status, payload[:300])
    return person_id


def make_group(owner: str, name: str) -> str:
    status, payload = call(
        "POST",
        "/contexts",
        actor=owner,
        roles="group_admin",
        body={"display_name": name},
    )
    assert status in (200, 201), (status, payload[:300])
    return js(payload)["id"]


def add_member(context_id: str, admin: str, who: str) -> None:
    status, payload = call(
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


def upload(context_id: str, actor: str, content: bytes) -> str:
    data, ctype = multipart(content)
    status, payload = call(
        "POST",
        f"/contexts/{context_id}/photos",
        actor=actor,
        contexts=context_id,
        raw=(data, ctype),
    )
    assert status in (200, 201), (status, payload[:400])
    return js(payload)["url"]


def post_memory(context_id: str, actor: str, image_url: str, caption: str) -> str:
    status, payload = call(
        "POST",
        f"/contexts/{context_id}/memories",
        actor=actor,
        contexts=context_id,
        body={"image_url": image_url, "caption": caption},
    )
    assert status in (200, 201), (status, payload[:400])
    return js(payload)["id"]


def decode_size(blob: bytes) -> tuple[int, int] | None:
    from PIL import Image

    try:
        return Image.open(io.BytesIO(blob)).size
    except Exception:
        return None


def main() -> int:
    # Vietnamese mobile shape, digits only: 0 + 9 digits.
    stem = f"{uuid.uuid4().int % 1000000:06d}"
    an = person(f"090{stem}1", "An")
    binh = person(f"091{stem}2", "Binh")
    la = person(f"093{stem}3", "Nguoi La")

    group = make_group(an, "Nhom tuong ky niem")
    add_member(group, an, binh)
    empty_group = make_group(an, "Nhom chua co anh")

    print(f"\n== bo du lieu ==\nnhom={group}  nhom rong={empty_group}\n")

    # --- 0. the empty state, measured BEFORE seeding ------------------------
    # This is the control that gives the seeded reading its meaning. Without
    # it, "the widget shows a photo" could just be a widget that always shows
    # something, and the report would not be able to tell the difference.
    status, payload = call(
        "GET", f"/contexts/{empty_group}/widget", actor=an, contexts=empty_group
    )
    empty_widget = js(payload)
    check(
        "DOI CHUNG: nhom chua co anh -> widget 200 va photo=None",
        status == 200 and empty_widget.get("photo") is None,
        f"status={status} photo={empty_widget.get('photo')}",
    )

    status, payload = call(
        "GET", f"/contexts/{empty_group}/memories", actor=an, contexts=empty_group
    )
    check(
        "DOI CHUNG: nhom chua co anh -> tuong 200 va rong",
        status == 200 and js(payload).get("memories") == [],
        f"status={status} n={len(js(payload).get('memories', []))}",
    )

    # --- 1. seed three photographs -----------------------------------------
    originals: list[bytes] = []
    urls: list[str] = []
    for i in range(1, 4):
        blob = photo_bytes(i)
        originals.append(blob)
        urls.append(upload(group, an, blob))
        post_memory(group, an, urls[-1], f"Anh thu {i}")

    # --- 2. F35: the wall ---------------------------------------------------
    status, payload = call(
        "GET", f"/contexts/{group}/memories", actor=an, contexts=group
    )
    wall = js(payload)
    memories = wall.get("memories", [])
    check(
        "F35 tuong tra ve du 3 ky uc vua dang",
        status == 200 and len(memories) == 3,
        f"status={status} n={len(memories)}",
    )
    check(
        "F35 mỗi dòng của tường có image_url va caption",
        all(m.get("image_url") and m.get("caption") for m in memories),
        json.dumps([m.get("caption") for m in memories], ensure_ascii=False),
    )
    check(
        "F35 tuong xep MOI NHAT truoc",
        [m.get("caption") for m in memories] == ["Anh thu 3", "Anh thu 2", "Anh thu 1"],
        json.dumps([m.get("caption") for m in memories], ensure_ascii=False),
    )

    # The question a fake repository structurally cannot answer: the string is
    # there, but is there a photograph behind it?
    resolved: list[tuple[int, int, int] | None] = []
    for m in memories:
        st, blob = call("GET", m["image_url"], actor=an, contexts=group)
        size = decode_size(blob) if st == 200 else None
        resolved.append((st, *size) if size else None)
    check(
        "F35 MOI image_url cua tuong tai duoc va giai ma duoc thanh anh 320x240",
        all(r is not None and r[0] == 200 and r[1:] == (320, 240) for r in resolved),
        str(resolved),
    )

    # --- 3. F38: the widget -------------------------------------------------
    status, payload = call("GET", f"/contexts/{group}/widget", actor=an, contexts=group)
    widget = js(payload)
    photo = widget.get("photo") or {}
    check(
        "F38 nhom CO anh -> widget khong con rong",
        status == 200 and widget.get("photo") is not None,
        f"status={status} photo={json.dumps(photo, ensure_ascii=False)[:200]}",
    )
    check(
        "F38 widget cam dung tam anh MOI NHAT (theo caption)",
        photo.get("caption") == "Anh thu 3",
        f"caption={photo.get('caption')!r} image_url={photo.get('image_url')!r}",
    )

    if photo.get("image_url"):
        st, blob = call("GET", photo["image_url"], actor=an, contexts=group)
        size = decode_size(blob)
        check(
            "F38 anh cua widget tai duoc va giai ma duoc",
            st == 200 and size == (320, 240),
            f"status={st} size={size} len={len(blob)}",
        )
        # Content, not just a URL: the newest upload carried tag 3.
        check(
            "F38 anh widget dung LA tam thu 3 (so theo noi dung, khong theo URL)",
            photo["image_url"] == urls[2],
            f"widget={photo['image_url']} tam3={urls[2]}",
        )

    # --- 4. neither row leaks across a group boundary -----------------------
    for path, label in (
        (f"/contexts/{group}/widget", "widget"),
        (f"/contexts/{group}/memories", "tuong"),
    ):
        st, body = call("GET", path, actor=la, contexts=group)
        check(
            f"nguoi la doc {label} cua nhom khac -> 403",
            st == 403,
            f"status={st} body={body[:120]!r}",
        )

    st, body = call("GET", urls[0], actor=la, contexts=group)
    check(
        "nguoi la tai anh cua nhom khac -> 403",
        st == 403,
        f"status={st} len={len(body)}",
    )

    # Binh is a real member: if this were 403 too, the three checks above would
    # be proving nothing but a blanket denial.
    st, body = call("GET", f"/contexts/{group}/widget", actor=binh, contexts=group)
    check(
        "DOI CHUNG: thanh vien that VAN doc duoc widget",
        st == 200 and js(body).get("photo") is not None,
        f"status={st}",
    )

    print("\n==================== TONG KET ====================")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} phep kiem hong")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("OK: tat ca phep kiem xanh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
