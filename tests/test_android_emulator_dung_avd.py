"""Mọi lệnh chẩn đoán phải trả lời về ĐÚNG AVD được hỏi, không phải máy đầu danh sách.

## Chuyện đã xảy ra (FAIL #505, đo tại e7644ad)

Máy tác giả có đúng MỘT emulator, nên lỗi vô hình. QA đo bằng adb giả và bắt được:

    ./android_emulator.sh check                             -> EXIT=0, emulator-5554
    RD_AVD=avd-khong-he-ton-tai ./android_emulator.sh check  -> EXIT=0, emulator-5554
    diff hai đầu ra                                          -> GIỐNG HỆT TỪNG BYTE (723 bytes)

AVD thứ hai không tồn tại trên máy đó. Cùng một câu trả lời cho hai câu hỏi khác
nhau nghĩa là cái cổng không hề đọc câu hỏi.

Gốc: `cmd_check`, `cmd_doctor`, `cmd_install_expo` gọi `booted_serial()` — hàm
trả về emulator đầu tiên trong `adb devices` có `sys.boot_completed=1`, không lọc
theo AVD. Cùng file, `cmd_down` dùng `serial_for_avd()` và lọc đúng; chú thích
ngay trên nó mô tả chính lớp lỗi này. Bản vá dừng lại một hàm trước cái cổng.

Hậu quả tệ nhất không phải màu đỏ giả mà màu XANH giả, và `test_ca2_*` dưới đây
là hình dạng chính xác của nó: cùng MỘT máy ảo hỏng, cùng MỘT cổng — một mình thì
ĐỎ, đứng cạnh máy của lane khác thì XANH. Máy hỏng không đổi, chỉ hàng xóm đổi.

## Cách file này đo, và vì sao không dựng emulator thật

Cái cần chứng minh không phải "qemu chạy được" mà "script chọn máy theo tiêu chí
NÀO". Hai emulator thật tốn ~2 phút, 4GB RAM và một /dev/kvm — và bằng chứng chỉ
chạy được trên một máy thì không phải bằng chứng. Nên `adb` và `emulator` được
thay bằng bản giả khai được bất kỳ đội hình nào, qua đúng cái cửa `ANDROID_HOME`
mà chính script mở ra. Không sửa script đang bị đo một byte nào.

## Phép đo này KHÔNG được phép phụ thuộc vào máy đang chạy

`adbq` gọi `ensure_adb_server`, hàm đó hỏi `port_dang_nghe $ADB_SERVER_PORT`
(mặc định 5037). Trên máy CÓ adb server thật, câu đó đúng ngay; trên máy KHÔNG
có, script đi bật server và bản adb giả không bao giờ nghe — cùng một SHA ra hai
kết quả tuỳ máy. Đó đúng là lỗi đã làm PR #487 bị trả về, nên ở đây cổng tự dựng
một socket ĐANG NGHE của riêng nó và trỏ `RD_ADB_SERVER_PORT` vào đó. Không đụng
tới adb server thật của máy, và không đọc trạng thái của nó.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "android_emulator.sh"

# Đội hình khai qua FAKE_EMUS: "<serial>:<avd>:<boot 0|1>:<api ok|dead>", cách
# nhau bằng khoảng trắng, theo đúng thứ tự `adb devices` sẽ in ra.
LANE_KHAC = "emulator-5554:avd-lane-khac-rd505:1:ok"
CUA_TOI_CHUA_BOOT = "emulator-5556:avd-cua-toi-rd505:0:ok"
CUA_TOI_MAT_MANG = "emulator-5556:avd-cua-toi-rd505:1:dead"
CUA_TOI_KHOE = "emulator-5556:avd-cua-toi-rd505:1:ok"

AVD_CUA_TOI = "avd-cua-toi-rd505"
AVD_LANE_KHAC = "avd-lane-khac-rd505"

# adb giả. Phải bỏ qua `-P <cổng>` mà `adbq` luôn truyền: bản giả nào chỉ biết
# `-s` sẽ rơi hết vào nhánh mặc định và im lặng trả rỗng, và một máy đo im lặng
# đọc y hệt một sản phẩm hỏng.
FAKE_ADB = r"""#!/usr/bin/env bash
set -uo pipefail

field() {  # field <serial> <chỉ số 2..4>
    local e s a b p
    for e in ${FAKE_EMUS:-}; do
        IFS=: read -r s a b p <<< "$e"
        if [ "$s" = "$1" ]; then
            case "$2" in 2) printf '%s' "$a";; 3) printf '%s' "$b";; 4) printf '%s' "$p";; esac
            return 0
        fi
    done
    return 1
}

