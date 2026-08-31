"""Bộ tự kiểm của harness phải chạy được mà không cần ai khởi động lại đội.

`team.sh` có cổng tự kiểm thật, và nó đã từng nổ. Nhưng nó là một hàm bash chỉ
tới được từ `start` và `restart`. Giữa hai lần khởi động — có khi cả ngày —
không có gì chạy nó. Mà cây harness KHÔNG có remote, KHÔNG có CI, KHÔNG có bước
triển khai: cây làm việc LÀ production, nên một lần lưu file là code đã sống.

Đo ngày 31/08: hồi quy đi vào theo `f874225` và tha bổng ba cổng kỹ năng. Nó
được tìm ra vì Lead tình cờ chạy `team.sh start` và thấy đỏ. Trong mấy giờ ở
giữa, `require_skills` đã tắt và mọi tín hiệu đều im. Cổng không yếu — cổng
không có ai gọi.

Hai lỗ hổng file này gác, cả hai đều đo được chứ không phải suy luận:

1. **Sàn.** Vòng bash cũ lặp trên một glob rồi `[ -e "$t" ] || continue`. Thư
   mục `tests/` rỗng làm nó in đúng một dòng tiêu đề rồi `return 0` — ĐẠT với
   **không một test nào chạy**. Đo tay trên `/tmp/fakeharness`: `EXIT=0`.
   `discover()` phải TỪ CHỐI ở đúng ba đường đó.

2. **Im lặng.** Thêm một máy chạy định kỳ là thêm một kiểu hỏng mà lượt gọi tay
   không có: chính nó dừng. Lúc đó nó không in gì, và "không in gì" là đúng thứ
   một canh gác khoẻ mạnh cũng in. Nên `status` phải coi im lặng là **thất bại**:
   chưa từng chạy · bản ghi cũ · bản ghi hỏng · bản ghi nói về mã KHÁC.

Ca thứ tư của mục 2 là ca không hiển nhiên: một canh gác có thể còn sống, đúng
nhịp, và xanh mãi mãi trong khi chấm một cây `lane.py` đã bị thay từ lâu. Quá
hạn không thấy được nó, vì bản ghi sai-mã vẫn được làm mới đúng giờ như mọi bản
ghi khác. Đúng cái bẫy `demo_watch.py` đã phải học bằng một lần trả giá.

Không ca nào ở đây đóng băng đồng hồ. Mốc thời gian ghi thẳng vào bản ghi dưới
dạng epoch quá khứ, vì một đồng hồ đứng yên làm đúng loại đột biến các ca này
sinh ra để bắt (dời ngưỡng quá hạn) trở thành vô hình.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "harness_selfcheck.py"
HARNESS_THAT = Path.home() / "agent-harness"

PASS_TEST = """import unittest


class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
"""

FAIL_TEST = """import unittest


class T(unittest.TestCase):
    def test_no(self):
        self.fail("co y lam do")


if __name__ == "__main__":
    unittest.main()
"""


def _mod():
    """Nạp script như một module, không chép lại logic của nó."""
    spec = importlib.util.spec_from_file_location("harness_selfcheck", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _mod()


def _harness_gia(
    root: Path, thieu: tuple[str, ...] = (), do: tuple[str, ...] = ()
) -> Path:
    """Cây harness giả: đủ file bắt buộc, cộng vài file nguồn cho dấu vân tay."""
    (root / "tests").mkdir(parents=True, exist_ok=True)
    for name in M.REQUIRED_TESTS:
        if name in thieu:
            continue
        body = FAIL_TEST if name in do else PASS_TEST
        (root / "tests" / name).write_text(body, encoding="utf-8")
    (root / "lane.py").write_text("# lane gia\n", encoding="utf-8")
    (root / "team.sh").write_text("#!/usr/bin/env bash\necho gia\n", encoding="utf-8")
    return root


def _lam_cu(root: Path, tuoi: float) -> None:
    """Dời mtime của MỌI nguồn được gác về quá khứ `tuoi` giây."""
    moc = time.time() - tuoi
    for p in M.guarded_sources(root):
        os.utime(p, (moc, moc))


def _chay(root: Path, *argv: str) -> subprocess.CompletedProcess:
    """Gọi qua CLI thật, vì chính CLI là thứ dòng crontab gọi."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--harness", str(root), *argv],
        capture_output=True,
        text=True,
        timeout=300,
    )


