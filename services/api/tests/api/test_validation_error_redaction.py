"""Một 422 nói SAI Ở TRƯỜNG NÀO, không nói LẠI NGƯỜI TA ĐÃ GÕ GÌ.

Handler mặc định của FastAPI đưa giá trị bị từ chối vào `input`, nguyên văn.
Với một số nguyên ngoài khoảng thì vô hại. Với bất cứ thứ gì người ta gõ —
tin nhắn nhóm, caption, bình luận dưới một tấm ảnh — đó là rò rỉ, và thông
báo lỗi lại đúng là phần hay bị dán vào bug report và vào chat nhất.

Đo được trước khi vá, trên `POST /contexts/{id}/memories/{id}/comments` với
body 5800 ký tự: 422 mang trả về đủ 5800 ký tự đó. Cùng hình dạng có sẵn ở
`messages.body` và ở mọi trường văn bản tự do khác — nên bản vá là MỘT handler
ở `create_app`, không phải một chỗ vá cho mỗi route.

File này gác đúng handler đó. Nó cố ý đứng ở tầng `tests/api` (fake repository,
rẻ, chạy ở mọi chặng) chứ không ở tầng Postgres: tính chất cần gác là hình
dạng của phản hồi 422, và hình dạng đó không cần database nào để sai.
"""

from __future__ import annotations

import uuid

import pytest

SECRET = "Chuyện riêng của nhóm này, không được xuất hiện lại trong lỗi"


def _errors(response) -> list[dict]:
    payload = response.json()
    assert isinstance(payload["detail"], list), payload
    return payload["detail"]


def test_a_too_long_comment_is_not_repeated_back(client):
    """Ca đỏ trước bản vá. 5800 ký tự đi vào, 5800 ký tự đi ra."""
    response = client.post(
        f"/contexts/{uuid.uuid4()}/memories/{uuid.uuid4()}/comments",
        headers={"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"},
        json={"body": SECRET * 100},
    )

    assert response.status_code == 422, response.text
    assert SECRET not in response.text


def test_a_too_long_group_message_is_not_repeated_back(client):
    """Cùng lỗ, trường khác, route khác — và đó là lý do bản vá ở một chỗ.

    `messages.body` đã có hình dạng này trên `main` từ trước việc F41. Nếu
    handler bị gỡ, ca này đỏ cùng ca trên, và đó là bằng chứng rằng bản vá gác
    cả những trường không ai đang sửa.
    """
    response = client.post(
        f"/contexts/{uuid.uuid4()}/messages",
        headers={"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"},
        json={"kind": "text", "body": SECRET * 100},
    )

    assert response.status_code == 422, response.text
    assert SECRET not in response.text


def test_no_validation_error_anywhere_carries_an_input_key(client):
    """`input` là trường duy nhất mà pydantic chép nguyên văn request vào.

    Gác bằng KHOÁ chứ không bằng chuỗi bí mật: một ca chỉ tìm `SECRET` sẽ xanh
    trở lại nếu handler chuyển sang cắt bớt chuỗi thay vì bỏ hẳn khoá, và
    "1000 ký tự đầu của câu người ta gõ" vẫn là câu người ta gõ.
    """
    response = client.post(
        f"/contexts/{uuid.uuid4()}/memories/{uuid.uuid4()}/comments",
        headers={"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"},
        json={"body": SECRET * 100},
    )

    for error in _errors(response):
        assert "input" not in error, error


@pytest.mark.parametrize(
    ("payload", "expected_field"),
    [
        ({}, "body"),
        ({"body": ""}, "body"),
        ({"body": 12345}, "body"),
        ({"body": "ổn", "author_id": str(uuid.uuid4())}, "author_id"),
    ],
)
def test_the_refusal_still_names_the_field_that_was_wrong(
    client, payload, expected_field
):
    """Bỏ `input` không được phép biến 422 thành một cái nhún vai.

    Một lỗi không nói được sai ở đâu sẽ bị client bỏ qua, và rồi người ta gỡ
    luôn cái handler. `loc` và `msg` ở lại chính vì thế: cả hai do pydantic và
    validator của repo này viết ra, và mọi `ValueError` trong `schemas.py` đều
    mang một câu hằng, không nhúng giá trị vào.
    """
    response = client.post(
        f"/contexts/{uuid.uuid4()}/memories/{uuid.uuid4()}/comments",
        headers={"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"},
        json=payload,
    )

    assert response.status_code == 422, response.text
    errors = _errors(response)
    assert any(expected_field in error["loc"] for error in errors), errors
    assert all(error.get("msg") for error in errors), errors
    assert all(error.get("type") for error in errors), errors
