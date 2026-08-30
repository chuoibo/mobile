"""There are two local ruff verdicts in this repo, and only one of them is pinned.

## What was measured

PR #246 makes `scripts/ruff_changed.sh` resolve the ruff that
`services/api/requirements-dev.txt` names, instead of taking whatever `ruff` is
first on PATH. The hole it closes is real and reproducible on this machine:

    ruff 0.9.2   (the pin, what CI installs)    31 findings over 322 tracked .py
    ruff 0.15.15 (this machine's PATH)          30

    seen only by the pin:
      services/api/app/domain/place_search.py:105:39: UP038

`tests/test_qa_scripts_are_ruff_formatted.py` is the *other* local ruff verdict
-- the ratchet that stops a new unformatted file under `tests/qa/` from reaching
main. It still calls bare `ruff` (`shutil.which("ruff")` at its `setUp`, and
`["ruff", "format", "--check", ...]` in `ruff_rejects_format`). So after #246 the
repository has one pinned ruff verdict and one PATH-dependent one, and nothing
says so out loud.

## Why this is a stake and not a bug report

Measured on the merged tree, both versions name the *same* 16 files under
`tests/qa/` as needing a reformat -- the sets are byte-identical, not merely the
same size. The second path is therefore latent today, not live: there is no file
whose ratchet verdict currently depends on which ruff answered.

That is a fact about today's tree and not a guarantee, which is exactly what
#246's own description says about the formatter half. `ruff format` output does
change between releases; the day it changes for a file under `tests/qa/`, the
ratchet starts giving a local verdict from a binary CI never runs -- the defect
#246 removed, one file over.

## Status: closed

This case was filed `xfail(strict=True)` rather than red, following
`tests/test_gate_ruff_skip_hides_pin_check.py`: a stake driven where the gap is,
which turns into a failure the moment somebody closes it and forgets to remove
the marker. Closing it was a `scripts/` change and `scripts/` is not QA's to edit.

DevOps closed it (#257): the ratchet now resolves its binary through
`scripts/ruff_pinned.sh`. The marker came off in the same change, because the
stake did its job -- on the merged tree the case reported XPASS(strict), which
is a failure, so shipping the fix without removing the marker would have turned
main red. That is the whole point of `strict`, and it worked as designed.

The case stays, unmarked, as a live guard: it now fails if the ratchet ever goes
back to trusting PATH.

## How it discriminates, and why not by reading the source

Asserting "the file contains the string ruff_pinned.sh" would pass on a version
that mentions the resolver in a comment and still shells out to PATH -- this repo
has already shipped a gate that read source text while the behaviour underneath
it was gone. So the probe is behavioural: put a ruff on PATH that reports a
version which is *not* the pin and rejects every file, then ask the ratchet's own
helper about a file that is properly formatted.

  - A PATH-dependent verdict uses the shim and answers "needs reformatting".
  - A pinned verdict rejects the shim on its version and answers "clean".

The shim reports `9.9.9` deliberately. A shim claiming to *be* the pin is
accepted by any version check, `scripts/ruff_pinned.sh` included -- that boundary
is measured in `doi-chung-246.sh` and is not what this case is about.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RATCHET = REPO_ROOT / "tests" / "test_qa_scripts_are_ruff_formatted.py"

# Formatted by ruff 0.9.2 and by ruff 0.15.15 alike -- checked both ways, since a
# source file that either version wants to rewrite would make this case red for
# the wrong reason and read exactly like the finding it is meant to pin.
DA_DINH_DANG = "x = 1\nprint(x)\n"


def _shim_ruff(directory: Path) -> None:
    """Write a `ruff` that is not the pin and rejects everything it is shown."""
    shim = directory / "ruff"
    shim.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            if [ "$1" = "--version" ]; then echo "ruff 9.9.9"; exit 0; fi
            echo "Would reformat: $*"
            exit 1
            """
        ),
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)


def _load_ratchet():
    spec = importlib.util.spec_from_file_location("ratchet_duoi_kiem", RATCHET)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DuongPhanQuyetRuffThuHai(unittest.TestCase):
    def test_shim_that_khong_the_voi_toi(self) -> None:
        """Run first, so the two failure shapes cannot be confused.

        "the gate ignored the shim" and "the shim never made it onto PATH" read
        identically from a green line, and this repo has already once reported
        the second as if it were the first.
        """
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _shim_ruff(bin_dir)
            env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
            found = shutil.which("ruff", path=env["PATH"])
            self.assertEqual(
                found,
                str(bin_dir / "ruff"),
                "shim không đứng đầu PATH -- mọi kết luận dưới đây vô nghĩa",
            )
            version = subprocess.run(
                [found, "--version"], capture_output=True, text=True, timeout=60
            )
            self.assertEqual(version.stdout.strip(), "ruff 9.9.9")

    def test_file_moi_da_dinh_dang_duoc_ban_ghim_chap_nhan(self) -> None:
        """The fixture is clean under the pin, so red below means the shim.

        Without this, a fixture that the pinned ruff happens to dislike would
        make the case below red while proving nothing about which binary answered.

        Asks the pin, not PATH. When this was written the ratchet judged with
        PATH's ruff, so controlling with PATH's ruff was controlling with the
        binary under test; now that the ratchet resolves the pin, PATH's answer
        is about a binary that no longer renders the verdict below -- a control
        against the wrong subject, which controls for nothing.

        Resolved directly rather than through the ratchet's own `pinned_ruff()`,
        so a bug in the ratchet's resolver cannot make its control agree with it.
        """
        resolved = subprocess.run(
            [str(REPO_ROOT / "scripts" / "ruff_pinned.sh")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        ruff = resolved.stdout.strip()
        self.assertEqual(
            (resolved.returncode, bool(ruff)),
            (0, True),
            f"không phân giải được ruff ghim: {resolved.stderr.strip()}",
        )
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "sach.py"
            probe.write_text(DA_DINH_DANG, encoding="utf-8")
            result = subprocess.run(
                [ruff, "format", "--check", "--no-cache", "--", str(probe)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"fixture không sạch với {ruff}: {result.stdout}{result.stderr}",
            )

    # The xfail(strict=True) marker that stood here is gone -- this is a live
    # guard now, following tests/test_gate_ruff_skip_hides_pin_check.py. The
    # ratchet resolves through scripts/ruff_pinned.sh as of the change that
    # removed this marker, so the case passes on its own merit; leaving the
    # marker would have turned that into XPASS(strict) -> failure, which is
    # exactly the tripwire it was placed to be.
    def test_cong_ratchet_khong_doi_phan_quyet_khi_path_co_ruff_la(self) -> None:
        ratchet = _load_ratchet()
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _shim_ruff(bin_dir)
            probe = Path(tmp) / "sach.py"
            probe.write_text(DA_DINH_DANG, encoding="utf-8")

            truoc = os.environ["PATH"]
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{truoc}"
            try:
                bi_tu_choi = ratchet.ruff_rejects_format(probe)
            finally:
                os.environ["PATH"] = truoc

        self.assertFalse(
            bi_tu_choi,
            "một ruff lạ trên PATH đổi được phán quyết của cổng ratchet -- "
            "phán quyết đó không phải phán quyết của CI",
        )


if __name__ == "__main__":
    unittest.main()