def _ban_ghi(root: Path, **doi) -> Path:
    """Bản ghi giống thật, rồi mới sửa đúng thứ ca test đang hỏi."""
    rec = root / "state" / "selfcheck.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ts": M._stamp(),
        "unix": time.time(),
        "verdict": "XANH",
        "code_fingerprint": M.fingerprint(root),
        "files": [{"name": n, "ok": True, "ran": 1} for n in M.REQUIRED_TESTS],
        "ran_tests": len(M.REQUIRED_TESTS),
    }
    data.update(doi)
    rec.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return rec


# --- sàn: ba đường mà danh sách nguồn có thể ngắn lại -----------------------


class TestSan:
    def test_thu_muc_tests_khong_co_thi_tu_choi(self, tmp_path):
        (tmp_path / "lane.py").write_text("# x\n", encoding="utf-8")
        with pytest.raises(M.Refuse) as e:
            M.discover(tmp_path)
        assert "KHONG KIEM DUOC" in str(e.value)

    def test_thu_muc_tests_rong_thi_tu_choi_chu_khong_dat(self, tmp_path):
        """Đây là lỗ đo được của vòng bash: glob rỗng -> ĐẠT, 0 test."""
        (tmp_path / "tests").mkdir()
        with pytest.raises(M.Refuse):
            M.discover(tmp_path)

    def test_thieu_mot_ca_bat_buoc_thi_tu_choi_va_goi_ten_no(self, tmp_path):
        _harness_gia(tmp_path, thieu=(M.REQUIRED_TESTS[2],))
        with pytest.raises(M.Refuse) as e:
            M.discover(tmp_path)
        # Gọi tên file mất, và chỉ đúng chỗ phải sửa nếu đổi tên là có ý.
        assert M.REQUIRED_TESTS[2] in str(e.value)
        assert "REQUIRED_TESTS" in str(e.value)

    def test_manifest_teo_lai_thi_tu_choi(self, tmp_path, monkeypatch):
        """Sàn không được đo bằng chính danh sách nó đang gác.

        Nếu sàn là `len(REQUIRED_TESTS)` thì xoá rỗng manifest làm "không
        thiếu gì" thành đúng, và cổng tự thao trên một bộ test bằng không —
        đúng hình dạng của cái glob rỗng mà file này sinh ra để từ chối.
        """
        _harness_gia(tmp_path)
        monkeypatch.setattr(M, "REQUIRED_TESTS", ())
        with pytest.raises(M.Refuse) as e:
            M.discover(tmp_path)
        assert "REQUIRED_TESTS" in str(e.value)

    def test_manifest_du_ten_nhung_duoi_san_cung_tu_choi(self, tmp_path, monkeypatch):
        _harness_gia(tmp_path)
        monkeypatch.setattr(M, "REQUIRED_TESTS", M.REQUIRED_TESTS[:2])
        with pytest.raises(M.Refuse):
            M.discover(tmp_path)

    def test_du_file_thi_tra_ve_het(self, tmp_path):
        _harness_gia(tmp_path)
        assert len(M.discover(tmp_path)) == len(M.REQUIRED_TESTS)

    def test_them_file_moi_khong_bi_chan(self, tmp_path):
        _harness_gia(tmp_path)
        (tmp_path / "tests" / "test_moi_toanh.py").write_text(
            PASS_TEST, encoding="utf-8"
        )
        assert len(M.discover(tmp_path)) == len(M.REQUIRED_TESTS) + 1

    def test_tu_choi_ghi_ban_ghi_va_thoat_3_chu_khong_0(self, tmp_path):
        _harness_gia(tmp_path, thieu=(M.REQUIRED_TESTS[0],))
        p = _chay(tmp_path, "run")
        assert p.returncode == 3, p.stdout + p.stderr
        assert "KHONG KIEM DUOC" in p.stderr
        rec = json.loads((tmp_path / "state" / "selfcheck.json").read_text())
        assert rec["verdict"] == "TU_CHOI"
        assert rec["ran_tests"] == 0


# --- run: xanh, đỏ, và đường báo động --------------------------------------


