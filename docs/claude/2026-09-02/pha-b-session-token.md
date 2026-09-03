# Pha B — bàn giao Codex: phiên thay header actor

- **Ngày:** 2026-09-02 · **Sửa:** 2026-09-03
- **Từ:** Claude
- **Tới:** Codex (review hợp đồng + hiện thực `api/`/`db/`) · Lead (cổng ADR)
- **PR này (docs, ĐỀ XUẤT):** https://github.com/chuoibo/ru-di-app/pull/513
- **PR mobile Pha A (không lẫn):** https://github.com/chuoibo/ru-di-app/pull/512

Hợp đồng: [ADR-0014](../../decisions/ADR-0014-phien-dang-nhap-thay-header-actor.md). Trạng thái **ĐỀ XUẤT** đến khi Lead chấp nhận. Đầu vào cùng lane với tác giả **không** phải verdict ADR-0007.

Không viết code `api/` hay `db/` trên nhánh Claude. Không OAuth / OTP SMS trong PR hiện thực ADR này. Không đổi tên remote của #513.

## Việc Codex làm sau khi Lead chấp nhận

1. Cờ env: **mặc định prod**; dev bật rõ; một dòng log lúc khởi động.
2. Session persist **chỉ SHA-256 digest** (cùng `GuestLink` / `OutingInvite`). Cấm token thô. Cấm `invite.id` làm secret.
3. Bootstrap: đổi lời mời **đích danh** (`group`/`friend`) lấy Bearer = `invited_person_id`. Không đọc `person_id` body. `source=link` không cấp phiên.
4. Nới `link_carries_digest` để đích danh mang digest. Re-login: **xoay digest tại chỗ** trên hàng `uq_outing_invites_person` đã có — không INSERT hàng thứ hai, không xoá `accepted_at`.
5. Roles: bảng nguồn 10 giá trị `ROLES` trong ADR mục 7. `context_ids` từ membership. Không fail-open role chưa có nguồn.
6. Membership tạo qua bootstrap đích danh: `origin=NAMED`. ACTIVE nhận phiên mới giữ ACTIVE.

## Tiêu chí tự kiểm trước khi gọi review (trùng ADR)

Prod + header giả không token → 401. Mặc định không env = prod. Log ghi chế độ.

Bootstrap `link` → không phiên. Đích danh còn hạn → đúng `invited_person_id`, không đọc `person_id`. Cùng digest lần hai → 409; accept link cũ vẫn chạy nếu chưa tiêu. Xoay → digest cũ chết, digest mới cấp phiên. ACTIVE + phiên mới → vẫn ACTIVE. Provenance `NAMED`.

Mỗi role chưa nguồn trên phiên (`advancer`, `recipient`, `sender`, `creditor`, `platform_moderator`): một ca prod. `batch_owner`: extra_roles từ resource. Ca âm: `member` không tự nhận `creditor` / `platform_moderator`. Case dev gửi header không phải chứng minh prod.

`tests/api` + `tests/postgres` chế độ dev vẫn xanh. Golden không đổi.

## Việc Claude làm sau khi route sống

`apps/mobile/`: Bearer + SecureStore. PR khác, sau contract đóng băng.

## Pha C–E (không làm trong PR hiện thực ADR)

| Pha | Ai | Chặn |
|---|---|---|
| C | Infra + Claude | API public TLS; EAS `preview`. **Cần B đã có đổi-invite-đích-danh** (danh sách mời đóng). Không chờ OAuth. Public + header giả = lỗ mở. |
| D | Claude + creds native | Google / Apple — bỏ bước nhờ người mời; không phải đường re-login đầu tiên |
| E | Lead | Quét VietQR bằng app ngân hàng. Không agent nào ký hộ (ADR-0010). |

## Đường lùi (nhắc)

Chỉ Lead tắt prod trên host người thật; mỗi lần tắt = PR hoặc issue Lead đóng (ngày, host, lý do). Bảng session không xoá.
