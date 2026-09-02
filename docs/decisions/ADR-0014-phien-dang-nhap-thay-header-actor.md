# ADR-0014 — Phiên đăng nhập thay header `X-Actor-ID` khi chạy production

- **Trạng thái:** 🟡 **ĐỀ XUẤT** 2026-09-02 — **Lead chấp nhận rồi Codex mới viết `api/` / `db/`**
- **Ngày:** 2026-09-02
- **DRI đề xuất:** Claude (lane `apps/mobile/`) · **Hiện thực server:** Codex · **Cổng:** Lead
- **Nguồn:** QA native 2026-09-02 · kế hoạch RuDi pha B · `app/api/deps.py` · ADR-0011 (không dùng cho OAuth)
- **Chặn:** một người lạ gửi header giả và được đối xử như thành viên nhóm

> **Không viết bảng session, không đổi `get_actor`, không gắn OAuth trước khi ADR này đóng băng.** Cùng lý do ADR-0004 tồn tại: hợp đồng sai ở đây không làm lệch allocator, nhưng làm rò dữ liệu nhóm khác — định nghĩa production-ready hẹp đã đo được là sai.

## Bối cảnh

`get_actor` đọc `X-Actor-ID` / `X-Actor-Roles` / `X-Actor-Contexts` và tin chúng. Comment trong `deps.py` nói rõ: *gateway tin cậy phải ghi đè, đây không phải auth production.* Gateway đó không tồn tại. Client Expo gửi header thẳng. RuDi login trên nhánh `claude/p0-w-rudi-human-loop` (PR mobie session) là skip có ghi nhãn «bản trải nghiệm». `PUT /people/{id}` và `POST /identity/...` mint person-id từ số điện thoại, không cấp phiên.

Pha A (Claude, `apps/mobile/`) cố ý **không** giả OAuth. Pha B là việc tiếp theo, và máy chủ phải có trước client khi đụng route mới.

## Quyết định

1. **Hai chế độ, một cờ env.** Tên cờ do Codex chọn khi hiện thực; hành vi bắt buộc:
   - chế độ *dev/demo*: giữ `X-Actor-ID` như hiện tại, để test Postgres và `/legacy` còn chạy;
   - chế độ *prod*: `get_actor` **không** tin `X-Actor-ID` do client gửi. Thiếu phiên hợp lệ → **401**. Gửi header giả khi đã bật prod → **401**, không 200 với actor giả.
2. **Phiên là hàng server.** Codex thêm persistence (bảng / event — lựa chọn schema thuộc Codex, không thuộc ADR này) cho: token mờ, `person_id`, hạn, thu hồi. Token không phải UUID người; không nhét person-id vào chỗ client có thể sửa rồi được tin.
3. **Cấp phiên không phải OAuth.** Một route nội bộ (ví dụ đổi person-id đã mint lấy token) đủ cho Pha B. Google / Apple / OTP nhà cung cấp **cấm** trong PR hiện thực ADR này.
4. **Client (Claude, sau khi route sống):** gửi `Authorization: Bearer …`, giữ token trong SecureStore, không ghi person-id vào header. RuDi 21 màn tiếp tục bản trải nghiệm khi chưa có token — copy phải nói vậy, không im lặng giả Minh Anh là user đã đăng nhập.
5. **Không đụng allocator, không đụng sổ.** Auth không được thành đường ghi tiền thứ hai.

## Tiêu chí ra (Pha B xong)

| Phép đo | Kết quả bắt buộc |
|---|---|
| Cờ prod + request không token, có `X-Actor-ID` hợp lệ hình thức | 401 |
| Cờ prod + token đã thu hồi hoặc hết hạn | 401 |
| Cờ prod + token còn hạn | actor đúng `person_id` của phiên, roles/context **suy từ DB**, không từ header client |
| Cờ dev | hành vi cũ, bộ `tests/api` và `tests/postgres` hiện tại vẫn chạy được (Codex được thêm case prod, không được phá case dev) |
| Golden allocator | không đổi |

## Những phương án bị bác

**Tin `X-Actor-ID` mãi, «gateway sẽ tới».**
Bác. Không có gateway. Production-ready đã đo là sai vì đúng chỗ này.

**OAuth Google/Apple trong cùng PR với bảng session.**
Bác. Đó là Pha D: secret nhà cung cấp, native rebuild, consent. Pha B chỉ cắt đường giả actor.

**Zustand/MMKV làm nguồn sự thật phiên.**
Bác. Phiên là hàng server. Cache client không cấp quyền.

**Claude sửa `deps.py` «cho lẹ».**
Bác. Ranh giới sở hữu 2026-08-27: Codex giữ `api/` và `db/`.

## Hệ quả

- Lead chấp nhận → Codex mở nhánh `codex/p0-w-rudi-session` (hoặc Work ID Lead đặt), PR riêng, Claude review.
- Claude không gửi SecureStore / Bearer trước khi route cấp token có trên nhánh Codex đã merge hoặc đang review với contract đóng băng.
- Pha C (API public TLS + EAS preview) **phụ thuộc** Pha B: đưa `EXPO_PUBLIC_API_URL` ra internet khi header giả vẫn ăn thì mở lỗ ra ngoài máy.
- ADR-0006 không đổi: test xanh không phải bằng chứng hành vi người thật.

## Đường lùi

Tắt cờ prod, `get_actor` trở lại header. Bảng session để nguyên, không xoá lịch sử.
