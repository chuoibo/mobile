"""Cổng "máy chủ đang chạy có đủ route của cây này không" phải cắn, và cắn đúng chỗ.

Ngày 2026-08-29, máy demo trên cổng 8099 phục vụ mã dựng từ TRƯỚC hai lần merge,
suốt sáu tiếng, trong khi báo khoẻ liên tục. Đo thật lúc 21:2xZ:

    cây mã (services/api tại main 0fbf500)   42 route
    máy chủ (http://127.0.0.1:8099)          37 route

    thiếu:  /places/search                            (F12, #155)
            /contexts/{context_id}/checkins           (F46, #136)
            /outings/{outing_id}/checkins             (F46)
            /outing-stops/{stop_id}/checkins          (F46)
            /outings/{outing_id}/invites/{invite_id}/revoke

Cơ chế nằm sẵn trong Compose: `api` phụ thuộc `migrate` bằng
`service_completed_successfully`. `migrate` hỏng thì `docker compose up -d`
dừng TRƯỚC khi đụng tới `api`, và container `api` CŨ vẫn giữ cổng. Đó là trạng
thái tệ nhất — một tiến trình cũ trả lời một URL mới.

Không cổng nào cũ bắt được, và lý do đáng ghi ra: mọi cổng trong repo này đọc
thứ ĐỨNG YÊN (file migration thành chuỗi, app gọi route mã nguồn có khai, ảnh
chạy non-root). Không cái nào hỏi tiến trình đang nghe cổng 8099 rằng nó là ai.
`/healthz` cố ý không chạm database nên nó trả 200 suốt — đúng, nhưng là câu
hỏi khác. `check_db_revision.sh` bắt được vế schema, nhưng `make up` chết ở
`migrate` từ lâu trước khi `make smoke` gọi tới nó.

Hai nửa đều chịu lực, cùng quy ước với test_db_revision_gate.py:

- Ca `_hong_*` chứng minh cổng **biết đỏ** — và biết phân biệt "đỏ vì lệch" với
  "đỏ vì không chạy được". Gộp hai cái đó là cách một cổng chết đọc y hệt một
  cổng đang bắt lỗi.
- Ca `_sach_*` chứng minh nó **biết im** khi đúng, kể cả khi máy chủ có THỪA
  route — máy chủ dựng từ nhánh khác là chuyện thường ngày trên máy này và bắt
  nó là dương tính giả sẽ khiến người ta tắt cổng.

Phía máy chủ dùng một HTTP server thật trong luồng riêng, không phải mock, vì
thứ cổng thật sự đọc là một response HTTP — content-type, mã lỗi, body hỏng đều
là những kiểu hỏng đã xảy ra trên máy này. Phía cây mã được thay bằng stub để
ca test không phụ thuộc vào việc hôm nay repo có bao nhiêu route; ca cuối chạy
thật trên cây và **skip có ghi log** khi thiếu FastAPI — skip không phải là xanh.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "scripts" / "check_server_routes.py"


def _load_gate():
    """Import the gate by path; it lives in scripts/ and is not a package."""
    spec = importlib.util.spec_from_file_location("check_server_routes", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


class _StubServer:
    """A real HTTP server answering a canned /openapi.json.

    Real rather than mocked on purpose: every failure this gate has to survive
    -- an HTML error page from a proxy, a 404 from a container that came up
    without the app, a truncated body -- is a property of the HTTP response,
    and a mock of `urlopen` would let all three through.
    """

    def __init__(self, body: bytes, ctype: str = "application/json", status: int = 200):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
                self.send_response(parent.status)
                self.send_header("Content-Type", parent.ctype)
                self.send_header("Content-Length", str(len(parent.body)))
                self.end_headers()
                self.wfile.write(parent.body)

            def log_message(self, *args) -> None:
                """Silence; pytest output is not a web server access log."""

        self.body = body
        self.ctype = ctype
        self.status = status
        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}"

    def __enter__(self) -> _StubServer:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def _doc(paths: list[str]) -> bytes:
    return json.dumps({"openapi": "3.1.0", "paths": {p: {} for p in paths}}).encode()


@pytest.fixture
def declared(monkeypatch):
    """Pin the code side so a case asserts the gate, not today's route count."""

    def _set(paths: list[str]) -> None:
        monkeypatch.setattr(gate, "code_paths", lambda: set(paths))

    return _set


# --------------------------------------------------------------------------
# Biết đỏ
# --------------------------------------------------------------------------


def test_hong_may_chu_thieu_route_thi_do(declared, capsys):
    """Đúng ca 29/08: máy chủ 37 route, cây khai 42."""
    declared(["/healthz", "/places/search", "/contexts/{context_id}/checkins"])
    with _StubServer(_doc(["/healthz"])) as srv:
        assert gate.main(["--url", srv.url]) == gate.EXIT_BEHIND
    err = capsys.readouterr().err
    # Tên route thiếu phải có trong thông báo. Một cổng chỉ nói "lệch" bắt người
    # đọc tự đi tìm, và người ta sẽ không tìm.
    assert "/places/search" in err
    assert "/contexts/{context_id}/checkins" in err
    assert "MÃ CŨ" in err


