#!/usr/bin/env python3
"""Measure what the two anchor-table floors from #465 actually stop.

Not a pytest case: a probe that mutates a WORKING COPY of the two gate scripts
and reads back the CLI exit code, so it measures the shipped command rather
than a re-implementation of it. Point it at any tree with `--tree`.

The question it answers, one name at a time: with exactly ONE name deleted from
`IMPORT_CRITICAL` / `REQUEST_FUNCTIONS` -- the table still full, still
non-empty, #430's emptiness floor still quiet -- does the gate still claim a
clean tree?

Before #465 the answer was yes for all 13 names, and for 9 of them the test
suite was green as well. Run it against a pre-#465 tree to see that; run it
against `main` to see exit 2 everywhere.

Each mutation asserts its own edit landed before the result is believed. A
`str.replace` that matches nothing leaves the module intact, and an intact
module reads exactly like "the floor held".

    python3 probe_san_neo_mat_mot_ten.py --tree /path/to/worktree
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# `(table file, name, how the name is spelled in the table)`. The contract
# scripts spell entries `"name": (0, 1)`, the pin script a bare `"name",`.
PIN_NAMES = [
    "fastapi",
    "starlette",
    "pydantic",
    "sqlalchemy",
    "alembic",
    "pytest",
    "pytest-subtests",
]
REQUEST_NAMES = [
    "fetch",
    "doFetch",
    "callAsActor",
    "callAnonymous",
    "translatedAsActor",
    "translatedAnonymous",
]


def drop_pin_name(source: str, name: str) -> str:
    """Delete `name` from IMPORT_CRITICAL only, leaving the anchor intact.

    After #465 the name appears twice -- once in the table, once in
    `REQUIRED_IMPORT_CRITICAL`. Removing only the first is the case that
    matters: the anchor still lists it, so the floor has something to notice.
    Before #465 there is no anchor and it appears once.
    """
    needle = f'        "{name}",\n'
    count = source.count(needle)
    if count not in (1, 2):
        raise SystemExit(f"đột biến KHÔNG ăn: {name!r} xuất hiện {count} lần")
    return source.replace(needle, "", 1)


def drop_request_name(source: str, name: str) -> str:
    """Delete `name` from the REQUEST_FUNCTIONS dict literal."""
    pattern = re.compile(rf'    "{re.escape(name)}": \(\d, \d\),\n')
    matches = pattern.findall(source)
    if len(matches) != 1:
        raise SystemExit(f"đột biến KHÔNG ăn: {name!r} khớp {len(matches)} lần")
    return source.replace(matches[0], "", 1)


def run(tree: Path, script: str, *args: str) -> tuple[int, str]:
    """Run a gate script from inside `tree` so REPO_ROOT still resolves there.

    Running a copy out of a temp directory answers a different question: the
    script exits 2 because `apps/mobile/src` is missing, which reads exactly
    like the floor firing and is not.
    """
    proc = subprocess.run(
        [sys.executable, f"scripts/{script}", *args],
        cwd=tree,
        capture_output=True,
        text=True,
    )
    blurb = (proc.stderr.strip() or proc.stdout.strip() or "").splitlines()
    return proc.returncode, blurb[-1][:88] if blurb else ""


def probe(tree: Path) -> int:
    rows: list[tuple[str, str, int, str]] = []

    for script, names, drop, extra in (
        ("check_pin_drift.py", PIN_NAMES, drop_pin_name, True),
        ("check_api_contract.py", REQUEST_NAMES, drop_request_name, False),
    ):
        path = tree / "scripts" / script
        pristine = path.read_text()
        try:
            for name in names:
                path.write_text(drop(pristine, name))
                args: tuple[str, ...] = ()
                if extra:
                    # Pin exactly this name to a version nobody can have, so the
                    # exit code turns on THIS name rather than on whatever else
                    # happens to drift on the machine running the probe.
                    reqs = Path(tempfile.mkdtemp()) / "reqs.txt"
                    reqs.write_text(f"{name}==0.0.0.dev0\n")
                    args = ("--requirements", str(reqs))
                code, blurb = run(tree, script, *args)
                rows.append((script, name, code, blurb))
        finally:
            path.write_text(pristine)

    blind = [r for r in rows if r[2] != 2]
    width = max(len(r[1]) for r in rows)
    print(f"cây đo: {tree}")
    print(f"{'bảng':<24} {'bỏ tên':<{width}} {'exit':<5} chữ cuối")
    for script, name, code, blurb in rows:
        mark = "MÙ" if code != 2 else "ok"
        print(f"{script:<24} {name:<{width}} {code:<5} {mark}  {blurb}")

    print(f"\n{len(rows) - len(blind)}/{len(rows)} chỗ TỪ CHỐI CHẠY (exit 2).")
    if blind:
        print(f"{len(blind)} chỗ vẫn trả lời như cây sạch:")
        for script, name, code, _ in blind:
            print(f"  MÙ  {script} :: {name} -> exit {code}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tree",
        type=Path,
        default=Path(__file__).resolve().parents[5],
        help="worktree to measure (mặc định: repo chứa chính file này)",
    )
    args = parser.parse_args()
    tree = args.tree.resolve()
    if not (tree / "scripts" / "check_pin_drift.py").is_file():
        raise SystemExit(f"không thấy scripts/check_pin_drift.py trong {tree}")
    if shutil.which("git") is None:  # pragma: no cover - environment guard
        print("cảnh báo: không có git, không khôi phục được nếu probe chết giữa chừng")
    return probe(tree)


if __name__ == "__main__":
    raise SystemExit(main())
