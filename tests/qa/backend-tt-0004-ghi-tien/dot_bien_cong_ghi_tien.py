#!/usr/bin/env python3
"""Mutation table for the write-side money gate (PR #495).

A gate that has never been seen red is a decoration. This applies seven
mutations and reports, for each, whether the gate caught it. Five of them are
aimed at the gate's own machinery rather than at the product, because a
recorder that quietly stopped recording satisfies every "nothing matched"
assertion in the file for free.

It then applies one *attribution* mutation, which is a different question:
not "is the gutted step caught" but "by which rule". It must turn the gate
green again, and the run fails if it does not.

Every mutation is applied to a file, measured, and reverted from an in-memory
copy of the original bytes -- never from git, so an uncommitted edit cannot be
destroyed by a run.

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://...' \
      python3 tests/qa/backend-tt-0004-ghi-tien/dot_bien_cong_ghi_tien.py

Exit codes: 0 = every mutation caught, 1 = at least one survived,
2 = could not measure (never a silent pass).
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
API = REPO / "services" / "api"

GATE = API / "tests" / "postgres" / "test_money_writes_are_integer_postgres.py"
REPOSITORY = API / "app" / "api" / "repository.py"
COLUMNS_GATE = API / "tests" / "postgres" / "test_money_columns_are_integer_postgres.py"

#: (label, file, find, replace, what it simulates)
MUTATIONS: list[tuple[str, pathlib.Path, str, str, str]] = [
    (
        "M1",
        REPOSITORY,
        "            confirmed_by_id=confirmed_by_id,\n            amount_vnd=amount_vnd,",
        "            confirmed_by_id=confirmed_by_id,\n            amount_vnd=float(amount_vnd),",
        "so cai nhan mot float — dung hoi quy tien that",
    ),
    (
        "M2",
        REPOSITORY,
        "                    participant_id=participant_id,\n                    amount_vnd=amount_vnd,",
        "                    participant_id=participant_id,\n                    amount_vnd=float(amount_vnd),",
        "phan bo xac nhan nhan float — Luat 2 vo khong tin hieu",
    ),
    (
        "M3",
        GATE,
        '    slice_.report_payment(state["obligation_id"], minute=5)',
        "    return  # mutant: buoc bi rut ruot, ten van con trong dict",
        "rut ruot mot buoc, GIU ten trong MONEY_WRITE_SURFACE",
    ),
    (
        "M4",
        GATE,
        "        return self.value is None or type(self.value) is int",
        "        return self.value is None or isinstance(self.value, int)",
        "doi sang isinstance — bay bool ma database VAN bat duoc",
    ),
    (
        "M5",
        GATE,
        "        match = _WRITE_TARGET.search(statement)\n        if match is None:\n            return",
        "        match = _WRITE_TARGET.search(statement)\n        if match is None or True:\n            return",
        "may quan sat chet — moi assert 'khong khop gi' thoa man mien phi",
    ),
    (
        "M6",
        GATE,
        "        if _looks_like_money(column):",
        "        if _looks_like_money(column) and False:",
        "phep dan xuat cot tien tra ve RONG",
    ),
    (
        "M7",
        COLUMNS_GATE,
        '    return column_name.endswith("_vnd") or "amount" in column_name',
        "    return False  # mutant: #486 thoi coi bat cu gi la tien",
        "dan xuat dung chung cua #486 bi lam rong — cong nay phai chet theo",
    ),
]

#: Attribution, not coverage. M3 proves the gutted step is caught; this proves
#: *what* catches it. Applying M3 together with the removal of the per-step
#: count must turn the gate green again -- if it stayed red, something else was
#: doing the catching and the per-step rule would be decoration.
ATTRIBUTION = (
    "A1",
    GATE,
    [
        (
            '    slice_.report_payment(state["obligation_id"], minute=5)',
            "    return  # mutant: buoc bi rut ruot",
        ),
        (
            "    silent = [name for name, count in per_step.items() if count == 0]",
            "    silent = []  # mutant: bo phep dem theo tung buoc",
        ),
    ],
    "M3 + bo phep dem moi buoc — PHAI xanh lai, nếu không thì M3 do vi ly do khac",
)

SELECT = "tests/postgres/test_money_writes_are_integer_postgres.py"


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            SELECT,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=API,
        capture_output=True,
        text=True,
        env={**os.environ, "MOBILE_REQUIRE_POSTGRES_TESTS": "1"},
    )
    tail = [line for line in proc.stdout.splitlines() if line.strip()]
    return proc.returncode, tail[-1] if tail else "(khong co output)"


def main() -> int:
    if not os.environ.get("MOBILE_TEST_DATABASE_URL"):
        print("KHONG KIEM DUOC: chua dat MOBILE_TEST_DATABASE_URL")
        return 2
    for path in {GATE, REPOSITORY, COLUMNS_GATE}:
        if not path.exists():
            print(f"KHONG KIEM DUOC: khong thay {path}")
            return 2

    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        print("KHONG KIEM DUOC: cay co thay doi chua commit —")
        print(dirty)
        return 2

    code, line = run_gate()
    print(f"M0  nen, khong dot bien{'':38} rc={code}  {line}")
    if code != 0:
        print("KHONG KIEM DUOC: nen da do san, bang dot bien vo nghia")
        return 2

    survived: list[str] = []
    for label, path, find, replace, description in MUTATIONS:
        original = path.read_bytes()
        text = original.decode()
        if text.count(find) != 1:
            print(
                f"{label}  KHONG KIEM DUOC: neo khop {text.count(find)} lan trong "
                f"{path.name} (can dung 1)"
            )
            return 2
        try:
            path.write_text(text.replace(find, replace), encoding="utf-8")
            code, line = run_gate()
        finally:
            path.write_bytes(original)
        caught = code != 0
        if not caught:
            survived.append(label)
        verdict = "BAT DUOC" if caught else "LOT  <-- song sot"
        print(f"{label}  {description:52.52} rc={code}  {line[:34]:34} {verdict}")

    label, path, pairs, description = ATTRIBUTION
    original = path.read_bytes()
    text = original.decode()
    for find, _replace in pairs:
        if text.count(find) != 1:
            print(f"{label}  KHONG KIEM DUOC: neo khop {text.count(find)} lan")
            return 2
    try:
        for find, replace in pairs:
            text = text.replace(find, replace)
        path.write_text(text, encoding="utf-8")
        code, line = run_gate()
    finally:
        path.write_bytes(original)
    attributed = code == 0
    verdict = (
        "XANH LAI -> dung phep dem moi buoc bat M3"
        if attributed
        else "VAN DO -> M3 do vi ly do KHAC, doc lai"
    )
    print(f"{label}  {description:52.52} rc={code}  {line[:34]:34} {verdict}")

    print()
    if survived:
        print(f"{len(survived)} dot bien SONG SOT: {', '.join(survived)}")
        return 1
    if not attributed:
        print("khong dot bien nao song sot, NHUNG quy thuoc A1 that bai")
        return 1
    print(f"khong dot bien nao song sot ({len(MUTATIONS)}/{len(MUTATIONS)} bat duoc)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
