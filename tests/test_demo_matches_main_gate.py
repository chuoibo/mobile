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
import subprocess
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


@pytest.fixture
def no_fetch(monkeypatch):
    """Neutralise `git fetch` for the cases whose subject is the comparison.

    Deliberately NOT `autouse`. It used to be, and that silently disarmed the
    whole fetch half of the gate: every case ran with `fetch_ref` replaced, so
    deleting the call site, or letting a failed fetch continue anyway, both left
    the file at 9 passed. qa-tt-0033 counted those as two of four surviving
    mutants. Fetch is exercised for real in `test_fetch_*` below; a case that
    wants it out of the way now has to ask.
    """
    monkeypatch.setattr(gate, "fetch_ref", lambda ref: None)


def _run(url: str, extra: list[str] | None = None) -> int:
    try:
        return gate.main(["--url", url, *(extra or [])])
    except SystemExit as exc:
        return int(exc.code)


# --- đỏ: cổng biết cắn ---------------------------------------------------


def test_do_khi_demo_thieu_route_cua_main(ref_is, no_fetch, capsys):
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


def test_do_khi_demo_thua_route_main_khong_co(ref_is, no_fetch, capsys):
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


def test_do_ca_hai_huong_cung_luc(ref_is, no_fetch):
    """Dựng từ một nhánh vừa cũ vừa lệch — thiếu và thừa không loại trừ nhau."""
    ref_is(["/healthz", "/chi-main-co"])
    with _StubServer(_doc(["/healthz", "/chi-demo-co"])) as server:
        assert _run(server.url) == gate.EXIT_DIFFERS


# --- đỏ vì KHÔNG CHẠY ĐƯỢC: mã khác, không được lẫn với mã 1 --------------


def test_do_khac_ma_khi_may_chu_tra_zero_route(ref_is, no_fetch):
    """0 route + exit 0 là hình dạng của mọi detector chết trong repo này."""
    ref_is(["/healthz"])
    with _StubServer(_doc([])) as server:
        assert _run(server.url) == gate.EXIT_CANNOT_RUN


def test_do_khac_ma_khi_may_chu_tra_html(ref_is, no_fetch):
    """Một container lên nhưng không có app trả trang lỗi HTML, không phải JSON."""
    ref_is(["/healthz"])
    with _StubServer(b"<html>502</html>", ctype="text/html") as server:
        assert _run(server.url) == gate.EXIT_CANNOT_RUN


def test_do_khac_ma_khi_khong_co_may_chu(ref_is, no_fetch):
    """Không ai nghe cổng: phải là 'không chạy được', không phải 'khớp'."""
    ref_is(["/healthz"])
    server = _StubServer(_doc(["/healthz"]))
    dead = server.url  # never started, so the port is closed
    assert _run(dead, ["--timeout", "1"]) == gate.EXIT_CANNOT_RUN


def test_ba_ma_thoat_la_ba_gia_tri_khac_nhau():
    """Gộp 'lệch' với 'không chạy được' là cách cổng chết đọc như cổng đang bắt lỗi."""
    assert len({gate.EXIT_OK, gate.EXIT_DIFFERS, gate.EXIT_CANNOT_RUN}) == 3


# --- xanh: cổng biết im --------------------------------------------------


def test_xanh_khi_bang_dung_bang(ref_is, no_fetch, capsys):
    ref_is(["/healthz", "/expenses", "/areas"])
    with _StubServer(_doc(["/areas", "/expenses", "/healthz"])) as server:
        assert _run(server.url) == gate.EXIT_OK
    out = capsys.readouterr().out
    # The count is printed on the pass path too: a number that falls while the
    # tree grows is this gate going blind, and blind looks exactly like clean.
    assert "3" in out


# --- cấu tạo: vế tham chiếu KHÔNG được là cây đang đứng -------------------


def _git(repo: Path, *args: str) -> None:
    done = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr.strip()}"


