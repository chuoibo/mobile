#!/usr/bin/env python3
"""Gỡ tư cách thành viên của bảy persona demo khỏi các nhóm không phải nhóm demo.

## Vì sao cần

Máy demo dùng chung. Mọi lượt QA đăng nhập bằng đúng bảy người mà
`seed_demo_data.py` gieo ra, rồi mỗi lượt tạo thêm một nhóm nháp. Đo trên máy
này ngày 2026-08-30, bảy persona demo là thành viên **active** của 10 context:

    Team Đà Lạt                                       7 người   <- nhóm demo
    Team Đà Lạt (tồn dư 30/08 — KHÔNG dùng để demo)   7 người
    Hội bạn demo QA07                                 x6 context
    Chi rieng cua Trang                               1 người
    probe                                             1 người

`group_count` trên màn Cá nhân đếm thẳng số membership active, nên Minh mở app
ra thấy "9 nhóm". Đó là rác của bộ đồ nghề nằm ở ngay cửa vào.

## Cái script này ĐỘNG tới, và cái nó KHÔNG động tới

Động tới: đúng một thứ — các hàng `memberships` của bảy persona demo ở những
context **không phải** nhóm demo. Và không xoá hàng nào: nó gọi route thật của
sản phẩm, `DELETE /contexts/{id}/members/{person_id}`, đúng đường mà một người
dùng bấm "rời nhóm" sẽ đi. Repository đặt `state='left'` + `left_at=now()` —
hai giá trị mà check constraint của bảng bắt phải đi cùng nhau.

KHÔNG động tới: `contexts` (nhóm rác vẫn còn nguyên cho lane khác dùng),
`people`, và không một dòng nào trong sổ — `confirmed_allocations`,
`expense_versions`, `collection_batches`. Sổ là nguồn sự thật của bất biến 3;
một script dọn rác không có việc gì ở đó.

## Điều nó KHÔNG sửa được, nói ra ở đây thay vì để người đọc tưởng

Rời nhóm chỉ đổi `group_count`. `spend_vnd`, `expense_count` và danh sách
`movements` trên `GET /people/{id}/finance` tính từ `confirmed_allocations` và
`collection_batches`, **không** lọc theo tư cách thành viên — vì màn Cá nhân
theo thiết kế là tài chính của một người **xuyên nhóm**. Nên sau khi chạy cái
này, tiền cũ của persona trong nhóm rác vẫn cộng vào tổng của họ, và tên nhóm
rác vẫn hiện trong dòng movement. Đo trước khi dọn, trên máy demo:

    Minh:  group_count=9  expense_count=17  spend=3.073.333đ
           movements có 4 dòng mang tên "Team Đà Lạt (tồn dư 30/08 — KHÔNG
           dùng để demo)"

Số dư **nhóm** thì không sao: `GET /contexts/{id}/balances` lọc theo
`context_id`, nên nhóm demo tính lại được và đúng.

## Chạy

    python3 scripts/don_rac_persona_demo.py                 # chỉ liệt kê
    python3 scripts/don_rac_persona_demo.py --apply         # gỡ thật

Mặc định là liệt kê chứ không phải làm. Máy demo dùng chung, và một script
đụng dữ liệu người khác đang dùng thì mặc định phải là "cho tôi xem trước".
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Cùng máy, cùng cổng như `check_demo_data.py`. Số lấy từ docker-compose.yml.
DEFAULT_DSN = "postgresql://mobile:mobile-dev-only@127.0.0.1:5432/mobile"
DEFAULT_API = "http://127.0.0.1:8099"

# Ba trạng thái, giống `check_demo_data.py`: gộp "không chạy được" vào "chạy
# rồi và hỏng" là cách một cổng chết đọc thành một cổng đang đỏ.
EXIT_OK = 0
EXIT_INCOMPLETE = 1
EXIT_CANNOT_RUN = 2

# Một cặp (context, person) có thể có nhiều hàng active — bảng chỉ có index
# thường trên `person_id WHERE left_at IS NULL`, không phải unique, và một lượt
# gieo dở đã để lại hai hàng cho cùng một người. Route chỉ đóng một hàng mỗi
# lần gọi, nên phải gọi lại cho tới khi hết.
MAX_ROWS_PER_PAIR = 8


def die(message: str) -> int:
    print(message, file=sys.stderr)
    return EXIT_CANNOT_RUN


def call(
    api_base: str, method: str, path: str, *, actor: uuid.UUID, context_id: uuid.UUID
) -> int:
    """One request, returning the HTTP status.

    The opener is built with an empty ProxyHandler on purpose. This machine has
    a proxy that intercepts localhost, and urllib honours `http_proxy` from the
    environment: without this, a DELETE aimed at 127.0.0.1 lands on a redirect
    page and the caller reads the failure as "already gone".
    """

    request = urllib.request.Request(
        f"{api_base}{path}",
        headers={
            "Accept": "application/json",
            "X-Actor-ID": str(actor),
            "X-Actor-Roles": "member",
            "X-Actor-Contexts": str(context_id),
        },
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"    {method} {path} -> HTTP {exc.code} {detail}", file=sys.stderr)
        return exc.code


def demo_people() -> tuple[list[uuid.UUID], str]:
    """Read the seven ids and the group name off the builder, never copied.

    A hardcoded list here would go on passing on the day somebody adds an
    eighth person to the demo, and the eighth would keep every junk membership
    while the report said everything was clean.
    """

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import seed_demo_data as seed

    return [pid for pid, _ in seed.PEOPLE], seed.GROUP_NAME


def keeper_context(connection, group_name: str) -> uuid.UUID:
    """The one group to keep. Two matches is a stop, not a coin flip."""

    rows = connection.execute(
        "SELECT id FROM contexts WHERE display_name = %s", (group_name,)
    ).fetchall()
    if len(rows) != 1:
        raise LookupError(
            f"cần đúng 1 context tên '{group_name}', tìm thấy {len(rows)}. "
            "Không đoán nhóm nào là nhóm demo."
        )
    return rows[0][0]


def junk_rows(connection, people: list[uuid.UUID], keeper: uuid.UUID) -> list[tuple]:
    return connection.execute(
        "SELECT m.context_id, c.display_name, m.person_id, count(*) "
        "FROM memberships m JOIN contexts c ON c.id = m.context_id "
        "WHERE m.person_id = ANY(%s) AND m.state = 'active' "
        "  AND m.left_at IS NULL AND m.context_id <> %s "
        "GROUP BY 1, 2, 3 ORDER BY 2, 3",
        (people, keeper),
    ).fetchall()


def report(connection, people: list[uuid.UUID]) -> None:
    rows = connection.execute(
        "SELECT c.display_name, count(*) AS hang, count(DISTINCT m.person_id) AS nguoi "
        "FROM memberships m JOIN contexts c ON c.id = m.context_id "
        "WHERE m.person_id = ANY(%s) AND m.state = 'active' AND m.left_at IS NULL "
        "GROUP BY 1 ORDER BY 1",
        (people,),
    ).fetchall()
    for name, hang, nguoi in rows:
        print(f"    {name!r}: {hang} hàng / {nguoi} người")
    print(f"    -> {len(rows)} context còn tư cách thành viên active")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument(
        "--apply", action="store_true", help="gỡ thật; mặc định chỉ liệt kê"
    )
    args = parser.parse_args()

    try:
        import psycopg
    except ImportError as exc:
        return die(f"KHÔNG CHẠY ĐƯỢC — thiếu psycopg: {exc}")

    try:
        people, group_name = demo_people()
    except Exception as exc:  # noqa: BLE001 - any import failure is cannot-run
        return die(f"KHÔNG CHẠY ĐƯỢC — không đọc được seed_demo_data.py: {exc}")

    try:
        connection = psycopg.connect(args.dsn, autocommit=True)
    except Exception as exc:  # noqa: BLE001 - any connect failure is cannot-run
        return die(f"KHÔNG CHẠY ĐƯỢC — không nối được database: {exc}")

    with connection:
        try:
            keeper = keeper_context(connection, group_name)
        except LookupError as exc:
            return die(f"KHÔNG CHẠY ĐƯỢC — {exc}")

        print(f"Nhóm demo giữ lại: {group_name!r}  ({keeper})")
        print("Bảy persona demo, TRƯỚC khi dọn:")
        report(connection, people)

        pending = junk_rows(connection, people, keeper)
        if not pending:
            print("\nKhông có tư cách thành viên rác nào. Không làm gì.")
            return EXIT_OK

        print(f"\n{len(pending)} cặp (nhóm rác, người) cần gỡ:")
        for context_id, name, person_id, rows in pending:
            print(f"    {name!r} <- {person_id} ({rows} hàng)")

        if not args.apply:
            print("\nMới chỉ liệt kê. Thêm --apply để gỡ thật.")
            return EXIT_OK

        print("\nGỡ qua DELETE /contexts/{id}/members/{person_id} …")
        for context_id, name, person_id, _ in pending:
            for _attempt in range(MAX_ROWS_PER_PAIR):
                status = call(
                    args.api,
                    "DELETE",
                    f"/contexts/{context_id}/members/{person_id}",
                    actor=person_id,
                    context_id=context_id,
                )
                # 404 is the route saying there is no active membership left,
                # which is the state this loop is driving towards.
                if status != 204:
                    break

        print("\nBảy persona demo, SAU khi dọn:")
        report(connection, people)
        left = junk_rows(connection, people, keeper)
        if left:
            print(f"\nCÒN SÓT {len(left)} cặp:", file=sys.stderr)
            for context_id, name, person_id, rows in left:
                print(f"    {name!r} <- {person_id} ({rows} hàng)", file=sys.stderr)
            return EXIT_INCOMPLETE

        print("\nSạch: persona demo chỉ còn thuộc nhóm demo.")
        return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
