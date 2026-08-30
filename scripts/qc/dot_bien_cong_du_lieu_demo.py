#!/usr/bin/env python3
"""Does `check_demo_data.py` actually bite, or does it just print numbers?

## Why a green run proves nothing on its own

`check_demo_data.py` exists because every other signal on the demo machine was
green while `outings` held zero rows. A gate written in response to a blind spot
is worth exactly as much as its ability to go red, and the only way to know that
is to break something on purpose and watch.

## Why the table below has GREEN rows in it

A mutation table that is red everywhere cannot distinguish a gate that bites
from a gate that is simply broken -- a gate that crashed on startup would also
be red for all ten rows. So three rows here MUST stay green:

    M0  nothing changed at all              the baseline
    M8  an outing's title changes           the gate counts rows, not content
    M9  nine outings land in ANOTHER group  the gate is scoped to the demo group

M9 is the load-bearing control. `check_demo_data` claims in its own docstring
that it "says nothing about the OTHER groups on a shared demo database". If M9
went red the gate would be counting globally, and every lane's probe data would
make the demo machine look broken.

## Why an isolated Postgres

The shared demo machine is the thing being guarded; deleting one of its outings
to see the gate blink is the kind of measurement that becomes the incident. This
provisions its own database and builds the five tables the gate's SQL reads,
with the column names it reads them by.

The cost of that isolation is real and worth saying: a green here is a statement
about the gate's ARITHMETIC, not about the demo machine's schema. If the machine
grows a column rename the gate would exit 2 there and still pass every row here.
Run the gate once against the real machine as well; the two together cover both
halves.

Usage:
    scripts/qc/dot_bien_cong_du_lieu_demo.py                    # tự dựng container
    scripts/qc/dot_bien_cong_du_lieu_demo.py --dsn postgresql://...   # DB có sẵn

Exit codes: 0 mọi hàng ra đúng như mong đợi (cả đỏ lẫn xanh),
1 có hàng sai -- cổng không gác đúng cái nó khai,
2 không chạy được.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "check_demo_data.py"

EXIT_OK = 0
EXIT_GATE_BLIND = 1
EXIT_CANNOT_RUN = 2

CONTAINER = "qc-dot-bien-cong-demo"
PORT = 5951
PROBE_DSN = f"postgresql://mobile:mobile-dev-only@127.0.0.1:{PORT}/probe"

# Hex with letters on purpose: an all-digit UUID trips repo_guard's
# long-number rule, which cannot tell one from a telephone number.
GROUP_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

# Only the tables and columns `check_demo_data.observed()` reads. Deliberately
# not the production schema: the point is to exercise the gate's SQL, and a
# migrated schema here would hide a column rename behind an exit 2.
SCHEMA = """
DROP TABLE IF EXISTS outings, collection_batches, memberships, expenses, contexts CASCADE;
CREATE TABLE contexts (id uuid PRIMARY KEY, display_name text NOT NULL);
CREATE TABLE outings (id uuid PRIMARY KEY, context_id uuid NOT NULL, title text);
CREATE TABLE collection_batches (id uuid PRIMARY KEY, context_id uuid NOT NULL);
CREATE TABLE memberships (id uuid PRIMARY KEY, context_id uuid NOT NULL, state text NOT NULL);
CREATE TABLE expenses (id uuid PRIMARY KEY, context_id uuid NOT NULL);
"""


def mutants(group: str, other: str) -> list[tuple[str, str | None, int]]:
    """(nhãn, SQL đột biến, mã thoát mong đợi). None nghĩa là không đổi gì."""

    return [
        ("M0  nền, không đổi gì", None, 0),
        (
            "M1  xoá một buổi đi",
            "DELETE FROM outings WHERE ctid = (SELECT ctid FROM outings LIMIT 1)",
            1,
        ),
        (
            "M2  thêm buổi đi thứ tư",
            f"INSERT INTO outings VALUES (gen_random_uuid(), '{group}', 'thừa')",
            1,
        ),
        (
            "M3  xoá một đợt thu",
            "DELETE FROM collection_batches "
            "WHERE ctid = (SELECT ctid FROM collection_batches LIMIT 1)",
            1,
        ),
        (
            "M4  xoá một khoản chi",
            "DELETE FROM expenses WHERE ctid = (SELECT ctid FROM expenses LIMIT 1)",
            1,
        ),
        (
            "M5  một thành viên rời nhóm",
            "UPDATE memberships SET state = 'left' "
            "WHERE ctid = (SELECT ctid FROM memberships LIMIT 1)",
            1,
        ),
        (
            "M6  thêm người thứ tám",
            f"INSERT INTO memberships VALUES (gen_random_uuid(), '{group}', 'active')",
            1,
        ),
        (
            "M7  đổi tên nhóm demo",
            f"UPDATE contexts SET display_name = 'đổi rồi' WHERE id = '{group}'",
            1,
        ),
        # --- đối chứng dương: ba hàng dưới đây PHẢI xanh -------------------
        (
            "M8  đổi tiêu đề buổi đi, không đổi số lượng",
            "UPDATE outings SET title = 'tên khác'",
            0,
        ),
        (
            "M9  đổ chín buổi đi vào NHÓM KHÁC",
            f"INSERT INTO outings SELECT gen_random_uuid(), '{other}', 'x' "
            "FROM generate_series(1, 9)",
            0,
        ),
    ]


def start_container() -> bool:
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, check=False)
    started = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER,
            "-e",
            "POSTGRES_USER=mobile",
            "-e",
            "POSTGRES_PASSWORD=mobile-dev-only",
            "-e",
            "POSTGRES_DB=probe",
            "-p",
            f"127.0.0.1:{PORT}:5432",
            "postgres:16",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if started.returncode != 0:
        print(
            f"không dựng được container: {started.stderr.strip()[:200]}",
            file=sys.stderr,
        )
        return False
    for _ in range(60):
        ready = subprocess.run(
            ["docker", "exec", CONTAINER, "pg_isready", "-U", "mobile", "-d", "probe"],
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            return True
        time.sleep(1)
    print("container không sẵn sàng sau 60s", file=sys.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="dùng database có sẵn thay vì tự dựng container")
    parser.add_argument(
        "--keep", action="store_true", help="giữ container lại sau khi chạy"
    )
    args = parser.parse_args(argv)

    try:
        import psycopg
    except ImportError:
        print("KHÔNG CHẠY ĐƯỢC — thiếu psycopg.", file=sys.stderr)
        return EXIT_CANNOT_RUN

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import seed_demo_data as seed
    except Exception as exc:  # noqa: BLE001 - any import failure is a cannot-run
        print(
            f"KHÔNG CHẠY ĐƯỢC — không đọc được seed_demo_data.py: {exc}",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN

    owns_container = args.dsn is None
    dsn = args.dsn or PROBE_DSN
    if owns_container and not start_container():
        return EXIT_CANNOT_RUN

    try:
        trips = seed.outings(datetime.now(UTC))
        n_outings = len(trips)
        n_people = len(seed.PEOPLE)
        n_expenses = sum(len(trip["expenses"]) for trip in trips)
        print(
            f"seed khai: outings {n_outings} · batches {n_outings} · "
            f"members {n_people} · expenses {n_expenses}"
        )
        print(f"tên nhóm : {seed.GROUP_NAME!r}\n")

        connection = psycopg.connect(dsn, autocommit=True, connect_timeout=10)

        def rebuild() -> None:
            connection.execute(SCHEMA)
            connection.execute(
                "INSERT INTO contexts VALUES (%s, %s)", (GROUP_ID, seed.GROUP_NAME)
            )
            connection.execute(
                "INSERT INTO contexts VALUES (%s, %s)", (OTHER_ID, "Nhóm khác")
            )
            for index in range(n_outings):
                connection.execute(
                    "INSERT INTO outings VALUES (gen_random_uuid(), %s, %s)",
                    (GROUP_ID, f"chuyến {index}"),
                )
                connection.execute(
                    "INSERT INTO collection_batches VALUES (gen_random_uuid(), %s)",
                    (GROUP_ID,),
                )
            for _ in range(n_people):
                connection.execute(
                    "INSERT INTO memberships VALUES (gen_random_uuid(), %s, 'active')",
                    (GROUP_ID,),
                )
            for _ in range(n_expenses):
                connection.execute(
                    "INSERT INTO expenses VALUES (gen_random_uuid(), %s)", (GROUP_ID,)
                )

        print(f"{'đột biến':46s} {'rc':>3s} {'mong đợi':>9s}  kết quả")
        print("-" * 96)
        wrong = 0
        for label, sql, want in mutants(GROUP_ID, OTHER_ID):
            rebuild()
            if sql:
                connection.execute(sql)
            run = subprocess.run(
                [sys.executable, str(GATE), "--dsn", dsn],
                capture_output=True,
                text=True,
            )
            lines = (run.stdout + run.stderr).strip().splitlines()
            first = lines[0] if lines else ""
            ok = run.returncode == want
            wrong += not ok
            print(
                f"{label:46s} {run.returncode:3d} {want:9d}  "
                f"{'ĐÚNG' if ok else 'SAI '}  {first[:52]}"
            )
        print("-" * 96)
        if wrong:
            print(
                f"{wrong} hàng SAI — cổng không gác đúng cái nó khai.", file=sys.stderr
            )
            return EXIT_GATE_BLIND
        print("Mọi hàng đúng: bảy đột biến bị bắt, ba đối chứng dương giữ xanh.")
        return EXIT_OK
    finally:
        if owns_container and not args.keep:
            subprocess.run(
                ["docker", "rm", "-f", CONTAINER], capture_output=True, check=False
            )


if __name__ == "__main__":
    raise SystemExit(main())