class TestRun:
    def test_cay_xanh_thi_thoat_0_va_ghi_dung_so_test(self, tmp_path):
        _harness_gia(tmp_path)
        p = _chay(tmp_path, "run")
        assert p.returncode == 0, p.stdout + p.stderr
        rec = json.loads((tmp_path / "state" / "selfcheck.json").read_text())
        assert rec["verdict"] == "XANH"
        assert rec["ran_tests"] == len(M.REQUIRED_TESTS)
        assert rec["code_fingerprint"].startswith("sha256:")

    def test_mot_file_do_thi_thoat_1_va_goi_ten_file(self, tmp_path):
        do = M.REQUIRED_TESTS[3]
        _harness_gia(tmp_path, do=(do,))
        p = _chay(tmp_path, "run")
        assert p.returncode == 1, p.stdout + p.stderr
        rec = json.loads((tmp_path / "state" / "selfcheck.json").read_text())
        assert rec["verdict"] == "DO"
        assert [f["name"] for f in rec["files"] if not f["ok"]] == [do]

    def test_khong_co_alert_thi_khong_lam_on_duong_bao_dong(self, tmp_path):
        _harness_gia(tmp_path, do=(M.REQUIRED_TESTS[1],))
        _chay(tmp_path, "run")
        assert not (tmp_path / "state" / "alerts.jsonl").exists()

    def test_co_alert_thi_do_di_vao_alerts_jsonl(self, tmp_path):
        _harness_gia(tmp_path, do=(M.REQUIRED_TESTS[1],))
        p = _chay(tmp_path, "run", "--alert")
        assert p.returncode == 1
        lines = (tmp_path / "state" / "alerts.jsonl").read_text().splitlines()
        ev = json.loads(lines[-1])
        assert ev["type"] == "HARNESS_SELFCHECK_RED"
        assert ev["alert"] is True
        assert M.REQUIRED_TESTS[1] in ev["files"]

    def test_co_alert_thi_tu_choi_cung_di_vao_alerts_jsonl(self, tmp_path):
        _harness_gia(tmp_path, thieu=(M.REQUIRED_TESTS[4],))
        assert _chay(tmp_path, "run", "--alert").returncode == 3
        ev = json.loads(
            (tmp_path / "state" / "alerts.jsonl").read_text().splitlines()[-1]
        )
        assert ev["type"] == "HARNESS_SELFCHECK_REFUSED"
        assert ev["alert"] is True

    def test_luot_thu_hai_khong_chen_luot_dang_chay(self, tmp_path):
        _harness_gia(tmp_path)
        lock = M._lock(tmp_path)
        assert lock is not None
        try:
            assert _chay(tmp_path, "run").returncode == 4
        finally:
            lock.unlink()

    def test_khoa_mo_coi_khong_chan_mai_mai(self, tmp_path):
        _harness_gia(tmp_path)
        lock = M._lock(tmp_path)
        qua_han = time.time() - M.PER_FILE_TIMEOUT * (len(M.REQUIRED_TESTS) + 2)
        os.utime(lock, (qua_han, qua_han))
        assert _chay(tmp_path, "run").returncode == 0


# --- status: im lặng là thất bại -------------------------------------------


