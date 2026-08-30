"""Cổng "máy demo có đúng bằng main không" phải cắn cả HAI hướng, và biết im khi khớp.

Ngày 2026-08-30 máy demo trên cổng 8099 phục vụ 58 route trong khi `origin/main`
khai 62. Bốn route thiếu đều là tính năng thật:

    /areas                                          F45
    /contexts/{context_id}/budget                   F34
    /contexts/{context_id}/messages/{message_id}/expense-draft   F24
    /screenshots/scan                               F26

Cổng anh em `check_server_routes.py` ĐÃ chạy trên chính máy đó và ĐẠT:

    {"declared": 58, "served": 58, "missing": [], "extra": []}   exit 0

Nó không sai — nó trả lời đúng câu nó hỏi ("máy chủ có đủ route của CÂY NÀY
không"). Nhưng bộ container dựng từ `/home/lakiet/mobile`, và cây đó đứng sau
`origin/main` 16 commit. Hai vế của phép so là **cùng một cây cũ**, nên phép so
không thể đỏ. Đó là xanh-by-construction: một phép kiểm đọc cả hai vế từ một
nguồn thì không bao giờ đỏ được, và nó đọc y hệt một phép kiểm đang đạt.

Vì vậy cổng mới neo vế tham chiếu vào `origin/main`, không vào cây đang đứng.

Quy ước hai nửa, giống test_server_routes_gate.py:

- Ca `_do_*` chứng minh cổng **biết đỏ**, và phân biệt "đỏ vì lệch" (mã 1) với
  "đỏ vì không chạy được" (mã 2). Gộp hai cái đó là cách một cổng chết đọc y
  hệt một cổng đang bắt lỗi.
- Ca `_xanh_*` chứng minh nó **biết im** khi hai bên bằng nhau — một cổng kêu
  cả lúc đúng sẽ bị tắt, và một cổng bị tắt không gác gì.

Vế `origin/main` được thay bằng stub để ca test không phụ thuộc vào việc hôm nay
main có bao nhiêu route; vế máy chủ là một HTTP server thật trong luồng riêng,
vì thứ cổng đọc là một response HTTP thật — content-type sai, 404, body hỏng đều
là kiểu hỏng đã xảy ra trên máy này và một mock của `urlopen` sẽ cho qua hết.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "scripts" / "check_demo_matches_main.py"


def _load_gate():
    """Import the gate by path; it lives in scripts/ and is not a package."""
    spec = importlib.util.spec_from_file_location("check_demo_matches_main", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


class _StubServer:
    """A real HTTP server answering a canned /openapi.json."""

    def __init__(self, body: bytes, ctype: str = "application/json", status: int = 200):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - name fixed by the base class
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
def ref_is(monkeypatch):
    """Pin the `origin/main` side so a case asserts the gate, not today's count."""

    def _set(paths: list[str]) -> None:
        monkeypatch.setattr(gate, "ref_paths", lambda ref: set(paths))

    return _set


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """`git fetch` is not this file's subject; every case runs as if it worked."""
    monkeypatch.setattr(gate, "fetch_ref", lambda ref: None)


def _run(url: str, extra: list[str] | None = None) -> int:
    try:
        return gate.main(["--url", url, *(extra or [])])
    except SystemExit as exc:
        return int(exc.code)


# --- đỏ: cổng biết cắn ---------------------------------------------------


def test_do_khi_demo_thieu_route_cua_main(ref_is, capsys):
    """Đúng lỗi 30/08: demo đứng sau main. Bốn route thật, tên thật."""
    thieu = [
        "/areas",
        "/contexts/{context_id}/budget",
        "/contexts/{context_id}/messages/{message_id}/expense-draft",
        "/screenshots/scan",
    ]
    ref_is(["/healthz", "/expenses", *thieu])
    with _StubServer(_doc(["/healthz", "/expenses"])) as server:
        assert _run(server.url) == gate.EXIT_DIFFERS
    err = capsys.readouterr().err
    for path in thieu:
        assert path in err, f"cổng đỏ mà không nói thiếu {path} thì người đọc mù"
    assert "THIẾU" in err


