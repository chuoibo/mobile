"""Đối chứng QA bổ sung cho F22 (#303) — những mặt bảng đột biến của PR không chạm.

PR #303 tự mang `scripts/mutation_rd_do_f22.py` (11 BREAKS + 4 KEEPS) và bảng đó
tái lập được: chạy lại trong cây sạch trên máy QA, DB riêng, ra 11/11 ĐỎ và 4/4
XANH. Đó là một bảng tốt — nó tự bắt được anchor mất, anchor trùng, và ca đỏ vì
NameError.

File này hỏi câu mà một bảng do chính tác giả viết không tự hỏi được: **tác giả
đã quên đột biến mặt nào?**

Cùng bộ bảo vệ như bảng của PR, cố ý — một bảng không phát hiện được anchor cũ,
anchor trùng, hay ca "đỏ vì lý do khác" là một bảng in ra con số nó không kiếm
được.

Cột `expect` là giả thuyết QA ghi TRƯỚC khi chạy. Hàng nào lệch với `expect` mới
là phát hiện, lệch theo chiều nào cũng vậy.

Kết quả đo được (main@7aa6dc8, PostgreSQL thật):

    RED    qa-claim-door-removed-entirely      đúng dự đoán — cửa CÓ được gác
    GREEN  qa-claim-list-dedupe-removed        đúng dự đoán — LỖ HỔNG PHỦ
    GREEN  qa-claim-share-lock-dropped         đúng dự đoán, nhưng TƯƠNG ĐƯƠNG
    RED    qa-box-order-axes-transposed        TỐT HƠN dự đoán — trục sắp có gác
    RED    qa-coords-emitted-as-pixels         đúng dự đoán

Cách chạy:

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://...' \\
        python3 tests/qa/qa-tt-0032-f22/mutation_bo_sung_303.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "services" / "api"

CLAIM_TESTS = ("tests/postgres/test_bill_self_claim_postgres.py",)
FACE_TESTS = (
    "tests/domain/test_faces.py",
    "tests/postgres/test_face_boxes_privacy_postgres.py",
)


@dataclass(frozen=True)
class Mutation:
    name: str
    kind: str
    expect: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]


MUTATIONS = [
    # PR đột biến "ai bị tính tiền" và "ai bị đá khỏi món", nhưng chưa bao giờ
    # GỠ HẲN lời gọi kiểm quyền. `record` bị ghi đè hai dòng sau, nên xoá lời
    # gọi này là một sửa đổi vô hình về mặt cú pháp — đúng loại sửa mà một lượt
    # dọn dẹp "bỏ biến không dùng" sẽ làm.
    Mutation(
        name="qa-claim-door-removed-entirely",
        kind="BREAKS",
        expect="RED",
        path="app/api/service.py",
        old=(
            "        record = self._bill_for_actor(bill_id, actor)\n"
            "        try:\n"
            "            record = self.repository.claim_bill_items("
        ),
        new="        try:\n            record = self.repository.claim_bill_items(",
        tests=CLAIM_TESTS,
    ),
    # Bấm hai lần. `dict.fromkeys` là thứ duy nhất đứng giữa một item_key lặp và
    # `uq_bill_item_shares_item_participant`. Không ca nào trong PR gửi khoá
    # trùng, nên hàng này hỏi: dedupe được GÁC, hay chỉ CÓ MẶT?
    Mutation(
        name="qa-claim-list-dedupe-removed",
        kind="BREAKS",
        expect="GREEN",
        path="app/api/repository.py",
        old="        requested = dict.fromkeys(item_keys)",
        new="        requested = list(item_keys)",
        tests=CLAIM_TESTS,
    ),
    # Khoá dòng thì test một luồng không nhìn thấy. Nhưng TRƯỚC khi đọc XANH này
    # thành lỗ hổng, phải kiểm tương đương: cả `claim_bill_items` lẫn
    # `confirm_bill_assignments` đều mở đầu bằng
    # `select(Bill).where(Bill.id == bill_id).with_for_update()`, nên hai lời gọi
    # đồng thời đã xếp hàng ở khoá dòng Bill trước khi chạm tới bảng share.
    # `create_bill` là writer thứ ba nhưng nó tạo hoá đơn nên chưa ai thấy.
    # => khoá ở tầng share là THỪA cho loại trừ lẫn nhau, và XANH là câu trả lời
    # ĐÚNG. Giữ hàng này lại chính vì kết luận đó cần được ghi ra, không phải để
    # tính vào cột lỗ hổng.
    Mutation(
        name="qa-claim-share-lock-dropped",
        kind="EQUIVALENT",
        expect="GREEN",
        path="app/api/repository.py",
        old=(
            "                .where(BillItemShare.participant_id == participant_id)\n"
            "                .with_for_update()"
        ),
        new="                .where(BillItemShare.participant_id == participant_id)",
        tests=CLAIM_TESTS,
    ),
    # Docstring của module cam kết một thứ tự đọc cụ thể: trên xuống dưới, rồi
    # trái sang phải. Hàng của PR gỡ hẳn `sorted`; hàng này GIỮ tính tất định mà
    # đảo trục — đúng thứ một lần sửa ẩu vào key sắp xếp sẽ tạo ra.
    Mutation(
        name="qa-box-order-axes-transposed",
        kind="BREAKS",
        expect="GREEN",
        path="app/domain/faces.py",
        old=(
            "    ordered = sorted(\n"
            "        {(top, left, width, height) for left, top, width, height in clamped}\n"
            "    )"
        ),
        new=(
            "    ordered = sorted(\n"
            "        {(top, left, width, height) for left, top, width, height in clamped},\n"
            "        key=lambda box: (box[1], box[0], box[2], box[3]),\n"
            "    )"
        ),
        tests=FACE_TESTS,
    ),
    # Hàng đối chứng. Toạ độ là PHÂN SỐ của ảnh theo hợp đồng; client nhận pixel
    # sẽ vẽ mọi ô sai chỗ ngay khi ảnh được thu nhỏ. Hàng này XANH thì hình học
    # của response không được khẳng định ở đâu cả.
    Mutation(
        name="qa-coords-emitted-as-pixels",
        kind="BREAKS",
        expect="RED",
        path="app/domain/faces.py",
        old='            "x": left / image_width,',
        new='            "x": float(left),',
        tests=FACE_TESTS,
    ),
]

_NOOP = [m.name for m in MUTATIONS if m.old == m.new]
if _NOOP:
    raise SystemExit(f"bảng có hàng no-op: {_NOOP}")

_BROKEN = ("NameError", "SyntaxError", "ImportError", "IndentationError")


def run_tests(paths: tuple[str, ...]) -> tuple[bool, str]:
    """(passed, output). Tầng postgres bắt buộc chạy, không được skip."""

    env = dict(os.environ)
    env.setdefault(
        "MOBILE_TEST_DATABASE_URL",
        "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile",
    )
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *paths,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:randomly",
        ],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    return done.returncode == 0, done.stdout + done.stderr


def main() -> int:
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "services/api"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        print("TỪ CHỐI: services/api đang bẩn; hoàn nguyên đột biến sẽ đè lên nó.")
        print(dirty)
        return 2

    every = tuple(sorted({p for m in MUTATIONS for p in m.tests}))
    passed, output = run_tests(every)
    if not passed:
        print("NỀN ĐỎ — dừng. Không con số nào bên dưới đọc được.")
        print(output[-2000:])
        return 2
    print("Nền XANH.\n")

    rows = []
    for mutation in MUTATIONS:
        target = API_ROOT / mutation.path
        original = target.read_text()
        if mutation.old not in original:
            rows.append((mutation, "ANCHOR-MISSING"))
            print(f"[{mutation.kind}] {mutation.name}: KHÔNG THẤY ANCHOR — bảng cũ")
            continue
        if original.count(mutation.old) != 1:
            count = original.count(mutation.old)
            rows.append((mutation, f"ANCHOR-AMBIGUOUS({count})"))
            print(f"[{mutation.kind}] {mutation.name}: ANCHOR CÓ {count} BẢN SAO")
            continue

        target.write_text(original.replace(mutation.old, mutation.new, 1))
        try:
            ok, out = run_tests(mutation.tests)
        finally:
            target.write_text(original)

        broken = next((b for b in _BROKEN if b in out), None)
        verdict = f"RED-BUT-BROKEN({broken})" if broken else ("GREEN" if ok else "RED")
        rows.append((mutation, verdict))
        print(
            f"[{mutation.kind}] {mutation.name}: {verdict}   (dự đoán {mutation.expect})"
        )

    print("\n--- bảng ---")
    lech = 0
    for mutation, verdict in rows:
        khop = verdict == mutation.expect
        if not khop:
            lech += 1
        print(f"{'ok ' if khop else 'LỆCH'}  {verdict:<22} {mutation.name}")
    print(f"\n{len(rows)} hàng, {lech} hàng lệch với giả thuyết QA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
