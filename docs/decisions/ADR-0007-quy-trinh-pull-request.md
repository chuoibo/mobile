# ADR-0007 — Chuyển sang Pull Request thật

- **Trạng thái:** ĐÃ CHẤP NHẬN
- **Ngày:** 2026-08-27
- **Người quyết:** **LEADER**
- **Bổ sung cho:** `ADR-0005` (đường đi của review doc)

## Chỉ thị

> *"2 bạn tự tạo PR tự review PR cho nhau cho tôi rồi tự code tôi review code cuối ở main thôi"*

## Quyết định

| | Trước | Sau |
|---|---|---|
| Review sống ở đâu | File Markdown trong nhánh | **Pull Request trên GitHub** |
| Ai review | Người kia, qua file review | Người kia, qua **PR review** |
| Leader xem ở đâu | Từng nhánh | **Chỉ `main`** |
| Vào `main` bằng gì | `git merge` cục bộ | **Merge PR** |

`ADR-0005` vẫn đúng ở phần cốt lõi — **review đi kèm chính thứ nó review** — nhưng cơ chế giờ là PR, không phải file. Vòng lặp "review-only PR cần được review" biến mất vì review là **comment**, không phải commit.

Review doc dài vẫn commit lên nhánh khi cần lập luận nhiều hơn một comment. Verdict thì đặt ở PR review: `APPROVE` / `REQUEST_CHANGES` / `REJECT`.

## Hệ quả

**Leader chỉ đọc `main`.** Nghĩa là thứ vào được `main` phải tự giải thích được — mô tả PR phải nói **cái gì thay đổi và vì sao**, không bắt người đọc suy từ diff.

**Không ai merge PR của chính mình** khi người kia còn gọi được. Codex đang hết hạn mức tới 2:49 PM; các PR mở trong khoảng đó **chờ**, không tự merge.

## Nợ đã biết

`W9a-E` (bật branch protection, required check) vẫn thuộc leader lane và **chưa bật**. Cho tới lúc đó, quy tắc "không tự merge PR của mình" là **kỷ luật**, không phải cưỡng chế. Đây đúng là khoảng trống mà blocker `B-01` của Codex đã chỉ ra.
