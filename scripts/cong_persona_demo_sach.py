#!/usr/bin/env python3
"""Cổng: màn Cá nhân của bảy persona demo có SẠCH không, đo bằng số.

## Vì sao cần một cổng chứ không phải một lần nhìn

Ngày 2026-08-30 màn Cá nhân của Minh mở ra có bốn dòng movement in nguyên chữ
"Team Đà Lạt (tồn dư 30/08 — KHÔNG dùng để demo)". Không ai cố ý làm thế: máy
demo dùng chung, mọi bộ đồ nghề QA đều đăng nhập bằng đúng bảy id mà
`seed_demo_data.py` sinh ra, và mỗi lượt lại gắn thêm cho họ một mẩu lịch sử.

Sửa xong một lần rồi nhìn bằng mắt thì hôm sau nó bẩn lại mà không ai biết. Nên
tính chất "persona demo chỉ có lịch sử trong nhóm demo" được viết ra thành bốn
phép đo chạy được, và cái nào hỏng thì in ra con số hỏng.

## Bốn điều nó đo, đúng bốn điều leader hỏi

    A  mỗi persona thuộc ĐÚNG 1 context, và đó là nhóm demo
    B  mọi dòng `movements` trên `GET /people/{id}/finance` thuộc nhóm demo
    C  `spend_vnd` và `expense_count` bằng đúng tổng của riêng nhóm demo
    D  KHÔNG có confirmed_allocation nào của họ nằm ngoài nhóm demo

D là phép đo chịu lực. A chỉ đọc `memberships`, mà rời nhóm không xoá tiền —
một persona có thể `group_count=1` mà `spend_vnd` vẫn một nửa là rác. Còn B đọc
`movements`, và movements chỉ liệt kê **nghĩa vụ** giữa người với người: đo
ngày 30/08 trên máy demo, B nói 5/7 persona "sạch" trong khi D nói cả 7 đều bẩn
— năm người kia có allocation trong nhóm rác nhưng không ai nợ ai, nên không
sinh dòng movement nào. Tin B một mình là chọn nhầm persona và đem lên sân khấu
một màn hình có một nửa số tiền đến từ nhóm tên là "KHÔNG dùng để demo".

## Cái nó KHÔNG đo

Không đo nhóm demo dựng đủ chưa — `check_demo_data.py` làm việc đó. Không đo
trang render ra sao. Và nó không sửa gì: một cổng biết xoá dữ liệu để tự làm
mình xanh thì không còn là cổng.

## Số đang đổi dưới chân thì KHÔNG kết luận

Máy demo dùng chung. Nếu giữa lúc đo có lane khác đang ghi, `spend_vnd` mà API
trả về và tổng mà SQL đọc sẽ lệch nhau vì chúng nhìn hai thời điểm. Trường hợp
đó thoát 2 ("không đo được"), không phải 1 ("bẩn") — gộp hai cái đó là cách một
phép đo chết đọc thành một sản phẩm hỏng. D được đo trong một snapshot
REPEATABLE READ nên nó vẫn có nghĩa; C là cái phải nhịn.

## Chạy

    python3 scripts/cong_persona_demo_sach.py
    python3 scripts/cong_persona_demo_sach.py --dsn ... --api http://127.0.0.1:8399

Mã thoát: 0 sạch · 1 bẩn · 2 không chạy/đo được.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DSN = "postgresql://mobile:mobile-dev-only@127.0.0.1:5432/mobile"
DEFAULT_API = "http://127.0.0.1:8099"

EXIT_OK = 0
EXIT_DIRTY = 1
EXIT_CANNOT_RUN = 2

# The floor under the denominator. `demo_identity()` reads the cast off the
# builder so that an eighth demo person cannot slip past unmeasured -- that
# guards the list GROWING. This guards it SHRINKING, which is the half that was
# missing: with `PEOPLE` empty the per-person loop below never runs, `failures`
# stays empty, and the gate prints "SẠCH -- cả 0 persona" and exits 0. An empty
# denominator is not a clean result, it is the absence of a measurement.
#
# Deliberately a floor and not an equality: adding a demo person must not red
# this gate, only removing one. If the cast is meant to shrink, change this
# number in the same commit -- loudly, and on purpose.
DEMO_CAST_SIZE = 7


def die(message: str) -> int:
    print(f"KHÔNG ĐO ĐƯỢC — {message}", file=sys.stderr)
    return EXIT_CANNOT_RUN


def demo_identity() -> tuple[list[tuple[uuid.UUID, str]], str]:
    """Read the seven ids and the group name off the builder, never copied.

    A hand-written list here would keep passing on the day somebody adds an
    eighth demo person, and the eighth would be the one nobody measured.
    """

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import seed_demo_data as seed

    return list(seed.PEOPLE), seed.GROUP_NAME


def finance(api_base: str, person_id: uuid.UUID) -> dict:
    """One `GET /people/{id}/finance`, as the Cá nhân screen asks it.

    The opener carries an empty ProxyHandler on purpose: this machine runs a
    proxy that intercepts localhost, and urllib honours `http_proxy` from the
    environment. Without it the request lands on a redirect page and the JSON
    decode fails somewhere far away from the cause.
    """

    request = urllib.request.Request(
        f"{api_base}/people/{person_id}/finance",
        headers={
            "Accept": "application/json",
            "X-Actor-ID": str(person_id),
            "X-Actor-Roles": "member",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=30) as response:
        return json.load(response)


def demo_context(connection, group_name: str) -> uuid.UUID:
    rows = connection.execute(
        "SELECT id FROM contexts WHERE display_name = %s", (group_name,)
    ).fetchall()
    if len(rows) != 1:
        raise LookupError(
            f"cần đúng 1 context tên {group_name!r}, tìm thấy {len(rows)}. "
            "Không đoán nhóm nào là nhóm demo."
        )
    return rows[0][0]


# Only the newest version of each expense counts. Corrections write a new
# version instead of overwriting, so an unfiltered sum adds the mistake to the
# fix. Same shape the repository itself uses for `spend_vnd`.
LEDGER_BY_CONTEXT = """
WITH newest AS (
    SELECT expense_id, max(version_number) AS version_number
    FROM expense_versions GROUP BY expense_id
)
SELECT ca.participant_id,
       e.context_id,
       c.display_name,
       sum(ca.amount_vnd)::bigint,
       count(DISTINCT ev.expense_id)