def _fake_api(repo: Path, paths: list[str]) -> None:
    """Write the smallest thing `ref_paths` will render: an `app` with .openapi().

    The gate renders with `from app.api.main import app; app.openapi()`. It never
    asks whether `app` is a FastAPI instance, so a plain object is enough and the
    case costs one interpreter start instead of importing the real API.
    """
    pkg = repo / "services" / "api" / "app" / "api"
    pkg.mkdir(parents=True, exist_ok=True)
    for init in (
        repo / "services" / "api" / "app" / "__init__.py",
        pkg / "__init__.py",
    ):
        init.write_text("", encoding="utf-8")
    (pkg / "main.py").write_text(
        "class _App:\n"
        "    def openapi(self):\n"
        f"        return {{'paths': {{p: {{}} for p in {paths!r}}}}}\n"
        "\n\napp = _App()\n",
        encoding="utf-8",
    )


@pytest.fixture
def hai_cay_lech_nhau(tmp_path, monkeypatch):
    """A real repo where the ref and the checked-out tree declare DIFFERENT routes.

    Returns `(sha_cua_ref, route_cua_ref, route_cua_cay_dang_dung)`.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    # Not an address: repo guard fails closed on anything email-shaped, and git
    # is happy with any string here.
    _git(repo, "config", "user.email", "cong-test-khong-phai-dia-chi")
    _git(repo, "config", "user.name", "gate test")

    cua_ref = ["/healthz", "/chi-co-o-ref"]
    _fake_api(repo, cua_ref)
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "ref")
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()

    # The tree the gate is standing in moves on. Committed, so no stray
    # uncommitted state can explain a difference.
    cua_cay = ["/healthz", "/chi-co-o-cay-dang-dung", "/them-mot-cai-nua"]
    _fake_api(repo, cua_cay)
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "cay dang dung di tiep")

    monkeypatch.setattr(gate, "REPO_ROOT", repo)
    return sha, set(cua_ref), set(cua_cay)


def test_ve_tham_chieu_doc_tu_ref_chu_khong_phai_cay_dang_dung(hai_cay_lech_nhau):
    """Lỗi gốc 30/08 là hai vế cùng một nguồn. Chặn nó bằng HÀNH VI.

    Bản trước của ca này grep mã nguồn: `assert 'REPO_ROOT / "services"' not in
    src`. Nó chỉ bắt được MỘT cách gõ. qa-tt-0033 viết lại đúng vi phạm đó bằng
    `.joinpath`, chạy cổng từ cây cũ soi container 58 route, và nhận được
    `"ref": "origin/main", "ref_routes": 58` kèm mã 0 — nguyên sự cố 30/08 dựng
    lại trong khi file này vẫn 9/9 XANH.

    Nên ca này không đọc chữ nữa. Nó dựng một repo thật mà `services/api` ở ref
    khai khác `services/api` của cây đang đứng, rồi hỏi `ref_paths` một câu duy
    nhất: anh trả về của ai? Mọi cách viết đều phải trả lời "của ref".
    """
    sha, cua_ref, cua_cay = hai_cay_lech_nhau
    assert cua_ref != cua_cay, "fixture hỏng: hai vế phải khác nhau thì mới đo được"

    duoc = gate.ref_paths(sha)

    assert duoc == cua_ref, (
        "ref_paths phải trả về route của REF. Trả về của cây đang đứng nghĩa là "
        "cổng này thừa hưởng đúng điểm mù xanh-by-construction mà nó sinh ra để bịt"
    )
    assert duoc != cua_cay


def test_ve_tham_chieu_khong_de_lai_worktree_mo_coi(hai_cay_lech_nhau):
    """Một mục worktree bị bỏ lại làm LƯỢT SAU đỏ ở một đường dẫn không còn tồn tại.

    Cổng chạy mỗi 10 phút dưới cron; rác tích lại thì hỏng lần thứ hai chứ không
    hỏng lần đầu, và lỗi đó rất khó truy về đây.
    """
    sha, _, _ = hai_cay_lech_nhau
    gate.ref_paths(sha)
    liet_ke = subprocess.run(
        ["git", "worktree", "list"],
        cwd=str(gate.REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    assert "demo-vs-main-" not in liet_ke, f"còn worktree tạm sót lại:\n{liet_ke}"


# --- nửa fetch: trước 2026-08-30 KHÔNG có ca nào ở đây --------------------
#
# `_no_network` từng là `autouse`, nên mọi ca trong file chạy với `fetch_ref` bị
# vô hiệu. Hệ quả đo được: gỡ hẳn lời gọi fetch, hoặc để fetch hỏng mà vẫn so
# tiếp, đều `9 passed`. Fetch lại đúng là tính chất mô tả PR dựa vào nhiều nhất
# ("so với một origin/main chưa fetch là đúng lỗi này lặp lại một tầng trên").


@pytest.fixture
def dem_fetch(monkeypatch):
    """Count calls to `fetch_ref` instead of silencing it."""
    goi: list[str] = []
    monkeypatch.setattr(gate, "fetch_ref", lambda ref: goi.append(ref))
    return goi


def test_fetch_duoc_goi_khi_khong_co_no_fetch(ref_is, dem_fetch):
    ref_is(["/healthz"])
    with _StubServer(_doc(["/healthz"])) as server:
        assert _run(server.url, ["--ref", "origin/main"]) == gate.EXIT_OK
    assert dem_fetch == ["origin/main"], (
        "cổng so với origin/main mà không fetch trước thì vế tham chiếu có tuổi "
        "không ai biết — đó là chính lỗi này lặp lại một tầng trên"
    )


def test_fetch_khong_duoc_goi_khi_co_no_fetch(ref_is, dem_fetch, capsys):
    ref_is(["/healthz"])
    with _StubServer(_doc(["/healthz"])) as server:
        assert _run(server.url, ["--no-fetch"]) == gate.EXIT_OK
    assert dem_fetch == [], "--no-fetch mà vẫn fetch thì cờ đó là lời nói suông"
    assert "--no-fetch" in capsys.readouterr().err, (
        "cổng degrade mà không khai ra là cổng degrade im lặng"
    )


def test_fetch_hong_thi_khong_chay_duoc_chu_khong_phai_khop(monkeypatch, ref_is):
    """Fetch hỏng -> mã 2. So tiếp với ref không rõ tuổi là câu trả lời sai."""

    class _Hong:
        returncode = 1
        stdout = ""
        stderr = "fatal: could not read from remote repository"

    monkeypatch.setattr(gate, "git", lambda *a, **k: _Hong())
    ref_is(["/healthz"])
    with _StubServer(_doc(["/healthz"])) as server:
        assert _run(server.url, ["--ref", "origin/main"]) == gate.EXIT_CANNOT_RUN


# --- những thứ máy chủ có thể trả mà không phải OpenAPI -------------------


def test_do_khac_ma_khi_content_type_noi_doi(ref_is, no_fetch):
    """JSON OpenAPI HỢP LỆ + `text/plain`.

    Ca `_tra_html` ở trên không phân biệt được guard nào đã cắn: body của nó
    cũng không parse được, nên gỡ hẳn mệnh đề content-type thì `json.loads` vẫn
    ném và mã vẫn là 2. Đầu vào này thì phân biệt được — gỡ guard ra là mã 0.
    """
    ref_is(["/healthz"])
    with _StubServer(_doc(["/healthz"]), ctype="text/plain") as server:
        assert _run(server.url) == gate.EXIT_CANNOT_RUN


def test_do_khac_ma_khi_json_top_level_la_list(ref_is, no_fetch):
    """`["/healthz"]` parse được, rồi `.get` ném AttributeError.

    Đo ngày 30/08 trên bản chưa vá: mã thoát **1** kèm traceback. Mã 1 là giá
    trị tệ nhất có thể ra ở đây — theo hợp đồng của chính cổng nó nghĩa là "máy
    demo lệch so với main", nên người đọc đi dựng lại máy demo để đuổi một sai
    lệch chưa từng được đo.
    """
    ref_is(["/healthz"])
    with _StubServer(b'["/healthz", "/expenses"]') as server:
        assert _run(server.url) == gate.EXIT_CANNOT_RUN
