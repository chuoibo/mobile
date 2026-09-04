# ADR-0016 — Phạm vi v1 là sản phẩm social theo `feature_list.md`; đăng nhập bằng OTP điện thoại và Google

- **Trạng thái:** 🟡 **ĐỀ XUẤT** 2026-09-03 — chờ Lead đánh ĐÃ CHẤP NHẬN. Mã M1 của lộ trình production-ready không merge trước khi dòng này đổi.
- **Quyết định bởi:** Lead (7 quyết định chốt trong phiên làm việc 2026-09-03, ghi lại ở mục 2).
- **Hiện thực:** lộ trình 8 mốc ở `/home/lakiet/.claude/plans/hi-n-t-i-th-nh-t-glittery-riddle.md` (bản sao sẽ được đưa vào `docs/architecture/02-lo-trinh-production-ready.md` ở PR đầu tiên của M1).
- **Thay đổi phạm vi sản phẩm VÀ một ngoại lệ sở hữu**, không phải thay đổi kỹ thuật thuần. Đọc trước khi trích spec 2026-08-25 để từ chối một tính năng.

## 1. Bối cảnh

Spec `docs/superpowers/specs/2026-08-25-group-hangout-ai-design.md` (ĐÃ HỘI TỤ, đóng băng theo charter §5) cắt khỏi v1 ở §2.2: nhắn tin tự do giữa người với người, gợi ý địa điểm, kế hoạch chuyến đi, kỷ niệm, và nói ở §7.2 «không dùng SMS OTP mặc định». ADR-0006 đã gác Giai đoạn 0 và cho dựng sản phẩm theo §14.3; ADR-0013 đã chấp nhận Expo Router với bốn điểm đến; ADR-0014 dựng phiên đăng nhập nhưng **cấm OTP trong chính PR đó** và để Google/Apple sang «Pha D».

Trong khi đó cây thật đã đi xa hơn spec: `apps/mobile/src/screens/**` có chat nhóm, kết bạn, bản đồ nhóm, album, bình chọn nối vào ~72 route thật; `product/feature_list.md` (47 tính năng) và 21 mockup `product/RuDi_Mobile_Product_Mockups/` mô tả sản phẩm social đầy đủ. Vỏ đang ship (`app/**` + `src/rudi/`) đẹp nhưng đọc fixture. Ngày 2026-09-03 Lead yêu cầu đưa app tới production-ready đúng theo mockup: login thật, kết bạn, group chat, AI trong chat, timeline có chiều sâu, chứng minh trên native.

Hai luật đang xung đột: charter nói «ADR phải được duyệt **trước** khi thay đổi có hiệu lực — không hợp thức hoá hậu nghiệm», còn spec đóng băng nói không làm những thứ Lead vừa yêu cầu. ADR này là chỗ giải xung đột đó, đúng cách charter quy định.

## 2. Quyết định

### 2.1 Phạm vi v1

RuDi v1 là **P0 của `product/feature_list.md` mục 8**: Authentication · Profile · Friends · Group · Group Chat · Create Outing · Discover Places · AI Place Recommendation · Receipt OCR · Bill Split · Expense Tracking · Settlement · Group Memories · AI Group Assistant.

Các cắt ở spec §2.2 **được gỡ** cho: nhắn tin tự do trong nhóm (kèm reaction, ảnh, mention), khám phá địa điểm + chi tiết địa điểm, kế hoạch chuyến đi (kèo, lịch trình, check-in chặng), kỷ niệm (tường nhóm, album, khoảnh khắc), và OTP điện thoại. Spec 2026-08-25 **giữ nguyên tại chỗ** làm lịch sử tranh luận; không sửa một dòng nào trong đó.

**Không đổi**, và ADR này tái khẳng định:

- Ba luật tiền (số nguyên đồng · Σ phân bổ = tổng · số dư tính lại từ sổ) và ADR-0004.
- ADR-0015: sản phẩm nói phần của mỗi người rồi dừng. Không đường thanh toán, không tài khoản ngân hàng, không VietQR — kể cả khi mockup 05.03/07.02 vẽ chúng.
- AI **chỉ tạo đề xuất có kiểu**; executor xác định chạy sau khi đúng chủ thể xác nhận; AI không gây side effect vật chất; mọi kết quả AI sửa được trước khi xác nhận; không có đường lui bí mật sang LLM đa dụng (spec §3, §5.4, §5.5).
- §1.1: không tab trống, không nhãn «sắp có», không ảnh mô phỏng kỹ năng chưa có. Tính năng chưa nối thì **gỡ khỏi tab / sheet tạo mới**, không để trên fixture.
- Khách mở link chỉ thấy envelope của mình. `receiver_confirmed` không phải bằng chứng ngân hàng. `completed` chỉ do domain transition.
- Luật §7.2/§7.3 về danh tính: **không bao giờ merge tài khoản theo tên, biệt danh hay email**; liên kết tài khoản là việc riêng, có ADR riêng khi làm.

### 2.2 Danh tính: hai cửa phiên mới, cùng một bảng phiên