serial=""
while :; do
    case "${1:-}" in
        -P) shift 2 ;;
        -s) serial="$2"; shift 2 ;;
        *)  break ;;
    esac
done
sub="${1:-}"; shift || true

case "$sub" in
  devices)
    echo "List of devices attached"
    for e in ${FAKE_EMUS:-}; do
        IFS=: read -r s _ _ _ <<< "$e"
        printf '%s\tdevice\n' "$s"
    done
    ;;
  emu)
    [ "${1:-} ${2:-}" = "avd name" ] && { field "$serial" 2; echo; echo OK; }
    ;;
  connect|reverse) : ;;
  shell)
    rest="$*"
    case "$rest" in
      "getprop sys.boot_completed")        [ "$(field "$serial" 3)" = "1" ] && echo 1 ;;
      "getprop init.svc.bootanim")         echo stopped ;;
      "getprop ro.build.version.release")  echo 15 ;;
      "getprop ro.build.version.sdk")      echo 35 ;;
      "pm list packages")                  echo package:host.exp.exponent ;;
      *" nc "*)
          host="$(sed -E 's/.* nc ([^ ]+) ([0-9]+).*/\1/' <<< "$rest")"
          if [ "$host" = "localhost" ]; then
              echo "nc: connect: Connection refused"
          elif [ "$(field "$serial" 4)" = "ok" ]; then
              echo "HTTP/1.1 200 OK"
          fi
          ;;
    esac
    ;;
esac
exit 0
"""

FAKE_EMULATOR = r"""#!/usr/bin/env bash
if [ "${1:-}" = "-list-avds" ]; then
    for e in ${FAKE_EMUS:-}; do IFS=: read -r _ a _ _ <<< "$e"; echo "$a"; done
fi
exit 0
"""


@pytest.fixture()
def sdk(tmp_path: Path) -> Path:
    """An ANDROID_HOME whose adb answers for whatever fleet FAKE_EMUS declares."""
    root = tmp_path / "sdk"
    (root / "platform-tools").mkdir(parents=True)
    (root / "emulator").mkdir(parents=True)
    adb = root / "platform-tools" / "adb"
    adb.write_text(FAKE_ADB)
    adb.chmod(0o755)
    emulator = root / "emulator" / "emulator"
    emulator.write_text(FAKE_EMULATOR)
    emulator.chmod(0o755)
    return root


@pytest.fixture()
def cong_adb_server():
    """A really-listening socket, so `ensure_adb_server` is satisfied by construction.

    Reading the machine's real adb server instead would make the same SHA produce
    different verdicts on different machines -- see the module docstring.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    try:
        yield sock.getsockname()[1]
    finally:
        sock.close()


def _run(
    args, *, sdk: Path, tmp_path: Path, fleet: str, avd: str, cong: int, timeout=90
):
    env = dict(os.environ)
    env.pop("ANDROID_SERIAL", None)
    env.update(
        {
            "ANDROID_HOME": str(sdk),
            "XDG_RUNTIME_DIR": str(tmp_path / "xdg"),
            "FAKE_EMUS": fleet,
            "RD_AVD": avd,
            "RD_ADB_SERVER_PORT": str(cong),
            "RD_BOOT_TIMEOUT": "3",
        }
    )
    env.pop("ANDROID_ADB_SERVER_PORT", None)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _serial_da_do(stdout: str) -> str:
    """The serial `check` says it measured -- the claim under test, not a side effect."""
    for line in stdout.splitlines():
        if line.strip().startswith("serial "):
            return line.split("serial", 1)[1].strip()
    return ""


needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
needs_ss = pytest.mark.skipif(
    shutil.which("ss") is None, reason="cần ss — script đọc bảng socket bằng nó"
)
gate = pytest.mark.parametrize  # noqa: F841  (đọc rõ hơn ở chỗ dùng)


# ------------------------------------------------------------------ CANARY --
# Hai ca dưới đây không kiểm sản phẩm, chúng kiểm CHÍNH MÁY ĐO. Một máy đo
# luôn-xanh và một máy đo luôn-đỏ đều in ra những con số trông hợp lý.


