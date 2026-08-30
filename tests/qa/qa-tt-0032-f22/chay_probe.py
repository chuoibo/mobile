"""Chép `probe_bam_hai_lan.py` vào tầng postgres, chạy, rồi dọn sạch.

Probe cần fixture `postgres_session` của `services/api/tests/postgres/conftest.py`
và một relative import tới file test của chính PR, nên nó phải đứng trong package
đó lúc chạy. QA không sở hữu `services/api/`, nên file không được để lại ở đó:
chép vào, chạy, xoá — kể cả khi pytest đỏ.

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://...' \\
        python3 tests/qa/qa-tt-0032-f22/chay_probe.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
PROBE = HERE / "probe_bam_hai_lan.py"
TARGET = API_ROOT / "tests" / "postgres" / "test_qa0032_probe_bam_hai_lan.py"


def main() -> int:
    if TARGET.exists():
        print(f"TỪ CHỐI: {TARGET} đã tồn tại — một lượt trước chưa dọn.")
        return 2

    env = dict(os.environ)
    env.setdefault(
        "MOBILE_TEST_DATABASE_URL",
        "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile",
    )
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"

    shutil.copyfile(PROBE, TARGET)
    try:
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(TARGET.relative_to(API_ROOT)),
                "-q",
                "-s",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:randomly",
            ],
            cwd=API_ROOT,
            env=env,
        )
    finally:
        TARGET.unlink(missing_ok=True)
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())