Cả hai cửa mint `account_sessions` **y như** `POST /sessions` của ADR-0014: `secrets.token_urlsafe(32)`, chỉ lưu digest SHA-256, TTL cũ, thu hồi bằng `DELETE /sessions/current`. Không JWT, không token loại hai.

**OTP điện thoại** — `POST /auth/otp/request {phone}` → `POST /auth/otp/verify {challenge_id, phone, code}` → `SessionResponse`.

1. **Không lưu số điện thoại.** Bảng `otp_challenges` chỉ giữ `phone_digest = HMAC(MOBILE_PERSON_ID_KEY, "ru-di:otp-phone:v1:" + số_chuẩn_hoá)` và `code_digest` (HMAC theo `id` challenge). Cùng mức rò rỉ với `people.id` hiện tại, không hơn.
2. Mã 6 số, sống 300 giây, tối đa 5 lần thử rồi cháy; gửi lại sau 60 giây; tối đa 5 challenge / 15 phút / số. Sai mã ⇒ 422 kèm `attempts_left`; hết hạn / đã dùng / không tồn tại / khác số ⇒ **một** 404 chung (không nói cho kẻ dò biết mã từng có thật — cùng lý do ADR-0014 đổi 409 thành 404).
3. `person_id` = `derive_person_id(số_chuẩn_hoá)` sẵn có, nên người từng được bạn thêm bằng số điện thoại (`PUT /people/{id}`) đăng nhập **về đúng row cũ**, giữ tên bạn họ đã đặt. Người mới nhận `display_name = "Thành viên mới"` và client đưa sang màn đặt tên.
4. `SmsSender` là Protocol có hai hiện thực: `LogSmsSender` (không nhà cung cấp; ghi log «đã phát challenge», **không bao giờ log số**, chỉ log mã khi `MOBILE_OTP_LOG_CODES=1`) và `HttpJsonSmsSender` (vendor-agnostic; eSMS.vn / SpeedSMS / Twilio là subclass sau).
5. **`MOBILE_OTP_DEBUG_CODE`** (mã cố định để Maestro và seed đăng nhập xác định) **chỉ hợp lệ khi sender là `log`**. Cấu hình cả gateway thật lẫn debug code ⇒ `create_app` **từ chối khởi động**, cùng hình dạng fail-closed với `AuthModeInvalid`. Nó độc lập với `MOBILE_AUTH_MODE`: host emulator chạy `prod` (bearer, không tin header) + log sender + mã cố định. Một host không gửi được SMS thật thì cũng không phục vụ được người thật, nên mã cố định không mở rộng bề mặt tấn công. Mã debug không bao giờ xuất hiện trong bất kỳ response.

**Google** — `POST /auth/google {id_token}` → `SessionResponse`.

6. Server verify chữ ký/`exp`/`iss` bằng `google-auth` (đã có sẵn qua `google-genai`, khai tường minh ở `pyproject.toml` + `requirements-dev.txt`) rồi **tự kiểm** `aud ∈ MOBILE_GOOGLE_CLIENT_IDS` (Android client id + Web client id). Thiếu biến ⇒ 503 `google_not_configured` (fail closed). Mọi lỗi token ⇒ **một** 401.
7. Bảng mới `account_identities(person_id, provider ∈ {phone, google}, subject, created_at, last_login_at)` unique `(provider, subject)`. `sub` Google thấy lần đầu ⇒ **`people` mới** (uuid4). **Không tra email, không merge theo email** — email không chứng minh ai cầm số điện thoại nào, và merge nhầm là ghép hai sổ cái của hai người.
8. Client dùng `@react-native-google-signin/google-signin` (cần development build; Expo Go không chạy được) với `webClientId` để nhận `idToken`. Apple Sign-In **chưa** thuộc ADR này (cần iOS + Apple Developer).

**Phiên biết nhóm của mình.**

9. `account_sessions.issued_via ∈ {invite, otp, google, genesis}`; `issued_from_invite_id` non-null ⇔ `issued_via = 'invite'` (CHECK). `scripts/genesis_session.py` ghi `genesis`.
10. `SessionResponse` (mọi cửa, kể cả `POST /sessions`) thêm `issued_via`, `contexts[]`, `is_new_person`, `profile`; `context_id` và `membership_state` trở thành nullable vì phiên OTP/Google có thể chưa thuộc nhóm nào.
11. Route mới `GET /people/me/contexts` (tên, số thành viên, vai trò, trạng thái membership **kể cả `invited` kèm `membership_id`**, tin nhắn cuối, số chưa đọc qua bảng `context_read_marks`) là cách duy nhất phiên biết nhóm. Không claim nào kiểu `X-Actor-Contexts` được đọc nữa — đúng tinh thần ADR-0014 §7.
12. Idempotency scope ở `prod` = `sha256(bearer)` khi có `Authorization` (hiện khoá theo `X-Actor-ID`, nên ở `prod` mọi write có bearer đang dùng chung scope `"anonymous"`).

### 2.3 Ngoại lệ sở hữu, có điều kiện

