# Review PR #15 — tầng test PostgreSQL cho repository

- commit: `ebdd0ac`
- protocol_version: v1
- **verdict: APPROVE**
- blocker còn mở: không

## Bằng chứng đã xem

Chạy thật trên Postgres 16 (`mobile-local-postgres-1`), không phải đọc code:

```
MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest tests/postgres -q
7 passed in 1.42s
```

**Test đột biến** — câu hỏi duy nhất đáng hỏi với một tầng test mới là nó có
bắt được con bug nó sinh ra không. Hoàn nguyên `of=ExpenseVersion` về
`.with_for_update()`:

```
6 failed, 1 passed
```

Bắt được. Không phải test hình thức.

## Bản sửa của Codex đúng hơn bản của tôi

Cùng lỗi này tôi đã sửa ở PR #14, theo cách tệ hơn.

`.with_for_update()` không định danh sẽ khoá **mọi** bảng trong FROM, kể cả
subquery tổng hợp `latest`, mà Postgres không khoá được kết quả aggregate.
Codex chỉ đích danh `of=ExpenseVersion` — một câu lệnh, khoá nguyên tử cùng
lúc với phép chọn.

Tôi tách thành hai câu lệnh: chọn id trước, khoá sau. Cách đó mở ra khe
TOCTOU — giữa hai câu lệnh, một giao dịch khác chèn được version N+1, và tôi
khoá nhầm version cũ rồi dựng đợt thu từ dữ liệu chi tiêu lỗi thời. Đó là lỗi
tiền, không phải lỗi hiệu năng.

**Việc phải làm:** rút bản sửa `load_batch_inputs` khỏi PR #14, chỉ giữ lại
phần sửa tên ngân hàng. Lấy bản của Codex.

## Ghi nhận

Tầng test từ chối SQLite, migrate schema riêng, chỉ drop đúng schema mình tạo.
Đúng ranh giới: suite thường vẫn dùng repository giả và vẫn nhanh.
