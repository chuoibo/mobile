"""`adb` treo vô hạn khi CHƯA có adb server — và mọi lệnh android- chết theo.

## Chuyện đã xảy ra, đo được 01:0x–02:2x ngày 01/09

    export PATH=$HOME/Android/Sdk/platform-tools:$PATH
    timeout 45 adb devices -l      -> rc=124, không in gì

Người báo lỗi đã thử đúng ba bước và kết luận sai địa chỉ:

  1. `adb kill-server && adb start-server`  -> start-server TỰ NÓ cũng treo
  2. `adb -P 5038 devices`  (server riêng, cổng riêng)  -> cũng treo
  3. emulator vẫn sống, console 5554 trả lời bình thường

Bước 2 làm người ta loại trừ "trạng thái cũ của server" và kết luận "hỏng nằm ở
adbd trong guest". Kết luận đó SAI, và nó sai theo hướng tốn nhất: không ai đi
sửa cái đang hỏng.

## Gốc thật: loopback của WSL2 HÚT SYN

Đo bằng socket thuần, không qua adb (01:5x ngày 01/09):

    connect 127.0.0.1:5038  -> TREO (cắt ở 3s)      ::1:5038     -> refused 0.00s
    connect 127.0.0.1:5037  -> nối được 0.00s       127.0.0.2:*  -> refused 0.00s
    mọi cổng không ai nghe trên 127.0.0.1 đều treo, TRỪ cổng nằm trong dải
    ip_local_port_range của kernel (cat /proc/sys/net/ipv4/ip_local_port_range).

    $ ip route get 127.0.0.1
    127.0.0.1 via <một gateway link-local> dev loopback0 table 127

127.0.0.1 không đi qua `lo` mà ra relay của Windows. Cổng trống thì SYN bị nuốt
— không có RST — nên `connect()` treo thay vì `ECONNREFUSED`.

adb client LUÔN thử connect vào cổng server của chính nó TRƯỚC khi quyết định có
cần bật server không. Cú thăm dò ấy treo, nên adb không bao giờ chạy tới đoạn bật
server. Vì thế cả ba triệu chứng trên là MỘT gốc — kể cả bước 2, thứ trông như
bằng chứng ngoại phạm cho adb.

Đối chứng trực tiếp trên máy thật, cùng cổng, cùng lúc:

    adb -P 5051 devices                       -> rc=124, treo 29.3s
    RD_ADB_SERVER_PORT=5051 make android-adb  -> rc=0,  7.0s, thấy 127.0.0.1:5561

## Cách file này đo

Không dựng emulator, không dựa vào việc máy chạy test có phải WSL hay không.
Cái cần gác là HÀNH VI của script khi adb hành xử như đã đo: **mọi lệnh client
treo chừng nào chưa có server đang nghe**. `adb` giả ở đây làm đúng thế, và cổng
server của nó là một socket THẬT (script hỏi `ss`, nên một marker file sẽ không
đủ).

Treo cũng là đỏ: hạn giờ của test ngắn hơn thời gian treo của adb giả.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "android_emulator.sh"

# How long the fake adb blocks a client call when no server is listening. Must
# exceed the script's per-call timeout so "the script waited it out" is a
# failure, and stay under the test timeout so a hang is still a red test.
HANG_SECONDS = 40

# Phải khớp CONG_THU_GOC trong scripts/android_emulator.sh.
CONG_THU_GOC = 5987

AVD = "rudi-test"
CONSOLE_PORT = 5602          # even, the emulator console convention
ADBD_PORT = CONSOLE_PORT + 1  # odd, what `adb connect` targets


def _free_port() -> int:
    """A port nothing is listening on, kept away from the script's own probe.

    The script probes 5987/5989/5991/5993 to detect the SYN blackhole; binding
    one of those here would make it read a live listener as "loopback healthy".
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fake_sdk(root: Path) -> Path:
    """An ANDROID_HOME whose adb reproduces the measured hang.

    Every client subcommand blocks while no server listens -- that is the bug.
    `server nodaemon` binds for real and answers from then on.
    """
    sdk = root / "sdk"
    (sdk / "platform-tools").mkdir(parents=True)
    (sdk / "emulator").mkdir(parents=True)

    adb = sdk / "platform-tools" / "adb"
    adb.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            # Parse the two flags the script actually passes.
            port=""; serial=""; args=()
            while [ $# -gt 0 ]; do
              case "$1" in
                -P) port="$2"; shift 2 ;;
                -L) port="${{2#tcp:}}"; shift 2 ;;
                -s) serial="$2"; shift 2 ;;
                *)  args+=("$1"); shift ;;
              esac
            done
            set -- "${{args[@]}}"
            echo "port=$port serial=$serial -- $*" >> "$RD_ADB_LOG"

            if [ "$1" = "server" ]; then
              # The real `adb server nodaemon` binds immediately and never
              # probes -- that is exactly why it is the way out.
              exec python3 -c '
            import socket, sys, os, time
            p = int(sys.argv[1])
            s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", p)); s.listen(8)
            open(os.environ["RD_FAKE_SERVER_MARK"], "w").write(str(os.getpid()))
            time.sleep(3600)
            ' "$port"
            fi

            # No server listening -> the client blocks. This is the whole bug:
            # adb probes its own server port before deciding to start one, and
            # on a SYN-blackholing loopback that probe never returns.
            if [ ! -s "$RD_FAKE_SERVER_MARK" ]; then
              sleep {HANG_SECONDS}
              exit 1
            fi

            case "$1 $2 $3" in
              "devices  "*|"devices"*)
                printf "List of devices attached\\n"
                [ -s "$RD_ATTACHED" ] && cat "$RD_ATTACHED"
                exit 0 ;;
            esac
            case "$1" in
              connect)
                # Only the emulator's real adbd port answers; everything else
                # is a port with nobody on it.
                if [ "$2" = "127.0.0.1:{ADBD_PORT}" ]; then
                  grep -q . "$RD_ATTACHED" 2>/dev/null || \\
                    printf "127.0.0.1:{ADBD_PORT}\\tdevice\\n" > "$RD_ATTACHED"
                  printf "connected to %s\\n" "$2"; exit 0
                fi
                printf "failed to connect to %s\\n" "$2"; exit 1 ;;
              emu)
                # Measured on the real machine: `adb emu` does NOT work over a
                # connect-attached transport (rc=1, no output).
                case "$serial" in 127.0.0.1:*) exit 1 ;; esac
                printf "{AVD}\\n"; exit 0 ;;
            esac
            case "$*" in
              *"getprop sys.boot_completed"*)      printf "1\\n"; exit 0 ;;
              *"getprop init.svc.bootanim"*)       printf "stopped\\n"; exit 0 ;;
              *"getprop ro.build.version.release"*) printf "15\\n"; exit 0 ;;
              *"getprop ro.build.version.sdk"*)    printf "35\\n"; exit 0 ;;
              *"pm list packages"*)                printf "package:host.exp.exponent\\n"; exit 0 ;;
              *10.0.2.2*)                          printf "HTTP/1.1 200 OK\\n"; exit 0 ;;
              *localhost*)                         printf "\\n"; exit 0 ;;
            esac
            exit 0
            """
        )
    )
    adb.chmod(0o755)

    emulator = sdk / "emulator" / "emulator"
    emulator.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            case "$*" in *-list-avds*) printf "{AVD}\\n"; exit 0 ;; esac
            echo "$@" >> "$RD_EMULATOR_LOG"
            sleep 600
            """
        )
    )
    emulator.chmod(0o755)
    return sdk


