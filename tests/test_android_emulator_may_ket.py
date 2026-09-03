"""`android-down` phải tắt được máy ảo ĐANG KẸT, và `android-up` không được bật đè lên nó.

## Chuyện đã xảy ra, đo được lúc 01:05–01:20 ngày 01/09

Emulator `rudi` (pid 754994) còn sống — `qemu-system-x86_64-headless -avd rudi`,
90% CPU, RSS 3.7G — nhưng guest không trả lời nữa:

    adb shell getprop sys.boot_completed   -> hết giờ 15s, không in gì
    adb devices                            -> hết giờ, và adb server kẹt theo

Chạy đúng lệnh sinh ra để dọn chuyện này:

    $ make android-down
    AVD 'rudi' không chạy — không tắt gì cả.
    rc=0

Sai, và sai theo hướng tệ nhất: thoát 0 với một câu khẳng định. Phải `kill 754994`
bằng tay mới dọn được.

## Một gốc, hai triệu chứng

`cmd_down` hỏi `serial_for_avd`, mà hàm đó chỉ nhận máy có
`sys.boot_completed = 1`. Máy kẹt không bao giờ đạt điều kiện ấy, nên với script
nó **không tồn tại**:

  * `down` từ chối tắt đúng cái máy cần tắt nhất — máy khoẻ thì tắt được, máy
    hỏng thì không.
  * `up` cũng không thấy nó, nên bật một `emulator -avd rudi` THỨ HAI đè lên
    cùng một AVD. Đo được ngay sau đó: máy mới nạp snapshot xong 10.9s rồi bị
    yêu cầu tắt (`Wait for emulator (pid 1015594) 20 seconds to shutdown
    gracefully before kill` trong /tmp/rd-emulator-rudi.log) — không ai gõ lệnh
    tắt nào. Hai instance cùng AVD giẫm lên nhau ở snapshot.

Nói gọn: script chỉ nhìn thấy máy KHOẺ. Máy sống-nhưng-hỏng thì vô hình, nên
vừa không tắt được vừa bị bật đè.

## Cách file này đo

Không dựng emulator thật. Cái cần chứng minh không phải "qemu chạy được" mà là
"script tìm ra instance qua đường NÀO". Emulator tự khai báo mình ở
`$XDG_RUNTIME_DIR/avd/running/pid_<PID>.ini` (có `avd.name=`, `port.adb=`) —
đường đó không đi qua adb nên máy kẹt vẫn khai. Test trỏ `XDG_RUNTIME_DIR` vào
thư mục tạm, dựng một tiến trình thật đóng vai qemu, và ghi file khai cho nó.

`adb` giả được đặt sleep LÂU HƠN hạn giờ của script ở đúng lệnh đã treo thật
(`shell getprop`). Nếu script gọi adb không hạn giờ thì nó treo — và treo cũng
là đỏ, đúng như hành vi thật.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "android_emulator.sh"

# Longer than the script's adb timeout, short enough that a hang shows up as a
# test timeout rather than a hung suite.
ADB_HANG_SECONDS = 25


def _fake_sdk(root: Path, *, adb_lists_device: bool) -> Path:
    """An ANDROID_HOME whose adb behaves like the wedged one did.

    `devices` still answers -- that is the whole trap, the machine looks present
    -- while `shell getprop` never returns.
    """
    sdk = root / "sdk"
    (sdk / "platform-tools").mkdir(parents=True)
    (sdk / "emulator").mkdir(parents=True)
    (sdk / "cmdline-tools" / "latest" / "bin").mkdir(parents=True)

    devices_body = (
        'printf "List of devices attached\\nemulator-5554\\tdevice\\n"'
        if adb_lists_device
        else 'printf "List of devices attached\\n"'
    )
    adb = sdk / "platform-tools" / "adb"
    adb.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            echo "$@" >> "$RD_ADB_LOG"
            args="$*"
            case "$args" in
              *"shell getprop"*) sleep {ADB_HANG_SECONDS}; exit 1 ;;
              devices*)          {devices_body}; exit 0 ;;
              *"emu avd name"*)  printf "{AVD_TEST}\\n"; exit 0 ;;
              *"emu kill"*)      exit 0 ;;
            esac
            exit 0
            """
        )
    )
    adb.chmod(0o755)

    # Records every launch. The assertion that matters for `up` is that this
    # file stays empty: a second instance on a held AVD must never start.
    emulator = sdk / "emulator" / "emulator"
    emulator.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            case "$*" in
              *-list-avds*) printf "{AVD_TEST}\\n"; exit 0 ;;
            esac
            echo "$@" >> "$RD_EMULATOR_LOG"
            sleep 600
            """
        )
    )
    emulator.chmod(0o755)
    return sdk


def _advertise(runtime_dir: Path, pid: int, avd_name: str) -> Path:
    """Write the instance file the emulator itself writes."""
    running = runtime_dir / "avd" / "running"
    running.mkdir(parents=True, exist_ok=True)
    ini = running / f"pid_{pid}.ini"
    ini.write_text(
        "grpc.port=8554\n"
        f'cmdline="qemu-system-x86_64-headless" "-avd" "{avd_name}"\n'
        f"avd.dir=/home/x/.android/avd/{avd_name}.avd\n"
        f"avd.name={avd_name}\n"
        "port.adb=5555\n"
        "port.serial=5554\n"
    )
    return ini


@pytest.fixture()
def may_ket(tmp_path: Path):
    """A live process standing in for a wedged qemu, plus its instance file."""
    proc = subprocess.Popen(
        ["sleep", "600"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        yield proc, tmp_path
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


# The AVD name every case below uses. It is deliberately NOT the name of a real
# AVD on this machine: `down` falls back to scanning the real /proc for a qemu
# process whose argv carries `-avd <name>`, so a test that names the developer's
# own AVD while that emulator is running kills the real one as collateral. It
# happened twice on 2026-09-03: the AVD shut down gracefully mid-measurement
# while this file was running, and nobody had typed a command. A per-run name
# keeps the case meaningful -- the scan still walks the real /proc -- and makes
# the only thing it can find the fake this test spawned.
AVD_TEST = f"rd-test-{os.getpid()}"


def _run(script_args, tmp_path: Path, sdk: Path, *, extra_env=None, timeout=90):
    env = dict(os.environ)
    env.update(
        {
            "ANDROID_HOME": str(sdk),
            "XDG_RUNTIME_DIR": str(tmp_path / "xdg"),
            "RD_AVD": AVD_TEST,
            "RD_ADB_LOG": str(tmp_path / "adb.log"),
            "RD_EMULATOR_LOG": str(tmp_path / "emulator.log"),
            "RD_BOOT_TIMEOUT": "3",
            "RD_KILL_TIMEOUT": "8",
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), *script_args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_down_tat_duoc_may_dang_ket(may_ket):
    """Máy sống-nhưng-chưa-boot-xong phải bị TẮT, không phải bị gọi là 'không chạy'."""
    proc, tmp_path = may_ket
    sdk = _fake_sdk(tmp_path, adb_lists_device=True)
    _advertise(tmp_path / "xdg", proc.pid, AVD_TEST)

    result = _run(["down"], tmp_path, sdk)

    assert proc.poll() is not None, (
        "android-down để nguyên tiến trình emulator đang kẹt.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "không chạy" not in result.stdout, (
        "script khai 'AVD không chạy' trong khi tiến trình của nó đang sống:\n"
        f"{result.stdout}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_down_khong_dung_may_cua_AVD_khac(may_ket):
    """Tính chất cũ phải giữ: `down` chỉ tắt AVD được hỏi.

    Bản vá lấy PID từ file khai; nếu nó lấy nhầm mọi PID thì lane này giết máy
    của lane kia — đúng cái bẫy mà cmd_down được viết ra để tránh.
    """
    proc, tmp_path = may_ket
    sdk = _fake_sdk(tmp_path, adb_lists_device=False)
    _advertise(tmp_path / "xdg", proc.pid, "rudi-cua-lane-khac")

    result = _run(["down"], tmp_path, sdk)

    assert proc.poll() is None, (
        "android-down giết máy ảo của AVD KHÁC.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.returncode == 0


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_down_khong_co_gi_thi_noi_khong_co_gi(tmp_path: Path):
    """Đối chứng ÂM: không có instance nào thì phải nói vậy, và thoát 0."""
    sdk = _fake_sdk(tmp_path, adb_lists_device=False)
    (tmp_path / "xdg" / "avd" / "running").mkdir(parents=True)

    result = _run(["down"], tmp_path, sdk)

    assert result.returncode == 0, result.stderr
    assert "không chạy" in result.stdout, result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_up_khong_bat_instance_thu_hai_len_AVD_dang_bi_giu(may_ket):
    """`up` gặp máy đang kẹt thì KHÔNG được bật cái thứ hai trên cùng AVD.

    Đây là cái đã giết emulator lúc 01:12: instance thứ hai nạp cùng snapshot
    rồi cả hai cùng chết.
    """
    proc, tmp_path = may_ket
    sdk = _fake_sdk(tmp_path, adb_lists_device=True)
    _advertise(tmp_path / "xdg", proc.pid, AVD_TEST)

    result = _run(["up"], tmp_path, sdk)

    launched = tmp_path / "emulator.log"
    assert not launched.exists() or launched.read_text().strip() == "", (
        "up đã bật thêm một emulator trên AVD đang có tiến trình giữ:\n"
        f"{launched.read_text() if launched.exists() else ''}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.returncode != 0, (
        "up phải thoát khác 0 khi AVD bị giữ bởi một máy không boot nổi.\n"
        f"stdout: {result.stdout}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_down_tat_duoc_may_KHONG_co_file_khai(tmp_path: Path):
    """Máy đang chạy mà KHÔNG có file tự khai thì vẫn phải tắt được.

    Đo được lúc 01:35 ngày 01/09, sau khi bản vá đầu đã xanh: trên máy này có
    `qemu-system-x86_64-headless -avd rudi -port 5554` (pid 1057178) đang sống,
    trong khi `/run/user/1000/avd/running/` chỉ chứa MỘT file khai mồ côi của
    một pid đã chết. Tức nguồn "file tự khai" không phải lúc nào cũng có —
    instance bật dưới `sg kvm` hoặc dưới XDG_RUNTIME_DIR khác thì không khai ở
    chỗ ta đọc.

    Nên phải hỏi thêm nguồn thứ hai: argv của chính tiến trình. Điều kiện là
    argv[0] phải LÀ binary qemu của emulator — nếu chỉ tìm chuỗi '-avd rudi'
    trong dòng lệnh thì cái shell đang chạy `android_emulator.sh` cũng khớp, và
    script sẽ tự giết mình.
    """
    # argv[0] is set independently of the binary actually executed, the way the
    # real emulator appears: /proc/<pid>/cmdline starts with the qemu binary
    # path. A `#!` script would show argv[0]="bash" and would not be a faithful
    # stand-in for what is running on this machine.
    proc = subprocess.Popen(
        [
            "/home/x/Android/Sdk/emulator/qemu/linux-x86_64/qemu-system-x86_64-headless",
            "-c",
            "import time; time.sleep(600)",
            "-avd",
            AVD_TEST,
            "-port",
            "5554",
        ],
        executable=sys.executable,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # No advertise file at all -- that is the point of this case.
        (tmp_path / "xdg" / "avd" / "running").mkdir(parents=True)
        sdk = _fake_sdk(tmp_path, adb_lists_device=False)
        time.sleep(0.5)

        result = _run(["down"], tmp_path, sdk)

        assert proc.poll() is not None, (
            "down bỏ sót emulator đang chạy vì nó không có file tự khai.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_down_khong_tu_giet_chinh_no(tmp_path: Path):
    """Đối chứng cho cách quét argv: chỉ khớp binary qemu, không khớp shell.

    `pgrep -f "\\-avd rudi"` sẽ khớp CHÍNH dòng lệnh đang chạy script (bẫy
    pgrep -f tự khớp). Nếu bản vá quét kiểu đó thì `down` tự bắn vào chân mình
    và người chạy thấy shell chết ngang chứ không thấy lỗi.
    """
    fake_dir = tmp_path / "bin"
    fake_dir.mkdir()
    # argv[0] is a shell, NOT a qemu binary -- must be ignored even though the
    # AVD name is right there in its argv.
    impostor = fake_dir / "khong-phai-qemu.sh"
    impostor.write_text("#!/usr/bin/env bash\nsleep 600\n")
    impostor.chmod(0o755)
    proc = subprocess.Popen(
        [str(impostor), "-avd", AVD_TEST],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        (tmp_path / "xdg" / "avd" / "running").mkdir(parents=True)
        sdk = _fake_sdk(tmp_path, adb_lists_device=False)
        time.sleep(0.5)

        result = _run(["down"], tmp_path, sdk)

        assert proc.poll() is None, (
            "down giết một tiến trình chỉ vì dòng lệnh của nó có '-avd rudi'.\n"
            f"stdout: {result.stdout}"
        )
        assert result.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
def test_down_khong_treo_khi_adb_khong_tra_loi(may_ket):
    """Lệnh phải có hạn giờ: adb treo thì `down` vẫn phải kết thúc.

    Thật ra đây là điều kiện để bản vá chạy được chút nào: nếu `serial_for_avd`
    gọi adb không hạn giờ thì `down` treo ngay ở đó, chưa từng tới đoạn kill.
    """
    proc, tmp_path = may_ket
    sdk = _fake_sdk(tmp_path, adb_lists_device=True)
    _advertise(tmp_path / "xdg", proc.pid, AVD_TEST)

    start = time.monotonic()
    _run(["down"], tmp_path, sdk, timeout=ADB_HANG_SECONDS + 30)
    elapsed = time.monotonic() - start

    assert elapsed < ADB_HANG_SECONDS, (
        f"down mất {elapsed:.1f}s — tức là nó đã ngồi chờ hết cú adb treo "
        f"{ADB_HANG_SECONDS}s thay vì cắt bằng hạn giờ."
    )
