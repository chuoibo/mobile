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

import argparse
import atexit
import functools
import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WATCH = REPO_ROOT / "scripts" / "demo_watch.py"


def _rev(repo: Path, ref: str) -> str | None:
    """Commit mà `ref` trỏ tới, hoặc None nếu cây này không nói được."""
    done = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    return done.stdout.strip() or None


# Mặc định của `_write_status` phải là một bản ghi GIỐNG THẬT, và `run` không bao
# giờ ghi một sha bịa: nó ghi commit mà ref vừa được phân giải. Bản đầu của
# fixture này để `"0" * 40`, và một sha không phân giải được thì mọi phép kiểm
# ràng buộc vào sha đều không có gì để bám — fixture tự bảo lãnh cho điểm mù mà
# ca test sinh ra để bắt. Cùng một cái bẫy đã ghi ở FAKE_GATE bên dưới.
#
# Nhưng sha đó KHÔNG được lấy từ `origin/main` của cây đang chạy test, và đây là
# chỗ bản đầu sai. `origin/main` là một ref ĐỘNG dùng chung: mọi worktree trên
# máy này chia nhau một thư mục .git, nên bất kỳ lane nào chạy `git fetch origin`
# — hay một lượt merge của Lead — đều dời nó GIỮA LÚC bộ test đang chạy. Hằng số
# này được chốt lúc import, còn `status` phân giải ref lúc ca test chạy: hai thời
# điểm cách nhau hàng phút trong một bộ test bốn phút rưỡi.
#
# Khi hai bên lệch nhau và phần đổi có đụng `services/api/app/api`, `status` trả
# mã 2 — và trả ĐÚNG: một bản ghi đo main ở commit trước đó thật sự không trả
# lời được câu hỏi hôm nay. Ca test đỏ không phải vì sản phẩm sai; nó đỏ vì ca
# test tự buộc mình vào một cái mốc người khác dời được. Đo lúc 02:5x trên cây
# này: origin/main nhích 33d16d8 -> 70b5b18 trong một lượt làm việc, và
# `route_surface_moved` giữa hai commit như vậy trả "28 file đã đổi".
#
# Nên cái neo là một repo riêng, có `origin/main` thật và ĐỨNG YÊN suốt lượt
# chạy. Các ca hỏi thẳng về chuyện sha lệch vẫn tự dựng repo của chúng
# (`_repo_ba_moc`) và tự truyền `--repo`; cái neo này chỉ đỡ cho phần còn lại.
@functools.lru_cache(maxsize=1)
def _neo() -> tuple[Path, str]:
    """Repo neo: `origin/main` có thật, phân giải được, và không ai dời được."""
    root = Path(tempfile.mkdtemp(prefix="demo-watch-neo-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    (root / "services/api/app/api").mkdir(parents=True)
    (root / "services/api/app/api/main.py").write_text("# neo\n", encoding="utf-8")
    _git(root, "init", "--quiet", "-b", "main", ".")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "neo")
    sha = _git(root, "rev-parse", "HEAD")
    # `status` hỏi `origin/main`, nên ref đó phải tồn tại trong repo neo.
    _git(root, "update-ref", "refs/remotes/origin/main", sha)
    return root, sha


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
        # Gọi lúc chạy chứ không chốt lúc import: `_neo` được nhớ nên vẫn là
        # cùng một repo cho cả lượt, mà `_git` thì đã có mặt khi tới đây.
        "ref_sha": _neo()[1],
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
    """`status` chạy trên repo neo, trừ khi ca test tự đưa repo của nó.

    Không để mặc định rơi vào cây thật: `status` phân giải `origin/main` trong
    repo nó được trỏ tới, và cây thật là nơi ref đó nhích dưới chân bộ test.
    """
    extra = list(extra or [])
    if "--repo" not in extra:
        extra = ["--repo", str(_neo()[0]), *extra]
    return watch.main(["status", "--state-dir", str(tmp_path), *extra])


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


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
    assert "4.0 giờ" in err, "phải nói ra nó im bao lâu"


def test_khoang_cach_duoi_mot_phut_khong_bi_lam_tron_thanh_khong(tmp_path, capsys):
    """ "cách đây 0 phút, quá hạn 0 phút" đọc như cổng hỏng, và cổng trông hỏng thì bị tắt.

    Đây là chữ thật một lượt đỏ đã in ra trước khi sửa: phút nguyên làm tròn mọi
    khoảng dưới 60 giây xuống 0, nên câu giải thích tự mâu thuẫn.
    """
    _write_status(tmp_path, ts=time.time() - 20)
    assert _status(tmp_path, ["--max-age", "5"]) == watch.EXIT_CANNOT_RUN
    err = capsys.readouterr().err
    assert "20 giây" in err and "quá hạn 5 giây" in err
    assert "0 phút" not in err


def test_ago_doc_duoc_o_ca_ba_bac():
    assert watch.ago(20) == "20 giây"
    assert watch.ago(600) == "10 phút"
    assert watch.ago(4 * 3600) == "4.0 giờ"
    assert watch.ago(-5) == "0 giây"


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


def test_khong_doi_chieu_duoc_phai_noi_LY_DO_chu_khong_phai_do_lien_ref(
    tmp_path, capsys
):
    """Mã thoát đúng mà chẩn đoán sai vẫn gửi người đọc đi sửa nhầm chỗ.

    Đo trên máy demo lúc 19:25 ngày 30/08. Lượt cron 19:20 hỏng vì `git fetch`
    đụng nhau trong `/home/lakiet/mobile` (repo dùng chung nhiều lane):

        state: "khong-doi-chieu-duoc"
        reason: "không fetch được ...: cannot lock ref 'refs/remotes/origin/main'"

    Bản ghi loại này KHÔNG có trường `ref` — lượt canh chết trước khi kịp chọn
    ref. Nhưng phép kiểm `--expect-ref` chạy TRƯỚC phép kiểm `state`, nên
    `data.get("ref")` ra `None`, lệch `origin/main`, và `status` in ra:

        phán quyết gần nhất là về 'None', không phải 'origin/main'.
        Chĩa lại lượt canh:  scripts/demo_watch.py install --apply --ref origin/main

    Lượt canh ĐANG chĩa đúng `origin/main`. Lệnh gợi ý là no-op, và lý do thật
    (fetch hỏng) bị nuốt hoàn toàn. Người vận hành chạy lệnh đó, thấy không đổi
    gì, và mất niềm tin vào chính cái cổng đang nói thật.
    """
    # Ghi qua chính `record()` mà `cmd_run` dùng, KHÔNG qua `_write_status`.
    # Helper kia bơm sẵn `ref` + `ref_sha` vào mọi bản ghi, nên nó dựng ra một
    # hình dạng sản phẩm không bao giờ sinh ra — và với nó ca này xanh sẵn,
    # trong khi máy thật đang đỏ. Bản ghi thật của một lượt hỏng có đúng sáu
    # trường: schema, ts, ts_iso, state, exit, reason.
    watch.record(
        watch.status_path(tmp_path),
        state=watch.STATE_CANNOT,
        code=watch.EXIT_CANNOT_RUN,
        detail={
            "reason": "không fetch được 'origin': "
            "cannot lock ref 'refs/remotes/origin/main'"
        },
    )
    assert "ref" not in json.loads(
        watch.status_path(tmp_path).read_text(encoding="utf-8")
    ), "fixture hỏng: bản ghi thật của lượt hỏng KHÔNG có trường ref"

    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN

    err = capsys.readouterr().err
    assert "cannot lock ref" in err, (
        "lý do thật của lượt canh bị nuốt — bản ghi có ghi, status không in ra"
    )
    assert "về 'None'" not in err, (
        "bản ghi 'không đối chiếu được' không có ref; báo nó là 'phán quyết về "
        "nhánh None' là chẩn đoán sai"
    )
    assert "install --apply --ref" not in err, (
        "gợi ý chĩa lại lượt canh là no-op ở đây: nó đã chĩa đúng origin/main"
    )


def test_state_la_khong_bao_gio_la_dat(tmp_path, capsys):
    """Một `state` bản này không biết đọc là "không biết", và không biết ≠ đạt.

    Bản ghi có thể do một bản demo_watch mới hơn viết ra, hoặc do người sửa tay.
    Nhánh mặc định phải đi về mã 2. Đây là chỗ dễ trượt thành `return EXIT_OK`
    khi ai đó dọn if/elif.
    """
    _write_status(tmp_path, ts=time.time() - 60, state="mot-trang-thai-tuong-lai")
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN
    assert "KHÔNG ĐỐI CHIẾU ĐƯỢC" in capsys.readouterr().err


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


# --- status: phán quyết về ref NÀO -----------------------------------------
#
# Sự cố 30/08 18:08 (bug-180816). Máy demo 8099 phục vụ 65 route trong khi
# `origin/main` khai 69 — thiếu đúng bốn route album kỷ niệm và gợi ý ngữ cảnh
# mà #301 vừa đưa vào main. Bản ghi DUY NHẤT trên máy lúc đó, còn nguyên trong
# ~/.cache/mobile-demo-watch/status.json, là:
#
#     {"state": "khop", "ref": "devops/may-demo-theo-main",
#      "ref_routes": 65, "served": 65, "missing": []}
#
# `status` đọc bản ghi đó và in "KHỚP — 65 route", mã 0. Nó ĐÚNG: máy demo khớp
# đúng cái nhánh nó được đem ra so. Nhưng câu người đọc tưởng mình vừa được trả
# lời là "máy demo có khớp MAIN không", và hai câu đó khác nhau kể từ lúc nhánh
# kia bị main bỏ lại.
#
# Nên đây là lỗ hổng thứ hai, độc lập với việc crontab rỗng: cắm lịch mà trỏ
# `--ref` vào một nhánh đang mở thì lượt canh chạy đều mỗi 10 phút, ghi "khop"
# mỗi 10 phút, và không bao giờ đỏ — một canh gác còn sống, còn ghi, còn tươi,
# đo sai đối tượng. Ngưỡng quá hạn không bắt được nó vì bản ghi luôn mới.


def test_phan_quyet_ve_nhanh_khac_khong_phai_phan_quyet_ve_main(tmp_path, capsys):
    """Bản ghi TƯƠI, state "khop", nhưng về một nhánh khác — không phải là đạt.

    Đây là hình dạng thật của bug-180816, dựng lại nguyên văn. Trước bản sửa ca
    này ra mã 0: `cmd_status` in `data["ref"]` ra màn hình nhưng không so nó với
    cái gì, nên mọi ref đều được nhận. Một trường được IN không phải là một
    trường được KIỂM.
    """
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_MATCH,
        ref="devops/may-demo-theo-main",
        ref_sha="29bd93f0e7f8fb1836ef29ec2f0dadf9864ffa65",
        ref_routes=65,
        served=65,
    )
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN
    err = capsys.readouterr().err
    assert "devops/may-demo-theo-main" in err, (
        "phải nêu ref đã đo, để người đọc thấy nó lệch đâu"
    )
    assert "origin/main" in err, "và nêu ref lẽ ra phải đo"