@needs_bash
@needs_ss
def test_canary_doi_hinh_lanh_thi_XANH(sdk: Path, tmp_path: Path, cong_adb_server: int):
    """Máy đo phải ra nổi màu xanh. Không thì mọi màu đỏ dưới đây vô nghĩa."""
    r = _run(
        ["check"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=CUA_TOI_KHOE,
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    assert r.returncode == 0, (
        "máy đo không xanh nổi trên một đội hình lành — hỏng ở máy đo, không ở sản phẩm.\n"
        f"stdout: {r.stdout}\nstderr: {r.stderr}"
    )
    assert _serial_da_do(r.stdout) == "emulator-5556", r.stdout


@needs_bash
@needs_ss
def test_canary_may_mat_mang_dung_MOT_MINH_thi_DO(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """Máy đo phải bắt được ca 'boot rồi nhưng không tới được API' khi nó đứng một mình.

    Đây là nửa còn lại của cặp đối chứng với `test_ca2_*`: cùng một máy ảo hỏng,
    cùng một cổng. Nếu ca này không đỏ thì ca kia không chứng minh được gì.
    """
    r = _run(
        ["check"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=CUA_TOI_MAT_MANG,
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    assert r.returncode != 0, (
        "máy đo in XANH cho một máy ảo không tới được API — máy đo mù.\n"
        f"stdout: {r.stdout}"
    )


# -------------------------------------------------------------------- CHECK --


@needs_bash
@needs_ss
def test_ca1_may_toi_hoi_chua_boot_xong_thi_DO(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """Máy lane khác khoẻ không được che cho việc máy của mình chưa qua logo."""
    r = _run(
        ["check"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=f"{LANE_KHAC} {CUA_TOI_CHUA_BOOT}",
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    assert r.returncode != 0, (
        f"check XANH trong khi '{AVD_CUA_TOI}' chưa boot xong — nó trả lời bằng "
        f"{_serial_da_do(r.stdout)!r} (máy của {AVD_LANE_KHAC}).\n{r.stdout}"
    )
    assert _serial_da_do(r.stdout) != "emulator-5554", (
        "check đo lên máy của lane khác:\n" + r.stdout
    )


@needs_bash
@needs_ss
def test_ca2_may_hong_cua_toi_XANH_len_chi_vi_co_hang_xom(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """Cùng máy ảo hỏng, cùng cổng: một mình ĐỎ (canary 2), có hàng xóm thì XANH.

    Máy hỏng không đổi — chỉ hàng xóm đổi. Một cổng mà kết luận phụ thuộc vào
    việc lane khác có đang chạy emulator hay không thì không gác được gì.
    """
    r = _run(
        ["check"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=f"{LANE_KHAC} {CUA_TOI_MAT_MANG}",
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    assert r.returncode != 0, (
        f"check XANH cho '{AVD_CUA_TOI}' chỉ vì {AVD_LANE_KHAC} đứng cạnh; "
        f"cùng máy ảo đó đứng một mình thì ĐỎ.\n{r.stdout}"
    )


@needs_bash
@needs_ss
def test_check_do_dung_may_duoc_hoi_khi_ca_hai_deu_khoe(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """Khẳng định DƯƠNG: không chỉ 'đỏ đúng lúc' mà còn 'đo đúng máy'.

    Chỉ dựa vào mã thoát thì một bản vá kiểu 'hai máy thì luôn đỏ' cũng qua được.
    """
    r = _run(
        ["check"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=f"{LANE_KHAC} {CUA_TOI_KHOE}",
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert _serial_da_do(r.stdout) == "emulator-5556", (
        f"được hỏi về '{AVD_CUA_TOI}' (emulator-5556) nhưng đo lên "
        f"{_serial_da_do(r.stdout)!r}:\n{r.stdout}"
    )


@needs_bash
@needs_ss
def test_avd_khong_ton_tai_khong_duoc_tra_loi_giong_avd_co_that(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """Chính phép đo QA dùng để mở phiếu: hai câu hỏi khác nhau, một câu trả lời.

    Trên bản cũ, đầu ra của hai lệnh dưới đây GIỐNG HỆT NHAU TỪNG BYTE dù AVD thứ
    hai không tồn tại trên máy.
    """
    chung = dict(sdk=sdk, tmp_path=tmp_path, fleet=LANE_KHAC, cong=cong_adb_server)
    co_that = _run(["check"], avd=AVD_LANE_KHAC, **chung)
    bia_dat = _run(["check"], avd="avd-khong-he-ton-tai-abc123", **chung)

    assert co_that.returncode == 0, f"{co_that.stdout}\n{co_that.stderr}"
    assert bia_dat.returncode != 0, (
        "check XANH cho một AVD không tồn tại:\n" + bia_dat.stdout
    )
    assert co_that.stdout != bia_dat.stdout, (
        "hai AVD khác nhau (một có thật, một bịa) cho cùng một đầu ra từng byte — "
        "cổng không hề đọc câu hỏi:\n" + co_that.stdout
    )


# ------------------------------------------------------------------- DOCTOR --


@needs_bash
@needs_ss
def test_doctor_khong_khai_may_lane_khac_thanh_may_cua_minh(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """`doctor` được hỏi về AVD nào thì phải nói về AVD đó.

    Đội hình đầy đủ vẫn được liệt kê ở phần `== adb ==` — chỗ đó liệt kê là đúng.
    Cái sai là dòng khai theo AVD lại điền serial của máy khác.
    """
    r = _run(
        ["doctor"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=f"{LANE_KHAC} {CUA_TOI_CHUA_BOOT}",
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    dong = [
        ln for ln in r.stdout.splitlines() if "đã boot" in ln and "đang giữ" not in ln
    ]
    assert dong, "doctor không còn dòng khai máy đã boot:\n" + r.stdout
    assert "emulator-5554" not in dong[0], (
        f"doctor khai máy của {AVD_LANE_KHAC} dưới nhãn máy đã boot, trong khi được "
        f"hỏi về '{AVD_CUA_TOI}' (máy này chưa boot xong):\n{dong[0]}"
    )


# -------------------------------------------------------------- INSTALL-EXPO --


@needs_bash
@needs_ss
def test_install_expo_khong_cham_vao_may_cua_lane_khac(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """Máy mình chưa boot thì phải dừng, không được quay sang máy lane khác.

    Bản cũ hỏi `booted_serial`, thấy emulator-5554, đọc `pm list packages` của
    NÓ và kết luận 'Expo Go đã có sẵn' — thoát 0 mà không cài gì cho ai.
    """
    r = _run(
        ["install-expo"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=f"{LANE_KHAC} {CUA_TOI_CHUA_BOOT}",
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    assert r.returncode != 0, (
        f"install-expo thoát 0 dựa trên máy của {AVD_LANE_KHAC}:\n{r.stdout}"
    )
    assert AVD_CUA_TOI in r.stderr, (
        "câu chẩn đoán không nêu tên AVD được hỏi:\n" + r.stderr
    )


# ---------------------------------------------------------------- ĐỐI CHỨNG --


@needs_bash
@needs_ss
def test_khong_co_may_nao_thi_DO_va_NOI_RA(
    sdk: Path, tmp_path: Path, cong_adb_server: int
):
    """Đỏ mà câm còn tệ hơn đỏ mà sai: `set -e` từng giết script ngay tại dòng gán."""
    r = _run(
        ["check"],
        sdk=sdk,
        tmp_path=tmp_path,
        fleet=CUA_TOI_CHUA_BOOT,
        avd=AVD_CUA_TOI,
        cong=cong_adb_server,
    )
    assert r.returncode != 0, r.stdout
    assert (r.stdout + r.stderr).strip(), (
        "check ĐỎ nhưng in 0 byte trên cả stdout lẫn stderr — không ai biết tìm từ đâu"
    )
    assert AVD_CUA_TOI in r.stderr, r.stderr


@needs_bash
@needs_ss
def test_khong_con_ham_tra_loi_may_nao_cung_duoc(sdk: Path):
    """`booted_serial` phải BIẾN MẤT, không phải chỉ mất người gọi.

    Chừng nào hàm đó còn nằm đấy, lệnh con tiếp theo sẽ lại gọi nó — và cái cổng
    lại mù đúng như cũ mà không ai sửa gì. Ca này gác cấu tạo, các ca trên gác
    hành vi; hành vi hồi quy được bằng cách thêm một người gọi mới.
    """
    nguon = SCRIPT.read_text()
    than = "\n".join(ln for ln in nguon.splitlines() if not ln.lstrip().startswith("#"))
    assert "booted_serial" not in than, (
        "scripts/android_emulator.sh vẫn còn booted_serial trong phần thân — "
        "hàm chọn 'emulator đầu danh sách' không được phép tồn tại trong file này"
    )


@needs_bash
def test_script_bien_dich_duoc():
    """Rẻ nhất, chạy trước mọi thứ: một lỗi cú pháp làm mọi ca trên đỏ vì lý do sai."""
    r = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=30
    )
    assert r.returncode == 0, r.stderr


def test_khong_doc_cay_ngoai_repo():
    """Cổng phải đo CHÍNH cây nó nằm trong.

    PR #487 bị trả về vì một cổng đọc cây ngoài repo: cùng một SHA ra `1 failed`
    rồi `0 failed` tuỳ máy. Ca này ghim đường dẫn về đúng repo chứa file test.
    """
    assert SCRIPT.is_file(), f"không thấy {SCRIPT}"
    goc = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if goc.returncode == 0:
        assert Path(goc.stdout.strip()).resolve() == REPO, (
            f"test đang đo {SCRIPT}, không nằm trong repo của chính nó ({REPO})"
        )


# Giữ `textwrap` được dùng: đọc rõ hơn khi ai đó thêm ca mới dựng script inline.
assert textwrap is not None
