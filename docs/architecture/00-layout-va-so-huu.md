# Layout monorepo và quyền sở hữu

> Chốt 2026-08-27 theo `ADR-0006`. Mục đích: hai engineer làm song song mà **không chạm cùng file**.

## Cây thư mục

```
services/api/                       FastAPI, Python 3.12+
  app/
    domain/                         ← CLAUDE. Thuần, không I/O, không framework
      allocator.py                  hiện thực ADR-0004
      contract.py                   hằng số + exception (từ phase0)
      ledger.py                     bất biến sổ, số dư tính lại được
      collection.py                 máy trạng thái đợt thu (spec mục 8)
    db/                             ← CODEX
      models.py · migrations/ · repository.py
    api/                            ← CODEX
      routes/ · deps.py · main.py
  tests/
    domain/                         ← CLAUDE
    db/ · api/                      ← CODEX

services/api/app/web/                ← CLAUDE. Trang cho khách, render từ server
  templates/ · static/               Khách KHÔNG cài gì — nên đây là web, không phải RN

apps/mobile/                        ← CLAUDE. Expo + TypeScript, làm SAU trang khách
phase0/                             ĐÓNG BĂNG TẠI CHỖ. Không sửa, không xoá
docs/protocol/v1/                   ĐÓNG BĂNG TẠI CHỖ
scripts/repo_guard.py               ← CODEX (đã xong)
```

## Nguyên tắc phân tầng — không thương lượng

**`domain/` không được import bất cứ thứ gì từ `db/`, `api/`, hay `payments/`.**

Lý do là bất biến 3 của spec mục 6.8: *số dư luôn tính lại được từ sổ; cache không bao giờ là nguồn sự thật.* Nếu domain biết về ORM, sớm muộn có người tính số dư bằng một cột đã lưu.

Kiểm bằng test import, không bằng lời hứa.

## Ranh giới giữa hai người

> **Đổi ngày 2026-08-27 theo quyết định của leader.** Trước đó không ai sở hữu UI — đó là lỗ thật trong bảng phân công. Leader chốt: Claude làm UI, Codex giữ backend.

| | Claude | Codex |
|---|---|---|
| Sở hữu | `web/` (trang khách), `apps/mobile/` | `db/`, `api/`, `payments/`, `domain/`, `tests/` phía backend |

**`domain/` bàn giao sang Codex.** Đã xong: `allocator` · `ledger` · `collection` · `permissions` · `visibility`. Còn thiếu: vòng đời `OffsetProposal` (mục 8.8) và quy tắc phạm vi capability của `GuestLink` (mục 8.2, bất biến 6). Hai cái đó giờ thuộc Codex.

**Ranh giới ở trang khách:** Claude sở hữu **template, câu chữ, style**. Codex sở hữu **route và truy cập dữ liệu**. Route gọi vào template; template không bao giờ tự query.

### Bảng cũ, giữ để đối chiếu

| | Claude | Codex |
|---|---|---|
| ~~Sở hữu~~ | ~~`domain/`, `tests/domain/`~~ | ~~`db/`, `api/`, `payments/`~~ |
| Đụng vào của nhau | qua PR + review, không sửa thẳng | như trên |
| Nhánh | `claude/api-domain-*` | `codex/api-infra-*` |

Domain là **thuần**: nhận `dict`, trả `dict`, ném `AllocationError`. Codex viết adapter ở `db/` và `api/`, **không sửa domain để cho vừa framework**.

## Lát cắt dọc đầu tiên

```
POST /expenses          tạo khoản chi, gọi allocator, trả đề xuất
POST /expenses/{id}/confirm    xác nhận → ghi ConfirmedAllocation vào sổ
POST /batches           gom nghĩa vụ chưa thanh toán thành đợt thu
POST /batches/{id}/publish     freeze → publish → sinh envelope
GET  /g/{token}         trang cho khách, KHÔNG cần cài app
POST /g/{token}/report  khách báo đã chuyển
POST /obligations/{id}/confirm-receipt   người nhận xác nhận
```

Đúng bước 2–4 của mục 14.3 trong spec. **Chưa làm Home, chưa làm tab, chưa làm vỏ chat** — mục 14.3 cấm thiết kế Home trước khi biết chính xác những hành động nào tồn tại.

## Ràng buộc mang từ spec sang, không được quên

| Ràng buộc | Nguồn |
|---|---|
| Tiền là **số nguyên đồng**, không float ở bất kỳ đâu | mục 4, bất biến 2 |
| `Σ ConfirmedAllocation == tổng khoản chi`, 100% | mục 4, bất biến 1 |
| Số dư **tính lại được** từ sổ; cache không phải nguồn sự thật | bất biến 3 |
| Sửa khoản chi tạo **phiên bản mới**, không ghi đè | mục 4 |
| `receiver_confirmed` **không phải** bằng chứng ngân hàng | mục 8, 15 |
| Không giữ tiền, không làm ví, và không nói chuyển vào đâu | mục 14.1 |
| `completed` chỉ do domain transition sinh ra, không có nút "đánh dấu xong" | bất biến 7 |
| Ghi riêng `recorded_by` · `paid_by/advancer` · `payer_acknowledgement` | mục 3 |
