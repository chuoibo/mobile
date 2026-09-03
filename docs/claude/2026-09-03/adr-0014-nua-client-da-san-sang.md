# ADR-0014 — nửa client: cái tôi định làm, và cái đã có sẵn trên main

- **Nhánh:** `claude/p0-w-rudi-du-lieu-that`
- **Trạng thái ADR-0014:** 🟢 **ĐÃ CHẤP NHẬN VÀ ĐÃ HIỆN THỰC** (PR #514, `main` tại `6aad3cf`).
- **Doc này viết lại 2026-09-03** sau khi #514 merge. Bản trước mô tả một hợp đồng cần Codex ship; hợp đồng đó **đã ship rồi**, và một phần việc tôi làm song song trở thành trùng lặp. Giữ lại vì phần trùng lặp đó là bài học, không phải rác.

---

## 1. Cái đã có trên `main`, không phải trên nhánh này

| Việc | Chỗ |
|---|---|
| `POST /sessions` đổi lời mời đích danh lấy phiên | `services/api/app/api/routes/sessions.py` |
| Đọc/ghi phiên, SecureStore, `Idempotency-Key` chống mất token | `apps/mobile/src/phien.ts` (208 dòng) |
| Bearer gắn vào mọi request có danh tính | `apps/mobile/src/api.ts` — `datTokenPhien` / `tokenPhienHienTai` |
| `authorization` trong CORS preflight | `services/api/app/api/cors.py` |
| e2e chạy uvicorn ở chế độ **prod** với phiên thật, 9/9 trong CI | `scripts/e2e_slice.sh` |
| Bốn màn đã nối | `NhanLoiMoi`, `MoiVaoChuyen`, `LenPlan`, `quan-tri` |

## 2. Cái tôi đã làm song song, và đã XOÁ khi gộp

Nhánh này từng có `src/rudi/phien.ts` (một seam ném `ChuaCoRouteError`), một nửa token trong `src/rudi/kho.ts`, và bearer riêng trong `api.ts`. Cả ba **đã xoá** khi gộp `origin/main`.

Không phải vì bản của main "thắng" mà vì hai bản hiện thực của **một** credential là hình dạng làm cả cây không trả lời được câu «cái nào đang có hiệu lực». Nhánh này giờ đọc `khoiPhucPhien()` của main và đưa token cho `datTokenPhien()` của main.

**Một chỗ tôi đã sai và main đúng.** Tôi bỏ hẳn `X-Actor-ID` khi có bearer, viện mục 7. Main **vẫn gửi cả hai**, có lý do ghi tại chỗ: `get_actor` chỉ đọc bộ ba đó khi host ở `dev`, còn `prod` thì lờ đi — nên gửi cả hai làm **một bản dựng** chạy được với cả máy demo lẫn host thật mà không cần cờ. Bản của tôi buộc phải có hai bản dựng.

## 3. Cái vẫn còn thiếu, đã đo lại trên `main` tại `03eb05a`

**Một phiên chưa cho biết NHÓM nào.** `SessionResponse` mang `token`, `person_id`, `expires_at`, `membership_state` — **không** có `context_id`. `contexts.py` khai `POST /contexts`, `GET /contexts/{id}`, members, balances, membership accept, và **không có route nào liệt kê nhóm của một người**.

Hệ quả trực tiếp: `src/rudi/nguon.ts` vẫn trả `trai-nghiem` khi chỉ có phiên, và nói ra đúng lý do đó. Hai màn tiền chỉ chạy live khi có người ghim `EXPO_PUBLIC_RUDI_ACTOR` + `EXPO_PUBLIC_RUDI_CONTEXT`.

Gỡ được bằng một trong hai, cả hai đều thuộc `api/`:
1. Thêm `context_id` (hoặc `outing_id`) vào `SessionResponse` — lời mời vốn đã thuộc về một outing, nên máy chủ đã biết.
2. Hoặc một route `GET /people/{id}/contexts`.

Cách 1 rẻ hơn và khớp với đường vào: người ta đăng nhập **bằng lời mời vào một chuyến**, nên nhóm là thứ đã biết ngay lúc cấp phiên.

## 4. Cảnh báo còn nguyên giá trị: có phiên chưa làm MỌI màn thành thật

**Đã nối:** Quyết toán và Tài chính — đọc `/contexts/{id}/balances`, `/recap`, `/members`, `/people/{id}/finance`, không chạm `fixtures.ts`.

**Chưa nối:** 19 màn còn lại.

Bẫy đã sập một lần trong lượt làm: nối Quyết toán mà chưa nối Tài chính thì cùng một lần mở app có màn hiện `6.785.000đ` của nhóm seed và màn kia hiện `3.840.000đ` của fixture — **đúng defect PR #512 được mở ra để sửa, quay ngược hướng**. Flow `20-du-lieu-that.yaml` giờ đi qua **cả hai** màn tiền trong một lượt vì lý do đó.

**Luật cho người nối tiếp:** nối màn nào thì thêm assertion cho màn đó vào flow 20 trong cùng commit. Một màn tiền ở chế độ live mà vẫn đọc fixture là một lời nói dối, và nhãn «Dữ liệu demo» đã tắt nên không còn gì cảnh báo người đọc.

## 5. Còn nợ khác

- **`scripts/check_api_contract.py` mù với route khai ngoài `app/api/routes/`.** `/healthz` khai ở `main.py:220` với `include_in_schema=False`, nên client nào gọi nó cũng làm cổng đỏ nhầm địa chỉ.
- **Seed và fixture RuDi kể hai câu chuyện khác nhau** — seed «Team Đà Lạt» 7 người, fixture 8 người với bill Xóm Lèo 1.280.000đ. Ở chế độ live màn hiện số của seed.
- **`repo_guard.py staged` không thấy pin digest hết hạn.** Hook pre-commit chạy `staged`, mà `staged` chỉ soi hunk của diff; allowlist thì ghim sha256 **cả file**. Một thay đổi lockfile không chứa số dài nào vẫn làm pin hết khớp, và chỉ `tree` / `range` bắt được.
