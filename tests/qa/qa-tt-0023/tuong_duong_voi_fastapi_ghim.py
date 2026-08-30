"""Check PR #290's shape table against a REAL fastapi 0.115.6, not an emulation.

`services/api/tests/api/test_route_declarations_under_pinned_fastapi.py` decides
what the pinned fastapi would do by monkey-patching one resolver on whatever
fastapi this machine has. That is a *model* of 0.115.6. A model can be wrong,
and a wrong model here is the worst kind of wrong: it produces a green gate for
a declaration that stops the container booting.

This script closes that loop from the outside. It reads the committed `SHAPES`
table -- by `ast.literal_eval`, so it measures the same corpus the gate uses
rather than a second copy that could drift -- and imports every shape with an
interpreter that really has fastapi 0.115.6 installed. Agreement on every row
is what makes the emulation's verdict worth reading.

It is a QA instrument, not a gate: it needs a venv this repo does not pin, so
it is run by hand and its result is quoted in the QA report.

    python3 -m venv /tmp/pin115
    /tmp/pin115/bin/pip install 'fastapi==0.115.6'
    python3 tests/qa/qa-tt-0023/tuong_duong_voi_fastapi_ghim.py /tmp/pin115/bin/python

Exit 0 when every row agrees, 1 on any disagreement.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLE = (
    REPO_ROOT / "services/api/tests/api/test_route_declarations_under_pinned_fastapi.py"
)

#: The string fastapi raises when a route promises a body under a status code
#: that forbids one. Matching on it rather than on a bare non-zero exit is the
#: difference between "refused for this reason" and "the child died of a typo".
REFUSAL = "must not have a response body"


def read_shapes(path: Path) -> dict[str, tuple[str, bool]]:
    """Read `SHAPES` out of the gate file without importing it.

    Importing would need pytest and `app` on the path; parsing needs neither,
    and it is what lets a bare pinned interpreter read the committed table.
    """

    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "SHAPES" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit(f"không tìm thấy SHAPES trong {path}")


def import_with(python: str, name: str, source: str) -> tuple[bool, str]:
    """Import one shape with `python`; return (refused?, combined output)."""

    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / f"shape_{name}.py").write_text(source)
        result = subprocess.run(
            [python, "-c", f"import shape_{name}"],
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONPATH=directory),
            timeout=120,
            check=False,
        )
    return result.returncode != 0, result.stdout + result.stderr


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(f"dùng: {argv[0]} <đường dẫn python có fastapi đã ghim>")
    python = argv[1]

    version = subprocess.run(
        [python, "-c", "import fastapi; print(fastapi.__version__)"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    print(f"trình thông dịch đối chứng: {python} — fastapi {version or '?'}")

    shapes = read_shapes(TABLE)
    print(f"đọc {len(shapes)} hình dạng từ {TABLE.relative_to(REPO_ROOT)}\n")

    header = f"{'hình dạng':38} {'bảng khai':>10} {'đo được':>10}  kết luận"
    print(header)
    disagreements = 0
    for name in sorted(shapes):
        source, must_be_refused = shapes[name]
        refused, output = import_with(python, name, source)
        right_reason = REFUSAL in output
        agrees = refused == must_be_refused and (not refused or right_reason)
        note = ""
        if refused and not right_reason:
            last = output.strip().splitlines()[-1:] or [""]
            note = "  ĐỎ SAI LÝ DO: " + last[0][:80]
        if not agrees:
            disagreements += 1
        verdict = "khớp" if agrees else "LỆCH"
        refused_word = "từ chối" if refused else "nhận"
        claim_word = "từ chối" if must_be_refused else "nhận"
        print(f"{name:38} {claim_word:>10} {refused_word:>10}  {verdict}{note}")

    print()
    if disagreements:
        print(
            f"KẾT LUẬN: LỆCH {disagreements} hàng — bảng của #290 không tả đúng 0.115.6"
        )
        return 1
    print("KẾT LUẬN: TƯƠNG ĐƯƠNG — mọi hàng khớp với fastapi thật")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
