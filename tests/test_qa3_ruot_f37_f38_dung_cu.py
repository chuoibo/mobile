"""The F37/F38 toolkit has to keep being able to tell a working reel from a dead one.

PR #490 shipped `do-grounding-reel.py` and hung an F37 conclusion on two lines it
printed. qa-tt-0003 pointed the instrument at six stub reels whose behaviour was
known in advance and found that three switched-OFF reels and two OBEYED ones all
produced `grounding: 5/5 · injection: 5/5 · exit 0` -- the same signature as a
healthy run. Both properties were `all()` over `picks`, and `all([])` is True, so
the numbers peaked exactly when there was no answer to measure.

That class of defect does not announce itself: the instrument stays green while
losing the ability to discriminate. So the discrimination itself is gated here
rather than left to whoever next reads the script.

These tests run no server, no database, no model and no browser. Everything
below is either a pure function, a stub on a loopback port, or a file on disk.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
BO = REPO / "tests" / "qa" / "qa3-123758-ruot-f37-f38"
BAO_CAO = REPO / "docs" / "claude" / "2026-08-31" / "qa3-123758-ruot-f37-f38.md"


def chay(*lenh, **kw):
    return subprocess.run(lenh, capture_output=True, text=True, timeout=300, **kw)


class DungCuPhanBietDuoc(unittest.TestCase):
    """The instruments must fail when pointed at something broken."""

    def test_do_grounding_reel_phan_biet_duoc_tam_ca(self):
        """Eight known reels, eight expected verdicts -- including both controls.

        `tu-kiem-6-ca.py` carries a POSITIVE control (`khoe`, must be green) as
        well as the dirty ones. Without it a script wired to `exit 1` would score
        every red row correct, and this test would pass while the instrument
        rejected healthy reels too.
        """
        r = chay(sys.executable, str(BO / "tu-kiem-6-ca.py"))
        self.assertEqual(
            r.returncode, 0, f"tu-kiem-6-ca.py đỏ:\n{r.stdout}\n{r.stderr}"
        )
        self.assertIn("DAT 8/8", r.stdout)

    def test_ban_cu_cua_dung_cu_khong_qua_duoc_tu_kiem(self):
        """The self-check must actually be able to fail.

        A green self-check proves nothing unless the version it was written to
        catch comes out red. The pre-fix instrument is reconstructed from git and
        fed to the same checker; if it passes, the checker has stopped checking.
        """
        cu = chay(
            "git",
            "-C",
            str(REPO),
            "show",
            "f18cbeb:tests/qa/qa3-123758-ruot-f37-f38/do-grounding-reel.py",
        )
        if cu.returncode != 0:
            self.skipTest("không có commit f18cbeb trong clone này (clone nông?)")
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "cu.py"
            p.write_text(cu.stdout, encoding="utf-8")
            r = chay(sys.executable, str(BO / "tu-kiem-6-ca.py"), str(p))
        self.assertEqual(
            r.returncode,
            1,
            "bản TRƯỚC KHI SỬA lẽ ra phải trượt bài tự kiểm này, nhưng nó qua:\n"
            + r.stdout,
        )
        # The exact lie the fix removes: a fraction at full marks on a reel that
        # never built.
        self.assertIn("VAN IN 'grounding: 5/5'", r.stdout)

    def test_bang_ground_reel_dung_lai_duoc(self):
        """The five-row grounding table in the report has a script behind it."""
        r = chay(sys.executable, str(BO / "do-ground-reel.py"))
        self.assertEqual(
            r.returncode, 0, f"do-ground-reel.py đỏ:\n{r.stdout}\n{r.stderr}"
        )
        self.assertIn("ĐẠT 5/5 hàng", r.stdout)


class KhoaKhongPhuThuocDoSau(unittest.TestCase):
    """`dung-stack.sh` must find the key from any depth, and refuse without it."""

    def test_khong_con_duong_dan_ba_tang(self):
        """The old three-level path must be gone from the CODE.

        Checked against comment-stripped lines on purpose: the fix's own comment
        quotes `../../../mobile/.env` to explain what was wrong with it, and a
        grep over the raw file reads that explanation as the defect it describes.
        A gate that cannot tell code from prose about code fails on documentation.
        """
        goc = (BO / "dung-stack.sh").read_text(encoding="utf-8")
        ma = "\n".join(d for d in goc.splitlines() if not d.lstrip().startswith("#"))
        self.assertNotIn(
            "../../../mobile/.env",
            ma,
            "vẫn còn đường dẫn ba tầng — chỉ giải đúng khi cây nằm cạnh mobile/",
        )
        self.assertIn("--git-common-dir", ma)

    def test_tu_choi_chay_khi_vang_khoa(self):
        """Copied outside any git repo and with no .env, it must exit 3.

        Placed before the container starts on purpose, so this costs no docker.
        A keyless run is the dangerous one: the reel route answers
        `reeled=false reason=unavailable`, which reads as "nothing wrong".
        """
        with tempfile.TemporaryDirectory() as d:
            gia = pathlib.Path(d) / "tests" / "qa" / "bo"
            gia.mkdir(parents=True)
            shutil.copy(BO / "dung-stack.sh", gia / "dung-stack.sh")
            moi = {
                k: v
                for k, v in os.environ.items()
                if k not in ("GEMINI_API_KEY", "MOBILE_ENV_FILE")
            }
            r = subprocess.run(
                ["bash", str(gia / "dung-stack.sh"), str(pathlib.Path(d) / "out")],
                capture_output=True,
                text=True,
                timeout=120,
                env=moi,
                cwd=d,
            )
        self.assertEqual(
            r.returncode, 3, f"lẽ ra phải TỪ CHỐI:\n{r.stdout}\n{r.stderr}"
        )
        self.assertIn("DỪNG: không tìm thấy GEMINI_API_KEY", r.stderr)
        # Whatever it prints, it must never print the key itself.
        self.assertNotIn("AIza", r.stdout + r.stderr)


class ChayLaiDuoc(unittest.TestCase):
    """The rerun instructions must be runnable by someone who was not here."""

    PLANS = ("plan-f38-widget.json", "plan-f37-thuoc-phim.json")

    def test_plan_da_duoc_commit_va_doc_duoc(self):
        """`di-bo.mjs` exits 2 without a plan file, so a missing plan is a dead block."""
        for ten in self.PLANS:
            p = BO / ten
            self.assertTrue(p.is_file(), f"thiếu {ten}")
            buoc = json.loads(p.read_text(encoding="utf-8"))
            self.assertGreater(len(buoc), 0)
            for b in buoc:
                self.assertTrue(
                    b.get("ten") or b.get("chu") or b.get("hash"),
                    f"bước không nêu thứ để bấm: {b}",
                )

    def test_moi_nhan_trong_plan_co_that_trong_ma_nguon_client(self):
        """A plan naming a control that no longer exists is a plan that cannot run.

        This does not prove the press SEQUENCE still works -- only a browser can
        say that. It proves every name in the plan is still a string the client
        ships, which is the failure mode a rename causes and the one a reader
        cannot see by eye.
        """
        goc_client = REPO / "apps" / "mobile" / "src"
        if not goc_client.is_dir():
            self.skipTest("apps/mobile không có trong cây này")
        nguon = "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in goc_client.rglob("*")
            if p.suffix in (".ts", ".tsx") and p.is_file()
        )
        # A `chu` step presses on-screen TEXT, which may be server data rather
        # than a client literal -- `Chuyến thử ruột` is a trip title `nem-anh.py`
        # writes at run time. Those are checked against the toolkit that creates
        # them; only role+name controls are checked against the client.
        du_lieu = "\n".join(p.read_text(encoding="utf-8") for p in BO.glob("*.py"))
        thieu = []
        for ten in self.PLANS:
            for b in json.loads((BO / ten).read_text(encoding="utf-8")):
                if b.get("ten"):
                    # `Vào app với tư cách Minh` is built as a template from the
                    # person's name; match the part the client actually spells.
                    nhan = b["ten"]
                    moc = (
                        "Vào app với tư cách"
                        if nhan.startswith("Vào app với tư cách")
                        else nhan
                    )
                    if moc not in nguon:
                        thieu.append(f"{ten}: nút {nhan!r} không còn trong client")
                elif b.get("chu") and b["chu"] not in du_lieu:
                    thieu.append(
                        f"{ten}: chữ {b['chu']!r} không do bộ công cụ này tạo ra — "
                        "không ai biết nó tới từ đâu"
                    )
        self.assertEqual(
            thieu, [], "nhãn trong plan không còn khớp nguồn của nó: " + str(thieu)
        )

    def test_khoi_chay_lai_khong_con_cho_trong(self):
        """No `<placeholder>` may survive in the rerun block.

        Five blanks (`<ctx> <minh-id> <outing> <ids-csv> <plan.json>`) meant the
        block could not be pasted by anyone who had not already done the run.
        """
        if not BAO_CAO.is_file():
            self.skipTest("không có báo cáo trong cây này")
        van = BAO_CAO.read_text(encoding="utf-8")
        khoi = van[van.index("## Chạy lại") :]
        cho_trong = re.findall(r"<[a-z][a-z0-9._-]*>", khoi)
        self.assertEqual(cho_trong, [], f"khối Chạy lại còn chỗ trống: {cho_trong}")


if __name__ == "__main__":
    unittest.main()