FROM confirmed_allocations ca
JOIN expense_versions ev ON ev.id = ca.expense_version_id
JOIN newest n ON n.expense_id = ev.expense_id
             AND n.version_number = ev.version_number
LEFT JOIN expenses e ON e.id = ev.expense_id
LEFT JOIN contexts c ON c.id = e.context_id
WHERE ca.participant_id = ANY(%s)
GROUP BY 1, 2, 3
"""

# LEFT JOIN, not JOIN, and the reason is measured rather than defensive:
# `public.expenses` on the demo machine carries NO foreign key on `context_id`,
# and 10.932 rows there point at a context that has no row in `contexts`. An
# inner join drops them silently, and the drop is invisible in exactly the
# wrong direction -- the total comes out *smaller* than what the screen shows,
# so the gate would report a persona as clean while the screen adds money from
# a group it cannot even name.

MEMBERSHIPS = """
SELECT m.person_id, m.context_id, c.display_name
FROM memberships m
LEFT JOIN contexts c ON c.id = m.context_id
WHERE m.person_id = ANY(%s) AND m.state = 'active' AND m.left_at IS NULL
"""


def money(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + "đ"


def main() -> int:
    parser = argparse.ArgumentParser(description="Cổng persona demo sạch")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--api", default=DEFAULT_API)
    args = parser.parse_args()

    try:
        import psycopg
    except ImportError as exc:
        return die(f"thiếu psycopg: {exc}")

    try:
        people, group_name = demo_identity()
    except Exception as exc:  # noqa: BLE001 - any import failure is cannot-run
        return die(f"không đọc được seed_demo_data.py: {exc}")

    # Guard the denominator before spending a database connection on it: every
    # assertion this gate makes lives inside the per-person loop, so a cast that
    # arrived short makes the whole verdict vacuous rather than wrong.
    if len(people) < DEMO_CAST_SIZE:
        return die(
            f"chỉ đọc được {len(people)} persona từ seed_demo_data.py, cần ít nhất "
            f"{DEMO_CAST_SIZE}. Danh sách PEOPLE bị rút ngắn, hoặc file đã đổi hình "
            f"dạng — mẫu số thiếu thì 'sạch' không có nghĩa gì."
        )

    ids = [pid for pid, _ in people]

    try:
        connection = psycopg.connect(args.dsn, connect_timeout=10)
    except Exception as exc:  # noqa: BLE001 - any connect failure is cannot-run
        return die(f"không nối được database: {exc}")

    with connection:
        connection.execute("SET search_path TO public")
        # One snapshot for every SQL answer below. Read across two transactions
        # and a concurrent writer turns "dirty" and "moved" into the same
        # picture.
        connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
        try:
            keeper = demo_context(connection, group_name)
        except LookupError as exc:
            return die(str(exc))

        ledger = connection.execute(LEDGER_BY_CONTEXT, (ids,)).fetchall()
        memberships = connection.execute(MEMBERSHIPS, (ids,)).fetchall()
        connection.rollback()

    print(f"Nhóm demo: {group_name!r}  ({keeper})")
    print(f"API: {args.api}\n")

    # SQL side, per person: what the demo group alone accounts for, and what
    # sits outside it.
    inside: dict[uuid.UUID, tuple[int, int]] = {}
    outside: dict[uuid.UUID, list[tuple[str, int, int]]] = {}
    for pid, context_id, display_name, amount, count in ledger:
        if context_id == keeper:
            inside[pid] = (int(amount), int(count))
        else:
            label = display_name or f"<context {context_id} không có trong contexts>"
            outside.setdefault(pid, []).append((label, int(amount), int(count)))

    groups: dict[uuid.UUID, list[str]] = {}
    for pid, context_id, display_name in memberships:
        groups.setdefault(pid, []).append(
            display_name or f"<context {context_id} không có trong contexts>"
        )

    failures: list[str] = []
    moved: list[str] = []
    measured = 0

    header = f"{'ai':6s} {'nhóm':>4s} {'spend_vnd':>12s} {'chi':>4s}  kết luận"
    print(header)
    print("-" * len(header))

    for pid, name in people:
        try:
            seen = finance(args.api, pid)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return die(f"không gọi được GET /people/{pid}/finance: {exc}")

        demo_spend, demo_count = inside.get(pid, (0, 0))
        junk = outside.get(pid, [])
        held = groups.get(pid, [])

        problems: list[str] = []

        # A -- membership.
        if held != [group_name]:
            problems.append(
                f"A: thuộc {len(held)} context {held!r}, cần đúng [{group_name!r}]"
            )

        # B -- what the screen prints.
        stray = sorted(
            {
                m["context_name"]
                for m in seen["movements"]
                if m["context_id"] != str(keeper)
            }
        )
        if stray:
            problems.append(f"B: {len(stray)} tên nhóm lạ trong movements: {stray!r}")

        # D -- the load-bearing one, race-free inside the snapshot.
        if junk:
            detail = ", ".join(f"{lbl!r} {money(a)}/{c} chi" for lbl, a, c in junk)
            problems.append(f"D: có allocation ngoài nhóm demo: {detail}")

        # C -- corroboration. A mismatch here with no D finding means the
        # numbers moved between the snapshot and the HTTP call, not that the
        # persona is dirty.
        c_ok = seen["spend_vnd"] == demo_spend and seen["expense_count"] == demo_count
        if not c_ok and not junk:
            moved.append(
                f"{name}: API spend={seen['spend_vnd']} count={seen['expense_count']} "
                f"nhưng sổ của nhóm demo là {demo_spend}/{demo_count}"
            )
        elif not c_ok:
            problems.append(
                f"C: API spend={money(seen['spend_vnd'])}/{seen['expense_count']} chi, "
                f"riêng nhóm demo là {money(demo_spend)}/{demo_count} chi"
            )

        verdict = "sạch" if not problems else "BẨN"
        print(
            f"{name:6s} {seen['group_count']:4d} {seen['spend_vnd']:12d} "
            f"{seen['expense_count']:4d}  {verdict}"
        )
        for problem in problems:
            print(f"        {problem}")
            failures.append(f"{name} — {problem}")

        measured += 1

    print()

    # The loop above is the only place this gate looks at anything. If it ran
    # fewer times than the cast it was handed, the tables printed above describe
    # a subset and the verdict below would be about people nobody looked at.
    if measured != len(people):
        return die(
            f"đo được {measured}/{len(people)} persona — vòng đo kết thúc sớm, "
            f"phán quyết bên dưới sẽ nói về người chưa ai nhìn."
        )
    if moved:
        print(
            "Số đổi giữa lúc đo — có lane khác đang ghi vào máy này:", file=sys.stderr
        )
        for line in moved:
            print(f"    {line}", file=sys.stderr)
        print(
            "\nKHÔNG KẾT LUẬN. Đo lại trên một instance không ai ghi vào.",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN

    if failures:
        print(f"BẨN — {len(failures)} vi phạm:", file=sys.stderr)
        for line in failures:
            print(f"    {line}", file=sys.stderr)
        return EXIT_DIRTY

    print(
        f"SẠCH — đo đủ {measured} persona demo (sàn {DEMO_CAST_SIZE}), "
        f"cả {measured} chỉ có lịch sử trong {group_name!r}."
    )
    return EXIT_OK


def run() -> int:
    """Keep a broken gate from being read as a dirty product.

    `main()` indexes the JSON body by key. If the API changes shape, the
    `KeyError` escapes and Python exits 1 -- which is `EXIT_DIRTY` under this
    gate's own contract. Anybody reading the exit code without reading the
    traceback concludes "persona bẩn" when the truth is "cổng gãy". The
    docstring already refuses to fold a dead measurement into a broken product
    for the concurrent-writer case; this closes the same hole for shape drift.

    The traceback is still printed -- this converts the verdict, not the
    diagnosis.
    """

    try:
        return main()
    except (KeyError, TypeError, IndexError) as exc:
        traceback.print_exc()
        return die(
            f"thân JSON không có hình dạng cổng này giả định ({exc!r}). "
            "Cổng GÃY, không phải persona bẩn."
        )


if __name__ == "__main__":
    raise SystemExit(run())
