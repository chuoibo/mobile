"""Canh gác định kỳ phải biết nói "tôi đã chết", chứ không chỉ "không có vấn đề".

`check_demo_matches_main.py` trả lời đúng câu của nó, nhưng ngày 30/08 không ai
gọi nó: máy demo phục vụ 58 route trong khi `origin/main` khai 62, suốt 16
commit, và chỗ duy nhất phát hiện ra là một người mở demo lên rồi ăn 404.

`demo_watch.py` là chỗ gọi định kỳ. Nó thêm một kiểu hỏng mà lượt gọi tay không
có: **chính nó dừng**. Crontab bị xoá, máy khởi động lại, checkout bị xoá — lúc
đó nó không in gì, và "không in gì" là đúng thứ một canh gác khoẻ mạnh cũng in.
Mọi detector chết trong repo này đều mặc bộ đồ đó: máy quét URL thiếu Chrome trả
`[]` + mã 0, `ruff_pinned.sh` in đường dẫn rồi mã 0.

Nên file này chia hai nửa:

- Nửa `run`: một lượt canh ghi lại phán quyết, và giữ nguyên ba mã thoát của
  cổng nó gọi. Gộp "lệch" với "không chạy được" là cách cổng chết đọc như cổng
  đang bắt lỗi.
- Nửa `status`: đọc phán quyết đó và coi **im lặng là thất bại**. Ba ca quan
  trọng nhất trong file này là "chưa từng chạy", "chạy lâu rồi" và "bản ghi
  hỏng" — cả ba phải ra mã 2, vì cả ba đều là lúc ta KHÔNG biết máy demo thế nào.

Không ca nào ở đây đóng băng đồng hồ. Mốc thời gian được ghi thẳng vào bản ghi
dưới dạng epoch quá khứ, vì một đồng hồ đứng yên làm đúng loại đột biến mà các
ca này sinh ra để bắt (dời ngưỡng quá hạn) trở thành vô hình.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WATCH = REPO_ROOT / "scripts" / "demo_watch.py"


def _load():
    spec = importlib.util.spec_from_file_location("demo_watch", WATCH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


watch = _load()


# Một "cổng" giả: in JSON ra stdout rồi thoát bằng mã được nhúng sẵn. Đủ để
# `demo_watch` phân biệt ba trạng thái mà không cần dựng FastAPI hay máy chủ.
#
# Dòng người-đọc SAU khối JSON không phải trang trí: cổng thật in đúng như vậy
# (`--json` in JSON rồi vẫn in câu tổng kết). Bản đầu của fixture này chỉ in mỗi
# JSON, nên bộ test XANH trong khi chạy thật ra "KHỚP ... None route" — `json.loads`
# trên cả luồng ném lỗi và bản ghi rỗng bị đọc thành "không thiếu route nào".
# Fixture không giống thật thì nó bảo lãnh cho chính điểm mù của mình.
FAKE_GATE = """#!/usr/bin/env python3
import json, sys
print(json.dumps({{"ref_routes": {routes}, "served": {served},
                   "missing": {missing}, "extra": []}}))
