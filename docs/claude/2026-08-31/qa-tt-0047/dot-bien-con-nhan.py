"""Đột biến: cổng của #389 có thật sự gác `receivable_vnd` không.

19 ca xanh ở tầng Postgres nói rằng con số đúng trên dữ liệu tác giả nghĩ ra.
Chúng KHÔNG nói rằng chúng đỏ được khi con số sai. Script này làm hỏng đúng
từng mảnh của truy vấn rồi xem cổng có kêu không.

Ba loại hàng, và cần cả ba mới đọc được bảng:

  CHET  — phải ĐỎ. Mỗi hàng là một cách con số này sai trong thực tế.
  SONG  — phải XANH. Đổi thứ không đổi nghĩa. Nếu hàng này cũng đỏ thì cổng
          chỉ đang ghim byte của file, không gác hành vi.
  BASE  — cây chưa đột biến, phải XANH. Không có nó thì một cây đỏ sẵn sẽ
          làm mọi hàng CHET "đỏ" vì lý do khác.

Từ chối chạy nếu không tìm thấy nguyên văn đoạn định thay: một đột biến no-op
in ra XANH và đọc y hệt một cổng đang giữ.
"""

import os
import pathlib
import subprocess
import sys

API = pathlib.Path("/tmp/qa47-main/services/api")
TARGET = API / "app" / "api" / "repository.py"
TEST = "tests/postgres/test_person_finance_postgres.py"
DBURL = pathlib.Path("/tmp/qa47-dburl.txt").read_text().strip()

# (mã, loại, mô tả, nguyên văn phải có, thay bằng)
MUTANTS = [
    (
        "M1",
        "CHET",
        "bỏ `participant_id != person_id`: phần của chính người ứng tiền "
        "bị tính là tiền người khác nợ họ -> 'còn nhận' bằng cả hoá đơn",
        """                ExpenseVersion.paid_by_id == person_id,
                ConfirmedAllocation.participant_id != person_id,""",
        """                ExpenseVersion.paid_by_id == person_id,""",
    ),
    (
        "M2",
        "CHET",
        "đếm PaymentReport thay vì ReceiptConfirmation: người nợ TỰ BÁO đã "
        "chuyển là xoá được tiền của chủ nợ — đúng câu màn hình hứa không xảy ra",
        """                select(func.coalesce(func.sum(ReceiptConfirmation.amount_vnd), 0))
                .select_from(ReceiptConfirmation)
                .join(
                    CollectionObligation,
                    CollectionObligation.id == ReceiptConfirmation.obligation_id,
                )
                .where(CollectionObligation.recipient_id == person_id)""",
        """                select(func.coalesce(func.sum(PaymentReport.amount_vnd), 0))
                .select_from(PaymentReport)
                .join(
                    CollectionObligation,
                    CollectionObligation.id == PaymentReport.obligation_id,
                )
                .where(CollectionObligation.recipient_id == person_id)""",
    ),
    (
        "M3",
        "CHET",
        "bỏ nửa `version_number` của mối nối newest: sửa một khoản chi thì "
        "cả bản cũ lẫn bản mới cùng được tính -> 'còn nhận' gấp đôi",
        """                newest,
                (newest.c.expense_id == ExpenseVersion.expense_id)
                & (newest.c.version_number == ExpenseVersion.version_number),
            )
            .where(
                ExpenseVersion.paid_by_id == person_id,""",
        """                newest,
                (newest.c.expense_id == ExpenseVersion.expense_id),
            )
            .where(
                ExpenseVersion.paid_by_id == person_id,""",
    ),
    (
        "M4",
        "CHET",
        "bỏ kẹp max(0, ...): xác nhận nhận tiền hai lần thì chủ nợ đọc một "
        "số ÂM trên màn hình",
        "        receivable_vnd = max(0, advanced_vnd - collected_vnd)",
        "        receivable_vnd = advanced_vnd - collected_vnd",
    ),
    (
        "K1",
        "SONG",
        "đổi tên biến cục bộ advanced_vnd -> ung_truoc_vnd. Không đổi nghĩa "
        "một chút nào; hàng này đỏ nghĩa là cổng đang ghim byte chứ không gác",
        "        advanced_vnd = int(",
        "        ung_truoc_vnd = int(",
    ),
]

# K1 đổi tên nên phải đổi cả chỗ dùng; gói kèm để nó vẫn biên dịch được.
K1_EXTRA = (
    "        receivable_vnd = max(0, advanced_vnd - collected_vnd)",
    "        receivable_vnd = max(0, ung_truoc_vnd - collected_vnd)",
)


def chay() -> tuple[bool, str]:
    env = {
        **os.environ,
        "MOBILE_TEST_DATABASE_URL": DBURL,
        "MOBILE_REQUIRE_POSTGRES_TESTS": "1",
    }
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            TEST,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    dong = [
        dg
        for dg in p.stdout.splitlines()
        if "passed" in dg or "failed" in dg or "error" in dg
    ]
    return p.returncode == 0, (dong[-1].strip() if dong else f"rc={p.returncode}")


def main() -> int:
    goc = TARGET.read_text()
    hang = []

    xanh, ghi = chay()
    hang.append(
        ("BASE", "BASE", "cây chưa đột biến", "XANH", "XANH" if xanh else "ĐỎ", ghi)
    )
    if not xanh:
        print("NỀN ĐỎ SẴN — dừng. Mọi hàng CHET dưới sẽ đỏ vì lý do khác.")
        in_bang(hang)
        return 2

    try:
        for ma, loai, mo_ta, truoc, sau in MUTANTS:
            if truoc not in goc:
                print(f"{ma}: KHÔNG tìm thấy nguyên văn cần thay — từ chối chạy.")
                print(f"  cần: {truoc[:90]!r}")
                return 3
            moi = goc.replace(truoc, sau, 1)
            if ma == "K1":
                moi = moi.replace(K1_EXTRA[0], K1_EXTRA[1], 1)
            assert moi != goc, f"{ma} là no-op"
            TARGET.write_text(moi)
            xanh, ghi = chay()
            cho = "ĐỎ" if loai == "CHET" else "XANH"
            duoc = "XANH" if xanh else "ĐỎ"
            hang.append((ma, loai, mo_ta, cho, duoc, ghi))
            print(f"{ma} ({loai}): chờ {cho}, được {duoc}  — {ghi}")
    finally:
        TARGET.write_text(goc)
        assert TARGET.read_text() == goc, "KHÔNG khôi phục được file gốc"
        print("\nĐã khôi phục repository.py về nguyên bản.")

    in_bang(hang)
    lot = [h for h in hang if h[3] != h[4]]
    if lot:
        print(f"\nLỖ HỔNG: {len(lot)} hàng không như chờ đợi: {[h[0] for h in lot]}")
        return 1
    print("\nMỌI HÀNG ĐÚNG NHƯ CHỜ ĐỢI.")
    return 0


def in_bang(hang) -> None:
    print("\n| Hàng | Loại | Hình dạng | Chờ | Được | pytest |")
    print("|---|---|---|---|---|---|")
    for ma, loai, mo_ta, cho, duoc, ghi in hang:
        print(f"| {ma} | {loai} | {mo_ta} | {cho} | **{duoc}** | `{ghi}` |")


if __name__ == "__main__":
    sys.exit(main())
