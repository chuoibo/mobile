#!/usr/bin/env python3
"""The demo machine must carry a dataset somebody can actually demo.

## Why this is a third gate and not a flag on the second one

`check_demo_matches_main.py` asks "does the demo serve the routes main
declares". It says so itself, in its own "what it does NOT prove" section:

    - It says nothing about the database.

That sentence was accurate and it was load-bearing. Measured on this machine on
2026-08-30, both gates green, ten minutes apart, for six hours:

    $ make demo-check URL=http://127.0.0.1:8099
    Route máy demo: 76 phục vụ / 76 origin/main khai — KHỚP
    exit 0

    $ docker exec mobile-local-postgres-1 psql -U mobile -d mobile -At -c \
        "SELECT count(*) FROM outings"
    0

Zero outings. F13 (tạo buổi đi), F14 (mời), F15 (đóng thời gian) and F16 (AI lên
kế hoạch) are finished and their tests are green, and all four render EMPTY on
the demo machine, because every screen that shows them reads from a table with
nothing in it. The album route answers 200 with an empty list, so it is not even
an error anybody would notice.

Every signal on the machine said the demo was fine. The route gate was right and
useless: it compared paths, and the paths were perfect.

## What it checks

That the demo group is fully built, against expectations **imported from
`seed_demo_data.py`** rather than copied into this file. A hand-written "expect
3 outings" here would not know when the script starts building four, and would
go on passing while the demo lost a trip. So the numbers come from the same
`outings()` and `PEOPLE` the builder itself uses.

Checked, and each one is something a human would SEE on the demo:

    outings      == len(outings())    Khám phá / kỷ niệm / album are empty without it
    batches      == len(outings())    the collection rounds behind the money screens
    members      == len(PEOPLE)       a split among two people is not the demo
    expenses     == sum of the specs  the ledger the whole hero path reads from

## Why counts, and why equality rather than "at least"

`>= 1` would pass the state this gate was written for. The demo group on
2026-08-30 had EIGHT collection rounds where the script declares three: several
runs stacked on top of each other, one of them dead partway. That is not a
dataset anybody designed, and "at least one" calls it healthy. Too many rounds
is as wrong as too few -- it means a rerun landed on top of a previous one, and
the money screens show a history nobody scripted.

## Why it does not check the memory wall

Because `seed_demo_data.py` does not build one. Asserting `memories > 0` here
would make this gate fail forever on a correctly seeded machine, and a gate that
is red when the thing it guards is right gets switched off within a day. The
memory wall being empty is a real gap in the demo, but it is a gap in the
BUILDER, and the honest place to say so is here in prose, not as a red line in a
checker that would be lying about which component is broken.

## What it does NOT prove

- Nothing here renders a screen. Rows in `outings` do not prove the Khám phá
  screen draws them; it proves the screen has something to draw. `imp detect`
  and the hero-path walk remain the only things that speak for the UI.
- It reads counts, not content. Three outings with empty titles pass.
- It says nothing about the OTHER groups on a shared demo database. The machine
  also carries probe data from several lanes; this gate is scoped to the one
  group the demo script builds, on purpose, because the rest is not demoed.
- A dataset that is correct now can be wrong ten minutes from now. That is what
  running it on a schedule is for, not what one green run means.

Usage:
  scripts/check_demo_data.py
  scripts/check_demo_data.py --dsn postgresql://mobile:...@127.0.0.1:5439/mobile
  scripts/check_demo_data.py --json

Exit codes: 0 the demo dataset is complete,
1 the dataset is incomplete or overbuilt -- the demo will show the wrong thing,
2 the check could not run -- and could not run is never a pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The default points at the shared demo stack, the same machine
# `check_demo_matches_main.py` defaults to. Ports come from docker-compose.yml.
DEFAULT_DSN = "postgresql://mobile:mobile-dev-only@127.0.0.1:5432/mobile"

# Exit 2, not 1. "Could not run" and "ran and found a problem" are different
# answers, and collapsing them is how a dead gate reads as a failing one. Same
# three states as `demo_watch.py`, deliberately.
EXIT_OK = 0
EXIT_DIFFERS = 1
EXIT_CANNOT_RUN = 2


def die(message: str) -> int:
    print(message, file=sys.stderr)
    return EXIT_CANNOT_RUN


def expectations() -> dict[str, int] | None:
    """Read the demo's shape off the builder, so the two cannot drift apart.

    Imported rather than hardcoded: see the module docstring. Returns None when
    the builder cannot be imported at all, which is a cannot-run, not a failure.
    """

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import seed_demo_data as seed

    trips = seed.outings(datetime.now(UTC))
    return {
        "outings": len(trips),
        "batches": len(trips),
        "members": len(seed.PEOPLE),
        "expenses": sum(len(trip["expenses"]) for trip in trips),
        "_group_name": seed.GROUP_NAME,
    }


def observed(connection, context_id) -> dict[str, int]:
    """Count what is actually on the machine.

    Read back from the database rather than inferred from anything this process
    did -- the builder's own reporting section makes the same argument for the
    same reason.
    """

    def one(sql: str) -> int:
        return connection.execute(sql, (context_id,)).fetchone()[0]

    return {
        "outings": one("SELECT COUNT(*) FROM outings WHERE context_id = %s"),
        "batches": one("SELECT COUNT(*) FROM collection_batches WHERE context_id = %s"),
        "members": one(
            "SELECT COUNT(*) FROM memberships "
            "WHERE context_id = %s AND state = 'active'"
        ),
        "expenses": one("SELECT COUNT(*) FROM expenses WHERE context_id = %s"),
    }


# What a human opening the demo sees when each count is wrong. The point of a
# gate is to hand back the consequence, not the number -- "outings 0/3" is a
# fact nobody can act on until they know it empties four screens.
CONSEQUENCE = {
    "outings": "Khám phá, kỷ niệm và album hiện RỖNG (F13/F14/F15/F16)",
    "batches": "màn tiền hiện lịch sử đợt thu không ai thiết kế",
    "members": "chia tiền giữa sai số người",
    "expenses": "sổ cái thiếu khoản chi, số dư và VietQR đọc từ đó",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bộ dữ liệu trên máy demo có dùng để demo được không"
    )
    parser.add_argument("--dsn", default=DEFAULT_DSN, help=f"mặc định {DEFAULT_DSN}")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--json", action="store_true", help="in kết quả dạng máy đọc")
    args = parser.parse_args(argv)

    try:
        import psycopg
    except ImportError:
        return die("KHÔNG ĐỐI CHIẾU ĐƯỢC — thiếu psycopg trên máy đang chạy gate.")

    try:
        expected = expectations()
    except Exception as exc:  # noqa: BLE001 - any import failure is a cannot-run
        return die(f"KHÔNG ĐỐI CHIẾU ĐƯỢC — không đọc được seed_demo_data.py: {exc}")

    group_name = expected.pop("_group_name")

    try:
        connection = psycopg.connect(args.dsn, connect_timeout=int(args.timeout))
    except Exception as exc:  # noqa: BLE001 - driver raises many shapes
        return die(
            f"KHÔNG ĐỐI CHIẾU ĐƯỢC — không nối được database demo: {exc}\n"
            "  Máy demo có đang chạy không?  docker ps | grep postgres"
        )

    with connection:
        row = connection.execute(
            "SELECT id FROM contexts WHERE display_name = %s LIMIT 1", (group_name,)
        ).fetchone()
        if row is None:
            message = (
                f"LỆCH — chưa có nhóm demo '{group_name}' trên máy này.\n"
                "  Máy demo chưa được nạp dữ liệu:  make demo"
            )
            if args.json:
                print(json.dumps({"group": None, "expected": expected}))
            print(message, file=sys.stderr)
            return EXIT_DIFFERS
        context_id = row[0]
        try:
            actual = observed(connection, context_id)
        except Exception as exc:  # noqa: BLE001 - driver raises many shapes
            # A missing table is the loudest example: a demo stack built before
            # `outings` existed answers this with UndefinedTable, and the first
            # version of this file let that escape as a traceback and exit 1 --
            # the exact collapse of "could not run" into "found a problem" that
            # the exit codes above exist to prevent. Caught, and reported as the
            # schema being too old to answer the question at all.
            return die(
                f"KHÔNG ĐỐI CHIẾU ĐƯỢC — không đọc được dữ liệu nhóm demo: {exc}\n"
                "  Nếu là 'relation does not exist': schema của máy đó cũ hơn\n"
                "  bảng cần đọc. Chạy migration rồi seed lại, đừng đọc số này."
            )

    wrong = {k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]}

    if args.json:
        print(
            json.dumps(
                {
                    "group": str(context_id),
                    "expected": expected,
                    "observed": actual,
                    "wrong": {k: list(v) for k, v in wrong.items()},
                },
                ensure_ascii=False,
            )
        )

    if not wrong:
        parts = ", ".join(f"{k} {actual[k]}" for k in sorted(expected))
        print(f"Dữ liệu demo '{group_name}': {parts} — ĐỦ, đúng bộ script khai.")
        return EXIT_OK

    print(
        f"Dữ liệu demo '{group_name}' ({context_id}) KHÔNG dùng để demo được:",
        file=sys.stderr,
    )
    for key in sorted(wrong):
        got, want = wrong[key]
        print(f"  {key:9s} {got}/{want}   -> {CONSEQUENCE[key]}", file=sys.stderr)
    print(
        "\nMột lượt chạy trước đã dựng dở, hoặc nhiều lượt chồng lên nhau.\n"
        "  Bộ riêng, không đụng ai:  MOBILE_PROJECT=demo MOBILE_API_PORT=8199 "
        "MOBILE_POSTGRES_PORT=5439 make demo\n"
        "  `make clean` XOÁ database dùng chung của cả máy — hỏi cả đội trước.",
        file=sys.stderr,
    )
    return EXIT_DIFFERS


if __name__ == "__main__":
    raise SystemExit(main())