@pytest.fixture()
def moi_truong(tmp_path: Path):
    """Fake SDK + a live process advertising itself as this AVD's emulator."""
    sdk = _fake_sdk(tmp_path)
    proc = subprocess.Popen(
        ["sleep", "600"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    running = tmp_path / "xdg" / "avd" / "running"
    running.mkdir(parents=True)
    (running / f"pid_{proc.pid}.ini").write_text(
        f"avd.name={AVD}\nport.adb={ADBD_PORT}\nport.serial={CONSOLE_PORT}\n"
    )
    (tmp_path / "attached").write_text("")
    try:
        yield sdk, tmp_path
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
        mark = tmp_path / "server.pid"
        if mark.is_file() and mark.read_text().strip():
            try:
                os.kill(int(mark.read_text().strip()), 9)
            except (ProcessLookupError, ValueError):
                pass


def _env(tmp_path: Path, sdk: Path, extra=None):
    env = dict(os.environ)
    env.update(
        {
            "ANDROID_HOME": str(sdk),
            "XDG_RUNTIME_DIR": str(tmp_path / "xdg"),
            "RD_AVD": AVD,
            "RD_ADB_LOG": str(tmp_path / "adb.log"),
            "RD_EMULATOR_LOG": str(tmp_path / "emulator.log"),
            "RD_FAKE_SERVER_MARK": str(tmp_path / "server.pid"),
            "RD_ATTACHED": str(tmp_path / "attached"),
            "RD_ADB_SERVER_PORT": str(_free_port()),
            "RD_ADB_SERVER_LOG": str(tmp_path / "adbserver.log"),
            "RD_BOOT_TIMEOUT": "30",
        }
    )
    env.pop("ANDROID_ADB_SERVER_PORT", None)
    env.pop("ANDROID_SERIAL", None)
    if extra:
        env.update(extra)
    return env


def _run(args, tmp_path: Path, sdk: Path, *, timeout=HANG_SECONDS - 5, extra=None):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=_env(tmp_path, sdk, extra),
        timeout=timeout,
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
@pytest.mark.skipif(shutil.which("ss") is None, reason="cần ss để đọc bảng socket")
def test_check_chay_duoc_khi_chua_co_adb_server(moi_truong):
    """Cổng chính: chưa có server thì mọi lệnh adb treo — script phải tự bật server.

    ĐỎ trước bản vá: `booted_serial` gọi thẳng `adb devices`, cú đó treo, hạn giờ
    cắt, không thấy máy nào, `check` chết ở 'không có máy ảo nào boot xong'.
    """
    sdk, tmp_path = moi_truong
    started = time.monotonic()
    result = _run(["check"], tmp_path, sdk)
    elapsed = time.monotonic() - started

    assert result.returncode == 0, (
        f"check hỏng khi chưa có adb server.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert elapsed < HANG_SECONDS, (
        f"check mất {elapsed:.1f}s — nó đã ngồi chờ hết cú adb treo thay vì "
        f"bật server."
    )
    assert "sys.boot_completed 1" in result.stdout, result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
@pytest.mark.skipif(shutil.which("ss") is None, reason="cần ss để đọc bảng socket")
def test_gan_may_ao_bang_connect_khong_cho_may_quet(moi_truong):
    """Phải gắn đích danh `adb connect 127.0.0.1:<console+1>`.

    Máy quét emulator TRONG adb server dò 127.0.0.1:5555,5557,… và trên máy có
    loopback hút SYN thì mỗi cú dò treo. Đo được trên máy thật: một server mới
    bật KHÔNG thấy emulator sau 60 GIÂY, trong khi `adb connect` gắn được ngay.
    Nên bật được server thôi chưa đủ.
    """
    sdk, tmp_path = moi_truong
    result = _run(["check"], tmp_path, sdk)

    log = (tmp_path / "adb.log").read_text()
    assert f"connect 127.0.0.1:{ADBD_PORT}" in log, (
        "script không hề gọi `adb connect` — nó đang trông chờ máy quét của adb,\n"
        f"thứ đã đo được là không bao giờ tới nơi.\nadb.log:\n{log}"
    )
    assert f"127.0.0.1:{ADBD_PORT}" in result.stdout, result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
@pytest.mark.skipif(shutil.which("ss") is None, reason="cần ss để đọc bảng socket")
def test_thong_bao_bat_server_khong_lot_vao_stdout(moi_truong):
    """Câu thông báo phải ra stderr, vì nó được in TRONG `$(adbq …)`.

    Gọi thẳng `ensure_adb_server` chứ không đi qua `check`. Lý do: qua `check`,
    dòng lọt vào stdout vẫn bị `awk` của booted_serial lọc mất, nên ca test XANH
    kể cả khi bỏ hết `>&2` — bảng đột biến M3 đã bắt được đúng lỗ đó ở bản đầu
    của chính file này. Một ca không giết được đột biến của mình thì nó đang gác
    thứ khác với cái tên nó mang.

    Vẫn là chuyện thật: `boot_completed` và `avd_of_serial` bắt stdout KHÔNG lọc,
    nên một dòng thông báo lọt ra là một serial giả hoặc một 'sys.boot_completed'
    giả.
    """
    sdk, tmp_path = moi_truong
    fns = tmp_path / "fns.sh"
    src = SCRIPT.read_text()
    fns.write_text(src[: src.index('case "${1:-check}"')])

    env = _env(tmp_path, sdk)
    result = subprocess.run(
        ["bash", "-c", f'set -euo pipefail; source "{fns}"; ensure_adb_server'],
        capture_output=True, text=True, env=env, timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "", (
        "ensure_adb_server in ra STDOUT; trong `$(adbq …)` dòng này thành giá trị:\n"
        f"{result.stdout!r}"
    )
    assert "adb server" in result.stderr, (
        "không nói gì cả cũng sai — người chạy cần biết server vừa được bật.\n"
        f"stderr: {result.stderr!r}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
@pytest.mark.skipif(shutil.which("ss") is None, reason="cần ss để đọc bảng socket")
def test_khong_bat_server_thu_hai_khi_da_co_mot_cai(moi_truong):
    """Đối chứng: server đã nghe rồi thì KHÔNG bật thêm cái nữa.

    Không có ca này thì bản vá "luôn luôn bật server" cũng xanh, và trên máy
    thật nó sẽ đá vào server 5037 mà các lane khác đang dùng.
    """
    sdk, tmp_path = moi_truong
    port = _free_port()
    mark = tmp_path / "server.pid"
    srv = subprocess.Popen(
        [
            str(sdk / "platform-tools" / "adb"), "-L", f"tcp:{port}",
            "server", "nodaemon",
        ],
        env={**os.environ, "RD_FAKE_SERVER_MARK": str(mark),
             "RD_ADB_LOG": str(tmp_path / "adb.log")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if mark.is_file() and mark.read_text().strip():
                break
            time.sleep(0.1)
        assert mark.read_text().strip(), "fake server không lên"

        (tmp_path / "adb.log").write_text("")
        started = time.monotonic()
        result = _run(
            ["check"], tmp_path, sdk, extra={"RD_ADB_SERVER_PORT": str(port)}
        )
        elapsed = time.monotonic() - started

        assert result.returncode == 0, result.stdout + result.stderr
        assert mark.read_text().strip() == str(srv.pid), (
            "script đã bật ĐÈ một server thứ hai lên cổng đang có người dùng"
        )
        assert "chưa chạy" not in result.stderr, result.stderr

        # Cái ở trên KHÔNG đủ, và bảng đột biến M4 đã chứng minh: bỏ hẳn phép
        # kiểm 'đã có ai nghe chưa' vẫn xanh, vì server thứ hai không bind nổi
        # nên chết trước khi kịp ghi đè marker. Phải đo dấu vết nó ĐỂ LẠI.
        launches = (tmp_path / "adb.log").read_text().count(" -- server nodaemon")
        assert launches == 0, (
            f"script bật thêm {launches} adb server trong khi cổng đã có người "
            "nghe — mỗi cú adb sẽ đẻ một tiến trình chết yểu."
        )
        # Và mỗi lần bật lại kéo theo phép thử loopback 3s. Server đã sẵn sàng
        # thì check phải nhanh, không phải 'vẫn ra kết quả đúng, chỉ chậm'.
        assert elapsed < 15, (
            f"check mất {elapsed:.1f}s dù server đã chạy sẵn — dấu hiệu mỗi cú "
            "adb đang chạy lại phép thử loopback."
        )
    finally:
        srv.kill()
        srv.wait(timeout=10)


@pytest.mark.skipif(shutil.which("bash") is None, reason="cần bash")
@pytest.mark.skipif(shutil.which("ss") is None, reason="cần ss để đọc bảng socket")
def test_phat_hien_loopback_hut_syn_khop_voi_thuc_te(tmp_path: Path):
    """Máy đo phải khớp với máy thật đang chạy test — trên MỌI máy.

    Không khẳng định máy này có lỗi WSL hay không; khẳng định rằng câu trả lời
    của script bằng đúng câu trả lời của một phép đo độc lập. Trên Linux thật cả
    hai là 'bình thường', trên WSL mirrored cả hai là 'hút SYN'. Ca này đỏ khi
    máy đo nói dối theo một trong hai hướng.
    """
    lo = int(Path("/proc/sys/net/ipv4/ip_local_port_range").read_text().split()[0])
    # Cùng bốn cổng mà script thử (CONG_THU_GOC + 0/2/4/6). Viết dạng tính chứ
    # không dạng danh sách: repo guard đọc một dãy số liền nhau thành số tài khoản.
    probe = next(p for p in (CONG_THU_GOC + 2 * k for k in range(4)) if p < lo)

    s = socket.socket()
    s.settimeout(3.0)
    t0 = time.monotonic()
    try:
        s.connect(("127.0.0.1", probe))
        pytest.skip(f"cổng {probe} có người nghe — không đo được")
    except socket.timeout:
        that_hut_syn = True
    except OSError:
        that_hut_syn = False
    finally:
        s.close()
    do_that = time.monotonic() - t0

    sdk = _fake_sdk(tmp_path)
    (tmp_path / "attached").write_text("")
    (tmp_path / "xdg" / "avd" / "running").mkdir(parents=True)
    result = _run(["adb"], tmp_path, sdk, timeout=60)

    script_noi_hut_syn = "HÚT SYN" in result.stdout
    assert script_noi_hut_syn == that_hut_syn, (
        f"máy đo lệch với thực tế: socket thuần {'TREO' if that_hut_syn else 'bị từ chối'} "
        f"sau {do_that:.2f}s ở cổng {probe}, còn script nói "
        f"{'HÚT SYN' if script_noi_hut_syn else 'bình thường'}.\n{result.stdout}"
    )
