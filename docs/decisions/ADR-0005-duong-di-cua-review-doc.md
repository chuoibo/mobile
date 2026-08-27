# ADR-0005 — Đường đi của review doc

- **Trạng thái:** ĐÃ CHẤP NHẬN
- **Ngày:** 2026-08-27
- **Nguồn:** Codex **BÁC** bản sửa B-02 ở ADR-0003
- **Thay thế:** mục 2 của `docs/team/charter.md`, phần "Review doc đi đường nào"

## Codex đúng, ADR-0003 sai

ADR-0003 sửa B-02 bằng cách cho review doc **commit thẳng vào `main`**. Codex bác: điều đó **mâu thuẫn trực tiếp** với `W9a-E` trong cùng bộ tài liệu, vốn giao leader **chặn direct push** vào `main`.

Tôi đã sửa một mâu thuẫn bằng cách tạo ra một mâu thuẫn khác, ở hai file cách nhau vài dòng. Charter mục 3.1 nói "chặn direct push", charter mục 2 nói "commit thẳng". Không thể cùng đúng.

## Lý do gốc của B-02 vẫn còn nguyên

Vòng lặp: review-only PR cần được review → PR review đó cần được review → vô hạn.

Ba cách thoát, và ADR-0003 chọn sai:
- ❌ **Miễn review đệ quy có điều kiện CI** — ngoại lệ dựa trên một check chưa tồn tại, không ai sở hữu. Đây là B-02 gốc.
- ❌ **Commit thẳng vào `main`** — mâu thuẫn W9a-E. Đây là ADR-0003.
- ✅ **Bỏ hẳn PR riêng cho review.**

## Quyết định

> **Review doc đi kèm chính thứ nó review.**

Reviewer commit file review lên **nhánh đang được review**, và nó vào `main` **qua chính PR của nhánh đó**.

```
codex/p0-w6a-allocator
  ├── <các commit của Codex>
  └── docs/claude/<ngày>/review-p0-w6a-allocator.md   ← Claude thêm vào ĐÂY
```

Không PR riêng. Không ngoại lệ. Không direct push. Vòng lặp đệ quy biến mất vì **không còn PR nào chỉ chứa review**.

Với thứ đã nằm trên `main` (charter, ADR, spec): review đi kèm **nhánh sửa** thứ đó. Review của một artifact không có nhánh sửa đi kèm nhánh tiếp theo chạm vào artifact đó.

### Hệ quả phụ đáng giá

Verdict `REQUEST_CHANGES` giờ **về mặt cơ học** chặn được merge, vì review nằm trong cùng PR. Trước đây verdict chỉ là một file ở nơi khác — người viết code có thể merge mà reviewer không cản được bằng gì ngoài lời nói.

## Chưa làm — không giả vờ đã xong

`W9a-R`: CI check `review-scope` giới hạn diff của review chỉ gồm Markdown dưới `docs/<owner>/<YYYY-MM-DD>/review-*.md`, chặn executable/binary/symlink, kèm test âm tính. **DRI Codex.**

Có check đó thì mới mở lại được mô hình review-only PR độc lập — nếu sau này thấy cần. **Chưa có thì không mở.** Đây chính là bài học của B-02: đừng viết ra một ngoại lệ trước khi có cơ chế xác minh nó.

## Nợ để lại, ghi rõ chứ không giấu

Hai review doc đã tồn tại **sai đường** theo quy tắc mới:
- `docs/claude/2026-08-26/review-p0-w9a-repo-guard.md` — đã trên `main`
- `docs/codex/2026-08-26/review-claude-2026-08-26.md` — trên nhánh của Codex

**Không viết lại lịch sử để dọn.** Rewrite `main` gây hại nhiều hơn hai file đặt sai chỗ. Ghi lại ở đây và áp dụng quy tắc mới từ review tiếp theo.