class TestStatusImLangLaThatBai:
    def test_chua_tung_chay_thi_mac_2(self, tmp_path):
        _harness_gia(tmp_path)
        p = _chay(tmp_path, "status")
        assert p.returncode == 2
        assert "CHUA CHAY LAN NAO" in p.stderr

    def test_ban_ghi_hong_thi_mac_2_chu_khong_bao_gio_la_0(self, tmp_path):
        _harness_gia(tmp_path)
        rec = tmp_path / "state" / "selfcheck.json"
        rec.parent.mkdir(parents=True, exist_ok=True)
        rec.write_text("{ khong phai json", encoding="utf-8")
        p = _chay(tmp_path, "status")
        assert p.returncode == 2
        assert "KHONG DOC DUOC" in p.stderr

    def _crontab_gia(self, tmp_path, noi_dung: str) -> dict:
        """PATH có một `crontab` giả trả về đúng nội dung mình muốn."""
        gia = tmp_path / "bin"
        gia.mkdir(exist_ok=True)
        luu = tmp_path / "cron.txt"
        luu.write_text(noi_dung, encoding="utf-8")
        (gia / "crontab").write_text(
            f'#!/usr/bin/env bash\n[ "$1" = "-l" ] && cat "{luu}" && exit 0\nexit 1\n'
        )
        (gia / "crontab").chmod(0o755)
        return {**os.environ, "PATH": f"{gia}:{os.environ['PATH']}"}

    def test_ban_ghi_cu_va_CO_khoi_cron_thi_bao_canh_gac_da_dung(self, tmp_path):
        _harness_gia(tmp_path)
        _ban_ghi(tmp_path, unix=time.time() - 4000)
        env = self._crontab_gia(tmp_path, f"{M.CRON_BEGIN}\n*/15 * * * * x\n")
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--harness", str(tmp_path), "status"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert p.returncode == 2, p.stdout + p.stderr
        assert "BAN GHI CU" in p.stderr

    def test_ban_ghi_cu_va_KHONG_co_khoi_cron_thi_bao_chua_cai(self, tmp_path):
        """Nói "canh gác đã dừng" khi chưa từng cài là bắt người ta đi tìm một
        cái xác không tồn tại. Hai đường cùng mã 2, nhưng chỉ về hai chỗ khác."""
        _harness_gia(tmp_path)
        _ban_ghi(tmp_path, unix=time.time() - 4000)
        env = self._crontab_gia(tmp_path, "*/5 * * * * viec-cua-nguoi-khac\n")
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--harness", str(tmp_path), "status"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert p.returncode == 2, p.stdout + p.stderr
        assert "CHUA CAI CANH GAC" in p.stderr
        assert "install --apply" in p.stderr

    def test_ban_ghi_moi_va_xanh_thi_mac_0(self, tmp_path):
        _harness_gia(tmp_path)
        _ban_ghi(tmp_path)
        p = _chay(tmp_path, "status")
        assert p.returncode == 0, p.stdout + p.stderr

    def test_ban_ghi_noi_do_thi_mac_1(self, tmp_path):
        _harness_gia(tmp_path)
        _ban_ghi(
            tmp_path, verdict="DO", files=[{"name": "test_x.py", "ok": False, "ran": 3}]
        )
        assert _chay(tmp_path, "status").returncode == 1

    def test_ban_ghi_tu_choi_thi_mac_2(self, tmp_path):
        _harness_gia(tmp_path)
        _ban_ghi(tmp_path, verdict="TU_CHOI", reason="thieu ca test")
        assert _chay(tmp_path, "status").returncode == 2


class TestStatusNoiVeMaNao:
    """Canh gác có thể còn sống, đúng nhịp, và xanh mãi mãi về mã đã bị thay."""

    def test_ma_da_doi_va_qua_han_an_han_thi_mac_2(self, tmp_path):
        # Ân hạn xét trên lần sửa MỚI NHẤT của cả cây, không phải của một file:
        # nếu bất kỳ nguồn nào vừa đổi thì dấu vân tay hiện tại mới có vài giây
        # và canh gác chưa thể bị quy tội. Nên để dựng đúng cảnh "đã quá hạn mà
        # vẫn chưa ai chấm", phải làm CẢ CÂY cũ đi, không chỉ file vừa sửa.
        # Bản đầu của ca này chỉ dời mtime của lane.py và đỏ — đỏ đúng, vì
        # tests/*.py vừa được tạo vẫn còn mới.
        _harness_gia(tmp_path)
        _ban_ghi(tmp_path)
        (tmp_path / "lane.py").write_text("# da sua\n", encoding="utf-8")
        _lam_cu(tmp_path, 4000)
        p = _chay(tmp_path, "status", "--max-age", "3600")
        assert p.returncode == 2, p.stdout + p.stderr
        assert "MA KHAC" in p.stderr

    def test_ma_vua_doi_thi_con_an_han_va_mac_0(self, tmp_path):
        _harness_gia(tmp_path)
        _ban_ghi(tmp_path)
        (tmp_path / "lane.py").write_text("# vua sua xong\n", encoding="utf-8")
        p = _chay(tmp_path, "status", "--max-age", "3600")
        assert p.returncode == 0, p.stdout + p.stderr
        assert "an han" in p.stdout

    def test_an_han_khong_che_duoc_canh_gac_da_chet(self, tmp_path):
        """Hai phép kiểm độc lập: mã vừa đổi KHÔNG tha cho bản ghi quá hạn."""
        _harness_gia(tmp_path)
        _ban_ghi(tmp_path, unix=time.time() - 4000)
        (tmp_path / "lane.py").write_text("# vua sua xong\n", encoding="utf-8")
        assert _chay(tmp_path, "status", "--max-age", "3600").returncode == 2


