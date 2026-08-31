"""`--status` chỉ trả lời được về THƯ MỤC đang đứng. Không ai hỏi được về main.

Đường hero là toàn bộ lời khai của PoC này: ảnh bill -> model đọc món -> gán ->
chia -> đợt thu -> trang khách. `scripts/hero_walk.sh` đi hết đường đó và ghi
một phán quyết; chặng `hero-walk` của `scripts/gate.sh` đọc lại phán quyết ấy.

Phán quyết được buộc vào cây bằng `merge-base --is-ancestor <sha> HEAD`, và
HEAD là HEAD của thư mục người gõ lệnh đang đứng. Luật đó đúng, và nó KHÔNG trả
lời được câu hỏi mà Lead thực sự hỏi lúc chốt sổ:

    đường hero có được chứng minh trên `origin/main` không?

Đo được lúc 2026-08-31T20:35 +0700, trước file này:

    scripts/gate.sh hero-walk        (ở nhánh devops, HEAD e069be1)
      -> HỎNG  "lượt đi bộ chạy ở client 7b8fed8, KHÔNG nằm trong HEAD e069be1"
    git merge-base --is-ancestor 7b8fed8 origin/main
      -> 1     (7b8fed8 thuộc backend/split-khai-ro-tap-nguoi-duoc-chia, CHƯA merge)

Nghĩa là lượt đi bộ gần nhất nói về một nhánh chưa vào main, và **main không có
phán quyết nào**. Điều đó nhìn từ nhánh đã đi bộ thì XANH — người đi bộ đứng
trên chính nhánh đó — nên nửa nguy hiểm im lặng đúng ở phía người không đi bộ.
Không có lệnh nào hỏi được nửa kia, nên không ai hỏi.

`--ref` là câu hỏi còn thiếu: buộc phán quyết vào một COMMIT do người gọi nêu
tên, chứ không vào thư mục tình cờ đang đứng.

## Vì sao chế độ `--ref` bỏ hai phép kiểm mà chế độ HEAD bắt buộc phải có

`--status` so vân tay cây LÚC ĐI BỘ với vân tay cây BÂY GIỜ, vì nó đang cho
phán quyết bảo lãnh cho *thư mục này*, và thư mục này đổi được sau lượt đi bộ.
Hỏi về một ref thì không còn thư mục nào để đổi: câu trả lời phải rút ra từ
`<sha>` và `<ref>`, cả hai đều bất biến. Bù lại, `--ref` đòi CHẶT hơn ở đúng
chỗ chặt hơn có nghĩa: `tree` phải bằng `clean`, vì một lượt đi bộ trên cây có
sửa chưa commit không bảo lãnh cho *bất kỳ* commit nào — kể cả commit nằm ngay
dưới nó. `test_luot_di_bo_tren_cay_BAN_khong_bao_lanh_cho_REF_NAO` giữ điều đó.

ĐỌC ĐỐI CHỨNG DƯƠNG TRƯỚC. `test_doi_chung_ref_CHUA_commit_da_di_bo_thi_XANH`
chứng minh chế độ này ra XANH được. Thiếu nó thì mọi ca "phải ĐỎ" ở dưới cũng
xanh y hệt trên một `--ref` bị hỏng thành "luôn luôn đỏ", và bảng vẫn đọc như
một bảng đã gác.
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
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def cay(tmp_path: Path) -> Path:
    """Repo git tạm mang đúng runner đang được kiểm, có HAI commit.

    Hai commit là tối thiểu để hỏi được câu hỏi của file này: `cu` là một ref
    KHÔNG chứa lượt đi bộ, `main` là ref có chứa. Một commit thì hai vế trùng
    nhau và ca "ref không chứa" không dựng được.
    """
    repo = tmp_path / "cay"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(RUNNER, repo / "scripts" / "hero_walk.sh")
    _git(repo.parent, "init", "-q", "-b", "main", str(repo))
    _git(repo, "config", "user.email", "gate@test")
    _git(repo, "config", "user.name", "gate")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "runner")
    _git(repo, "branch", "cu")  # ref đứng TRƯỚC lượt đi bộ
    (repo / "sau.txt").write_text("việc làm sau khi cắt nhánh cu\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "commit thứ hai")
    return repo


def _chay(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, MOBILE_HERO_WALK_DIR=str(repo.parent / "phan-quyet"))
    return subprocess.run(
        [str(repo / "scripts" / "hero_walk.sh"), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _ngoai_git_hoac_thieu(repo: Path):
    done = _chay(repo, "--ngoai-git")
    return done.stdout.strip() if done.returncode == 0 else None


def _co_node_modules(repo: Path) -> None:
    thu_muc = repo / "apps" / "mobile" / "node_modules"
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / "goi.js").write_text("module.exports = 1;\n", encoding="utf-8")
    loai_tru = repo / ".git" / "info" / "exclude"
    loai_tru.parent.mkdir(parents=True, exist_ok=True)
    loai_tru.write_text("node_modules/\n", encoding="utf-8")


def _ghi(repo: Path, **truong) -> None:
    """Một phán quyết XANH hợp lệ, rồi đè lên đúng trường ca này đang đổi."""
    _co_node_modules(repo)
    verdict = {
        "ts": time.time(),
        "rc": 0,
        "url": URL,
        "sha": _git(repo, "rev-parse", "--short", "HEAD"),
        "tree": "clean",
        "worktree": str(repo),
        "ngoai_git": _ngoai_git_hoac_thieu(repo),
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


# --- đối chứng dương -------------------------------------------------------


def test_doi_chung_ref_CHUA_commit_da_di_bo_thi_XANH(cay):
    """Không có ca này, mọi ca "phải ĐỎ" ở dưới cũng xanh trên một cờ luôn-đỏ."""
    _ghi(cay)
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "main" in done.stdout


# --- chính cái cổng --------------------------------------------------------


def test_ref_KHONG_chua_commit_da_di_bo_thi_DO(cay):
    """Đây là hình dạng đo được lúc 20:35: phán quyết nói về một nhánh chưa merge.

    `cu` đứng trước lượt đi bộ, đúng như `origin/main` đứng trước 7b8fed8.
    """
    _ghi(cay)
    done = _chay(cay, "--status", "--ref", "cu")
    assert done.returncode == 2, done.stdout + done.stderr
    assert "cu" in done.stdout


def test_cay_BAY_GIO_ban_KHONG_lam_hong_cau_hoi_ve_ref(cay):
    """Hai chế độ phải trả lời hai câu hỏi khác nhau — nếu không thì `--ref` vô nghĩa.

    Sửa chưa commit trong thư mục này làm chế độ HEAD ĐỎ (đúng: client bây giờ
    không phải client đã đi bộ). Nó KHÔNG được làm hỏng câu trả lời về `main`,
    vì `main` là một commit và không ai sửa được một commit bằng cách gõ vào
    thư mục làm việc.
    """
    _ghi(cay)
    (cay / "dang-sua.txt").write_text("bản nháp chưa commit\n", encoding="utf-8")

    theo_cay = _chay(cay, "--status")
    assert theo_cay.returncode == 2, theo_cay.stdout

    theo_ref = _chay(cay, "--status", "--ref", "main")
    assert theo_ref.returncode == 0, theo_ref.stdout + theo_ref.stderr


def test_luot_di_bo_tren_cay_BAN_khong_bao_lanh_cho_REF_NAO(cay):
    """Bỏ hai phép kiểm vân tay KHÔNG được nới thành "bỏ luôn chuyện cây bẩn".

    Mã một lượt đi bộ bẩn chạy không nằm trong commit nào, nên nó không nói
    được gì về `main` dù sha nó ghi có là tổ tiên của `main` đi nữa.
    """
    _ghi(cay, tree="dirty:0123456789abcdef")
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


@pytest.mark.parametrize("tre", ["?", "blind"])
def test_tree_khong_doc_duoc_cung_khong_bao_lanh_cho_ref(cay, tre):
    """ "Không đọc được" không phải "cây sạch" — cùng luật với chế độ HEAD."""
    _ghi(cay, tree=tre)
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


def test_tree_VANG_MAT_khong_doc_duoc_la_cay_sach(cay):
    """Bộ chạy cũ không ghi trường này. Thiếu = chưa biết, không phải sạch."""
    _ghi(cay)
    thu_muc = cay.parent / "phan-quyet" / "verdict.json"
    v = json.loads(thu_muc.read_text(encoding="utf-8"))
    del v["tree"]
    thu_muc.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


def test_ref_KHONG_TON_TAI_thi_DO_chu_khong_XANH(cay):
    """Một ref gõ sai phải ĐỎ. Xanh ở đây là cổng tự tháo bằng lỗi chính tả."""
    _ghi(cay)
    done = _chay(cay, "--status", "--ref", "khong-he-co-ref-nay")
    assert done.returncode == 2, done.stdout + done.stderr


def test_phan_quyet_DUT_khong_thanh_XANH_chi_vi_hoi_ve_ref(cay):
    _ghi(cay, rc=1, buoc_hong="QUET BILL: anh -> mon")
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


def test_phan_quyet_CU_QUA_khong_thanh_XANH_chi_vi_hoi_ve_ref(cay):
    _ghi(cay, ts=time.time() - 100 * 3600)
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


def test_phan_quyet_ve_MAY_KHAC_khong_bao_lanh_cho_ref(cay):
    _ghi(cay, url="http://127.0.0.1:9999")
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


def test_sha_repo_nay_KHONG_CO_thi_DO(cay):
    """Clone khác, nhánh bị viết lại, hoặc phán quyết sửa tay."""
    _ghi(cay, sha="dead1234")
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


def test_chua_ai_di_bo_thi_DO_chu_khong_im_lang(cay):
    """Vắng phán quyết là vắng bằng chứng, không phải bằng chứng vắng lỗi."""
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 2, done.stdout + done.stderr


def test_dong_ket_qua_NOI_RO_no_tra_loi_ve_ref_nao(cay):
    """Một dòng xanh không nói nó xanh VỀ CÁI GÌ là dòng bị đọc nhầm sang cây này."""
    _ghi(cay)
    done = _chay(cay, "--status", "--ref", "main")
    assert done.returncode == 0, done.stdout + done.stderr
    sha_main = _git(cay, "rev-parse", "--short", "main")
    assert "main" in done.stdout
    assert sha_main in done.stdout


def test_khong_co_ref_thi_van_la_che_do_cu(cay):
    """Không truyền `--ref` thì hành vi phải y như trước: hỏi về THƯ MỤC NÀY."""
    _ghi(cay)
    (cay / "dang-sua.txt").write_text("bản nháp chưa commit\n", encoding="utf-8")
    done = _chay(cay, "--status")
    assert done.returncode == 2, done.stdout + done.stderr
