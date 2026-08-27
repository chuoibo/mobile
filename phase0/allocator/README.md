# W6 — allocator tiền *(đã chuyển thành code sản phẩm)*

> **ADR-0006 đổi thân phận W6:** từ *oracle nghiên cứu dùng một lần* thành **code sản phẩm**.
> Tài sản đã chuyển đi, không còn bản sao ở đây để tránh hai bản trôi khỏi nhau:

| Cũ | Mới |
|---|---|
| `phase0/allocator/golden/` | `services/api/tests/domain/golden/` |
| `phase0/allocator/tests/` | `services/api/tests/domain/` |
| `phase0/allocator/contract.py` | `services/api/app/domain/contract.py` |
| *(chưa từng tồn tại)* | `services/api/app/domain/allocator.py` |

Hợp đồng vẫn là `docs/decisions/ADR-0004-hop-dong-allocator.md`, **đóng băng 2026-08-27** sau 4 vòng review.

## Cái gì KHÔNG chuyển: bài tập hai bản viết mù

Bỏ, có lý do ghi ở `ADR-0006`. Tóm tắt: bốn vòng review hợp đồng **đã làm xong** phần việc mà differential test định làm — lôi ra 22 chỗ spec im lặng, trước khi có dòng code nào.

Ba lớp bảo vệ còn lại, mỗi lớp một tuyên bố khác nhau, **không lớp nào một mình là cổng** — xem `services/api/tests/domain/`.