class TestDauVanTay:
    def test_touch_khong_doi_dau_van_tay(self, tmp_path):
        _harness_gia(tmp_path)
        truoc = M.fingerprint(tmp_path)
        moc = time.time() - 999
        os.utime(tmp_path / "lane.py", (moc, moc))
        assert M.fingerprint(tmp_path) == truoc

    def test_sua_noi_dung_doi_dau_van_tay(self, tmp_path):
        _harness_gia(tmp_path)
        truoc = M.fingerprint(tmp_path)
        (tmp_path / "lane.py").write_text("# khac roi\n", encoding="utf-8")
        assert M.fingerprint(tmp_path) != truoc

    def test_sua_mot_file_test_cung_doi_dau_van_tay(self, tmp_path):
        _harness_gia(tmp_path)
        truoc = M.fingerprint(tmp_path)
        (tmp_path / "tests" / M.REQUIRED_TESTS[0]).write_text(
            PASS_TEST + "# them\n", encoding="utf-8"
        )
        assert M.fingerprint(tmp_path) != truoc

    def test_quay_ve_noi_dung_cu_thi_dau_van_tay_tro_lai(self, tmp_path):
        _harness_gia(tmp_path)
        truoc = M.fingerprint(tmp_path)
        p = tmp_path / "lane.py"
        goc = p.read_text()
        p.write_text("# tam\n", encoding="utf-8")
        p.write_text(goc, encoding="utf-8")
        assert M.fingerprint(tmp_path) == truoc

    def test_khong_dem_pycache(self, tmp_path):
        _harness_gia(tmp_path)
        truoc = M.fingerprint(tmp_path)
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "lane.cpython-313.pyc").write_bytes(b"\x00rac")
        assert M.fingerprint(tmp_path) == truoc


