"""Phán quyết hero-walk phải buộc vào CÂY nó đi bộ, không chỉ vào COMMIT.

`git rev-parse HEAD` trả cùng một chuỗi cho một checkout sạch và cho chính
checkout đó cộng thêm những sửa chưa nằm trong commit nào. Trước bản vá này,
phán quyết chỉ ghi `sha`, nên hai trạng thái đó không phân biệt được — và thư
mục phán quyết là **dùng chung cho mọi worktree trên máy**, nên một lượt đi bộ
chạy trên bản vá local của một lane sẽ bảo lãnh cho commit hỏng nằm dưới nó,
trong `make gate` của mọi lane còn lại.

Đo thật trên 69938b7 trước khi viết file này, không phải suy luận:

    phá mối nối quét bill rồi COMMIT (e845ced)
    vá lại NGAY TRONG CÂY LÀM VIỆC, không commit
    scripts/hero_walk.sh          -> XANH 16/16, ghi sha=e845ced
    git checkout -- .             (cây trở lại đúng bản đã commit, tức bản hỏng)
    scripts/hero_walk.sh --status -> "ĐI ĐƯỢC 16/16 chặng, client e845ced
                                      (nằm trong HEAD e845ced)", mã 0
    scripts/hero_walk.sh          -> mã 1, ĐỨT ở chặng quét bill

Cổng báo xanh cho một cây mà đường hero đứt. Một trường mang hai nghĩa, và
nghĩa nguy hiểm là nghĩa im lặng.

Các ca ở đây chạy trên một repo git TẠM, có bản sao của chính runner. Không ca
nào làm bẩn cây thật: cây client thật là nguồn dùng chung, và mượn nó làm giấy
nháp chính là kiểu hỏng #424 đã phải gỡ.

Hai nhóm ca, và nhóm thứ hai giữ nhóm thứ nhất khỏi thành lời hứa suông:

- Nhóm ĐỌC: `--status` từ chối phán quyết không buộc được vào cây này.
- Nhóm VÂN TAY: `--van-tay` thật sự phân biệt được sạch với bẩn. Thiếu nhóm
  này, một `cay_van_tay` luôn trả "clean" vẫn làm cả nhóm ĐỌC xanh — ca F sẽ
  đi nhánh sạch và xanh vì lý do sai.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "scripts" / "hero_walk.sh"
URL = "http://127.0.0.1:8099"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


@pytest.fixture
def cay(tmp_path: Path) -> Path:
    """Repo git tạm mang đúng runner đang được kiểm.

    `REPO_ROOT` của runner là `dirname($0)/..`, nên đặt bản sao ở
    `<tmp>/scripts/` là đủ để nó coi `<tmp>` là cây nó đang gác.
    """
    repo = tmp_path / "cay"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(RUNNER, repo / "scripts" / "hero_walk.sh")
    _git(repo.parent, "init", "-q", "-b", "main", str(repo))
    # Không có phần đuôi tên miền: repo guard chặn chuỗi hình dạng email, và
    # một danh tính git giả cũng không được là ngoại lệ cho luật đó.
    _git(repo, "config", "user.email", "gate@test")
    _git(repo, "config", "user.name", "gate")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "runner")
    return repo


def _chay(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, MOBILE_HERO_WALK_DIR=str(repo.parent / "phan-quyet"))
    return subprocess.run(
        [str(repo / "scripts" / "hero_walk.sh"), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _van_tay(repo: Path) -> str:
    done = _chay(repo, "--van-tay")
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _ghi(repo: Path, **truong) -> None:
    """Một phán quyết XANH hợp lệ, rồi đè lên đúng trường mà ca này đang đổi.

    Mặc định phải là bản GIỐNG THẬT và phải qua được mọi phép kiểm khác, nếu
    không ca sẽ đỏ vì trường khác và bảng nói về chuyện khác.
    """
    verdict = {
        "ts": time.time(),
        "rc": 0,
        "url": URL,
        "sha": _git(repo, "rev-parse", "--short", "HEAD"),
        "tree": "clean",
        "worktree": str(repo),
        "routes": "77",
        "anh": "/tmp/ro.jpg",
        "so_chang": "16/16",
        "so_mon": 5,
        "buoc_hong": None,
    }
    verdict.update(truong)
    thu_muc = repo.parent / "phan-quyet"
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / "verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False), encoding="utf-8"
    )


def _lam_ban(repo: Path, noi_dung: str) -> None:
    (repo / "scripts" / "hero_walk.sh").write_text(
        (repo / "scripts" / "hero_walk.sh").read_text(encoding="utf-8")
        + f"\n# {noi_dung}\n",
        encoding="utf-8",
    )


# --- nhóm ĐỌC: --status từ chối phán quyết không buộc được vào cây này ------


def test_doi_chung_phan_quyet_sach_va_dung_cay_thi_XANH(cay):
    """Đối chứng. Không có nó, "cổng biết từ chối" và "cổng đỏ với mọi thứ"
    nhìn từ bảng là một."""
    _ghi(cay)
    done = _chay(cay, "--status", "--url", URL)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "ĐI ĐƯỢC" in done.stdout


def test_phan_quyet_khong_ghi_trang_thai_cay_khong_doc_duoc_la_cay_sach(cay):
    """Trường VẮNG MẶT là "không biết", không phải "sạch".

    Đây là ca trung tâm: phán quyết do bộ chạy CŨ ghi ra không có trường này,
    và đọc sự vắng mặt thành giá trị an toàn đúng là lỗi cả file này mở ra để
    đóng.
    """
    _ghi(cay)
    p = cay.parent / "phan-quyet" / "verdict.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    del d["tree"]
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    done = _chay(cay, "--status", "--url", URL)
    assert done.returncode == 2, done.stdout + done.stderr
    # Phải NÊU TÊN lý do từ chối. Chỉ so mã thoát thì ca này xanh kể cả khi cổng
    # từ chối vì một lý do khác hẳn.
    assert "KHÔNG GHI trạng thái cây làm việc" in done.stdout


def test_khong_doc_duoc_trang_thai_cay_cung_khong_phai_dat(cay):
    _ghi(cay, tree="?")
    done = _chay(cay, "--status", "--url", URL)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "KHÔNG ĐỌC ĐƯỢC trạng thái cây" in done.stdout


def test_luot_di_bo_tren_cay_ban_cua_WORKTREE_KHAC_khong_bao_lanh_cay_nay(cay):
    """Chính là lỗi đã đo được: thư mục phán quyết dùng chung giữa các worktree."""
    _lam_ban(cay, "sua chua commit")
    _ghi(cay, tree=_van_tay(cay), worktree="/home/lane-khac/wt/frontend")

    done = _chay(cay, "--status", "--url", URL)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "CÓ SỬA CHƯA COMMIT" in done.stdout
    assert "/home/lane-khac/wt/frontend" in done.stdout


def test_sua_chua_commit_da_doi_thi_phan_quyet_het_hieu_luc(cay):
    """Cùng worktree, nhưng client bây giờ không còn là client đã đi bộ."""
    _lam_ban(cay, "trang thai LUC DI BO")
    van_tay_luc_do = _van_tay(cay)
    _ghi(cay, tree=van_tay_luc_do, worktree=str(cay))

    _lam_ban(cay, "sua them SAU khi di bo")
    assert _van_tay(cay) != van_tay_luc_do

    done = _chay(cay, "--status", "--url", URL)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "ĐÃ KHÁC so với bây giờ" in done.stdout


def test_cay_ban_van_bao_lanh_cho_CHINH_no_va_noi_ro_dieu_do(cay):
    """Người đang sửa dở vẫn lấy được màu xanh cho cây của chính họ.

    Một cổng bắt đi bộ lại sau mỗi lần gõ phím sẽ bị gỡ khỏi danh sách, và một
    cổng bị gỡ không gác gì cả. Nhưng dòng XANH phải tự khai là nó đo trên mã
    không nằm trong commit nào.
    """
    _lam_ban(cay, "dang sua do")
    _ghi(cay, tree=_van_tay(cay), worktree=str(cay))

    done = _chay(cay, "--status", "--url", URL)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "ĐO TRÊN CÂY CÓ SỬA CHƯA COMMIT" in done.stdout


def test_cay_ban_khong_lam_hong_phep_kiem_to_tien_cua_sha(cay):
    """Trục cây là trục MỚI, không được nuốt trục sha đã có."""
    ngoai = _git(cay, "commit-tree", "HEAD^{tree}", "-m", "nhanh khac")
    _ghi(cay, sha=ngoai[:7])
    done = _chay(cay, "--status", "--url", URL)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "nhánh khác" in done.stdout


# --- nhóm VÂN TAY: cái làm nhóm trên không thành lời hứa suông --------------


def test_cay_that_su_sach_thi_van_tay_dung_bang_clean(cay):
    """Nếu thiếu ca này, một `cay_van_tay` luôn trả "clean" vẫn làm cả nhóm
    ĐỌC ở trên xanh — và cổng quay lại đúng chỗ mù ban đầu."""
    assert _git(cay, "status", "--porcelain") == ""
    assert _van_tay(cay) == "clean"


def test_sua_chua_commit_lam_van_tay_khac_clean(cay):
    _lam_ban(cay, "mot dong")
    assert _van_tay(cay).startswith("dirty:")


def test_hai_noi_dung_sua_khac_nhau_cho_hai_van_tay_khac_nhau(cay):
    """Chỉ băm DANH SÁCH đường dẫn là chưa đủ: sửa khác nội dung trên cùng một
    file phải ra vân tay khác, nếu không "vá lại rồi phá lại" là vô hình."""
    p = cay / "scripts" / "hero_walk.sh"
    goc = p.read_text(encoding="utf-8")

    p.write_text(goc + "\n# A\n", encoding="utf-8")
    a = _van_tay(cay)
    p.write_text(goc + "\n# B\n", encoding="utf-8")
    b = _van_tay(cay)

    assert a.startswith("dirty:") and b.startswith("dirty:")
    assert a != b


def test_file_moi_chua_track_cung_lam_doi_van_tay(cay):
    """`git diff HEAD` không bao giờ thấy file chưa track, mà một .ts mới dưới
    apps/mobile/src thì tsc vẫn biên dịch vào client mà lượt đi bộ lái."""
    sach = _van_tay(cay)
    (cay / "man-moi.ts").write_text("export const x = 1;\n", encoding="utf-8")
    assert _van_tay(cay) != sach
    assert _van_tay(cay).startswith("dirty:")