def test_ref_dung_thi_van_dat(tmp_path):
    """Đối chứng bắt buộc: bản sửa không được biến mọi bản ghi thành đỏ.

    Không có ca này thì `return EXIT_CANNOT_RUN` vô điều kiện cũng làm ca trên
    xanh — và một cổng đỏ với mọi đầu vào bị tắt trong một ngày.
    """
    _write_status(tmp_path, ts=time.time() - 60, state=watch.STATE_MATCH)
    assert _status(tmp_path) == watch.EXIT_OK


def test_ref_khac_ten_nhung_cung_commit_van_la_phan_quyet_ve_main(tmp_path):
    """Đo bằng SHA tuyệt đối của main thì vẫn là đo main, dù tên ref không khớp.

    `demo_watch.py run` ghi lại cả `ref` lẫn `ref_sha`. Cron mặc định trỏ
    `origin/main`, nhưng một lượt chạy tay bằng `--ref <sha>` vẫn trả lời đúng
    câu hỏi nếu sha đó CHÍNH LÀ main lúc này. So tên mà không xét sha thì ca đó
    đỏ oan, và một cổng đỏ oan cũng bị tắt như một cổng câm.

    Sha lấy từ repo neo chứ không từ cây thật, vì "main lúc này" của cây thật
    đổi giữa lúc bộ test chạy — xem ghi chú ở `_neo`. Ca này hỏi về việc so TÊN
    với so SHA, không hỏi gì về lịch sử của repo này, nên buộc nó vào lịch sử
    đó chỉ thêm một đường đỏ oan chứ không thêm phép kiểm nào.
    """
    sha = _neo()[1]
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_MATCH,
        ref=sha,
        ref_sha=sha,
    )
    assert _status(tmp_path) == watch.EXIT_OK