class TestKhoiCrontab:
    def test_khoi_co_dau_moc_hai_dau_va_duong_dan_tuyet_doi(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        block = M.cron_block(tmp_path, repo)
        assert block.startswith(M.CRON_BEGIN)
        assert block.rstrip().endswith(M.CRON_END)
        # Cron chạy với PATH tối thiểu: cả trình thông dịch lẫn script phải là
        # đường dẫn tuyệt đối, và gốc harness phải nói rõ ra.
        assert sys.executable in block
        assert f"HARNESS_ROOT={tmp_path}" in block
        assert "run --alert" in block

    def test_dong_cron_tro_vao_checkout_ben_vung_khong_phai_worktree(self, tmp_path):
        """Dòng crontab sống lâu hơn cái nhánh sinh ra nó.

        File này gần như luôn được chạy từ worktree của một lane — thứ bị xoá,
        bị rebase, hoặc ở trên một nhánh không bao giờ merge. Một dòng cron trỏ
        vào đó là một canh gác hẹn giờ tự chết. Nên khối phải gọi bản trong
        `--repo`, KHÔNG phải `__file__`.
        """
        repo = tmp_path / "mobile"
        (repo / "scripts").mkdir(parents=True)
        block = M.cron_block(tmp_path, repo)
        assert str(repo / "scripts" / "harness_selfcheck.py") in block
        # Chính là điểm của ca này: đường dẫn worktree đang chạy không được lọt
        # vào dòng crontab.
        assert str(SCRIPT) not in block

    def test_tu_choi_cai_khi_checkout_chua_co_file(self, tmp_path):
        """Cron nhận dòng trỏ vào file không có, rồi hỏng im mỗi 15 phút."""
        repo = tmp_path / "chua-merge"
        (repo / "scripts").mkdir(parents=True)
        p = _chay(tmp_path, "install", "--repo", str(repo), "--apply")
        assert p.returncode == 2, p.stdout + p.stderr
        assert "TU CHOI CAI" in p.stderr

    def test_cai_duoc_khi_checkout_da_co_file(self, tmp_path, monkeypatch):
        """Đường đi thật, nhưng không đụng crontab của máy: giả lập `crontab`."""
        repo = tmp_path / "mobile"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "harness_selfcheck.py").write_text("# ban da merge\n")
        gia = tmp_path / "bin"
        gia.mkdir()
        luu = tmp_path / "crontab.txt"
        luu.write_text("*/5 * * * * viec-cua-nguoi-khac\n")
        (gia / "crontab").write_text(
            "#!/usr/bin/env bash\n"
            f'LUU="{luu}"\n'
            'if [ "$1" = "-l" ]; then cat "$LUU"; exit 0; fi\n'
            'if [ "$1" = "-" ]; then cat > "$LUU"; exit 0; fi\n'
            "exit 1\n"
        )
        (gia / "crontab").chmod(0o755)
        monkeypatch.setenv("PATH", f"{gia}:{os.environ['PATH']}")
        p = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--harness",
                str(tmp_path),
                "install",
                "--repo",
                str(repo),
                "--apply",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PATH": f"{gia}:{os.environ['PATH']}"},
        )
        assert p.returncode == 0, p.stdout + p.stderr
        sau = luu.read_text()
        assert M.CRON_BEGIN in sau
        assert "viec-cua-nguoi-khac" in sau, "đã xoá dòng cron của người khác"

    def test_go_khoi_khong_dung_toi_dong_khac(self):
        cu = (
            "*/5 * * * * viec-cua-nguoi-khac\n"
            f"{M.CRON_BEGIN}\n*/15 * * * * cua-toi\n{M.CRON_END}\n"
            "0 3 * * * mot-viec-nua\n"
        )
        con = M._strip_block(cu)
        assert "viec-cua-nguoi-khac" in con
        assert "mot-viec-nua" in con
        assert "cua-toi" not in con
        assert M.CRON_BEGIN not in con

    def test_in_khoi_ma_khong_ghi_thi_khong_doi_crontab(self, tmp_path):
        p = _chay(tmp_path, "install")
        assert p.returncode == 0
        assert M.CRON_BEGIN in p.stdout


# --- neo vào cây harness THẬT ----------------------------------------------