def test_do_khi_demo_thua_route_main_khong_co(ref_is, capsys):
    """Hướng còn lại: demo dựng từ nhánh chưa merge, khoe thứ chưa tồn tại.

    Đây là hướng mà cổng anh em cố ý THA — và tha đúng, cho stack dùng chung.
    Trên máy demo thì nó là lỗi: leader sẽ thấy một tính năng biến mất ở lần
    dựng lại kế tiếp.
    """
    ref_is(["/healthz"])
    with _StubServer(_doc(["/healthz", "/tinh-nang-cua-nhanh-chua-merge"])) as server:
        assert _run(server.url) == gate.EXIT_DIFFERS
    err = capsys.readouterr().err
    assert "THỪA" in err
    assert "/tinh-nang-cua-nhanh-chua-merge" in err


def test_do_ca_hai_huong_cung_luc(ref_is):
    """Dựng từ một nhánh vừa cũ vừa lệch — thiếu và thừa không loại trừ nhau."""
    ref_is(["/healthz", "/chi-main-co"])
    with _StubServer(_doc(["/healthz", "/chi-demo-co"])) as server:
        assert _run(server.url) == gate.EXIT_DIFFERS


# --- đỏ vì KHÔNG CHẠY ĐƯỢC: mã khác, không được lẫn với mã 1 --------------


def test_do_khac_ma_khi_may_chu_tra_zero_route(ref_is):
    """0 route + exit 0 là hình dạng của mọi detector chết trong repo này."""
    ref_is(["/healthz"])
    with _StubServer(_doc([])) as server:
        assert _run(server.url) == gate.EXIT_CANNOT_RUN


def test_do_khac_ma_khi_may_chu_tra_html(ref_is):
    """Một container lên nhưng không có app trả trang lỗi HTML, không phải JSON."""
    ref_is(["/healthz"])
    with _StubServer(b"<html>502</html>", ctype="text/html") as server:
        assert _run(server.url) == gate.EXIT_CANNOT_RUN


def test_do_khac_ma_khi_khong_co_may_chu(ref_is):
    """Không ai nghe cổng: phải là 'không chạy được', không phải 'khớp'."""
    ref_is(["/healthz"])
    server = _StubServer(_doc(["/healthz"]))
    dead = server.url  # never started, so the port is closed
    assert _run(dead, ["--timeout", "1"]) == gate.EXIT_CANNOT_RUN


def test_ba_ma_thoat_la_ba_gia_tri_khac_nhau():
    """Gộp 'lệch' với 'không chạy được' là cách cổng chết đọc như cổng đang bắt lỗi."""
    assert len({gate.EXIT_OK, gate.EXIT_DIFFERS, gate.EXIT_CANNOT_RUN}) == 3


# --- xanh: cổng biết im --------------------------------------------------


def test_xanh_khi_bang_dung_bang(ref_is, capsys):
    ref_is(["/healthz", "/expenses", "/areas"])
    with _StubServer(_doc(["/areas", "/expenses", "/healthz"])) as server:
        assert _run(server.url) == gate.EXIT_OK
    out = capsys.readouterr().out
    # The count is printed on the pass path too: a number that falls while the
    # tree grows is this gate going blind, and blind looks exactly like clean.
    assert "3" in out


# --- cấu tạo: vế tham chiếu KHÔNG được là cây đang đứng -------------------


def test_ve_tham_chieu_doc_tu_ref_chu_khong_phai_cay_dang_dung():
    """Lỗi gốc 30/08 là hai vế cùng một nguồn. Chặn nó bằng cấu tạo.

    `ref_paths` phải nhận một ref và dựng cây riêng cho ref đó. Nếu nó đọc
    `services/api` của worktree đang đứng thì cổng này thừa hưởng đúng điểm mù
    của cổng anh em, và không ca hành vi nào ở trên phát hiện được — cả hai vế
    sẽ chỉ cùng sai một cách im lặng.
    """
    import inspect

    src = inspect.getsource(gate.ref_paths)
    assert "worktree" in src, "ref_paths phải dựng worktree riêng cho ref"
    assert 'REPO_ROOT / "services"' not in src, (
        "ref_paths đang đọc services/api của cây đang đứng — đó đúng là điểm mù "
        "mà cổng này sinh ra để bịt"
    )