def test_any_ref_la_loi_thoat_co_y_chu_khong_phai_mac_dinh(tmp_path):
    """Bỏ kiểm ref phải là một câu người ta gõ ra, không phải điều xảy ra khi im lặng.

    Mặc định của mọi cổng trong repo này là phía nghiêm; `--any-ref` tồn tại cho
    lượt chạy tay đang chĩa vào một nhánh đang mở, và nó hiện diện trong dòng
    lệnh nên đọc log là thấy.
    """
    # `ref_sha` phải là một commit KHÁC main, nếu không thì ca này đo nhầm luật:
    # "cùng commit, khác tên" đã được nhận có chủ ý ngay ở ca trên, nên bản ghi
    # mang đúng sha của main sẽ xanh vì lý do đó chứ không vì `--any-ref`.
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_MATCH,
        ref="nhanh/dang-mo",
        ref_sha="29bd93f0e7f8fb1836ef29ec2f0dadf9864ffa65",
    )
    assert _status(tmp_path) == watch.EXIT_CANNOT_RUN
    assert _status(tmp_path, ["--any-ref"]) == watch.EXIT_OK


def test_lech_van_la_lech_du_ref_dung(tmp_path):
    """Kiểm ref chen thêm một mã 2 vào đường đi — nó không được nuốt mã 1.

    Gộp "đo nhầm chỗ" với "đo đúng chỗ và thấy lệch" là mất đúng thông tin cần
    để biết phải dựng lại máy demo hay phải sửa dòng cron.
    """
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_DIFFERS,
        exit=1,
        missing=["/contexts/{context_id}/albums"],
    )
    assert _status(tmp_path) == watch.EXIT_DIFFERS