print("Máy demo khớp: {served} route, không thiếu, không thừa.")
print({stderr!r}, file=sys.stderr)
raise SystemExit({code})
"""


def _write_status(tmp_path: Path, **fields) -> Path:
    """Ghi một bản ghi hợp lệ, cho phép ca test đè từng trường."""
    payload = {
        "schema": watch.SCHEMA,
        "ts": time.time(),
        "ts_iso": "2026-08-30T09:00:00+00:00",
        "state": watch.STATE_MATCH,
        "exit": 0,
        "url": "http://127.0.0.1:8099",
        "ref": "origin/main",
        "ref_sha": "0" * 40,
        "ref_routes": 65,
        "served": 65,
        "missing": [],
        "extra": [],
    }
    payload.update(fields)
    path = watch.status_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _status(tmp_path: Path, extra: list[str] | None = None) -> int:
    return watch.main(["status", "--state-dir", str(tmp_path), *(extra or [])])


def _git(repo: Path, *args: str) -> None:
    done = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Một repo thật có `main` mang một cổng giả — `run` dựng worktree thật."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    _git(root, "init", "--quiet", "-b", "main", ".")
    gate = root / watch.GATE_RELPATH
    gate.write_text(
        FAKE_GATE.format(routes=7, served=7, missing="[]", stderr="", code=0),
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "cổng giả trên main")
    return root


def _run(repo: Path, state: Path, extra: list[str] | None = None) -> int:
    return watch.main(
        [
            "run",
            "--repo",
            str(repo),
            "--state-dir",
            str(state),
            "--ref",
            "main",
            "--no-fetch",
            *(extra or []),
        ]
    )


# --- status: im lặng KHÔNG phải là đạt ------------------------------------


def test_chua_tung_chay_khong_phai_la_dat(tmp_path, capsys):
    """Không có bản ghi nào = không ai biết máy demo thế nào. Mã 2, không phải 0.

    Đây là hình dạng của mọi cổng chết trong repo: không in gì, mã 0, và đọc y
    hệt một cổng vừa chạy xong sạch sẽ.
    """
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN
    err = capsys.readouterr().err
    assert "chưa từng chạy" in err, "phải nói ra là chưa chạy, đừng im rồi trả mã"


def test_qua_han_la_canh_gac_da_chet_chu_khong_phai_demo_dung(tmp_path, capsys):
    """Bản ghi cũ hơn ngưỡng: canh gác đã dừng, và ta KHÔNG biết demo ra sao.

    Phán quyết ghi trong file là "khớp" — ca này đỏ đúng vì nó quá hạn, không
    vì nội dung. Nếu ngưỡng bị gỡ, ca này xanh trong khi canh gác đã chết hàng
    giờ, và đó chính là lỗ hổng cần gác.
    """
    _write_status(tmp_path, ts=time.time() - 4 * 3600, state=watch.STATE_MATCH)
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN
    err = capsys.readouterr().err
    assert "240 phút" in err, "phải nói ra nó im bao lâu"


def test_moi_va_khop_thi_dat(tmp_path):
    """Cổng kêu cả lúc đúng sẽ bị tắt, và cổng bị tắt không gác gì."""
    _write_status(tmp_path, ts=time.time() - 60, state=watch.STATE_MATCH)
    assert _status(tmp_path) == watch.EXIT_OK


def test_ngay_truoc_nguong_van_dat_ngay_sau_thi_khong(tmp_path):
    """Ngưỡng phải là một ngưỡng thật, không phải "cũ thì đỏ" chung chung.

    Hai điểm hai bên cùng một ngưỡng, chỉ khác dấu — nếu phép so bị đảo hoặc bỏ,
    một trong hai vế đổi màu.
    """
    _write_status(tmp_path, ts=time.time() - 100)
    assert _status(tmp_path, ["--max-age", "200"]) == watch.EXIT_OK
    assert _status(tmp_path, ["--max-age", "50"]) == watch.EXIT_CANNOT_RUN


def test_lech_moi_van_la_lech(tmp_path, capsys):
    """Lệch phải ra mã 1 và nêu tên route, để người đọc biết dựng lại cái gì."""
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_DIFFERS,
        exit=1,
        missing=["/areas", "/screenshots/scan"],
    )
    assert _status(tmp_path) == watch.EXIT_DIFFERS
    err = capsys.readouterr().err
    assert "/areas" in err and "/screenshots/scan" in err


def test_luot_canh_khong_doi_chieu_duoc_khong_bi_doc_thanh_khop(tmp_path):
    """Lượt canh gần nhất tự nói "tôi không so được" — kế thừa mã 2, không phải 0."""
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_CANNOT,
        exit=2,
        reason="máy chủ chưa chạy",
    )
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN


def test_ban_ghi_hong_khong_bao_gio_la_dat(tmp_path):
    """JSON hỏng và schema lạ đều là "không biết", và không biết thì không đạt."""
    path = watch.status_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ đây không phải json", encoding="utf-8")
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN

    _write_status(tmp_path, schema=watch.SCHEMA + 99)
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN

    _write_status(tmp_path, ts="hôm qua")
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN


def test_ba_ma_thoat_la_ba_gia_tri_khac_nhau():
    assert len({watch.EXIT_OK, watch.EXIT_DIFFERS, watch.EXIT_CANNOT_RUN}) == 3


# --- run: giữ nguyên ba trạng thái, và ghi lại chúng ----------------------


def test_run_khop_ghi_lai_phan_quyet(repo, tmp_path):
    state = tmp_path / "state"
    assert _run(repo, state) == watch.EXIT_OK
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert data["state"] == watch.STATE_MATCH
    assert data["served"] == 7
    assert data["ref_routes"] == 7
    # Ghi xong thì `status` phải đọc lại được — hai nửa nói cùng một ngôn ngữ.
    assert _status(state) == watch.EXIT_OK


def test_run_lech_giu_ma_1_va_giu_ten_route(repo, tmp_path):
    """Cổng bên trong trả mã 1 thì `run` cũng phải mã 1, kèm route thiếu."""
    (repo / watch.GATE_RELPATH).write_text(
        FAKE_GATE.format(
            routes=9,
            served=7,
            missing='["/areas", "/posts"]',
            stderr="THIẾU 2 route",
            code=1,
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "--quiet", "-am", "cổng giả: lệch")
    state = tmp_path / "state"
    assert _run(repo, state) == watch.EXIT_DIFFERS
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert data["state"] == watch.STATE_DIFFERS
    assert data["missing"] == ["/areas", "/posts"]
    assert _status(state) == watch.EXIT_DIFFERS


def test_run_cong_khong_chay_duoc_ra_ma_2_chu_khong_phai_1(repo, tmp_path):
    """Cổng trả mã 2 ("không so được") không được tụt xuống thành "lệch"."""
    (repo / watch.GATE_RELPATH).write_text(
        FAKE_GATE.format(
            routes=0, served=0, missing="[]", stderr="máy chủ chưa chạy", code=2
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "--quiet", "-am", "cổng giả: không so được")
    state = tmp_path / "state"
    assert _run(repo, state) == watch.EXIT_CANNOT_RUN
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert data["state"] == watch.STATE_CANNOT
    assert _status(state) == watch.EXIT_CANNOT_RUN


def test_cong_khong_tra_json_thi_khong_duoc_khai_la_khop(repo, tmp_path):
    """Mã 0 mà không đọc được số route KHÔNG được ghi thành "khớp".

    Đây là lỗi thật của chính file này ở bản đầu: cổng in JSON rồi in thêm một
    câu tổng kết, `json.loads` trên cả luồng ném lỗi, bản ghi rỗng, và nó in ra
    "KHỚP — phục vụ đúng None route" kèm mã 0. Không đếm được thì không khẳng
    định được; một phán quyết không có mẫu số là phán quyết của một phép đo đã
    ngừng đo.
    """
    (repo / watch.GATE_RELPATH).write_text(
        "#!/usr/bin/env python3\nprint('xong, mọi thứ ổn')\n", encoding="utf-8"
    )
    _git(repo, "commit", "--quiet", "-am", "cổng giả: mã 0 nhưng không có JSON")
    state = tmp_path / "state"
    assert _run(repo, state) == watch.EXIT_CANNOT_RUN
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert data["state"] == watch.STATE_CANNOT
    assert _status(state) == watch.EXIT_CANNOT_RUN


def test_doc_JSON_dung_khi_co_chu_bam_theo_sau():
    """Cổng thật in JSON rồi in tiếp; phải đọc được vế đầu, không được bỏ cuộc."""
    assert watch.parse_report('{"served": 65}\nMáy demo khớp: 65 route.') == {
        "served": 65
    }
    assert watch.parse_report("") is None
    assert watch.parse_report("không có json ở đây") is None
    # Một mảng JSON hợp lệ vẫn không phải báo cáo — None, không phải {}.
    assert watch.parse_report("[1, 2, 3]") is None


def test_ref_chua_co_cong_thi_noi_ra_chu_khong_im(repo, tmp_path):
    """Chưa merge thì chưa canh được — và phải nói thế, không phải trả 0.

    Đây là trạng thái thật cho tới khi PR này vào main.
    """
    _git(repo, "rm", "--quiet", watch.GATE_RELPATH)
    _git(repo, "commit", "--quiet", "-m", "main chưa có cổng")
    state = tmp_path / "state"
    assert _run(repo, state) == watch.EXIT_CANNOT_RUN
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert watch.GATE_RELPATH in data["reason"]


def test_ref_la_nhanh_local_co_dau_gach_khong_bi_doc_thanh_ten_remote(repo, tmp_path):
    """`devops/canh-may-demo` là tên NHÁNH, không phải remote `devops`.

    Tách chuỗi ở dấu `/` rồi fetch vế đầu sẽ báo "không đối chiếu được" cho một
    ref hoàn toàn phân giải được — tức là cổng tự làm mình mù đúng ở đường mà
    người ta dùng khi PR còn đang mở.
    """
    _git(repo, "branch", "devops/canh-may-demo")
    assert watch.remote_for("devops/canh-may-demo", repo) == "origin"
    assert watch.remote_for("origin/main", repo) == "origin"


def test_khong_fetch_duoc_thi_khong_so_voi_ref_cu(repo, tmp_path):
    """Repo không có remote: fetch hỏng, và so với một ref cũ là đúng lỗi gốc."""
    state = tmp_path / "state"
    assert (
        watch.main(
            ["run", "--repo", str(repo), "--state-dir", str(state), "--ref", "main"]
        )
        == watch.EXIT_CANNOT_RUN
    )
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert "fetch" in data["reason"]


# --- cấu tạo: cổng phải chạy từ CÂY REF, không từ cây đang đứng -----------


def test_chay_cong_cua_ref_chu_khong_phai_ban_trong_cay_dang_dung(repo, tmp_path):
    """Yêu cầu của Lead, đo bằng hành vi chứ không bằng đọc chữ trong file.

    Lỗi gốc 30/08 là một checkout cũ (`/home/lakiet/mobile`, sau main 16 commit).
    Một dòng cron trỏ vào đường dẫn nào đó trên đĩa là đúng loại thứ một tháng
    sau vẫn còn trỏ chỗ cũ. Nên logic kiểm phải lấy từ `--ref`, không lấy từ cây
    gọi nó.

    Cách đo: hai bản cổng KHÁC NHAU về mã thoát. Bản trên `main` nói "khớp" (0);
    bản trong cây làm việc, chưa commit, nói "lệch" (1). `git worktree add` chỉ
    lấy bản đã commit, nên:

        chạy bản của ref        -> 0
        chạy bản của cây đứng   -> 1

    Một con số phân biệt được hai đường, và nó không thể đúng vì tình cờ.
    """
    (repo / watch.GATE_RELPATH).write_text(
        FAKE_GATE.format(
            routes=9,
            served=7,
            missing='["/chi-co-o-cay-ban"]',
            stderr="bản của cây đang đứng",
            code=1,
        ),
        encoding="utf-8",
    )
    # Cố ý KHÔNG commit: main vẫn giữ bản mã 0.
    state = tmp_path / "state"
    assert _run(repo, state) == watch.EXIT_OK, (
        "đã chạy cổng của cây đang đứng thay vì của ref — đúng điểm mù cần bịt"
    )
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert data["missing"] == [], "phán quyết đến từ bản chưa commit"


def test_run_khong_de_lai_worktree_rac(repo, tmp_path):
    """Worktree rò rỉ làm LƯỢT SAU đỏ trên một đường dẫn không còn tồn tại."""
    state = tmp_path / "state"
    for _ in range(3):
        assert _run(repo, state) == watch.EXIT_OK
    listed = subprocess.run(
        ["git", "worktree", "list"], cwd=str(repo), capture_output=True, text=True
    )
    assert listed.stdout.count("\n") == 1, f"còn worktree sót lại:\n{listed.stdout}"


# --- crontab: sửa lịch của người khác là cách mục khác biến mất -----------


def test_go_khoi_khong_dung_toi_dong_cua_nguoi_khac():
    other = "0 3 * * * /usr/bin/backup.sh"
    block = f"{watch.CRON_BEGIN}\n*/10 * * * * canh\n{watch.CRON_END}"
    assert watch.strip_block(f"{other}\n{block}") == other
    assert watch.strip_block(other) == other
