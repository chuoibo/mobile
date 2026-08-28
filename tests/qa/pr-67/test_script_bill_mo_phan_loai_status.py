"""Script #67 phải phân biệt "cổng đã chạy và từ chối" với "cổng chưa chạy".

Lỗi được tái lập ở đây (báo cáo xanh giả của script #67): script coi mọi mã khác 200
ở lượt ảnh mờ là "từ chối, ĐẠT". Nhưng 413 `image_too_large` là từ chối vì KÍCH
THƯỚC — server chặn trước khi ảnh tới Gemini, nên cổng đang được kiểm không chạy
lần nào. Script vẫn in "XANH" và thoát 0. Cùng một dạng: 415 (sai định dạng),
502 (reader chết), và lỗi mạng (không nối được server).

Chỉ 422 mới là bằng chứng cổng đã chạy: `receipt_too_blurry` /
`receipt_unreadable` / `not_a_receipt` là phán quyết ngữ nghĩa, tức là ảnh đã
được đọc rồi mới bị từ chối. Xem `services/api/app/api/routes/receipts.py`.

Các test ở đây chạy chính script thật qua subprocess, đối diện một server giả
bằng `http.server` trong tiến trình test: không cần Gemini, không cần API thật,
không cần ảnh bill thật. Ảnh nguồn là bill tổng hợp vẽ bằng PIL trong thư mục
tạm ngoài repo (script từ chối ảnh nằm trong cây làm việc, có chủ ý).

Bằng chứng ĐỎ-trước-khi-sửa nằm trong mô tả PR: trên bản script cũ,
test_413/415/502/mixed cùng thấy exit 0 thay vì 2, và test lỗi mạng thấy exit 1
(traceback URLError) thay vì 2.
"""

from __future__ import annotations

import contextlib
import json
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "qc" / "repro_bill_mo_gemini_bia_mon.py"

pytest.importorskip("PIL", reason="script #67 cần Pillow để dựng bản mờ")

# One reading, used as the sharp ground truth. The blurred answers below differ
# from it on purpose where a test needs "money changed".
_TRUTH = {
    "items": [
        {"name": "Pho bo tai", "line_total_vnd": 65000},
        {"name": "Bun cha", "line_total_vnd": 70000},
    ],
    "items_total_vnd": 135000,
    "total_vnd": 135000,
    "totals_agree": True,
    "warnings": [],
    "confidence": 0.93,
}

_FABRICATED = {
    "items": [
        {"name": "Pho bo tai", "line_total_vnd": 65000},
        {"name": "Bun cha", "line_total_vnd": 70000},
        {"name": "Tra da", "line_total_vnd": 10000},
    ],
    "items_total_vnd": 145000,
    "total_vnd": 145000,
    "totals_agree": True,
    "warnings": [],
    "confidence": 0.91,
}


class _StubHandler(BaseHTTPRequestHandler):
    """Answers POST /receipts/scan from the plan its server carries."""

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        # Size of the image part only, the way the real server measures it:
        # it reads the upload, not the multipart envelope.
        start = body.index(b"\r\n\r\n") + 4
        end = body.rindex(b"\r\n--")
        image_len = end - start

        server = self.server
        with server.lock:
            server.calls.append(image_len)
            index = len(server.calls)
        status, payload = server.plan(index, image_len)

        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args) -> None:  # keep pytest output readable
        return