@pytest.mark.skipif(not HARNESS_THAT.is_dir(), reason="máy này không có harness")
class TestNeoVaoHarnessThat:
    def test_danh_sach_bat_buoc_khop_voi_cay_that(self):
        """Manifest phải nói về file có thật, không phải tên đã chết.

        Một manifest trỏ vào file không tồn tại làm `discover()` TỪ CHỐI mãi
        mãi; một manifest thiếu file có thật làm sàn thấp hơn thực tế. Cả hai
        đều là cổng nói về một cây khác cây đang chạy.
        """
        that = {p.name for p in (HARNESS_THAT / "tests").glob("test_*.py")}
        thieu = sorted(set(M.REQUIRED_TESTS) - that)
        assert thieu == [], f"REQUIRED_TESTS trỏ vào file không có thật: {thieu}"
        chua_khai = sorted(that - set(M.REQUIRED_TESTS))
        assert chua_khai == [], (
            f"cây harness có file test chưa khai trong REQUIRED_TESTS: "
            f"{chua_khai} — sàn đang thấp hơn thực tế"
        )

    def test_duong_bao_dong_that_hien_duoc_su_kien_nay(self):
        """Đo hành vi của `format_alert.py`, không đọc văn bản nguồn của nó.

        Một kiểu sự kiện mới bị formatter bỏ rơi là cách một kiểu hỏng mới trở
        thành vô hình. Nhánh cuối của `render()` nói là nó không bỏ rơi ai —
        ca này bắt nó chứng minh, bằng cách bơm đúng dòng JSON mà `run --alert`
        ghi ra và đòi một dòng chữ cho Lead.
        """
        fmt = HARNESS_THAT / "format_alert.py"
        if not fmt.is_file():
            pytest.skip("cây harness không có format_alert.py")
        ev = {
            "type": "HARNESS_SELFCHECK_RED",
            "alert": True,
            "severity": "critical",
            "files": ["test_phat_hien_hong.py"],
            "note": "harness tu kiem DO",
        }
        p = subprocess.run(
            [sys.executable, str(fmt)],
            input=json.dumps(ev) + "\n",
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert p.returncode == 0, p.stderr
        assert "HARNESS_SELFCHECK_RED" in p.stdout, (
            "format_alert.py im lặng với sự kiện này — báo động sẽ không tới Lead"
        )
        assert "test_phat_hien_hong.py" in p.stdout


@pytest.mark.skipif(
    not (HARNESS_THAT / "team.sh").is_file(), reason="máy này không có team.sh"
)
class TestTeamShDoBangHanhVi:
    """Đo `team.sh check` LÀM GÌ, không đọc `team.sh` VIẾT GÌ.

    Bản đầu của hai ca này grep văn bản nguồn: một ca đòi chuỗi `SAN_TEST` có
    trong file, ca kia đòi chuỗi `check)`. Bảng đột biến bắt được cả hai là vô
    dụng — thay sàn thành `-lt 0` vẫn để lại dòng khai `SAN_TEST=6` ở đầu file,
    và bọc `# check)` thành comment vẫn để lại chuỗi `check)`. Hai đột biến gỡ
    đúng hai thứ này SỐNG SÓT qua bộ test đọc-chữ.

    Nên các ca dưới đây dựng một cây harness giả rồi chạy `team.sh check` thật
    vào nó qua `HARNESS_ROOT`, và đọc mã thoát.
    """

    @staticmethod
    def _chay_check(root: Path) -> subprocess.CompletedProcess:
        team = HARNESS_THAT / "team.sh"
        return subprocess.run(
            ["bash", str(team), "check"],
            env={**os.environ, "HARNESS_ROOT": str(root)},
            capture_output=True,
            text=True,
            timeout=600,
        )

    def test_cay_du_file_va_xanh_thi_check_thoat_0(self, tmp_path):
        _harness_gia(tmp_path)
        p = self._chay_check(tmp_path)
        assert p.returncode == 0, p.stdout + p.stderr
        # Mỗi file phải hiện kèm SỐ test đã chạy. Một dấu ✓ không có số đọc y
        # hệt một file chạy đúng 0 test — mẫu cũ của team.sh chỉ khớp "tests"
        # số nhiều, nên file chạy 1 test in ra ô trống.
        cham = re.findall(r"✓ (\S+)\s+Ran (\d+) test", p.stdout)
        assert len(cham) == len(M.REQUIRED_TESTS), p.stdout
        assert all(int(n) >= 1 for _, n in cham), p.stdout

    def test_mot_file_do_thi_check_thoat_khac_0(self, tmp_path):
        """Chứng minh `check` CHẠY bộ test chứ không chỉ đếm file."""
        _harness_gia(tmp_path, do=(M.REQUIRED_TESTS[2],))
        assert self._chay_check(tmp_path).returncode != 0

    def test_thu_muc_tests_rong_thi_check_thoat_khac_0(self, tmp_path):
        """Lỗ đã đo: glob rỗng làm vòng cũ trả 0 sau khi chạy 0 test."""
        (tmp_path / "tests").mkdir()
        p = self._chay_check(tmp_path)
        assert p.returncode != 0, (
            "team.sh check nói ĐẠT trên một thư mục tests/ rỗng: " + p.stdout + p.stderr
        )

    def test_duoi_san_thi_check_thoat_khac_0(self, tmp_path):
        """Bộ test teo lại — mọi file còn lại đều xanh — vẫn phải ĐỎ."""
        _harness_gia(tmp_path)
        for name in M.REQUIRED_TESTS[2:]:
            (tmp_path / "tests" / name).unlink()
        p = self._chay_check(tmp_path)
        assert p.returncode != 0, (
            "team.sh check nói ĐẠT với 2 file test còn lại: " + p.stdout + p.stderr
        )

    def test_check_khong_dung_toi_worktree_hay_tmux(self, tmp_path):
        """`start` fetch + dựng worktree + đòi tmux; `check` phải không làm gì cả."""
        _harness_gia(tmp_path)
        assert self._chay_check(tmp_path).returncode == 0
        assert not (tmp_path / "wt").exists()
