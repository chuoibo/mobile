"""Probe QA: `POST /bills/{id}/my-items` làm gì khi cùng một item_key lặp lại.

Đây KHÔNG phải test đề xuất thêm vào bộ của sản phẩm — đây là một PHÉP ĐO.

Hàng đột biến `qa-claim-list-dedupe-removed` đứng XANH, nghĩa là phép khử trùng
trong `SqlAlchemyApiRepository.claim_bill_items` **có mặt nhưng không được gác**.
"Có mặt nhưng không được gác" có hai cách đọc rất khác nhau, và chỉ chạy thật mới
phân biệt được:

  a) sản phẩm đã xử lý đúng khoá lặp, chỉ là không test nào nói ra, hoặc
  b) sản phẩm 500 khi bấm hai lần, và không ai nhận ra.

`item_keys` là một list, nên client nào cộng dồn mỗi lần chạm — hoặc người dùng
bấm hai lần trước khi response về — sẽ gửi khoá lặp. Ràng buộc
`uq_bill_item_shares_item_participant` là thứ nó sẽ đâm vào.

File này phải nằm trong `services/api/tests/postgres/` mới lấy được fixture
`postgres_session`; dùng `chay_probe.py` cạnh đây để chép vào, chạy, rồi xoá đi.

Kết quả đo (main@7aa6dc8, PostgreSQL thật): cách đọc (a) — HTTP 200, đúng số
hàng. Sản phẩm ĐÚNG, chỉ là không có ca nào giữ nó như vậy.
"""

from __future__ import annotations

from .test_bill_self_claim_postgres import (  # noqa: F401  (fixture)
    _claim,
    _shares,
    app,
    table,
)


def test_probe_bam_hai_lan_cung_mot_khoa(app, table, postgres_session):  # noqa: F811
    """Cùng một món hai lần trong một body."""

    response = _claim(app, table["bill_id"], table["an"], ["pho", "pho"])
    print(f"\n[probe] item_keys=['pho','pho'] -> HTTP {response.status_code}")
    rows = _shares(postgres_session, table["bill_id"])
    print(f"[probe] bill_item_shares = {len(rows)} hàng (mong đợi 1)")
    assert response.status_code == 200, response.text
    assert len(rows) == 1


def test_probe_khoa_lap_canh_mon_that(app, table, postgres_session):  # noqa: F811
    """Khoá lặp đứng cạnh một món thứ hai có thật.

    Một phép khử trùng viết ẩu kiểu "bỏ phần đuôi" sẽ lộ ra ở đây thành hàng bị
    thiếu, chứ không thành một cú sập — nên ca này bắt được chiều hỏng mà ca
    trên không bắt được.
    """

    response = _claim(app, table["bill_id"], table["an"], ["pho", "bia", "pho", "pho"])
    print(
        f"\n[probe] item_keys=['pho','bia','pho','pho'] -> HTTP {response.status_code}"
    )
    rows = _shares(postgres_session, table["bill_id"])
    print(f"[probe] bill_item_shares = {len(rows)} hàng (mong đợi 2: pho + bia)")
    assert response.status_code == 200, response.text
    assert len(rows) == 2
