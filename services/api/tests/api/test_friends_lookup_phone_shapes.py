"""rd-qa-36 · Mọi hình dạng thân yêu cầu mà một lời từ chối có thể vọng số ra.

`test_friends_routes.py` đã giữ hai hình dạng: số gửi dưới dạng JSON *number*, và
một chuỗi sai định dạng. Cả hai đều là **chuỗi hoặc số ở tầng cao nhất** của
`{"phone": ...}`.

Cái chưa ai gác là các hình dạng mà pydantic vọng lại NGUYÊN CẢ CẤU TRÚC chứ
không chỉ một vô hướng: `{"phone": {"so": "..."}}` và `{"phone": [...]}`. Nếu ai
đó sau này thay phần tự parse tay bằng một body model — việc trông như dọn dẹp —
422 của FastAPI đặt cả cái dict/list đó dưới khoá `"input"`, và số điện thoại rời
máy chủ trong chính lời từ chối. Đó là lý do file này liệt kê hình dạng chứ không
liệt kê giá trị.

Ba đường không-phải-JSON ở cuối (thân rỗng, thân cắt cụt, thân không phải UTF-8)
gác nhánh `except ValueError` của handler: cả ba phải ra cùng một câu cố định,
không phải một traceback.

Đo trên máy chủ uvicorn thật trước khi viết file này: 24 hình dạng, grep cả thân
LẪN mọi header LẪN log máy chủ tìm chữ số đã gửi — 23 sạch. Cái thứ 24 là số do
chính người gọi đặt vào query string; nó không đi qua handler này nên không có ca
nào ở đây, xem báo cáo QA.
"""

from __future__ import annotations

import re

import pytest

from app.api.person_identity import KEY_ENV_VAR

from .helpers import ADVANCER_ID, actor_headers

#: Rộng hơn định dạng thật có chủ ý: một ca chỉ bắt đúng một cách viết sẽ bỏ sót
#: số viết cách khác, và "cách khác" chính là đường nó thoát ra.
DIGIT_RUN = re.compile(r"\d{6,}")

#: Tổng hợp, ghép lúc chạy: `repo_guard.py` từ chối dãy chữ số hình dạng số điện
#: thoại trong file đã commit và không phân biệt được số bịa với số thật.
FAKE_MOBILE = "0" + "9" * 2 + "1" + "2" * 3 + "4" * 3


@pytest.fixture
def identity_key(monkeypatch):
    monkeypatch.setenv(KEY_ENV_VAR, "x" * 64)
    return None


def _lookup(client, payload=None, *, content=None):
    kwargs = {"content": content} if content is not None else {"json": payload}
    return client.post(
        "/friends/lookup",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
        **kwargs,
    )


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        # Hai hình dạng nguy hiểm nhất: pydantic vọng lại cả cấu trúc.
        ("số nằm trong một object lồng", {"phone": {"so": FAKE_MOBILE}}),
        ("số tách thành mảng chữ số", {"phone": list(FAKE_MOBILE)}),
        ("số nằm dưới tên field khác", {"sdt": FAKE_MOBILE}),
        ("số là khoá chứ không phải giá trị", {FAKE_MOBILE: "phone"}),
        # Vô hướng sai kiểu.
        ("phone là bool", {"phone": True}),
        ("phone là null", {"phone": None}),
        ("thiếu hẳn field", {}),
        # Chuỗi đúng kiểu nhưng sai dạng.
        ("chuỗi dài 200 ký tự", {"phone": FAKE_MOBILE * 20}),
        ("số kèm đuôi chữ", {"phone": FAKE_MOBILE + "abc"}),
        ("chữ số toàn ký tự rộng", {"phone": "０" + "９" * 9}),
        ("số kèm ký tự xuống dòng", {"phone": FAKE_MOBILE + "\nGET /x"}),
    ],
)
def test_no_body_shape_makes_the_refusal_echo_the_number(
    client, identity_key, label, payload
):
    """Mỗi hình dạng phải ra một câu cố định, không mang chữ số nào."""
    refused = _lookup(client, payload)

    assert refused.status_code == 422, f"{label}: {refused.status_code} {refused.text}"
    assert DIGIT_RUN.search(refused.text) is None, f"{label}: {refused.text}"


@pytest.mark.parametrize(
    ("label", "raw"),
    [
        ("thân là chữ trần, không phải JSON", FAKE_MOBILE.encode()),
        ("thân là JSON cắt cụt", b'{"phone": "' + FAKE_MOBILE.encode()),
        ("thân rỗng", b""),
        ("thân không phải UTF-8", b'{"phone": "' + FAKE_MOBILE.encode() + b'\xff"}'),
    ],
)
def test_a_body_that_is_not_json_is_refused_without_a_traceback(
    client, identity_key, label, raw
):
    """Nhánh `except ValueError` — cả ba lối vào, cùng một câu."""
    refused = _lookup(client, content=raw)

    assert refused.status_code == 422, f"{label}: {refused.status_code} {refused.text}"
    assert DIGIT_RUN.search(refused.text) is None, f"{label}: {refused.text}"


def test_no_response_header_carries_the_number(client, identity_key):
    """Thân là chỗ người ta nhìn; header là chỗ người ta quên nhìn."""
    refused = _lookup(client, {"phone": FAKE_MOBILE + "0"})

    blob = "\n".join(f"{name}: {value}" for name, value in refused.headers.items())
    assert DIGIT_RUN.search(blob) is None, blob
