"""Canary matrix for tests/test_workflows_gate_pull_requests.py (PR #214).

The PR author probed six spellings of the `on:` key. This probes something
else: workflows that DECLARE `pull_request` and still never gate a pull
request. Each canary is run against the real gate, in a throwaway repo tree,
so the gate's own file-globbing and assertions run -- not just `triggers()`.

Contract: a canary marked EXPECT_RED must make the gate exit non-zero.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

GATE = pathlib.Path(sys.argv[1]).resolve()  # the gate file under test

VALID = """name: test
on:
  pull_request:
  push:
    branches: [main]
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

# (label, expect_red, files: {name: content})
CASES: list[tuple[str, bool, dict[str, str]]] = [
    # --- control: the shape the PR ships. Must be GREEN, else everything below is noise.
    ("KIỂM SOÁT · đúng bản PR", False, {"test.yml": VALID}),
    # --- the bug the PR fixes, three ways of writing it (must all be RED)
    (
        "push-only, khối",
        True,
        {"test.yml": "name: t\non:\n  push:\n    branches: [main]\njobs: {}\n"},
    ),
    (
        "push-only, inline",
        True,
        {"test.yml": "name: t\non: [push, workflow_dispatch]\njobs: {}\n"},
    ),
    ("push-only, scalar trần", True, {"test.yml": "name: t\non: push\njobs: {}\n"}),
    # --- SEMANTIC evasions: `pull_request` IS declared, gate still must decide.
    # These are how a real regression hides: the word is present, the trigger is dead.
    (
        "pull_request lọc nhánh không tồn tại",
        True,
        {
            "test.yml": "name: t\non:\n  pull_request:\n    branches: [khong-ton-tai-branch]\njobs: {}\n"
        },
    ),
    (
        "pull_request types rỗng",
        True,
        {"test.yml": "name: t\non:\n  pull_request:\n    types: []\njobs: {}\n"},
    ),
    (
        "pull_request paths không bao giờ khớp",
        True,
        {
            "test.yml": "name: t\non:\n  pull_request:\n    paths: ['khong/ton/tai/**']\njobs: {}\n"
        },
    ),
    (
        "pull_request có, mọi job if push",
        True,
        {
            "test.yml": "name: t\non:\n  pull_request:\n  push:\n    branches: [main]\njobs:\n"
            "  a:\n    if: github.event_name == 'push'\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo hi\n"
        },
    ),
    (
        "pull_request_target thay vì pull_request",
        True,
        {"test.yml": "name: t\non:\n  pull_request_target:\njobs: {}\n"},
    ),
    # --- disappearance: the gate iterates files that EXIST.
    ("test.yml bị xoá hẳn", True, {"repo-guard.yml": VALID}),
    ("mọi workflow bị xoá", True, {}),
    # --- shapes that are legitimate and must stay GREEN (false-positive check)
    (
        "hợp lệ · inline có pull_request",
        False,
        {"test.yml": "name: t\non: [push, pull_request]\njobs: {}\n"},
    ),
    (
        "hợp lệ · khoá on có ngoặc kép",
        False,
        {"test.yml": 'name: t\n"on":\n  pull_request:\n  push:\njobs: {}\n'},
    ),
    ("hợp lệ · đuôi .yaml", False, {"test.yaml": VALID}),
    (
        "hợp lệ · flow mapping {pull_request: null}",
        False,
        {"test.yml": "name: t\non: {push: null, pull_request: null}\njobs: {}\n"},
    ),
]


def run_case(files: dict[str, str]) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "tests").mkdir()
        (root / ".github" / "workflows").mkdir(parents=True)
        shutil.copy(GATE, root / "tests" / GATE.name)
        for name, content in files.items():
            (root / ".github" / "workflows" / name).write_text(
                content, encoding="utf-8"
            )
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", f"tests/{GATE.name}", "-q"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout


def main() -> int:
    blind: list[str] = []
    noisy: list[str] = []
    print(f"cổng đang kiểm: {GATE}\n")
    for label, expect_red, files in CASES:
        code, out = run_case(files)
        red = code != 0
        if expect_red and not red:
            mark, verdict = "MÙ ", "XANH mà lẽ ra phải ĐỎ"
            blind.append(label)
        elif not expect_red and red:
            mark, verdict = "ỒN ", "ĐỎ mà lẽ ra phải XANH"
            noisy.append(label)
        else:
            mark, verdict = "ok  ", "ĐỎ" if red else "XANH"
        print(f"{mark}{label:44s} -> {verdict}")

    print(f"\nchỗ mù (bỏ lọt vi phạm): {len(blind)}")
    for b in blind:
        print(f"  - {b}")
    print(f"báo động giả (chặn bản hợp lệ): {len(noisy)}")
    for n in noisy:
        print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
