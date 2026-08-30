"""Does F26's SUCCESS path run end to end on a bank-transfer screenshot?

Opt-in, not a pytest case: it calls Gemini over the network, costs money, and
its answer depends on a model revision nobody in this repo pins. The filename
has no ``test_`` prefix so the gate suite never collects it.

    scripts/e2e_slice.sh --keep                   # prints the API URL
    cd services/api
    set -a; . /path/to/repo/.env; set +a          # GEMINI_API_KEY
    python3 tests/live/probe_f26_bank_transfer.py --api http://127.0.0.1:PORT

Every earlier F26 run on record read a Grab or a ShopeeFood order and stopped
at the result card (``tests/qa/qa-tt-0034``). Two things were therefore never
measured: what the reader does with a *banking* screenshot -- the one shape a
person actually photographs when settling a bill -- and whether the number it
reads can reach the ledger. This probe measures both, in one run, against a
live server.

The images are drawn here from constants, so nothing in ADR-0010 6.5 is bent:
no real bill, no real account, no real person. The account digits are masked
the way a banking app masks them and the two payees are invented ("MAU" =
sample). The PNGs are written to a temporary directory and never committed --
repo guard is fail-closed on binaries and that is the correct answer.

Two payees on purpose. ``app/domain/screenshot.py`` refuses a reading whose
*keys* look like identity, but ``merchant`` is a free string: a transfer to a
shop and a transfer to a person are the two sides of whether a person's name
can ride into the app inside a field that is not an identity field.

What this can show: the classification, merchant and total the live model
returns for each image; whether the total survives ``POST /expenses`` and
``confirm`` into ledger-derived balances.

What it cannot show: that any of it is stable across model revisions, across
real phone screenshots of real banking apps in other languages and themes, or
that a *person* holding the phone understands the card the app draws.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
_FONT_DIR = "/usr/share/fonts/truetype/dejavu"

# One namespace so a re-run replays the same people and the same group rather
# than growing a new one per run. Same trick `khoiDongNhom` uses on the client.
_NS = uuid.UUID("6f5a1d2c-0e7b-4a53-9c31-2f6d8b0a4e11")
_PAYER = uuid.uuid5(_NS, "f26-payer")
_FRIEND_A = uuid.uuid5(_NS, "f26-friend-a")
_FRIEND_B = uuid.uuid5(_NS, "f26-friend-b")
_PEOPLE = {
    _PAYER: "Người trả trước (mẫu)",
    _FRIEND_A: "Bạn A (mẫu)",
    _FRIEND_B: "Bạn B (mẫu)",
}


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """A real TrueType face, falling back to the bitmap default."""

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"{_FONT_DIR}/{name}", size)
    except OSError:
        return ImageFont.load_default()


def _transfer_screen(
    path: Path,
    *,
    payee: str,
    amount_text: str,
    memo: str,
    stamped_at: str,
) -> None:
    """One completed-transfer screen in the shape a banking app draws it."""

    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)

    d.rectangle([0, 0, W, 150], fill=(20, 60, 130))
    d.text((40, 55), "NGÂN HÀNG MẪU", font=font(40, True), fill="white")

    d.ellipse([W // 2 - 60, 220, W // 2 + 60, 340], outline=(0, 150, 70), width=8)
    d.line([W // 2 - 28, 282, W // 2 - 6, 306], fill=(0, 150, 70), width=10)
    d.line([W // 2 - 6, 306, W // 2 + 30, 258], fill=(0, 150, 70), width=10)

    d.text((40, 380), "Chuyển tiền thành công", font=font(42, True), fill=(20, 20, 20))
    d.text((40, 460), amount_text, font=font(64, True), fill=(0, 120, 60))

    d.line([40, 570, W - 40, 570], fill=(210, 210, 210), width=2)
    rows = [
        ("Người nhận", payee),
        ("Số tài khoản", "**** **** 8901"),
        ("Ngân hàng", "Ngân hàng Mẫu (DEMOBANK)"),
        ("Nội dung", memo),
        ("Thời gian", stamped_at),
        ("Mã giao dịch", "FT9900000000"),
    ]
    y = 610
    for label, value in rows:
        d.text((40, y), label, font=font(26), fill=(110, 110, 110))
        d.text((40, y + 34), value, font=font(32), fill=(20, 20, 20))
        y += 100

    im.save(path)


def draw_images(out: Path) -> dict[str, Path]:
    """Two completed transfers: one to a shop, one to a person."""

    out.mkdir(parents=True, exist_ok=True)
    shop = out / "chuyen-khoan-quan-an.png"
    person = out / "chuyen-khoan-nguoi.png"
    _transfer_screen(
        shop,
        payee="QUAN NUONG SO 7",
        amount_text="450.000 VND",
        memo="Tra tien an toi thu Bay",
        stamped_at="30/08/2026 21:15",
    )
    _transfer_screen(
        person,
        payee="NGUYEN VAN MAU",
        amount_text="180.000 VND",
        memo="Tra tien ca phe",
        stamped_at="30/08/2026 09:02",
    )
    return {"quán ăn": shop, "người": person}


# --- the live server ------------------------------------------------------


def _headers(actor: uuid.UUID, context: uuid.UUID | None, key: str | None) -> dict:
    # The union of what `screens/chat/nhom.ts` and `src/api.ts` send. Without
    # `advancer` the confirm is 403 role_not_permitted, because gate 2 of
    # section 8.3 only lets the person who fronted the money say so.
    head = {
        "X-Actor-ID": str(actor),
        "X-Actor-Roles": "group_admin,member,advancer,recipient,batch_owner",
    }
    if context is not None:
        head["X-Actor-Contexts"] = str(context)
    if key is not None:
        head["Idempotency-Key"] = str(uuid.uuid5(_NS, key))
    return head


def call(
    api: str,
    method: str,
    path: str,
    *,
    actor: uuid.UUID | None = None,
    context: uuid.UUID | None = None,
    key: str | None = None,
    body: dict | None = None,
) -> tuple[int, object]:
    """One JSON round trip that returns the status instead of raising on 4xx."""

    head = {} if actor is None else _headers(actor, context, key)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        head["Content-Type"] = "application/json"
    req = urllib.request.Request(api + path, data=data, headers=head, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"null")
        except ValueError:
            return exc.code, raw.decode("utf-8", "replace")


def post_image(api: str, image: Path, actor: uuid.UUID) -> tuple[int, object]:
    """Upload one PNG as multipart/form-data, the way the phone does."""

    boundary = "----f26probe" + uuid.uuid4().hex
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="image"; '
            + f'filename="{image.name}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n",
            image.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    req = urllib.request.Request(
        api + "/screenshots/scan",
        data=body,
        method="POST",
        headers={
            "X-Actor-ID": str(actor),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"null")
        except ValueError:
            return exc.code, raw.decode("utf-8", "replace")


def open_group(api: str) -> uuid.UUID:
    """Three named people in one group, all active. Replays on a second run."""

    for person, name in _PEOPLE.items():
        status, body = call(
            api,
            "PUT",
            f"/people/{person}",
            actor=person,
            key=f"name:{person}",
            body={"display_name": name},
        )
        if status not in (200, 201):
            raise SystemExit(f"PUT /people/{person} -> {status} {body}")

    status, body = call(
        api,
        "POST",
        "/contexts",
        actor=_PAYER,
        key="context",
        body={"display_name": "Nhóm thử F26 (mẫu)"},
    )
    if status not in (200, 201) or not isinstance(body, dict):
        raise SystemExit(f"POST /contexts -> {status} {body}")
    context = uuid.UUID(body["id"])

    for friend in (_FRIEND_A, _FRIEND_B):
        status, body = call(
            api,
            "POST",
            f"/contexts/{context}/members",
            actor=_PAYER,
            context=context,
            key=f"invite:{friend}",
            body={"person_id": str(friend)},
        )
        if status == 409:
            continue
        if status not in (200, 201) or not isinstance(body, dict):
            raise SystemExit(f"POST members -> {status} {body}")
        membership = body["id"]
        status, body = call(
            api,
            "POST",
            f"/memberships/{membership}/accept",
            actor=friend,
            context=context,
            key=f"accept:{friend}",
            body={},
        )
        if status not in (200, 201, 409):
            raise SystemExit(f"POST accept -> {status} {body}")
    return context


def into_the_ledger(api: str, context: uuid.UUID, reading: dict, tag: str) -> None:
    """Do what the app's "Chốt" leads to: the read total, split, confirmed.

    `KetQuaQuetAnh`'s onChot copies `merchant` into the occasion field and
    `total_vnd` into the amount field and hands the person the manual form.
    Nothing between there and here re-reads the picture, so the number posted
    is the number the model read.
    """

    proposal = {
        "context_id": str(context),
        "description": reading["merchant"],
        "recorded_by_id": str(_PAYER),
        "paid_by_id": str(_PAYER),
        "verification_scope": "totals_only",
        "occurred_at": datetime.now(UTC).isoformat(),
        "participants": [str(p) for p in _PEOPLE],
        "total_amount_vnd": reading["total_vnd"],
    }
    status, body = call(
        api, "POST", "/expenses", actor=_PAYER, context=context, body=proposal
    )
    print(f"  POST /expenses            -> {status}")
    if status != 201 or not isinstance(body, dict):
        print(f"  {body}")
        return
    allocation = body["allocation"]["allocations"]
    print(f"  allocation                {allocation}")
    print(f"  Σ phân bổ                 {sum(allocation.values())}")

    status, confirmed = call(
        api,
        "POST",
        f"/expenses/{body['expense_id']}/confirm",
        actor=_PAYER,
        context=context,
        key=f"confirm:{tag}",
        body={
            "proposal": proposal,
            "expected_allocations": allocation,
            "acknowledge_as_advancer": True,
        },
    )
    print(f"  POST .../confirm          -> {status}")
    if status != 201 or not isinstance(confirmed, dict):
        print(f"  {confirmed}")
        return
    print(
        f"  ghi vào sổ                version {confirmed['version_number']}, "
        f"tổng {confirmed['total_amount_vnd']}"
    )

    for person, name in _PEOPLE.items():
        status, finance = call(
            api, "GET", f"/people/{person}/finance", actor=person, context=context
        )
        if status != 200 or not isinstance(finance, dict):
            print(f"  GET finance {person} -> {status} {finance}")
            continue
        print(f"  sổ · {name:<24} {json.dumps(finance, ensure_ascii=False)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True, help="base URL of a live API")
    parser.add_argument("--out", default=None, help="where to write the PNGs")
    args = parser.parse_args()

    api = args.api.rstrip("/")
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="f26-"))
    images = draw_images(out)
    print(f"ảnh mẫu (không vào Git): {out}")

    readings: dict[str, dict] = {}
    for label, path in images.items():
        status, body = post_image(api, path, _PAYER)
        print(f"\nPOST /screenshots/scan  [{label}] -> {status}")
        print(f"  {json.dumps(body, ensure_ascii=False)}")
        if status == 200 and isinstance(body, dict):
            readings[label] = body

    if not readings:
        print("\nKhông có lượt đọc nào thành công — đường thành công CHƯA chạy.")
        return 1

    context = open_group(api)
    print(f"\nnhóm thử: {context}")
    for label, reading in readings.items():
        print(f"\n--- vào sổ từ ảnh [{label}] ---")
        into_the_ledger(api, context, reading, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
