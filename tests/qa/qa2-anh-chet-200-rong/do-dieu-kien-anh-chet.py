"""Measure every condition under which the two byte-serving routes answer.

## Why this file exists

A mutation run on F35 (`qa2-060012`, PR #428) forced `PhotoStorage.read` to
return `b""` and noticed something nobody had asked about: the route answered
**HTTP 200 with zero bytes**, not 404. A check written as `assert status == 200`
stays green over a wall of completely broken thumbnails.

That was a mutation, not a real condition. A mutation proves a *measurement*
can bite; it does not prove a *user* can reach the state. This file separates
the two. It walks each way the bytes behind a photo can be missing or wrong and
records what the route actually returns, so the shape of the answer is a
measurement rather than a reading of the source.

The product has exactly two routes that emit image bytes -- `photos.py:76` and
`photos.py:115`, found by grepping every `Response(content=...)` under
`app/api/routes/`. Both are measured here.

## The conditions, and why each one is separate

A "dead image" is not one state. These are different failures with different
right answers, and collapsing them is how a report ends up recommending a fix
for something no user can hit:

  A  no DB row for the id            the caller asked for a photo that never was
  B  DB row, file deleted            storage lost what the ledger still lists
  C  caller is not a member          a permission answer, not a storage answer
  D  DB row, file truncated to 0     the ledger says N bytes, the disk has none
  E  DB row, file overwritten junk   bytes arrive, none of them are an image
  F  path replaced by a directory    an OS error class that is not FileNotFound
  G  file unreadable (chmod 000)     the other OS error class
  H  healthy photo                   the positive control

Without H the whole table is worthless: a dead stack answers every row the same
way, and a reader cannot tell "the route is broken" from "my probe is broken".

## Reachability, which is the question the table cannot answer

Rows D-G are built by reaching around the product and editing the media root by
hand. That a probe can create a state says nothing about whether a person can.
So the second half measures the only door the product opens into that
directory -- `POST /contexts/{id}/photos` -- and asks whether anything a caller
can send comes out the other side as zero bytes on disk, including a write that
fails partway through under a real `RLIMIT_FSIZE` ceiling.

Usage:
    ANH_API=http://127.0.0.1:PORT ANH_MEDIA=/path/to/media python3 do-dieu-kien-anh-chet.py
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("ANH_API", "http://127.0.0.1:8000").rstrip("/")
MEDIA = pathlib.Path(os.environ.get("ANH_MEDIA", "/tmp/does-not-exist"))

# Same reason as every other probe in this directory: the machine proxy
# swallows loopback unless the opener is told there is no proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

ROWS: list[tuple[str, str, str, str]] = []
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
) -> tuple[int, bytes, dict[str, str]]:
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
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")
    return ok


def photo_bytes() -> bytes:
    """A synthetic JPEG. No camera took it and nobody is in it."""

    from PIL import Image

    image = Image.new("RGB", (320, 240), (240, 240, 240))
    for x in range(0, 320, 32):
        for y in range(0, 240, 32):
            if (x // 32 + y // 32) % 2:
                for dx in range(min(32, 320 - x)):
                    for dy in range(min(32, 240 - y)):
                        image.putpixel((x + dx, y + dy), (40, 90, 160))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def multipart(content: bytes, filename: str = "anh.jpg") -> tuple[bytes, str]:
    boundary = "----qa2anh" + uuid.uuid4().hex
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: image/jpeg\r\n\r\n",
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def person(phone: str, name: str) -> str:
    status, payload, _ = call("POST", "/identity/person-id", body={"phone": phone})
    assert status == 200, (status, payload[:300])
    person_id = js(payload)["person_id"]
    status, payload, _ = call(
        "PUT", f"/people/{person_id}", actor=person_id, body={"display_name": name}
    )
    assert status in (200, 201), (status, payload[:300])
    return person_id


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


def media_files() -> set[pathlib.Path]:
    return {p for p in MEDIA.rglob("*") if p.is_file()}


def upload_and_locate(
    context_id: str, actor: str, content: bytes
) -> tuple[dict, pathlib.Path]:
    """Upload a photo and return its response plus the file it produced.

    The storage key is deliberately not in the response -- it is opaque on
    purpose -- so the file is found by diffing the media root instead of by
    querying the database. That keeps this probe from depending on a schema it
    is not measuring.
    """

    before = media_files()
    data, ctype = multipart(content)
    status, payload, _ = call(
        "POST",
        f"/contexts/{context_id}/photos",
        actor=actor,
        contexts=context_id,
        raw=(data, ctype),
    )
    assert status in (200, 201), (status, payload[:400])
    new = media_files() - before
    assert len(new) == 1, f"expected exactly one new file, saw {len(new)}"
    return js(payload), new.pop()


def decode_size(blob: bytes) -> tuple[int, int] | None:
    from PIL import Image

    try:
        return Image.open(io.BytesIO(blob)).size
    except Exception:
        return None


def record(route: str, condition: str, status: int, payload: bytes) -> None:
    size = decode_size(payload)
    ROWS.append(
        (
            route,
            condition,
            f"{status}",
            f"{len(payload)} byte" + (f", giai ma {size[0]}x{size[1]}" if size else ""),
        )
    )


def main() -> int:
    if MEDIA == pathlib.Path("/tmp/does-not-exist"):
        print("Dat ANH_MEDIA = MOBILE_MEDIA_ROOT cua stack dang do.", file=sys.stderr)
        return 2
    # The API creates this on its first upload; a stack that has served none
    # yet has no directory to diff against, and creating it changes nothing --
    # `PhotoStorage.write` does the same `mkdir(parents=True, exist_ok=True)`.
    MEDIA.mkdir(parents=True, exist_ok=True)

    stem = f"{uuid.uuid4().int % 1000000:06d}"
    an = person(f"090{stem}1", "An")
    la = person(f"093{stem}3", "Nguoi La")
    group = make_group(an, "Nhom do anh chet")

    print(f"\n== bo du lieu ==\napi={BASE}\nmedia={MEDIA}\nnhom={group}\n")
    print("== PHAN 1: tam dieu kien tren route anh cua NHOM ==")

    blob = photo_bytes()

    # --- H: the positive control, measured FIRST ---------------------------
    # Everything below is read against this. A stack that is dead, or a probe
    # whose headers are wrong, fails this line and invalidates the rest.
    healthy, healthy_path = upload_and_locate(group, an, blob)
    status, payload, headers = call("GET", healthy["url"], actor=an, contexts=group)
    record("photos", "H doi chung duong: anh lanh", status, payload)
    check(
        "H DOI CHUNG DUONG: anh lanh -> 200 va giai ma duoc",
        status == 200 and decode_size(payload) == (320, 240),
        f"status={status} len={len(payload)} size={decode_size(payload)}"
        f" ctype={headers.get('content-type')}",
    )
    server_says = healthy["byte_size"]
    check(
        "H may chu KHAI byte_size trong response upload",
        isinstance(server_says, int) and server_says == len(payload),
        f"byte_size={server_says} len tra ve={len(payload)}",
    )

    # --- A: no DB row ------------------------------------------------------
    status, payload, _ = call(
        "GET",
        f"/contexts/{group}/photos/{uuid.uuid4()}",
        actor=an,
        contexts=group,
    )
    record("photos", "A id khong co trong DB", status, payload)
    check(
        "A id la -> 404 photo_not_found",
        status == 404 and js(payload).get("code") == "photo_not_found",
        f"status={status} code={js(payload).get('code')}",
    )

    # --- C: not a member ---------------------------------------------------
    status, payload, _ = call("GET", healthy["url"], actor=la, contexts=group)
    record("photos", "C nguoi khong phai thanh vien", status, payload)
    check(
        "C nguoi la -> 403",
        status == 403,
        f"status={status} code={js(payload).get('code')}",
    )

    # --- B: DB row survives, file deleted ----------------------------------
    gone, gone_path = upload_and_locate(group, an, blob)
    gone_path.unlink()
    status, payload, _ = call("GET", gone["url"], actor=an, contexts=group)
    record("photos", "B file bi XOA khoi dia", status, payload)
    check(
        "B file bi xoa -> 404 photo_not_found",
        status == 404 and js(payload).get("code") == "photo_not_found",
        f"status={status} code={js(payload).get('code')}",
    )

    # --- D: file truncated to zero -----------------------------------------
    empty, empty_path = upload_and_locate(group, an, blob)
    declared = empty["byte_size"]
    empty_path.write_bytes(b"")
    status, payload, headers = call("GET", empty["url"], actor=an, contexts=group)
    record("photos", "D file bi cat ve 0 BYTE", status, payload)
    check(
        "D file 0 byte -> 200 voi 0 byte (LO HONG)",
        status == 200 and len(payload) == 0,
        f"status={status} len={len(payload)}"
        f" content-length={headers.get('content-length')}"
        f" ctype={headers.get('content-type')}",
    )
    check(
        "D may chu BIET so byte dung ({} byte) ma khong doi chieu".format(declared),
        status == 200 and len(payload) == 0 and declared > 0,
        f"DB khai byte_size={declared}, route phat {len(payload)} byte",
    )

    # --- E: file overwritten with non-image bytes --------------------------
    junk, junk_path = upload_and_locate(group, an, blob)
    junk_path.write_bytes(b"khong phai anh, chi la chu")
    status, payload, headers = call("GET", junk["url"], actor=an, contexts=group)
    record("photos", "E file bi ghi de bang RAC", status, payload)
    check(
        "E file rac -> 200 voi rac, dan nhan image/jpeg (LO HONG)",
        status == 200
        and decode_size(payload) is None
        and headers.get("content-type", "").startswith("image/"),
        f"status={status} len={len(payload)} giai ma={decode_size(payload)}"
        f" ctype={headers.get('content-type')}",
    )

    # --- F: path replaced by a directory -----------------------------------
    isdir, isdir_path = upload_and_locate(group, an, blob)
    isdir_path.unlink()
    isdir_path.mkdir()
    try:
        status, payload, _ = call("GET", isdir["url"], actor=an, contexts=group)
    except Exception as exc:  # a 500 with no body still counts as a reading
        status, payload = 0, str(exc).encode()
    record("photos", "F duong dan bi thay bang THU MUC", status, payload)
    check(
        "F duong dan la thu muc -> KHONG phai 404 (lop loi khac)",
        status != 404,
        f"status={status} len={len(payload)}",
    )
    isdir_path.rmdir()

    # --- G: file exists but is unreadable ----------------------------------
    locked, locked_path = upload_and_locate(group, an, blob)
    locked_path.chmod(0o000)
    unreadable = True
    try:
        locked_path.read_bytes()
        unreadable = False  # running as root: the row cannot be built here
    except PermissionError:
        pass
    if unreadable:
        try:
            status, payload, _ = call("GET", locked["url"], actor=an, contexts=group)
        except Exception as exc:
            status, payload = 0, str(exc).encode()
        record("photos", "G file chmod 000", status, payload)
        check(
            "G file khong doc duoc -> KHONG phai 404 (lop loi khac)",
            status != 404,
            f"status={status} len={len(payload)}",
        )
    else:
        ROWS.append(
            ("photos", "G file chmod 000", "-", "khong dung duoc: dang chay root")
        )
        print("[SKIP] G chmod 000 khong co tac dung voi user hien tai")
    locked_path.chmod(0o600)

    # --- the same hole on the avatar route ---------------------------------
    print("\n== PHAN 2: cung dieu kien tren route ANH DAI DIEN ==")
    before = media_files()
    data, ctype = multipart(blob)
    status, payload, _ = call(
        "POST", f"/people/{an}/avatar", actor=an, raw=(data, ctype)
    )
    check("avatar upload duoc", status in (200, 201), f"status={status}")
    avatar = js(payload)
    avatar_path = (media_files() - before).pop()

    status, payload, _ = call("GET", f"/people/{an}/avatar", actor=an, contexts=group)
    record("avatar", "H doi chung duong: avatar lanh", status, payload)
    check(
        "H' avatar lanh -> 200 va giai ma duoc",
        status == 200 and decode_size(payload) == (320, 240),
        f"status={status} len={len(payload)} size={decode_size(payload)}",
    )

    avatar_path.write_bytes(b"")
    status, payload, headers = call(
        "GET", f"/people/{an}/avatar", actor=an, contexts=group
    )
    record("avatar", "D file bi cat ve 0 BYTE", status, payload)
    check(
        "D' avatar 0 byte -> 200 voi 0 byte (LO HONG, cung hinh dang)",
        status == 200 and len(payload) == 0,
        f"status={status} len={len(payload)}"
        f" declared byte_size={avatar.get('byte_size')}",
    )

    # --- PART 3: can a caller reach rows D or E through the product? -------
    print("\n== PHAN 3: nguoi dung THAT co tao ra duoc trang thai do khong ==")

    # R1: an empty body. The one input that most obviously "is" zero bytes.
    data, ctype = multipart(b"")
    status, payload, _ = call(
        "POST",
        f"/contexts/{group}/photos",
        actor=an,
        contexts=group,
        raw=(data, ctype),
    )
    check(
        "R1 upload than RONG -> bi tu choi, khong tao ban ghi",
        status >= 400,
        f"status={status} code={js(payload).get('code')}",
    )

    # R2: a truncated JPEG -- valid header, missing tail. The realistic
    # "upload interrupted" shape, and the one a naive sanitizer lets through.
    data, ctype = multipart(blob[: len(blob) // 2])
    status, payload, _ = call(
        "POST",
        f"/contexts/{group}/photos",
        actor=an,
        contexts=group,
        raw=(data, ctype),
    )
    check(
        "R2 upload JPEG CAT CUT -> bi tu choi",
        status >= 400,
        f"status={status} code={js(payload).get('code')}",
    )

    # R3: the smallest image the sanitizer will accept. If any accepted upload
    # can be zero bytes on disk, it is this one.
    from PIL import Image

    tiny = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(tiny, format="PNG")
    smallest, smallest_path = upload_and_locate(group, an, tiny.getvalue())
    check(
        "R3 anh 1x1 (nho nhat chap nhan duoc) -> file tren dia > 0 byte",
        smallest_path.stat().st_size > 0 and smallest["byte_size"] > 0,
        f"tren dia={smallest_path.stat().st_size} byte_size={smallest['byte_size']}",
    )

    # R4: the sanitizer itself, over the corpus, in process. Every input it
    # ACCEPTS must carry bytes; anything else means the door can emit an empty
    # file without anybody editing the media root.
    sys.path.insert(
        0, str(pathlib.Path(__file__).resolve().parents[3] / "services" / "api")
    )
    from app.media.images import ImageRejected, sanitize_image  # noqa: E402

    corpus: list[tuple[str, bytes]] = [
        ("rong", b""),
        ("mot byte", b"\x00"),
        ("chu thuan", b"khong phai anh"),
        ("jpeg cat cut", blob[: len(blob) // 2]),
        ("jpeg chi header", blob[:2]),
        ("anh 1x1", tiny.getvalue()),
        ("anh 320x240", blob),
    ]
    accepted_empty: list[str] = []
    verdicts: list[str] = []
    for label, raw in corpus:
        try:
            out = sanitize_image(raw)
        except ImageRejected as exc:
            verdicts.append(f"{label}: TU CHOI ({exc.code})")
            continue
        verdicts.append(f"{label}: NHAN {len(out.data)} byte")
        if len(out.data) == 0:
            accepted_empty.append(label)
    for line in verdicts:
        print(f"    {line}")
    check(
        "R4 khong dau vao nao duoc NHAN ma cho ra 0 byte",
        not accepted_empty,
        f"cho ra rong: {accepted_empty}",
    )

    # R5: a write that fails partway. RLIMIT_FSIZE is a real kernel ceiling,
    # not a mock: the write raises EFBIG exactly the way ENOSPC would on a full
    # disk. The question is whether the final path is left holding a short or
    # empty file, which is the only way the product itself could manufacture
    # row D.
    script = textwrap.dedent(
        """
        import pathlib, resource, signal, sys, tempfile
        sys.path.insert(0, sys.argv[1])
        from app.media.storage import PhotoStorage

        root = pathlib.Path(tempfile.mkdtemp())
        store = PhotoStorage(root)
        key = "ab" * 16
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))
        try:
            store.write(key, b"x" * 200000)
            print("WROTE")
        except OSError as exc:
            print("RAISED", exc.errno)
        final = root / key[:2] / key[2:4] / key
        leftovers = sorted(p.name for p in root.rglob("*") if p.is_file())
        print("FINAL_EXISTS", final.exists())
        print("FINAL_SIZE", final.stat().st_size if final.exists() else -1)
        print("LEFTOVERS", leftovers)
        """
    )
    api_dir = str(pathlib.Path(__file__).resolve().parents[3] / "services" / "api")
    proc = subprocess.run(
        [sys.executable, "-c", script, api_dir],
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = proc.stdout.strip()
    for line in out.splitlines():
        print(f"    {line}")
    check(
        "R5 ghi hong giua chung -> KHONG de lai file o duong dan cuoi",
        "FINAL_EXISTS False" in out and "LEFTOVERS []" in out,
        out.replace("\n", " | ") or proc.stderr[-200:],
    )

    print("\n== BANG: route x dieu kien -> may chu tra gi ==")
    width = max(len(r[1]) for r in ROWS)
    for route, condition, status, detail in ROWS:
        print(f"  {route:<7} {condition:<{width}}  {status:>4}  {detail}")

    print(f"\n{len(FAILURES)} dong FAIL")
    for line in FAILURES:
        print(f"  - {line}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
