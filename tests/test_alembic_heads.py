"""Cổng chặn nhánh alembic đôi phải cắn, và phải cắn trên chính cây này.

Cổng đã tồn tại từ `635a40f` nhưng chỉ được gọi từ `.github/workflows/
repo-guard.yml`, và workflow đó đang chết ở giây thứ ba vì Actions vượt hạn
mức. Nghĩa là cho tới file này, cổng **chưa chạy lần nào** — không phải "chạy và
xanh", mà là chưa từng được thực thi. Đặt ở `tests/` để nó nằm trong lệnh cổng
chuẩn `python3 -m pytest services/api/tests tests -q`, thứ chạy được trên máy
mà không cần Actions, không cần database, không cần cài alembic.

Hai nửa đều chịu lực, giống cổng ruff:

- `test_cay_that_chi_co_mot_head` là **chính cái cổng**. Nó đỏ vào đúng ngày ai
  đó mở nhánh migration thứ hai, và đó là lý do duy nhất cổng này tồn tại.
- Các ca dựng cây giả chứng minh cổng **biết đỏ**. Một cổng chỉ từng xanh không
  phân biệt được với một cổng hỏng — repo này đã đếm được năm cổng như thế
  trong một buổi.

Mọi ca đều gọi script thật qua subprocess, đọc mã thoát thật, chứ không import
rồi so sánh một bản sao của phép tính head với chính nó. Mã thoát là thứ hook
và CI thực sự đọc, nên mã thoát là thứ phải được test.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD = REPO_ROOT / "scripts" / "check_alembic_heads.py"
REAL_VERSIONS = (
    REPO_ROOT / "services" / "api" / "app" / "db" / "migrations" / "versions"
)


def _render_down(down: object) -> str:
    if down is None:
        return "None"
    if isinstance(down, str):
        return f'"{down}"'
    inner = ", ".join(f'"{x}"' for x in down)  # type: ignore[union-attr]
    return f"({inner},)" if len(down) == 1 else f"({inner})"  # type: ignore[arg-type]


def migration(revision: str, down: object, *, annotated: bool = True) -> str:
    """One alembic version file, shaped like the ones in this repository.

    `annotated` switches between the two assignment forms that actually appear
    in `services/api/app/db/migrations/versions`. Both must parse: a form the
    guard cannot read drops that file out of the graph entirely, and a dropped
    file is how a fork would go unseen.
    """
    if annotated:
        head = (
            f'revision: str = "{revision}"\n'
            f"down_revision: str | Sequence[str] | None = {_render_down(down)}\n"
        )
    else:
        head = (
            f'revision = "{revision}"\ndown_revision = {_render_down(down)}\n'
        )
    return f'"""{revision}: mot buoc migration gia."""\n\n{head}'


class AlembicHeadGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.versions = Path(tempfile.mkdtemp(prefix="alembic-heads-"))
        self.addCleanup(shutil.rmtree, self.versions, ignore_errors=True)

    def write(self, name: str, body: str) -> None:
        (self.versions / name).write_text(body, encoding="utf-8")

    def run_guard(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GUARD), *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def run_on_temp(self) -> subprocess.CompletedProcess:
        return self.run_guard(str(self.versions))

    # -- the gate itself ------------------------------------------------

    def test_cay_that_chi_co_mot_head(self) -> None:
        """The real migration tree, checked by the real entry point, no args."""
        result = self.run_guard()
        self.assertEqual(
            result.returncode,
            0,
            f"cay migration that co nhanh doi:\n{result.stdout}{result.stderr}",
        )
        self.assertIn("mot head duy nhat", result.stdout)

    def test_cay_that_co_migration_de_doc(self) -> None:
        """A guard that reads zero files would pass every fork ever pushed.

        The parse step is the guard's single point of silent failure: change the
        assignment shape it recognises and the graph empties, at which point
        "no heads to disagree" reads exactly like "one head".
        """
        self.assertTrue(REAL_VERSIONS.is_dir(), REAL_VERSIONS)
        count = len(list(REAL_VERSIONS.glob("*.py")))
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        # Whatever the guard is reading, it has to be the whole directory.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            from check_alembic_heads import doc_migrations
        finally:
            sys.path.pop(0)
        self.assertEqual(len(doc_migrations(REAL_VERSIONS)), count)

    # -- it knows how to go red ------------------------------------------

    def test_nhanh_doi_bi_tu_choi(self) -> None:
        self.write("0001_goc.py", migration("0001", None))
        self.write("0002_nhanh_a.py", migration("0002a", "0001"))
        self.write("0003_nhanh_b.py", migration("0003b", "0001"))

        result = self.run_on_temp()

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("2 head", result.stderr)
        # Both heads named, with their files: the message has to be actionable
        # without opening the directory.
        self.assertIn("0002a", result.stderr)
        self.assertIn("0003b", result.stderr)
        self.assertIn("0002_nhanh_a.py", result.stderr)
        self.assertIn("0003_nhanh_b.py", result.stderr)

    def test_nhanh_doi_viet_bang_gan_thuong_van_bi_tu_choi(self) -> None:
        """The un-annotated form parses too, so a fork cannot hide in it."""
        self.write("0001_goc.py", migration("0001", None, annotated=False))
        self.write("0002_a.py", migration("0002a", "0001", annotated=False))
        self.write("0003_b.py", migration("0003b", "0001", annotated=False))

        result = self.run_on_temp()

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("2 head", result.stderr)

    def test_nhanh_doi_o_giua_chuoi_dai_van_bi_bat(self) -> None:
        """The fork that actually happened was not at the tip of a short chain."""
        self.write("0001.py", migration("0001", None))
        self.write("0002.py", migration("0002", "0001"))
        self.write("0003.py", migration("0003", "0002"))
        self.write("0004_a.py", migration("0004a", "0003"))
        self.write("0004_b.py", migration("0004b", "0003"))
        self.write("0005_a.py", migration("0005a", "0004a"))

        result = self.run_on_temp()

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("0005a", result.stderr)
        self.assertIn("0004b", result.stderr)

    def test_ba_head_deu_duoc_goi_ten(self) -> None:
        self.write("0001.py", migration("0001", None))
        for name in ("a", "b", "c"):
            self.write(f"0002_{name}.py", migration(f"0002{name}", "0001"))

        result = self.run_on_temp()

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("3 head", result.stderr)
        for name in ("a", "b", "c"):
            self.assertIn(f"0002{name}", result.stderr)

    # -- and how to stay quiet -------------------------------------------

    def test_chuoi_thang_duoc_chap_nhan(self) -> None:
        self.write("0001.py", migration("0001", None))
        self.write("0002.py", migration("0002", "0001"))
        self.write("0003.py", migration("0003", "0002"))

        result = self.run_on_temp()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0003", result.stdout)

    def test_merge_revision_noi_lai_nhanh_doi(self) -> None:
        """A tuple `down_revision` is the supported way back to one head."""
        self.write("0001.py", migration("0001", None))
        self.write("0002_a.py", migration("0002a", "0001"))
        self.write("0002_b.py", migration("0002b", "0001"))
        self.write("0003_merge.py", migration("0003", ("0002a", "0002b")))

        result = self.run_on_temp()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0003", result.stdout)

    # -- it refuses to be green for the wrong reason ----------------------

    def test_thu_muc_rong_bi_tu_choi(self) -> None:
        """Zero migrations is not one head, and must not be reported as one.

        This is the shape every dead gate in this repository has had: nothing to
        check, so nothing to complain about, so green.
        """
        result = self.run_on_temp()

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("khong co migration nao", result.stderr)

    def test_thu_muc_khong_ton_tai_bi_tu_choi(self) -> None:
        result = self.run_guard(str(self.versions / "khong-he-co"))

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("khong thay", result.stderr)

    def test_doc_lai_file_sau_khi_sua_chu_khong_doc_pycache(self) -> None:
        """Regression: the first version of this guard answered from `.pyc`.

        It imported each version module, so a second run after an edit reported
        the value cached in `__pycache__` -- including a green on a tree that
        had just been forked. Run, edit, run again: the second answer has to be
        about the file as it is now.
        """
        self.write("0001.py", migration("0001", None))
        self.write("0002.py", migration("0002", "0001"))
        self.write("0003.py", migration("0003", "0002"))
        self.assertEqual(self.run_on_temp().returncode, 0)

        # Repoint the tip at the root: same files, now a fork.
        self.write("0003.py", migration("0003", "0001"))
        result = self.run_on_temp()

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("2 head", result.stderr)


if __name__ == "__main__":
    unittest.main()