# --- phán quyết về main CŨ: tươi, đúng tên, và vẫn không trả lời câu hỏi ---


def _repo_ba_moc(root: Path) -> tuple[str, str, str]:
    """Một repo có `main` đi qua ba mốc; trả về sha của A, B, C.

    A→B chỉ đổi tài liệu, A→C thêm một file route. Hai đường đó phải được
    `status` đối xử KHÁC nhau, nên chúng phải là commit thật: phép kiểm đọc
    `git diff` giữa hai sha chứ không đọc con số nào trong bản ghi.
    """
    (root / "services/api/app/api/routes").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    _git(root, "init", "--quiet", "-b", "main", ".")
    (root / "services/api/app/api/routes/expenses.py").write_text("# route\n")
    (root / "docs/ghi-chu.md").write_text("mốc A\n")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "A")
    a = _git(root, "rev-parse", "HEAD")
    (root / "docs/ghi-chu.md").write_text("mốc B — chỉ tài liệu\n")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "B chỉ đụng tài liệu")
    b = _git(root, "rev-parse", "HEAD")
    (root / "services/api/app/api/routes/albums.py").write_text("# reel\n")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "C thêm route reel")
    c = _git(root, "rev-parse", "HEAD")
    return a, b, c


def test_phan_quyet_ve_main_CU_khong_phai_phan_quyet_ve_main_BAY_GIO(tmp_path, capsys):
    """Bản ghi tươi, state "khop", ref ĐÚNG là 'main' — và vẫn phải ra mã 2.

    Đây là bug-231718 dựng lại nguyên văn. `status` chỉ so TÊN ref; khi tên
    khớp thì nó bỏ qua `ref_sha` hoàn toàn. Nên một phán quyết đo main ở commit
    TRƯỚC khi route reel merge vẫn in "KHỚP — 76 route" và thoát 0, trong khi
    main đã khai 77. Đo trên cây thật lúc 00:5x: bản ghi ref_sha=66a6990 (trước
    #352) ra `rc=0` với đúng câu "KHỚP 0 giây trước — 76 route".

    Nó còn IN cái sha cũ ra giữa dòng xanh — một trường được in không phải là
    một trường được kiểm, y hệt hình dạng của bug-180816 ngay bên trên.
    """
    root = tmp_path / "repo"
    root.mkdir()
    a, _b, c = _repo_ba_moc(root)
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_MATCH,
        ref="main",
        ref_sha=a,
        ref_routes=76,
        served=76,
    )
    rc = _status(tmp_path, ["--repo", str(root), "--expect-ref", "main"])
    assert rc == watch.EXIT_CANNOT_RUN, (
        "phán quyết đo main tại A, nhưng main giờ ở C và C thêm một route — "
        "bản ghi đó không trả lời được câu hỏi hôm nay"
    )
    err = capsys.readouterr().err
    assert a[:12] in err, "phải nêu commit đã đo"
    assert c[:12] in err, "và commit main đang đứng, để người đọc thấy nó lệch đâu"


