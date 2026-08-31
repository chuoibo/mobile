"""The bundle-tree gate must answer three states, and each half must be load bearing.

`scripts/check_tree_matches_main.py` exists because on 2026-08-31 at 03:20 a
bundle was exported from a checkout that did not match `origin/main`, published
to the demo box missing two whole screens, and every signal stayed green. The
gate is only worth having if it is red in exactly the situations that were
green that night, so these tests build real git repositories and put the gate in
front of them.

Two of these tests are mutants rather than assertions about behaviour. The gate
has two halves -- "is HEAD `origin/main`" and "is any tracked file dirty" -- and
the tempting reading of the incident is that the first half alone would have
caught it. It would not: a fast-forward lands exactly on main's SHA and leaves a
deleted file deleted. So each half is deleted in turn from a copy of the real
script, and the test asserts the copy goes GREEN on the case that half exists to
catch. A gate whose halves can be removed without any test noticing is a gate
that is already half gone.

The mutation is applied to the real source text and the anchor is required to
appear exactly once, because a mutation that silently patched nothing is a
mutation that reads as "the code is well guarded".
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "check_tree_matches_main.py"
WRAPPER = REPO_ROOT / "scripts" / "xuat_bundle.sh"

EXIT_KHOP = 0
EXIT_LECH = 1
EXIT_KHONG_KIEM_DUOC = 2

# The one line that decides the verdict. Both mutants cut a half out of it.
ANCHOR = "    off = head != ref_sha or bool(verdict.dirty)"

GIT_ID = [
    "-c",
    "user.email=test-khong-co-hom-thu",
    "-c",
    "user.name=test",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=main",
]


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(
        ["git", *GIT_ID, "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} hỏng: {done.stderr.strip()}")
    return done


def run_gate(tree: Path, *extra: str, script: Path | None = None):
    """Call the gate exactly as a person would, and return the completed process."""
    return subprocess.run(
        ["python3", str(script or GATE), "--tree", str(tree), "--no-fetch", *extra],
        capture_output=True,
        text=True,
        timeout=180,
    )


class TreeFixture:
    """An upstream repo plus clones of it, in a directory that cleans itself up."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="cong-bundle-test-")
        self.base = Path(self.tmp.name)
        self.upstream = self.base / "upstream"
        self.upstream.mkdir()
        git(self.upstream, "init", "--quiet")
        for n in range(5):
            (self.upstream / f"man{n}.tsx").write_text(f"export const Man{n} = 1;\n")
            git(self.upstream, "add", "-A")
            git(self.upstream, "commit", "--quiet", "-m", f"man {n}")

    def clone(self, name: str, back: int = 0) -> Path:
        work = self.base / name
        subprocess.run(
            ["git", *GIT_ID, "clone", "--quiet", str(self.upstream), str(work)],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        if back:
            git(work, "reset", "--hard", "--quiet", f"HEAD~{back}")
        return work

    def cay_0320(self) -> Path:
        """The incident tree: fast-forwarded onto main, still missing a file.

        This is built by actually running the command that was run that night,
        not by asserting what it does -- the whole point is that the command
        succeeds, so a fixture that faked the state would be testing a guess.
        """
        work = self.clone("cay-0320", back=4)
        (work / "man0.tsx").unlink()
        pull = subprocess.run(
            ["git", *GIT_ID, "-C", str(work), "pull", "-q", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert pull.returncode == 0, "tiền đề hỏng: pull đáng lẽ THÀNH CÔNG"
        assert (pull.stdout + pull.stderr) == "", "tiền đề hỏng: pull đáng lẽ IM LẶNG"
        return work

    def close(self) -> None:
        self.tmp.cleanup()


class BaTrangThai(unittest.TestCase):
    """KHỚP, LỆCH và KHÔNG KIỂM ĐƯỢC must be three answers, not two."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fx = TreeFixture()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fx.close()

    def test_cay_sach_dung_moc_la_khop(self) -> None:
        done = run_gate(self.fx.clone("sach"))
        self.assertEqual(done.returncode, EXIT_KHOP, done.stderr)
        self.assertIn("KHỚP", done.stdout)

    def test_cay_lui_bon_commit_la_lech_va_noi_ra_so_bon(self) -> None:
        done = run_gate(self.fx.clone("lui", back=4))
        self.assertEqual(done.returncode, EXIT_LECH)
        self.assertIn("LỆCH", done.stderr)
        self.assertIn("ĐỨNG SAU 4 commit", done.stderr)

    def test_ca_0320_head_bang_main_ma_van_lech(self) -> None:
        """HEAD is byte-identical to main and the tree is still wrong."""
        cay = self.fx.cay_0320()
        head = git(cay, "rev-parse", "HEAD").stdout.strip()
        ref = git(cay, "rev-parse", "origin/main").stdout.strip()
        self.assertEqual(head, ref, "tiền đề hỏng: HEAD phải bằng origin/main")

        done = run_gate(cay)
        self.assertEqual(done.returncode, EXIT_LECH, done.stdout)
        self.assertIn("LỆCH", done.stderr)
        self.assertIn("man0.tsx", done.stderr)

    def test_in_ra_sha_that_su_dung_de_doi_chieu(self) -> None:
        cay = self.fx.clone("in-sha")
        head = git(cay, "rev-parse", "HEAD").stdout.strip()
        done = run_gate(cay)
        self.assertIn(head, done.stdout, "cổng phải in SHA nó thật sự đã dùng")

    def test_khong_phai_git_la_hai_khong_phai_khong(self) -> None:
        """Could-not-run must never collapse into a pass."""
        khong = Path(self.fx.base) / "khong-phai-git"
        khong.mkdir()
        done = run_gate(khong)
        self.assertEqual(done.returncode, EXIT_KHONG_KIEM_DUOC, done.stdout)
        self.assertIn("KHÔNG KIỂM ĐƯỢC", done.stderr)

    def test_ref_khong_giai_duoc_la_hai(self) -> None:
        done = run_gate(self.fx.clone("ref-la"), "--ref", "origin/khong-ton-tai")
        self.assertEqual(done.returncode, EXIT_KHONG_KIEM_DUOC, done.stdout)

    def test_file_chua_theo_doi_cung_la_lech(self) -> None:
        """The bundler reads the disk, not the index."""
        cay = self.fx.clone("chua-theo-doi")
        (cay / "nhap.tsx").write_text("export const Nhap = 1;\n")
        self.assertEqual(run_gate(cay).returncode, EXIT_LECH)
        self.assertEqual(run_gate(cay, "--bo-qua-chua-theo-doi").returncode, EXIT_KHOP)


class SelftestCuaCong(unittest.TestCase):
    """The gate ships a --selftest; CI must run it, or it is decoration."""

    def test_selftest_xanh(self) -> None:
        done = subprocess.run(
            ["python3", str(GATE), "--selftest"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("selftest xanh", done.stdout)
        self.assertNotIn("SAI ", done.stdout)


class HaiNuaDeuCanNhau(unittest.TestCase):
    """Delete each half of the verdict and prove the gate goes green.

    If a mutant stays red, that half was not what catches the case and the
    argument in the docstring is wrong -- which is worth knowing.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.fx = TreeFixture()
        cls.source = GATE.read_text()
        if cls.source.count(ANCHOR) != 1:
            raise AssertionError(
                f"neo đột biến xuất hiện {cls.source.count(ANCHOR)} lần, phải đúng 1 — "
                "một neo trùng thì đột biến có thể vá nhầm bản sao"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fx.close()

    def _mutant(self, thay_bang: str) -> Path:
        """Write a copy of the real gate with one half of the verdict removed."""
        mutant = Path(self.fx.base) / f"dot-bien-{abs(hash(thay_bang))}.py"
        mutated = self.source.replace(ANCHOR, thay_bang)
        self.assertNotEqual(mutated, self.source, "đột biến không đổi gì — no-op")
        mutant.write_text(mutated)
        return mutant

    def test_bo_nua_file_ban_thi_ca_0320_thanh_xanh(self) -> None:
        cay = self.fx.cay_0320()
        self.assertEqual(
            run_gate(cay).returncode, EXIT_LECH, "nền phải ĐỎ trước khi đột biến"
        )
        mutant = self._mutant("    off = head != ref_sha")
        done = run_gate(cay, script=mutant)
        self.assertEqual(
            done.returncode,
            EXIT_KHOP,
            "bỏ nửa 'file bẩn' mà ca 03:20 vẫn đỏ — nghĩa là nửa đó không phải "
            "thứ bắt được nó, và lập luận trong docstring sai",
        )

    def test_bo_nua_head_thi_cay_lui_bon_commit_thanh_xanh(self) -> None:
        cay = self.fx.clone("lui-dot-bien", back=4)
        self.assertEqual(
            run_gate(cay).returncode, EXIT_LECH, "nền phải ĐỎ trước khi đột biến"
        )
        mutant = self._mutant("    off = bool(verdict.dirty)")
        done = run_gate(cay, script=mutant)
        self.assertEqual(
            done.returncode,
            EXIT_KHOP,
            "bỏ nửa 'HEAD' mà cây lùi 4 commit vẫn đỏ — nửa đó không phải thứ bắt được nó",
        )


class CongChayTruocKhiXuat(unittest.TestCase):
    """A gate with no caller is a gate nobody runs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fx = TreeFixture()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fx.close()

    def test_makefile_co_muc_goi_cong(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text()
        self.assertIn("bundle-check:", makefile)
        self.assertIn("bundle:", makefile)
        self.assertIn("check_tree_matches_main.py", makefile)
        self.assertIn("xuat_bundle.sh", makefile)
        # Both targets must be .PHONY: there is a file named `bundle` the
        # moment somebody exports into ./bundle, and make would then decide
        # the target is up to date and skip the check entirely.
        phony = [ln for ln in makefile.splitlines() if ln.startswith(".PHONY:")]
        self.assertTrue(phony, "Makefile không có dòng .PHONY nào")
        declared = " ".join(phony).split()
        self.assertIn("bundle-check", declared)
        self.assertIn("bundle", declared)

    def test_wrapper_dung_truoc_khi_goi_expo(self) -> None:
        """A LỆCH tree must stop the wrapper before `expo export` is reached.

        Asserted by the exit code AND by the absence of the export banner: if
        the wrapper printed step 2 it had already moved past the gate, and a
        check that runs after the thing it guards is not a gate.
        """
        cay = self.fx.cay_0320()
        done = subprocess.run(
            [str(WRAPPER), "--tree", str(cay), "--no-fetch"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(done.returncode, EXIT_LECH, done.stdout + done.stderr)
        self.assertIn("DỪNG", done.stderr)
        self.assertNotIn("2/3", done.stdout, "cổng phải chặn TRƯỚC bước export")

    def test_wrapper_khong_kiem_duoc_cung_dung(self) -> None:
        khong = Path(self.fx.base) / "khong-git"
        khong.mkdir()
        done = subprocess.run(
            [str(WRAPPER), "--tree", str(khong), "--no-fetch"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(done.returncode, EXIT_KHONG_KIEM_DUOC, done.stdout)
        self.assertNotIn("2/3", done.stdout)


if __name__ == "__main__":
    unittest.main()
