"""Bộ dò "ca test có đọc ra ngoài repo không" phải đỏ được, và phải từ chối được.

Cổng `gate.sh suite-in-repo` trả lời câu hỏi mà hai lần trước ta trả lời sai:
phán quyết của bộ chặn có phải hàm của repo không. QA chặn #487 vì nó không
phải — cùng SHA, cách 13 phút, `1 failed` rồi `0 failed`. Bản vá lần đó quét lại
cả bộ và kết luận "đúng một file", nhưng quét theo hướng cây-ngoài-repo BIẾN MẤT,
mà cây biến mất chỉ làm ca test BỎ QUA. Hướng giết là cây CÒN ĐÓ và KHÁC ĐI.

Đo 31/08 trên `tests/test_harness_selfcheck.py`, file mà lượt quét đó đã tha:

    ~/agent-harness như hôm nay              43 passed
    cùng cây + ĐÚNG MỘT file test mới        1 failed, 36 passed, 6 skipped

Nên bộ dò này không đoán "cây lạ trông thế nào" nữa. Nó gắn `sys.addaudithook`
vào tiến trình pytest và ghi lại mọi đường TUYỆT ĐỐI nằm ngoài cây làm việc mà
từng ca chạm tới. Một ca không chạm ra ngoài thì không thể bị cái ngoài lay
chuyển.

Những ca dưới đây đo chính bộ dò đó, trên các dự án pytest tí hon dựng trong
`tmp_path` — nên chúng không lặp lại lỗi mà chúng đang gác.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_suite_stays_in_repo.py"

# Ca sạch: chỉ đụng file trong chính cây của nó.
CA_SACH = """def test_khong_cham_ra_ngoai():
    assert 1 + 1 == 2
"""

# Ca đọc ra ngoài. `Path.home()` là đường ngắn nhất tới "ngoài repo" và cũng
# đúng hình dạng đã cắn repo này hai lần.
CA_DOC_NGOAI = """import os
from pathlib import Path


def test_cham_vao_home():
    os.scandir(str(Path.home())).close()
    assert True
"""

# Cùng hành vi, nhưng gói sau một bí danh cục bộ. Đây là ca phân biệt bộ dò
# hành-vi với một lượt grep: `grep Path.home()` vẫn thấy dòng này, nhưng
# `grep` cho `AGENT_HARNESS` thì không, và cổng AST của repo này đã từng mù
# đúng kiểu đó với `def now(): return time.time()`.
CA_DOC_NGOAI_QUA_BI_DANH = """import os
from pathlib import Path


def _o_dau():
    return Path(os.sep.join([str(Path.home()), ".config"])).parent


def test_cham_qua_bi_danh():
    os.scandir(str(_o_dau())).close()
    assert True
"""


def _du_an(root: Path, ca: dict[str, str]) -> Path:
    """Một cây repo tí hon đủ để bộ dò chạy được trên nó."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, root / "scripts" / SCRIPT.name)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    for name, body in ca.items():
        (root / "tests" / name).write_text(body, encoding="utf-8")
    return root


def _chay(repo: Path, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *argv],
        capture_output=True,
        text=True,
        timeout=300,
    )


class TestBoDoDocRaNgoai:
    def test_bo_sach_thi_dat_va_in_ra_mau_so(self, tmp_path):
        """Xanh phải kèm số ca đã chạy — 0 ca cũng cho 0 finding."""
        repo = _du_an(tmp_path, {"test_sach.py": CA_SACH})
        p = _chay(repo, "tests", "--min-items", "1")
        assert p.returncode == 0, p.stdout + p.stderr
        assert "XANH: 1 ca" in p.stdout, p.stdout

    def test_ca_doc_ra_ngoai_thi_do_va_bi_goi_ten(self, tmp_path):
        repo = _du_an(tmp_path, {"test_ngoai.py": CA_DOC_NGOAI})
        p = _chay(repo, "tests", "--min-items", "1")
        assert p.returncode == 1, p.stdout + p.stderr
        assert "test_ngoai.py::test_cham_vao_home" in p.stdout, p.stdout

    def test_bi_danh_cuc_bo_khong_giau_duoc(self, tmp_path):
        """Chỗ một lượt grep sẽ mù, và là lý do bộ dò này đo hành vi."""
        repo = _du_an(tmp_path, {"test_bd.py": CA_DOC_NGOAI_QUA_BI_DANH})
        p = _chay(repo, "tests", "--min-items", "1")
        assert p.returncode == 1, p.stdout + p.stderr
        assert "test_bd.py::test_cham_qua_bi_danh" in p.stdout, p.stdout

    def test_ca_sach_ben_canh_ca_ban_chi_to_dung_ca_ban(self, tmp_path):
        """Quy trách nhiệm theo từng ca, không phải theo cả lượt chạy."""
        repo = _du_an(
            tmp_path, {"test_sach.py": CA_SACH, "test_ngoai.py": CA_DOC_NGOAI}
        )
        p = _chay(repo, "tests", "--min-items", "2")
        assert p.returncode == 1, p.stdout + p.stderr
        assert "1/2 ca" in p.stdout, p.stdout
        assert "test_khong_cham_ra_ngoai" not in p.stdout, p.stdout

    def test_chay_it_hon_san_thi_tu_choi_chu_khong_dat(self, tmp_path):
        """Sàn mẫu số: một lượt quét 0 ca cho 0 finding, đọc y hệt cây sạch."""
        repo = _du_an(tmp_path, {"test_sach.py": CA_SACH})
        p = _chay(repo, "tests", "--min-items", "500")
        assert p.returncode == 3, p.stdout + p.stderr
        assert "KHONG KIEM DUOC" in p.stderr, p.stderr

    def test_khong_chay_duoc_pytest_thi_tu_choi_chu_khong_dat(self, tmp_path):
        """Không có gì để chạy là KHÔNG ĐO ĐƯỢC, không bao giờ là ĐẠT."""
        repo = _du_an(tmp_path, {})
        p = _chay(repo, "tests", "--min-items", "1")
        assert p.returncode == 3, p.stdout + p.stderr
        assert "KHONG KIEM DUOC" in p.stderr, p.stderr

    def test_ghim_lam_ca_da_biet_thanh_xanh_ma_van_in_ly_do(self, tmp_path):
        """Mục đã ghim không được biến mất khỏi báo cáo — ghim ≠ giấu."""
        repo = _du_an(tmp_path, {"test_ngoai.py": CA_DOC_NGOAI})
        nodeid = "tests/test_ngoai.py::test_cham_vao_home"
        chen = (
            f'    DA_BIET["{nodeid}"] = "ly do ghim cho ca test nay"\n'
            "    raise SystemExit(main())\n"
        )
        src = (repo / "scripts" / SCRIPT.name).read_text(encoding="utf-8")
        (repo / "scripts" / SCRIPT.name).write_text(
            src.replace("    raise SystemExit(main())\n", chen), encoding="utf-8"
        )
        p = subprocess.run(
            [
                sys.executable,
                str(repo / "scripts" / SCRIPT.name),
                "--repo",
                str(repo),
                "tests",
                "--min-items",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert p.returncode == 0, p.stdout + p.stderr
        assert "da ghim" in p.stdout, p.stdout
        assert "ly do ghim cho ca test nay" in p.stdout, p.stdout


if __name__ == "__main__":  # pragma: no cover
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