def test_main_nhich_ma_be_mat_route_khong_doi_thi_van_dat(tmp_path):
    """Đối chứng bắt buộc: không được biến mọi lần main nhích thành đỏ.

    Không có ca này thì "ref_sha != main bây giờ -> mã 2" vô điều kiện cũng làm
    ca trên xanh — và cổng sẽ đỏ sau MỌI merge, kể cả merge tài liệu, tức đỏ
    gần như liên tục trong một ngày đội merge mỗi vài phút. Một cổng đỏ với mọi
    đầu vào bị tắt trong một ngày, và lúc đó nó không gác gì nữa.

    Phán quyết đo main tại A vẫn trả lời đúng câu hỏi về main tại B, vì giữa A
    và B không có file nào dưới bề mặt route đổi.
    """
    root = tmp_path / "repo"
    root.mkdir()
    a, b, _c = _repo_ba_moc(root)
    _git(root, "reset", "--hard", "--quiet", b)
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_MATCH,
        ref="main",
        ref_sha=a,
        ref_routes=76,
        served=76,
    )
    assert _status(tmp_path, ["--repo", str(root), "--expect-ref", "main"]) == (
        watch.EXIT_OK
    )


def test_ref_sha_cay_nay_khong_co_thi_khong_phai_dat(tmp_path, capsys):
    """Không phân giải được sha đã đo thì KHÔNG so được, và không so được ≠ đạt.

    Hay gặp thật: cron canh từ một checkout đã fetch, lane chạy `make gate` từ
    worktree fetch lâu rồi. Trả 0 ở đây là đọc "cây tôi thiếu commit đó" thành
    "máy demo đúng".
    """
    root = tmp_path / "repo"
    root.mkdir()
    _repo_ba_moc(root)
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_MATCH,
        ref="main",
        ref_sha="0" * 40,
    )
    rc = _status(tmp_path, ["--repo", str(root), "--expect-ref", "main"])
    assert rc == watch.EXIT_CANNOT_RUN
    assert "fetch" in capsys.readouterr().err, "phải nói ra cách gỡ"


def test_lech_ve_main_cu_van_la_lech_chu_khong_bi_nuot_thanh_ma_2(tmp_path):
    """Phép kiểm sha mới chen thêm một mã 2 vào đường đi — không được nuốt mã 1.

    Cùng lý do như `test_lech_van_la_lech_du_ref_dung`: gộp "đo chỗ cũ" với "đo
    và thấy thiếu route" là mất đúng thông tin cần để biết phải dựng lại máy
    demo hay chỉ cần đo lại.
    """
    root = tmp_path / "repo"
    root.mkdir()
    a, b, _c = _repo_ba_moc(root)
    _git(root, "reset", "--hard", "--quiet", b)
    _write_status(
        tmp_path,
        ts=time.time() - 60,
        state=watch.STATE_DIFFERS,
        exit=1,
        ref="main",
        ref_sha=a,
        missing=["/contexts/{context_id}/albums/{outing_id}/reel"],
    )
    assert _status(tmp_path, ["--repo", str(root), "--expect-ref", "main"]) == (
        watch.EXIT_DIFFERS
    )


# --- canh gác phải có chỗ gọi, nếu không nó là đồ trang trí ----------------


