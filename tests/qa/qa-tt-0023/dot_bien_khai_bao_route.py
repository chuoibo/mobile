"""Mutation table for the three gates that guard route declarations.

Three files now claim to catch "a route declares a body under a bodyless status
code, so the app cannot be imported by the fastapi the image installs":

  * services/api/tests/api/test_bodyless_status_declarations.py   (#288, in-process)
  * services/api/tests/api/test_route_declarations_under_pinned_fastapi.py (#290, child interpreter)
  * scripts/check_pinned_import.sh                                (#292, real 0.115.6 in the image)

A gate that is red for every edit is not a gate, it is an alarm. So the table
below carries rows in both directions: three that BREAK the invariant and must
turn the gate red, and one that PRESERVES it -- a legal declaration that the
pinned fastapi imports happily -- which must stay green. The property-preserving
row is the one that separates "measures the pinned rule" from "allergic to the
characters `-> None`", and it is the row that told the three gates apart.

Each row edits the working tree, runs the gate, then restores the tree from a
copy taken before any edit -- restore is in a `finally`, because a mutation left
behind is worse than no measurement.

    python3 tests/qa/qa-tt-0023/dot_bien_khai_bao_route.py \
        bash -o pipefail -c "cd services/api && python3 -m pytest \
            tests/api/test_route_declarations_under_pinned_fastapi.py -q"

    python3 tests/qa/qa-tt-0023/dot_bien_khai_bao_route.py \
        bash scripts/check_pinned_import.sh

`-o pipefail` is not decoration: piping pytest into `tail` hands the pipeline
tail's exit status, and the first run of this table read four real red gates as
four green ones because of it.

Exit 0 when every row lands where it claims, 1 otherwise.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MEMORIES = REPO_ROOT / "services/api/app/api/routes/memories.py"
CONTEXTS = REPO_ROOT / "services/api/app/api/routes/contexts.py"

#: The decorator of the route that actually took the container down, as it
#: stands on main after #288 fixed it.
DECLARATION = (
    "    status_code=status.HTTP_204_NO_CONTENT,\n"
    "    responses=ERRORS,\n"
    ")\ndef delete_memory_reaction("
)

#: name -> (edits, must the gate go red?)
#: An edit is (file, old, new) and `old` must appear exactly once, or the row
#: is reported as unmeasurable rather than quietly patching the wrong copy.
ROWS: list[tuple[str, list[tuple[Path, str, str]], bool]] = [
    (
        "M1 memories: 204 trở lại '-> None' (đúng lỗi đã ship)",
        [(MEMORIES, ") -> Response:", ") -> None:")],
        True,
    ),
    (
        "M2 contexts.leave_context: 204 với '-> None' (file KHÁC)",
        [(CONTEXTS, ") -> Response:", ") -> None:")],
        True,
    ),
    (
        "M3 memories: '-> None' NHƯNG khai response_model=None (GIỮ tính chất)",
        [
            (
                MEMORIES,
                DECLARATION,
                DECLARATION.replace(
                    "    responses=ERRORS,",
                    "    response_model=None,\n    responses=ERRORS,",
                ),
            ),
            (MEMORIES, ") -> Response:", ") -> None:"),
        ],
        False,
    ),
    (
        "M4 memories: 204 đổi thành 304, vẫn '-> None' (mã khác, cùng lớp lỗi)",
        [
            (
                MEMORIES,
                DECLARATION,
                DECLARATION.replace(
                    "    status_code=status.HTTP_204_NO_CONTENT,",
                    "    status_code=304,",
                ),
            ),
            (MEMORIES, ") -> Response:", ") -> None:"),
        ],
        True,
    ),
]


def main(argv: list[str]) -> int:
    gate = argv[1:]
    if not gate:
        raise SystemExit(f"dùng: {argv[0]} <lệnh cổng...>")

    touched = {path for _, edits, _ in ROWS for path, _, _ in edits}
    backups: dict[Path, str] = {}
    for path in touched:
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=path.name)
        handle.write(path.read_bytes())
        handle.close()
        backups[path] = handle.name

    def restore() -> None:
        for path, backup in backups.items():
            shutil.copyfile(backup, path)

    broken = 0
    try:
        for name, edits, must_go_red in ROWS:
            applied = True
            for path, old, new in edits:
                text = path.read_text()
                if text.count(old) != 1:
                    print(f"KHÔNG ĐO ĐƯỢC | {name}: neo khớp {text.count(old)} lần")
                    applied = False
                    break
                path.write_text(text.replace(old, new, 1))
            if not applied:
                restore()
                broken += 1
                continue

            result = subprocess.run(
                gate,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=1800,
                check=False,
            )
            restore()

            went_red = result.returncode != 0
            landed = went_red == must_go_red
            broken += 0 if landed else 1
            print(
                f"{'ĐẠT ' if landed else 'HỎNG'} | {name}\n"
                f"       mong đợi {'ĐỎ' if must_go_red else 'XANH'}, "
                f"đo được rc={result.returncode} ({'ĐỎ' if went_red else 'XANH'})"
            )
            tail = (result.stdout + result.stderr).strip().splitlines()
            if tail:
                print(f"       {tail[-1][:150]}")
    finally:
        restore()

    print()
    print("BẢNG ĐỘT BIẾN:", "ĐẠT hết" if broken == 0 else f"{broken} hàng HỎNG")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