def test_hong_may_chu_khong_chay_thi_exit_2_chu_khong_phai_1(declared):
    """Không gọi được ≠ gọi được và thấy lệch. Gộp hai cái là cách cổng chết."""
    declared(["/healthz"])
    # Cổng đã đóng: dựng rồi tắt ngay để chắc chắn không ai nghe ở đó.
    with _StubServer(_doc(["/healthz"])) as srv:
        dead_url = srv.url
    with pytest.raises(SystemExit) as exc:
        gate.main(["--url", dead_url])
    assert exc.value.code == gate.EXIT_CANNOT_RUN


def test_hong_tra_ve_html_thi_khong_duoc_coi_la_dat(declared):
    """Trang lỗi của proxy là HTML. Parse nó ra 0 route rồi báo xanh là kiểu
    hỏng đã xảy ra với axe trên repo này — kiểm content-type trước khi tin."""
    declared(["/healthz"])
    with _StubServer(b"<html>502 Bad Gateway</html>", ctype="text/html") as srv:
        with pytest.raises(SystemExit) as exc:
            gate.main(["--url", srv.url])
    assert exc.value.code == gate.EXIT_CANNOT_RUN


def test_hong_openapi_khong_co_route_nao_thi_exit_2(declared):
    """0 route + exit 0 là hình dạng của MỌI detector chết trong repo này."""
    declared(["/healthz"])
    with _StubServer(_doc([])) as srv:
        with pytest.raises(SystemExit) as exc:
            gate.main(["--url", srv.url])
    assert exc.value.code == gate.EXIT_CANNOT_RUN


def test_hong_http_404_thi_exit_2(declared):
    """Container lên nhưng không có app: /openapi.json trả 404."""
    declared(["/healthz"])
    with _StubServer(b"not found", ctype="text/plain", status=404) as srv:
        with pytest.raises(SystemExit) as exc:
            gate.main(["--url", srv.url])
    assert exc.value.code == gate.EXIT_CANNOT_RUN


def test_hong_json_hong_thi_exit_2(declared):
    declared(["/healthz"])
    with _StubServer(b'{"paths": {', ctype="application/json") as srv:
        with pytest.raises(SystemExit) as exc:
            gate.main(["--url", srv.url])
    assert exc.value.code == gate.EXIT_CANNOT_RUN


# --------------------------------------------------------------------------
# Biết im
# --------------------------------------------------------------------------


def test_sach_khop_chinh_xac_thi_dat(declared, capsys):
    declared(["/healthz", "/places/search"])
    with _StubServer(_doc(["/healthz", "/places/search"])) as srv:
        assert gate.main(["--url", srv.url]) == gate.EXIT_OK
    out = capsys.readouterr().out
    # Đếm phải in ra kể cả khi ĐẠT: số route tụt trong khi cây lớn lên là cổng
    # này đang mù, và mù trông y hệt sạch.
    assert "2 phục vụ / 2 cây này khai" in out


def test_sach_may_chu_thua_route_khong_phai_loi(declared, capsys):
    """Máy chủ dựng từ nhánh khác là chuyện thường ngày trên máy năm worktree.
    Bắt nó là dương tính giả, và dương tính giả làm người ta tắt cổng."""
    declared(["/healthz"])
    with _StubServer(_doc(["/healthz", "/mot-route-cua-nhanh-khac"])) as srv:
        assert gate.main(["--url", srv.url]) == gate.EXIT_OK
    assert "1 route máy chủ có mà cây này không" in capsys.readouterr().out


def test_sach_url_co_dau_gach_cuoi_van_chay(declared):
    """`make smoke` ghép URL từ `docker port`; một dấu / thừa không được thành
    //openapi.json rồi 404."""
    declared(["/healthz"])
    with _StubServer(_doc(["/healthz"])) as srv:
        assert gate.main(["--url", srv.url + "/"]) == gate.EXIT_OK


# --------------------------------------------------------------------------
# Phía cây mã: chạy thật, không stub
# --------------------------------------------------------------------------


def test_cay_ma_dung_duoc_openapi_that():
    """`code_paths()` phải dựng được từ services/api thật.

    Stub ở trên chứng minh phép so sánh; ca này chứng minh vế còn lại thật sự
    đọc được ứng dụng. Thiếu FastAPI thì skip CÓ GHI LÝ DO — skip không phải
    là xanh.
    """
    if importlib.util.find_spec("fastapi") is None:
        pytest.skip("SKIP có lý do: máy này không có fastapi, không dựng được app.")
    paths = gate.code_paths()
    assert isinstance(paths, set)
    # Không ghim con số: nó tăng mỗi lần thêm route, và một test phải sửa mỗi
    # tuần là một test người ta sẽ sửa mà không đọc. Ghim thứ không được phép
    # biến mất: lát cắt dọc tiền là lý do repo này tồn tại.
    #
    # KHÔNG dùng `/healthz` — nó có `include_in_schema=False`, nên nó không nằm
    # trong openapi.json ở cả hai phía. Cổng này so hai tài liệu OpenAPI với
    # nhau, nên route bị giấu khỏi schema thì vô hình với nó ở CẢ hai vế, và
    # điều đó không sao: một route không ai khai thì cũng không ai lệch về nó.
    assert "/expenses" in paths
    assert "/batches" in paths
    assert len(paths) > 20