def test_gate_co_chang_goi_canh_gac(tmp_path):
    """`scripts/gate.sh` phải có chặng `demo-watch`, và nó phải chạy mặc định.

    Cả sự cố này lẫn sự cố 30/08 nó sinh ra để bắt đều KHÔNG phải lỗi của cổng:
    cổng chạy đúng cả hai lần. Lỗi là không ai gọi nó. `check_demo_matches_main.py`
    có `make demo-check` — một chỗ gọi TAY, chỉ được gõ khi đã có người nghi ngờ.
    `demo_watch.py status` thì trước bản sửa này không có chỗ gọi nào.

    `--list` in ra từ mảng STAGES, tức là chính danh sách được chạy khi không
    chọn chặng nào — nên có tên trong đó nghĩa là chạy mặc định, không phải một
    chặng phải nhớ mà bật.
    """
    listed = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "gate.sh"), "--list"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert listed.returncode == 0, listed.stderr
    assert "demo-watch" in listed.stdout, (
        "gate.sh không có chặng nào đọc phán quyết canh gác — "
        "đúng hình dạng đã để máy demo lệch 4 route mà cả đội không thấy"
    )


# --- run: giữ nguyên ba trạng thái, và ghi lại chúng ----------------------


def test_run_khop_ghi_lai_phan_quyet(repo, tmp_path):
    state = tmp_path / "state"
    assert _run(repo, state) == watch.EXIT_OK
    data = json.loads(watch.status_path(state).read_text(encoding="utf-8"))
    assert data["state"] == watch.STATE_MATCH
    assert data["served"] == 7
    assert data["ref_routes"] == 7
    # Ghi xong thì `status` phải đọc lại được — hai nửa nói cùng một ngôn ngữ.
    # `--expect-ref main`: repo giả này chỉ có nhánh `main`, và `_run` đo đúng
    # nhánh đó. Mặc định của `status` là `origin/main` vì đó là ref thật của
    # máy demo; ở đây phải nói ra ref của fixture, chứ không nới mặc định.
    #
    # `--repo` cũng phải là repo giả: `status` phân giải ref trong cây được chỉ,
    # và hỏi cây KHÁC cái cây vừa được đo là so hai commit không liên quan gì
    # nhau. Thiếu nó thì `main` ở đây là nhánh `main` của chính repo này.
    assert _status(state, ["--repo", str(repo), "--expect-ref", "main"]) == (
        watch.EXIT_OK
    )


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
    assert _status(state, ["--repo", str(repo), "--expect-ref", "main"]) == (
        watch.EXIT_DIFFERS
    )


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


def test_dong_cron_tro_vao_checkout_on_dinh_chu_khong_phai_cay_dang_dung(repo):
    """Dòng cron sống lâu; cây worktree của một lane thì không.

    Nếu nó tự ghim `__file__` thì lịch chạy sẽ trỏ vào worktree của người vừa
    cài, và worktree đó bị xoá là canh gác câm — im lặng đọc y hệt "vẫn ổn".
    """
    block = watch.cron_block(
        argparse.Namespace(url="http://127.0.0.1:8099", repo=str(repo))
    )
    assert str(repo / "scripts" / "demo_watch.py") in block
    assert str(WATCH) not in block, "đang ghim chính cây đang đứng vào crontab"


def test_dong_cron_mang_dung_nhip_va_dung_ref_duoc_chon(repo):
    """Nhịp và ref phải đi vào dòng cron, không bị hằng số mặc định đè lên.

    Cài `* * * * *` mà báo `*/10 * * * *` là cách người ta tin vào một nhịp
    không tồn tại — bản đầu của file này in ra đúng như thế.
    """
    block = watch.cron_block(
        argparse.Namespace(
            url="http://127.0.0.1:8099",
            repo=str(repo),
            schedule="* * * * *",
            ref="devops/nhanh-dang-mo",
        )
    )
    assert block.count("* * * * * ") == 1
    assert watch.CRON_SCHEDULE not in block
    assert "--ref devops/nhanh-dang-mo" in block


def test_khong_cam_lich_tro_vao_file_khong_ton_tai(repo, capsys):
    """Cắm cron trỏ vào file không có = 10 phút một lần hỏng mà không ai đọc."""
    (repo / "scripts" / "demo_watch.py").unlink(missing_ok=True)
    code = watch.main(["install", "--repo", str(repo), "--apply"])
    assert code == watch.EXIT_CANNOT_RUN
    assert "không tồn tại" in capsys.readouterr().err


def test_go_khoi_khong_dung_toi_dong_cua_nguoi_khac():
    other = "0 3 * * * /usr/bin/backup.sh"
    block = f"{watch.CRON_BEGIN}\n*/10 * * * * canh\n{watch.CRON_END}"
    assert watch.strip_block(f"{other}\n{block}") == other
    assert watch.strip_block(other) == other