@contextlib.contextmanager
def _stub_server(plan):
    """Run the stub on a free port; `plan(index, image_len) -> (status, body)`."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    server.plan = plan
    server.calls = []
    server.lock = threading.Lock()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _sharp_then(status: int, body: dict):
    """Ground truth on call 1, then the same answer for every blurred call."""

    def plan(index: int, image_len: int):
        del image_len
        if index == 1:
            return 200, _TRUTH
        return status, body

    return plan


@pytest.fixture(scope="module")
def bill_image() -> Path:
    """A synthetic receipt-looking PNG, written outside the repo."""

    from PIL import Image, ImageDraw

    workdir = Path(tempfile.mkdtemp(prefix="qa-pr67-bill-"))
    if _REPO in workdir.resolve().parents:
        pytest.skip("TMPDIR nằm trong repo; script #67 từ chối ảnh trong cây")

    image = Image.new("RGB", (240, 340), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 224, 40), fill="black")
    for row in range(9):
        top = 64 + row * 26
        draw.rectangle((20, top, 150, top + 9), fill="black")
        draw.rectangle((170, top, 220, top + 9), fill="black")
    draw.rectangle((20, 306, 220, 314), fill="black")
    path = workdir / "bill.png"
    image.save(path)
    yield path


def _run(api_base: str, bill: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--api-base",
            api_base,
            "--bill-image",
            str(bill),
            "--runs",
            "2",
            "--blur-radius",
            "8",
            "--upscale",
            "2",
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_413_vi_kich_thuoc_khong_duoc_tinh_la_dat(bill_image):
    """413 = server chặn theo dung lượng. Gemini chưa thấy ảnh -> chưa kết luận."""

    body = {"code": "image_too_large", "detail": "Ảnh bill vượt quá giới hạn 8 MB."}
    with _stub_server(_sharp_then(413, body)) as (_server, base):
        result = _run(base, bill_image)

    assert result.returncode == 2, (
        "413 phải là KHÔNG KẾT LUẬN (2), không phải XANH (0).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "XANH" not in result.stdout


def test_415_sai_dinh_dang_khong_duoc_tinh_la_dat(bill_image):
    """415 cũng là từ chối trước khi đọc: cùng lớp xanh giả với 413."""

    body = {"code": "unsupported_image_type", "detail": "Định dạng ảnh không hỗ trợ."}
    with _stub_server(_sharp_then(415, body)) as (_server, base):
        result = _run(base, bill_image)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "XANH" not in result.stdout


def test_502_reader_chet_khong_duoc_tinh_la_dat(bill_image):
    """Reader chết thì cổng không chạy. Đọc thành 'từ chối, ĐẠT' là dối."""

    body = {"code": "receipt_reader_unavailable", "detail": "Thử lại sau."}
    with _stub_server(_sharp_then(502, body)) as (_server, base):
        result = _run(base, bill_image)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "XANH" not in result.stdout


def test_422_van_la_dat(bill_image):
    """Chống sửa quá tay: 422 vẫn phải là ĐẠT, đây mới là cổng chạy thật."""

    body = {"code": "receipt_too_blurry", "detail": "Ảnh bill quá mờ."}
    with _stub_server(_sharp_then(422, body)) as (_server, base):
        result = _run(base, bill_image)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ĐẠT" in result.stdout


def test_bia_im_lang_van_do(bill_image):
    """Chống sửa quá tay: 200 + tiền khác + không cảnh báo vẫn phải ĐỎ."""

    with _stub_server(_sharp_then(200, _FABRICATED)) as (_server, base):
        result = _run(base, bill_image)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "BỊA IM LẶNG" in result.stdout


def test_mot_lan_413_lan_at_cac_lan_422_dat(bill_image):
    """Một ô chưa quét làm cả lượt chạy không kết luận được, không phải 'đa số ĐẠT'."""

    def plan(index: int, image_len: int):
        del image_len
        if index == 1:
            return 200, _TRUTH
        if index == 2:
            return 422, {"code": "receipt_too_blurry", "detail": "mờ"}
        return 413, {"code": "image_too_large", "detail": "to quá"}

    with _stub_server(plan) as (_server, base):
        result = _run(base, bill_image)

    assert result.returncode == 2, result.stdout + result.stderr


def test_khong_noi_duoc_server_khong_phai_ket_luan_do(bill_image):
    """Server không nối được là KHÔNG CHẠY ĐƯỢC (2), không phải 'tái lập được lỗi' (1)."""

    # Bind then release: the port is guaranteed refused, so the script fails
    # fast instead of sitting on its 120s socket timeout.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]

    result = _run(f"http://127.0.0.1:{dead_port}", bill_image)

    assert result.returncode == 2, (
        "lỗi mạng phải là 2.\n" f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "Traceback" not in result.stderr


def test_tu_ha_upscale_cho_den_khi_payload_lot_qua_gioi_han(bill_image):
    """Ca #67 gọi là 'ảnh chụp tay run' phải chạy được, không phải bỏ trống.

    Mờ NHẸ làm PNG TO hơn (gradient nén kém hơn giấy phẳng), nên đúng hai mức mờ
    nguy hiểm nhất là hai mức bị 413. Script phải tự hạ độ phóng cho tới khi cả
    ảnh nét lẫn ảnh mờ lọt dưới giới hạn, rồi mới đo.
    """

    from PIL import Image, ImageFilter

    # Calibrate the stub's limit from the real rendered sizes so the case is
    # exactly "upscale 2 is too big, a smaller one fits" without a magic number.
    def _rendered_bytes(scale: float, radius: float) -> int:
        image = Image.open(bill_image).convert("RGB")
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.LANCZOS,
        )
        if radius:
            image = image.filter(ImageFilter.GaussianBlur(radius=radius))
        target = Path(tempfile.mkdtemp(prefix="qa-pr67-size-")) / "x.png"
        image.save(target)
        return target.stat().st_size

    big = _rendered_bytes(2, 8)
    small = _rendered_bytes(1, 8)
    assert small < big, "ca kiểm này cần bản nhỏ thật sự nhẹ hơn bản to"
    limit = (small + big) // 2

    def plan(index: int, image_len: int):
        if image_len > limit:
            return 413, {"code": "image_too_large", "detail": "to quá"}
        if index == 1:
            return 200, _TRUTH
        return 422, {"code": "receipt_too_blurry", "detail": "mờ"}

    with _stub_server(plan) as (server, base):
        result = _run(base, bill_image, "--max-image-bytes", str(limit))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "413" not in result.stdout, result.stdout
    assert max(server.calls) <= limit, (
        "script vẫn gửi payload vượt giới hạn thay vì tự hạ độ phóng: "
        f"{server.calls} > {limit}"
    )