Charter 2026-08-27 giao `db/`, `api/`, `domain/` cho Codex. Lead quyết định ngày 2026-09-03: **Claude hiện thực trực tiếp cả `apps/mobile/` lẫn backend** cho toàn bộ lộ trình production-ready, vì các lane khác đã dừng từ 31/08 và CI GitHub không chạy (billing). Đây là **ngoại lệ được ghi cho lộ trình này, không phải luật mới** — cùng hình dạng với ngoại lệ ADR-0014 đã ghi. Điều kiện đi kèm: mỗi PR backend ghi câu «Backend do Claude làm theo uỷ quyền ADR-0016; charter không đổi», ghi vào `docs/codex/QUEUE.md` mục nào Claude đang nhận, và không có PR backend nào merge mà thiếu ca `tests/postgres` thật cho persistence mới lẫn ca âm cho từng cửa. Không ai tự review PR của mình; verdict vẫn đăng bằng PR comment (cùng tài khoản GitHub nên `gh pr review` không dùng được); trước khi merge vẫn phải có agy test theo luật đội, và digest của agy không phải bằng chứng — người merge chạy lại cổng trong cây sạch.

### 2.4 Cái không thuộc ADR này

Nơi deploy, TLS/URL công khai, backup ảnh, SMS vendor thật, Sentry, realtime/push, map SDK, tìm kiếm chung, follow/creator, Apple Sign-In, liên kết tài khoản phone↔Google. Mỗi mục cần quyết định riêng khi tới lượt; danh sách và đề xuất một dòng nằm ở mục 10 của kế hoạch.

## 3. Hệ quả

- `nguon.ts` phía client bỏ cặp `EXPO_PUBLIC_RUDI_ACTOR/CONTEXT` khi `contexts[]` có trên phiên; fixture chỉ còn sau cờ dev tường minh; bundle production không bao giờ hiện «bản trải nghiệm».
- `PUT /people/{id}` vẫn là cách một thành viên đặt tên người chưa đăng nhập; OTP sau đó **tìm** đúng row đó.
- Seed mới (`scripts/seed_rudi_world.py`) đăng nhập bằng OTP debug qua HTTP, không precompute `person_id`; host có gateway thật **không seed được**, đúng thiết kế.
- Cây legacy `apps/mobile/src/screens/**` + `App.tsx` + `VoTab` bị xoá theo từng mảng khi vỏ RuDi đạt parity trên native; module API client `*.ts` được giữ và port. Không xoá test trước khi có test thay ở màn mới.
- `README.md`, `PRODUCT.md`, `CLAUDE.md` có các câu đã lỗi thời («chưa có auth production», «chưa quyết Home/tab», «apps/mobile không có trên main», «product/ không có trên main») — sửa trong PR docs kèm ADR này.

## 4. Cái này KHÔNG chứng minh

- Gỡ cắt ở spec không chứng minh sản phẩm social là đúng hướng — ADR-0006 vẫn đúng: **chưa có bằng chứng hành vi nào**. Đây là đánh cược có ý thức của Lead, ghi lại cho người đọc sau.
- Có OTP và Google không chứng minh phân quyền đúng; nó chỉ làm cổng phân quyền đã có bắt đầu có ý nghĩa với người thật (cùng câu ADR-0014 đã nói).
- Mã debug fail-closed không chứng minh gateway SMS thật hoạt động — chưa có vendor nào được nối.

## 5. Phương án đã bác

| Phương án | Vì sao không |
|---|---|
| Firebase Auth / Supabase Auth cho Phone + Google | Thêm một hệ danh tính thứ hai bên cạnh `people`; server vẫn phải verify token họ rồi map sang `account_sessions`; SMS của Firebase cần billing riêng. Lead chọn backend-owned. |
| Lưu `phone_e164` để tra cứu/vận hành | Vi phạm luật «không cột, không cache, không file» cho số điện thoại; digest đã đủ để tra khi client gửi lại số. |
| Auto-merge tài khoản Google với tài khoản phone theo email | Email không chứng minh sở hữu số điện thoại; merge nhầm là ghép hai sổ cái. Spec §7.2 cấm merge theo tên; ADR này mở rộng cấm sang email. |
| Gate mã debug bằng `MOBILE_AUTH_MODE=dev` | Bắt host emulator tin lại `X-Actor-*` — đúng cái ADR-0014 vừa gỡ. Gate theo sender `log` giữ được `prod` trên máy đo. |
| JWT access token | Hai định dạng token; bảng digest đã có và thu hồi được. |
| SSE/WebSocket cho chat trong ADR này | Route sync chạy threadpool 40 thread; giữ một thread mỗi phòng chat sẽ bóp chết route tiền trên một worker. Polling 4 giây bằng cursor `?after=` đã có. Mở lại khi host ≥ 2 worker + store chung. |
| Chỉ làm những gì spec cho phép | Trái với yêu cầu Lead 2026-09-03 và với cây thật đã có; sẽ để 22 màn đẹp tiếp tục đọc fixture. |
| Làm theo yêu cầu, không mở ADR | Charter cấm hợp thức hoá hậu nghiệm; người đọc sau không biết ai quyết. |
