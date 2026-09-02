# Pha B — bàn giao Codex: phiên thay header actor

- **Ngày:** 2026-09-02
- **Từ:** Claude
- **Tới:** Codex · Lead (cổng ADR)
- **PR mobile (Pha A, không lẫn vào đây):** https://github.com/chuoibo/ru-di-app/pull/512

## Việc

Lead đọc [ADR-0014](../../decisions/ADR-0014-phien-dang-nhap-thay-header-actor.md). Trạng thái đang **ĐỀ XUẤT**. Chấp nhận rồi Codex mới đụng `get_actor` / schema.

Không viết code `api/` hay `db/` trên nhánh Claude. Không OAuth trong PR Pha B.

## Tiêu chí Codex tự kiểm trước khi gọi review

1. Cờ prod + `X-Actor-ID` giả, không token → 401.
2. Roles và context_ids suy từ DB của phiên, không copy từ header client.
3. `tests/api` + `tests/postgres` chế độ dev vẫn xanh; thêm case prod, đừng phá case cũ.
4. Allocator / golden không đổi.

## Việc Claude làm sau khi route sống

`apps/mobile/`: Bearer + SecureStore, RuDi login hết skip im lặng. Đó là PR khác, sau contract đóng băng.

## Pha C–E (không làm trong PR này)

| Pha | Ai | Chặn |
|---|---|---|
| C | Infra + Claude | API public TLS; EAS `preview`; `EXPO_PUBLIC_API_URL` không trỏ laptop. **Cần B trước** — public + header giả là lỗ mở. |
| D | Claude + creds native | Google / Apple / OTP nhà cung cấp; OCR camera; GPS check-in 04.03 |
| E | Lead | Quét VietQR bằng app ngân hàng. Không agent nào ký hộ (ADR-0010). |
