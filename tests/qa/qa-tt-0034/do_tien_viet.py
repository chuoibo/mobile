"""Which written Vietnamese money forms F24 can carry from chat into a draft.

Why this file exists
--------------------
`GeminiChatExpenseReader`'s prompt tells the model, in as many words, to copy
the amount **as text** and to "preserve the written money form such as 180k,
1 trieu, or 180.000d; do not calculate, round, or convert it". So whatever
spelling a person used in the message is exactly what reaches
`app/domain/receipt.normalize_vnd`.

`_CURRENCY_MARKER` in that module is `(?:VND|VNĐ|đ|₫|d)` -- the symbol, never
the word. So a message written "480000 đồng", which is the most ordinary way a
person types an amount in a Vietnamese chat, is transcribed faithfully and then
refused by the normalizer. The route answers 422 `chat_expense_unreadable` and
the card says "Không đọc được khoản chi từ tin nhắn" -- a sentence that blames
the message when the model read it correctly.

This is a table, not an assertion suite, so it stays honest when the gap is
closed: run it again and the TU CHOI rows become numbers.

    python3 tests/qa/qa-tt-0034/do_tien_viet.py

Runs from the repository root; no server, no key, no database.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services" / "api"))

from app.domain.receipt import ReceiptError, normalize_vnd  # noqa: E402

# Every form here is one a person plausibly types, or that the model plausibly
# copies out of what they typed. The comment on each line says which.
CACH_VIET = [
    ("480k", "nhắn tay, dạng ngắn"),
    ("480 k", "nhắn tay, có dấu cách"),
    ("480 nghìn", "nhắn tay, viết chữ"),
    ("480 ngàn", "nhắn tay, giọng miền Nam"),
    ("1 triệu", "nhắn tay, đơn vị triệu"),
    ("1tr", "nhắn tay, viết tắt"),
    ("480000", "gõ thẳng số"),
    ("480.000đ", "số có chấm, ký hiệu đ"),
    ("480,000 VND", "số có phẩy, mã tiền tệ"),
    ("480000 đồng", "viết CHỮ đồng"),
    ("480.000 đồng", "số có chấm + chữ đồng"),
    ("480000 dong", "chữ đồng không dấu"),
    ("2 trăm nghìn", "đọc thành lời"),
]


def main() -> int:
    tu_choi = []
    print(f"{'cách viết':22} {'ý nghĩa':28} kết quả")
    print("-" * 72)
    for text, y_nghia in CACH_VIET:
        try:
            print(f"{text!r:22} {y_nghia:28} {normalize_vnd(text)}")
        except ReceiptError as exc:
            tu_choi.append(text)
            print(f"{text!r:22} {y_nghia:28} TỪ CHỐI ({getattr(exc, 'code', exc)})")
    print("-" * 72)
    print(f"{len(tu_choi)}/{len(CACH_VIET)} cách viết bị từ chối: {tu_choi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
