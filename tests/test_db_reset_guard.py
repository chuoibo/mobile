"""`make db-reset` must destroy the ledger and nothing else.

The command exists to break a coupling: `make clean` removes both named volumes,
so "give me an empty ledger" used to also mean "throw away every uploaded bill".
That makes two failure modes worth a test, and they fail in opposite directions:

  * Too eager -- it also takes the photos. Then it is `clean` with a friendlier
    name, and the coupling it was written to break is still there.
  * Too quiet -- it removes nothing and exits 0. Then the operator believes the
    machine is clean while every old row still answers, which is worse than an
    error because nobody goes looking.

The refusal paths run here for real, as a subprocess, with no Docker: the script
checks its arguments before it touches a daemon. The Docker-dependent path is
marked and skipped when there is no daemon, and a skip is recorded as a skip --
this file never reports a green it did not earn.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "reset_demo_db.sh"
MAKEFILE = REPO_ROOT / "Makefile"


def run(**env_overrides: str) -> subprocess.CompletedProcess[str]:
    """Run the script with a deliberately minimal environment."""
    import os

    env = dict(os.environ)
    env.pop("PROJECT", None)
    env.pop("CONFIRM", None)
    env.update(env_overrides)
    return subprocess.run(
        ["sh", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def executable_lines(path: Path) -> str:
    """Source with `#` comments and blank lines removed.

    Grepping the whole file would be a test that passes on prose. This script's
    own comments explain *why* it avoids `down -v`, and they quote the flag to
    do it -- so a full-text search for the dangerous form matches the sentence
    warning against it. Strip the commentary and ask only what the shell runs.
    """
    kept = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        kept.append(line)
    return "\n".join(kept)


def test_script_exists_and_is_shell() -> None:
    assert SCRIPT.exists(), f"thiếu {SCRIPT}"
    assert SCRIPT.read_text(encoding="utf-8").startswith("#!/bin/sh")


def test_refuses_empty_project() -> None:
    """No project name means the volume name points at nothing."""
    result = run(PROJECT="", CONFIRM="")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "PROJECT rỗng" in result.stderr


def test_refuses_when_confirm_missing() -> None:
    result = run(PROJECT="khong-ton-tai-abc")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Từ chối" in result.stderr
    # The refusal has to name both volumes and say which way each one goes.
    # An operator who cannot tell this apart from `clean` will reach for
    # `clean`, and that is the command that costs the photos.
    assert "mobile-postgres-data" in result.stderr
    assert "mobile-media-data" in result.stderr


def test_refuses_when_confirm_names_a_different_project() -> None:
    """Typing *a* project name is not typing *this* project's name.

    The dangerous shape is a machine with several stacks, an operator holding a
    confirmation string in muscle memory from the last one, and a command that
    accepts any non-empty answer.
    """
    result = run(PROJECT="du-an-a", CONFIRM="du-an-b")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Từ chối" in result.stderr


def test_never_runs_down_with_volumes_flag() -> None:
    """`down -v` is exactly the command this script exists to not be."""
    code = executable_lines(SCRIPT)
    assert "docker compose" in code, "test đang đọc nhầm file"
    for dangerous in ("down -v", "down --volumes", "-v down"):
        assert dangerous not in code, (
            f"script chạy '{dangerous}' — lệnh đó lấy CẢ volume ảnh, "
            "tức là nó đã trở thành `make clean` dưới một cái tên hiền hơn"
        )


def test_removes_the_ledger_volume_by_name_not_by_wildcard() -> None:
    code = executable_lines(SCRIPT)
    assert 'docker volume rm "$LEDGER_VOL"' in code
    # The media volume name may be READ (to prove it survived) but must never
    # appear as an argument to a removal.
    assert not re.search(r"volume\s+rm\b[^\n]*MEDIA_VOL", code)


def test_verifies_media_volume_survived() -> None:
    """Existence alone does not prove the photos are there.

    A deleted-then-recreated volume wears the same name and is empty. The
    script compares CreatedAt across the teardown to tell those apart, so that
    comparison has to actually be in the code.
    """
    code = executable_lines(SCRIPT)
    assert "MEDIA_BEFORE" in code and "MEDIA_AFTER" in code
    assert '"$MEDIA_AFTER" != "$MEDIA_BEFORE"' in code


def test_makefile_does_not_hardcode_the_confirmation() -> None:
    """A confirmation the recipe fills in for you is decoration, not a gate.

    `CONFIRM='$(PROJECT)'` in the recipe would satisfy the check on every run
    and the operator would never be asked anything.
    """
    src = MAKEFILE.read_text(encoding="utf-8")
    recipe = re.search(r"^db-reset:.*?(?=\n\w|\n\n\w|\Z)", src, re.S | re.M)
    assert recipe is not None, "không tìm thấy target db-reset trong Makefile"
    body = recipe.group(0)
    assert "reset_demo_db.sh" in body
    assert "CONFIRM='$(CONFIRM)'" in body, (
        "recipe phải chuyển tiếp CONFIRM của người gõ, không tự điền"
    )
    assert "CONFIRM='$(PROJECT)'" not in body


def test_makefile_declares_the_target_phony() -> None:
    src = MAKEFILE.read_text(encoding="utf-8")
    phony = re.search(r"^\.PHONY:\s*(.*)$", src, re.M)
    assert phony is not None
    assert "db-reset" in phony.group(1).split()


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="cần docker: đường này hỏi daemon xem volume có tồn tại không",
)
def test_refuses_when_the_ledger_volume_does_not_exist() -> None:
    """A missing volume is an abort, not a shrug.

    `docker volume rm` on a name nothing matches is the quiet failure this
    guards: it would tear the stack down, remove nothing, bring it back up on
    the untouched old ledger, and print no complaint.
    """
    name = "du-an-khong-bao-gio-ton-tai-9f3a"
    result = run(PROJECT=name, CONFIRM=name)
    if result.returncode == 0:
        pytest.fail(f"đáng lẽ phải từ chối:\n{result.stdout}\n{result.stderr}")
    combined = result.stdout + result.stderr
    if "Cannot connect to the Docker daemon" in combined:
        pytest.skip("docker có trên PATH nhưng daemon không chạy")
    assert f"không có volume nào tên '{name}_mobile-postgres-data'" in result.stderr
    # And it must not have torn anything down on the way to finding out.
    assert "tắt project" not in result.stdout
