# ADR-0003 — Sửa hai blocker về enforcement của cổng

- **Trạng thái:** ĐÃ CHẤP NHẬN
- **Ngày:** 2026-08-26
- **Nguồn:** review của Codex tại `docs/codex/2026-08-26/review-claude-2026-08-26.md`, verdict `REQUEST_CHANGES`
- **Áp dụng:** `docs/team/charter.md`, `docs/team/backlog.md`

## B-01 — Required check không có DRI kích hoạt

**Codex chỉ ra:** charter cho phép FIELD-GATE khi W9a "xong", backlog giao Codex tạo CI check, nhưng **không ai** được giao việc **bật** required status check và branch protection. Hook local bị bỏ qua bằng `--no-verify`; có workflow file trong repo mà required check chưa bật thì PR vẫn merge được khi scanner đỏ.

**Nhận.** Đây là lỗi loại (1) vi phạm cổng và (3) quyền riêng tư — đúng phân loại blocker ở charter mục 4.

**Sửa:**
- Charter mục 3.1 mới: tách `artifact_complete` (Codex) khỏi `enforcement_active` (**LEADER**).
- FIELD-GATE đổi điều kiện từ "W9a xong" → "W9a **enforcement đang hoạt động**".
- Backlog thêm **W9a-E** ở leader lane: bật required check, PR bắt buộc, chặn direct push, chạy **PR dry-run âm tính và xác nhận bị chặn thật**, lưu bằng chứng cấu hình không chứa PII.

Điểm cốt lõi: **có hàng rào trong repo không bằng hàng rào đang bật.** Chỉ leader bật được branch protection — engineer không có quyền đó, nên nó phải nằm ở leader lane chứ không phải giả định ngầm.

## B-02 — Miễn review đệ quy dựa trên CI check không tồn tại

**Codex chỉ ra:** charter miễn review đệ quy cho review-only PR "chỉ khi CI xác nhận diff chỉ chứa Markdown review". Không work item nào sở hữu check đó, không có tên check, không có artifact để tái lập. Tức là một ngoại lệ MERGE-GATE **không kiểm chứng được**.

**Nhận.** Tôi tạo ra một ngoại lệ rồi gắn điều kiện cho một cơ chế chưa tồn tại. Đó là quy tắc trên giấy.

**Sửa — chọn phương án (b) của Codex, bỏ hẳn ngoại lệ:**
Review doc **commit thẳng vào `main`** bởi chính người viết review, giới hạn đường dẫn `docs/<owner>/<YYYY-MM-DD>/review-*.md`, chỉ Markdown. Không PR, không review lại, **không cần ngoại lệ nào**.

Vì sao hợp lệ: review doc **ghi nhận** một verdict, nó **không mang quyền quyết định** — quyền đó sống ở `docs/decisions/`. Vòng lặp review đệ quy biến mất vì không còn PR để review.

Muốn quay lại mô hình review-only PR → phải có CI check giới hạn đường dẫn và chặn executable/binary/symlink **trước**, kèm test âm tính.

## Suggestion đã áp dụng

- **S-1:** `verdict` chuẩn hoá thành `APPROVE` / `REQUEST_CHANGES` / `REJECT`.
- **S-3:** Ghi chú vào sơ đồ phụ thuộc: governance chặn **dữ liệu thật và thực thi thực địa**, không chặn build/test bằng fixture tổng hợp.

## Suggestion chưa áp dụng

- **S-2** (biến "6–10 tuần" của P0-Gọn thành estimate có assumptions) — chờ ADR-0002 được quyết. Nếu leader không chọn P0-Gọn thì suggestion này rơi.
