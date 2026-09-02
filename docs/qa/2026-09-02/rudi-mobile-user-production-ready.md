# RuDi mobile — người dùng thường thấy gì, và còn thiếu gì để ra production

- **Verdict:** **KHÔNG SHIP.** Đây là bản trải nghiệm (chip «Bản trải nghiệm» trên nhiều màn). Người lạ cài về sẽ nghĩ họ đang dùng sản phẩm; họ đang xem kịch bản Team Đà Lạt.
- **Đo lúc:** 2026-09-02, trên máy ảo Android, không phải trình duyệt.
- **Cây:** `f63628d` (`mobile: hoàn thiện giao diện RuDi theo mockup`) cộng `apps/mobile/package.json` **chưa commit** (SDK `~57.0.17` trên HEAD → `~54.0.37` trên đĩa). Test chạy trên cây đĩa.
- **Máy:** AVD `rudi-qa3`, Android 15, 1080×2400, qemu headless. Expo Go **54.0.8**. Metro `localhost:8081`.
- **Đối chiếu:** 21 mockup trong `product/RuDi_Mobile_Product_Mockups`. Dữ liệu canonical: Team Đà Lạt, 8 người, chuyến 17–19/10/2026, bill Xóm Lèo **1.280.000đ**, tổng chuyến demo **3.840.000đ**.
- **Tác giả lượt đo:** Claude, charter exploratory trên native. Ảnh chụp nằm ngoài git (`/tmp/rudi-qa-20260902/`) vì repo guard.
- **Không phải:** cổng backend, allocator, Postgres, hay `GET /g/{token}`. Luồng `/legacy` (API demo) **không** được bấm trong lượt này.

Một câu cho người quyết định ship: **màn hình đẹp, điều hướng đi được nhiều chỗ, tiền và tài khoản thì không.**

---

## 0. Production-ready theo người dùng thường nghĩa là gì

Không dùng định nghĩa «có đủ màn». Người dùng thường không mở Expo Go, không gõ `npx expo start`, không biết Team Đà Lạt là fixture.

Họ cần làm được mạch này, bằng dữ liệu **của họ**, trên máy **của họ**:

1. Cài app như cài app khác (Play Store / TestFlight / file APK nội bộ), mở lên không cần laptop lập trình viên.
2. Tạo tài khoản thật; sai mật khẩu thì bị từ chối; quên mật khẩu thì lấy lại được. Hôm sau mở lại vẫn là họ, không phải Minh Anh.
3. Tạo hội / rủ bạn thật. Bạn kia thấy cùng một chuyến, không thấy chuyến của hội khác.
4. Tạo kèo, lên lịch, chat, bình chọn — thao tác **ghi lại**, không chỉ đổi màn.
5. Chụp hoá đơn thật, chia đúng tổng (số nguyên đồng, tổng phân bổ = tổng bill), thấy số trên quyết toán **trùng** số trên tài chính cá nhân.
6. Chuyển khoản bằng VietQR quét được bằng app ngân hàng, rồi người nhận xác nhận trong app — app không được viết «đã chốt từ sổ cái» nếu số đang hard-code.
7. Giữ ảnh kỷ niệm của hội đó. Sửa hồ sơ, xem tiền của mình.

Lượt native này đo được mục 4–7 **ở lớp vỏ UI**. Mục 1–3 **chưa có** trên đường người dùng vừa bấm. Mục 5–6 **nói dối** trên màn đang mở.

Định nghĩa hẹp phía kiến trúc (cài được · hoá đơn thật · không đọc dữ liệu hội khác) nằm ở `docs/architecture/01-duong-toi-production.md` — đo ngày 2026-08-30 tại SHA khác. Doc này **không** chép số của bản đó. Đây là góc người cầm điện thoại ngày 2026-09-02.

---

## 1. Người dùng làm được gì hôm nay

Họ mở được một app native (qua Expo Go + Metro), đi qua bốn tab **Khám phá / Lên plan / Tin nhắn / Cá nhân**, bấm `+`, và mở gần như đủ 21 màn mockup.

| Việc người dùng thử | Kết quả trên emulator |
|---|---|
| Vuốt welcome | 4 chấm trang trí; swipe không đổi nội dung |
| «Rủ Đi thôi!» | Vào login |
| «Tìm hiểu thêm» | **Bỏ qua login**, đáp Khám phá |
| Gõ email bất kỳ + mật khẩu 3 ký tự | Vào cá nhân hoá. Placeholder vẫn ghi «Ít nhất 8 ký tự» |
| Google / Apple / Quên mật khẩu / Đăng ký | Không nhúc |
| Chọn sở thích rồi tiếp | Vào Khám phá. Không lưu server |
| Tìm địa điểm từ khoá không có | Hiện «Chưa thấy nơi phù hợp» — **ổn** |
| Chip Cafe / Vui chơi / … | Đổi màu chip; **vẫn 4 quán** |
| Tim / lọc «Từ 90% hợp gu», «Trong 2 km», «Đã lưu» | Có lọc (trên 4 fixture) |
| Mở chi tiết quán, thêm vào chuyến | Mở lịch trình AI **cũ**; 18:00 vẫn «BBQ bên hồ Tuyền Lâm», không phải Xóm Lèo |
| Chat nhóm | Có composer + thẻ AI + lối sang vote. Gửi tin: code cộng tin vào state local; `adb input text` không dính field nên **chưa chứng minh trên máy** |
| Xác nhận vote | Đổi lựa chọn trên UI; nút xác nhận **không** `onPress` |
| Tạo cuộc hẹn | Form đã điền sẵn Đà Lạt. Bỏ chọn 1 người được. «Chọn tất cả» chết. «Tạo cuộc hẹn» nhảy timeline fixture |
| Check-in | Composer caption trên ảnh mẫu, không phải theo dõi 4/8 đã tới |
| Bill Xóm Lèo | Giấy vẽ 6 dòng, tổng **1.280.000đ** khớp canonical. Không camera, không OCR |
| Gán người từng món | Chạm avatar đổi được trên màn. Xác nhận nhảy settlement hard-code, **không** tính lại từ gán |
| Quyết toán | Số mâu thuẫn — xem B1 |
| Tường / album | Số 256 / 18 / 12 in ra; ảnh thật trên lưới khoảng vài tấm |
| Tài chính | Cùng 2.840.000đ dù chọn «Tháng này / 3 tháng / Năm 2026» |
| Cài đặt, chỉnh hồ sơ, đã lưu, tài khoản | Chết |

Hành trình người dùng **không** tạo được hội mới, không mời bạn, không giữ phiên, không chụp bill thật, không thanh toán.

---

## 2. Điểm tốt (đã thấy trên máy)

Những thứ này không cứu được ship, nhưng đừng giả vờ app trống.

- **Vỏ 21 màn có thật trên native**, không chỉ mockup PNG. Bốn tab + sheet `+` đi được; nhiều route mở bằng deep link `exp://127.0.0.1:8081/--/…`.
- **Nhận mình là demo.** Chip «Bản trải nghiệm» / «OCR demo» / «Camera demo» xuất hiện. Ghi chú settlement: «Đã trả là xác nhận trong RuDi, không phải bằng chứng ngân hàng» — câu này đúng luật sản phẩm (`receiver_confirmed` ≠ chứng từ bank).
- **Bill 1.280.000đ** và 6 dòng Xóm Lèo khớp `CANONICAL_DATA.md`. Nhóm 8 người, ngày 17–19/10/2026, tên Team Đà Lạt nhất quán hơn mockup PNG cũ (một số PNG còn 7 người).
- **Tìm kiếm rỗng** và **lọc khoảng cách / match / đã lưu** có phản hồi. Tim quán đổi được trên màn.
- **Gán món theo người** (chạm avatar) là tương tác thật trên client, không chỉ ảnh tĩnh.
- **Thẻ AI plan trong chat** có — mockup audit từng đánh thiếu.
- **Nút ngày** trên lịch trình AI đổi ngày được. «Dùng plan này» đi tới timeline.
- Sheet `+` liệt kê đúng bốn việc (tạo hẹn, chia bill, đăng kỷ niệm, luồng backend) và hàng nào gắn `href` thì mở được **khi vào từ FAB trong app**.

Đó là chất lượng **demo UI**. Người dùng thường sẽ đọc chúng như sản phẩm.

---

## 3. Điểm xấu — xếp theo mức hại người dùng

### Chặn ship (người dùng sẽ tin số / tin tài khoản)

**B1 — Cùng một chuyến, ba con số tiền, vẫn ghi «đã chốt từ sổ cái».**

Màn `Quyết toán chuyến đi` (`/settlements/team-da-lat`):

- Hero: «Tổng chi tiêu của nhóm **3.840.000đ** · Đã chốt từ sổ cái · 8 thành viên».
- «Minh Anh sẽ nhận **780.000đ**» = 320 + 260 + 120 + 80. Nội bộ bốn dòng này cộng đúng.
- Thanh: «Đã nhận 580.000đ · còn 200.000đ».
- Chỉ 4/8 thành viên xuất hiện là người chuyển. Bốn người kia biến mất khỏi danh sách trả.

Màn `Tài chính của tôi`:

- «Tổng chi tháng 10 **2.840.000đ**»
- Cần trả **200.000đ**, Sẽ nhận **780.000đ** từ 4 người.

Người dùng không cần biết «sổ cái». Họ thấy 3,84 triệu, 780 nghìn và 2,84 triệu trên cùng một chuyến. Luật 3 của repo: số dư tính lại từ sổ; màn này **không** đang đọc sổ — `DEMO_GROUP.tripTotalVnd` và mảng `SETTLEMENTS` hard-code trong `Bill.tsx`.

Repro: mở `/settlements/team-da-lat`, kéo xuống, rồi `/finance`.

**B2 — Đăng nhập không thể thất bại.**

- Placeholder: «Ít nhất 8 ký tự». Nút Enable khi `password.length >= 3` (`Onboarding.tsx`).
- Email bất kỳ + mật khẩu 3 ký tự vào cá nhân hoá.
- Google, Apple, «Quên mật khẩu?», «Đăng ký ngay»: không `onPress` (hoặc Pressable trống).
- Mockup 01.02: Google / Apple / SĐT + OTP, lỗi khi sai.
- Không có phiên. Hôm sau mở lại vẫn kịch bản Minh Anh.

Repro: Welcome → Rủ Đi thôi → email bất kỳ → `abc` → Đăng nhập.

**B3 — «Thêm vào Đà Lạt cuối tuần» không thêm quán đó.**

Từ Tiệm Nướng Xóm Lèo, CTA mở lịch trình AI generic. Slot 18:00 vẫn BBQ Tuyền Lâm.

Người dùng hiểu nút là «nhét quán này vào chuyến». App chỉ đổi route.

### Hỏng chức năng (đã bấm, tái lập được)

| ID | Người dùng gặp | Repro |
|---|---|---|
| F1 | Welcome 4 chấm nhưng không có 4 slide | Welcome, swipe ngang |
| F2 | «Tìm hiểu thêm» = vào app luôn, không giải thích sản phẩm | Welcome → Tìm hiểu thêm |
| F3 | Chip loại hình (Cafe, …) không lọc danh sách | Khám phá → Cafe — vẫn 4 quán. `category` không nằm trong `visiblePlaces` |
| F4 | Banner «tìm thấy **12** nơi» trong khi chỉ có 4 `PLACES`. Search `zzzzkhongco` vẫn để banner 12 phía trên «0 kết quả» | Khám phá; AI Match |
| F5 | «Chỉnh lịch trình» (copy còn nói kéo thả) không làm gì | Lịch trình AI |
| F6 | «Xác nhận lựa chọn của tôi» không `onPress`. Kết quả 4/3/1 phiếu hiện **trước** khi vote | `/votes/diem-den` |
| F7 | «Chọn tất cả» không `onPress`. Bỏ Thanh → 7/8, bấm Chọn tất cả vẫn 7/8 | `/outings/new` |
| F8 | Chết: Đổi ảnh (check-in), Nhắc 2 người đang chờ, Chia sẻ quán, Cài đặt / Chỉnh hồ sơ / Đã lưu / Tài khoản. Segment tài chính đổi tab nhưng **2.840.000đ** không đổi | các màn đó |
| F9 | Check-in là viết caption trên ảnh stock. Mockup 04.03: 4/8 đã tới, map, nhắc người chưa tới, live location tới 11:30 | `/check-ins/new` |
| F10 | OCR là giấy vẽ. «Chụp lại» bật khung camera giả. Badge: «Sẵn sàng đọc 6 dòng bằng OCR» khi 6 dòng đã in sẵn | `/smart-split/xom-leo/review` |
| F11 | Deep link `/create` làm Expo Go crash («requires a newer version of Expo Go»). FAB `+` trong app sau đó mở sheet được | `exp://…/--/create` |
| F12 | Giữa session: Expo Go fatal `Failed to download remote update`. Reload xong chạy lại. Session native **không ổn định** | sau timeline, không thoát Expo Go |

### Lệch mockup / copy (thấy trên máy, chưa hẳn crash)

- Tên sản phẩm **Rủ Đi** trên welcome, **RuDi** trên cá nhân hoá và nhiều câu AI.
- Login là email/password, không phải 01.02.
- Cá nhân hoá: không budget preset, không đồng bộ danh bạ, bước `1/1`.
- Khám phá: «Đà Lạt, Lâm Đồng» không phải picker. Chuông thông báo không có hộp thư.
- Chi tiết quán: không map, không «Chỉ đường». Giờ mở cứng.
- Tạo hẹn: ngày/điểm đến không phải date picker. Lưới thành viên chỉ tên riêng — hai «Minh». CTA «Tạo cuộc hẹn» nằm dưới fold trên 1080×2400.
- Tường: thiếu tab Tường / Album / Kế hoạch / Thành viên.
- Album: đếm 256/18/12, lưới ~4 thumbnail. «Thêm ảnh» không đi photo picker hệ thống (trong lượt này).
- Hồ sơ: Minh Anh, 12 chuyến / 6 hội / 256 kỷ niệm. Mockup 07.01 là Tuấn Kiệt. Không đếm bạn, không chip sở thích, không public/private.
- Thành tích: cấp 12 / 12/18 huy hiệu. Mockup: Level 7, lưới Food Hunter / Bill Hero.
- Quyết toán: **không VietQR**. Tài chính: không Đã trả / Còn nhận / Còn phải trả + QR như 07.02.

---

## 4. Tính năng — cái app **có** trên UI, và cái **chưa dùng được**

Cột «Người dùng thường» = mở app như khách, không biết fixture, không deep-link QA.

Chú giải: **Vỏ** = màn/route có, dữ liệu demo, thao tác không bền. **Chết** = bấm không đổi gì. **Nói dối** = copy hoặc số mâu thuẫn với hành vi. **Chưa đo** = không kết luận pass.

### 01. Bắt đầu

| Màn | Mockup | Trên native | Người dùng thường |
|---|---|---|---|
| 01.01 Welcome | READY | Có. CTA chính đi login | Vỏ. Pager chết (F1). «Tìm hiểu thêm» skip auth (F2) |
| 01.02 Login | READY | Có form email | **Không phải auth.** B2 |
| 01.03 Cá nhân hoá | READY | Chip chọn được | Vỏ. Không persist |

### 02. Khám phá

| Màn | Mockup | Trên native | Người dùng thường |
|---|---|---|---|
| 02.01 Khám phá | READY | 4 quán fixture, search rỗng OK | Không đổi thành phố, không thông báo. Chip loại hình chết (F3). «12 nơi» (F4) |
| 02.02 AI Match | NEEDS UPDATE | Xếp hạng 4 quán gắn nhãn 12 | Không phải tìm kiếm tự nhiên / LLM |
| 02.03 Chi tiết quán | NEEDS UPDATE | Ảnh + mô tả + CTA | Không map/chỉ đường. Thêm vào chuyến nói dối (B3). Share chết |

### 03. Chat & AI plan

| Màn | Mockup | Trên native | Người dùng thường |
|---|---|---|---|
| 03.01 Chat | NEEDS UPDATE | Composer, thẻ AI, 8 thành viên | Tin không ra server. Đính kèm chỉ chèn `[Ảnh chuyến đi]` vào ô soạn. Thông tin nhóm không phải màn admin |
| 03.02 Lịch trình AI | NEEDS UPDATE | Đổi ngày được | Không chỉnh/kéo thả (F5). «Dùng plan này» → timeline fixture |
| 03.03 Bình chọn | NEEDS UPDATE | Chọn radio được | Không ghi phiếu (F6). Kết quả hiện sẵn |

### 04. Kèo / chuyến

| Màn | Mockup | Trên native | Người dùng thường |
|---|---|---|---|
| 04.01 Tạo kèo | READY | Form prefill | Không tạo entity. Ngày cứng. Chọn tất cả chết (F7) |
| 04.02 Timeline | NEEDS UPDATE | Render activity | Hàng không bấm được. «Tùy chọn» chết |
| 04.03 Check-in | READY trên index mockup | Composer ảnh mẫu | **Sai màn so với spec** (F9). Không GPS nhóm |

### 05. Chia bill

| Màn | Mockup | Trên native | Người dùng thường |
|---|---|---|---|
| 05.01 Xem bill | READY | Giấy 1.280.000đ | Không chụp, không OCR (F10) |
| 05.02 Gán món | NEEDS UPDATE | Đổi avatar local | Không tin cậy %. Confirm không allocate |
| 05.03 Quyết toán | NEEDS UPDATE | 4 khoản hard-code | **B1.** Không VietQR. Nhắc người chờ chết |

### 06. Kỷ niệm

| Màn | Mockup | Trên native | Người dùng thường |
|---|---|---|---|
| 06.01 Tường | READY | Vài post fixture | Thiếu tab. Không post thật lên hội |
| 06.02 Album | READY | Đếm canonical, ít thumbnail | Không đủ 256 ảnh. Picker chưa chứng minh |
| 06.03 Khoảnh khắc | READY | Caption composer | Crop/xoá chưa chứng minh editor thật |

### 07. Cá nhân

| Màn | Mockup | Trên native | Người dùng thường |
|---|---|---|---|
| 07.01 Hồ sơ | NEEDS UPDATE | Minh Anh cố định | Không sửa được (Chỉnh hồ sơ chết) |
| 07.02 Tài chính | READY | 2.84M / 200k / 780k | Period chết. Không QR. Lệch B1 |
| 07.03 Thành tích | READY | Huy hiệu demo | Không gắn hành vi thật |

### Việc app **không có** trên đường người dùng vừa đi

Không thấy màn (hoặc chỉ thấy chữ) cho: đăng ký thật, OTP SĐT, khôi phục mật khẩu, danh sách hội của *tôi*, mời bạn / danh bạ, đổi nhóm, bản đồ/GPS, camera/thư viện hệ thống, đẩy thông báo, VietQR, xác nhận đã nhận tiền từ người thật, Store listing, onboarding quyền (camera, location) có hậu quả, chế độ khách `/g/{token}` từ mobile, Dark mode / landscape, tài khoản xoá/export.

Hàng «Luồng backend hiện tại» trong sheet `+` trỏ `/legacy` — **chưa mở** trong lượt này. Đừng đọc bảng trên như «API chia tiền không tồn tại»; đọc là «UI RuDi 21 màn không gọi nó».

---

## 5. Nút trông bấm được nhưng không làm gì

Đã xác nhận bằng tap trên emulator và/hoặc đọc handler trống:

- Login: Google, Apple, Quên mật khẩu, Đăng ký ngay
- Welcome pager (4 dots)
- Chip category Khám phá (`setCategory` không lọc)
- Chi tiết quán: Chia sẻ
- Lịch trình: Chỉnh lịch trình
- Vote: Xác nhận lựa chọn của tôi
- Tạo hẹn: Chọn tất cả; date/destination không phải picker; toggle «Nhờ RuDi gợi ý» là hình, không state
- Timeline: Tùy chọn (ellipsis)
- Check-in: Đổi ảnh
- Settlement: Nhắc 2 người đang chờ
- Profile: Cài đặt, Chỉnh hồ sơ, Đã lưu, Tài khoản
- Finance: «Xem chi tiết» (nếu chỉ đổi UI period thì period cũng không đổi số)

Những cái **có** handler: tim quán, lọc match/gần/đã lưu, search, đổi ngày itinerary, chọn radio vote (chỉ local), bỏ chọn thành viên từng người, gán avatar món, FAB `+` (trong app), Dùng plan này, Tạo cuộc hẹn → timeline, Dùng ảnh này → assignment → settlement.

---

## 6. Làm sao để app này thành production-ready — theo mạch người dùng

Không phải «vẽ thêm màn». 21 màn đã có. Việc còn lại là **đừng nói dối**, rồi **nối từng bước người dùng vào dữ liệu thật**.

Ước lượng người-ngày dưới đây là thứ tự ưu tiên, không phải phép đo.

### Cổng 0 — Ngừng nói dối trên bản đang mở (trước khi khoe cho người ngoài)

Người dùng tin chữ trên màn hơn tin ADR.

1. Xoá hoặc đổi «Đã chốt từ sổ cái» cho đến khi số hero = tổng allocation từ sổ. Không hard-code `3.840.000` cạnh `780.000` như cùng một sự thật.
2. Một nguồn tiền cho settlement + finance. Cùng trip, cùng actor, hai màn phải ra cùng số. Luật 1–3 giữ nguyên (đồng nguyên, tổng = bill, số dư từ sổ).
3. Banner «12 nơi» → `PLACES.length` (hiện 4), hoặc nạp đủ 12 quán.
4. Login: hoặc chặn thật sự ≥ 8 ký tự + từ chối sai, hoặc thay bằng «Vào bản demo với tư cách Minh Anh» — đừng giả form mật khẩu.
5. Chip loại hình: lọc hoặc bỏ. «Chọn tất cả», «Xác nhận vote», «Chỉnh lịch trình», «Nhắc 2 người»: gắn hành vi hoặc ẩn nút.
6. Deep link `/create` không được crash Expo Go; FAB và route phải cùng một sheet.

Xong cổng 0, bản này **vẫn là demo**, nhưng demo không lừa tiền và không lừa tài khoản.

### Cổng 1 — Cài như app thật

Người dùng thường không chạy Metro.

- Lượt này: máy ảo + Expo Go 54. Không Play Store, không TestFlight, không APK production.
- `apps/mobile/eas.json` **có** trên cây (development / preview / production). **Chưa** chạy EAS build, **chưa** cài bản đó lên máy người lạ.
- SDK trên HEAD là 57; đĩa test là 54. Người khác clone `main` rồi mở Expo Go 54 sẽ lệch. Chốt một SDK, commit, gắn Expo Go / dev client tương ứng.
- F11/F12: crash native phải hết trên máy thật trước khi đưa cho hội bạn.

Gỡ: một bản **preview nội bộ** (EAS preview) mà người không phải dev cài được, cold start không cần laptop. Đo bằng: đưa máy người khác, họ mở app, thấy welcome.

### Cổng 2 — Họ là chính họ

Không có chuyện «bấm Đăng nhập là xong».

- Đăng ký / đăng nhập / đăng xuất / quên mật khẩu. Sai thì lỗi, đúng thì phiên còn sau kill app.
- Mockup 01.02 (Google / Apple / SĐT+OTP) nếu giữ trên UI thì phải ra nhà cung cấp thật; nếu chưa làm thì **đừng vẽ nút**.
- Cá nhân hoá ghi preference của user đó, lần sau còn.
- Hồ sơ là user đó, sửa được. Không lock Minh Anh.

Phía API, auth hiện là header `X-Actor-ID` do client tự khai — người dùng không thấy, nhưng hội bạn sẽ thấy hậu quả (ai cũng có thể là ai). Việc đó thuộc backend + ADR; mobile chỉ cần gửi phiên, không gửi «tôi muốn là UUID này».

### Cổng 3 — Hội thật, chuyến thật, không phải luôn Đà Lạt

Mọi CTA «tạo» hiện `router.replace` sang id `team-da-lat`.

Người dùng cần:

- Tạo hội trống / rủ bằng link hoặc danh bạ.
- Tạo chuyến với ngày và người **họ** chọn; «Chọn tất cả» hoạt động; date picker thật.
- Danh sách hội/chuyến của họ ở tab Lên plan và Tin nhắn — không pin một trip demo.
- Thêm quán vào chuyến thì **đúng quán đó** (vá B3).
- Chat: tin của A hiện trên máy B. Vote: xác nhận ghi phiếu, kết quả không có trước khi ai vote.
- Check-in: đúng 04.03 hoặc hạ scope mockup (đừng để READY nếu màn đang là composer).

### Cổng 4 — Tiền thật, một sự thật

Đây là sản phẩm chia bill. UI RuDi hiện **không** đi allocator.

Mạch người dùng:

1. Chụp / chọn ảnh hoá đơn thật (camera + library, quyền hệ thống, lỗi ảnh mờ).
2. OCR hoặc nhập tay → người **sửa** dòng → xác nhận.
3. Gán người từng món → `POST` expense → allocator (đồng nguyên, tổng = bill) → confirm vào sổ.
4. Gom nghĩa vụ → publish envelope + **VietQR**.
5. Người trả quét QR bằng app ngân hàng (chỉ Leader được chỉ máy banking vào QR, ADR-0010).
6. Người nhận `confirm-receipt`. App không có nút «đánh dấu xong». «Đã trả» giữ đúng nghĩa xác nhận in-app.

UI 05.01–05.03 phải đọc số từ API đó, không từ `fixtures.ts`. Gán món trên màn assignment phải **đổi** số settlement. Period tài chính phải đổi số hoặc biến mất.

Có sẵn `/legacy` trong sheet `+` — đó là đường API cũ. Production-ready nghĩa là **cùng một người dùng** đi 21 màn RuDi mà tiền vẫn đi đường sổ, không phải hai app dán cạnh nhau.

### Cổng 5 — Kỷ niệm và cá nhân không rỗng

- Ảnh từ máy họ, vào đúng hội, không đếm 256 khi lưới có 4 tấm — hoặc đếm đúng số đang có.
- Tường đủ tab nếu mockup còn yêu cầu; post/like bền.
- Thành tích gắn hành vi (chuyến đã đi, bill đã chốt), hoặc ghi rõ «trang trí demo».
- Thông báo chuông: inbox thật hoặc ẩn icon.

### Cổng 6 — Ổn định máy thật trước khi khoe

Chưa đo, nên chưa pass: iOS, điện thoại vật lý, camera/GPS/OCR thật, OAuth/OTP nhà cung cấp, push, airplane, xoay ngang, kill-restart phiên, hai máy hai user cùng lúc, VietQR ngân hàng.

F12 (remote update) và F11 (`/create`) đủ để không đưa bản Expo Go này cho khách.

---

## 7. Thứ tự làm nếu chỉ được một việc tại một thời điểm

Cho người dùng thường, không cho roadmap nội bộ:

1. **B1** — một sự thật tiền trên settlement + finance; bỏ câu sổ cái nếu chưa có sổ.
2. **B2** — auth thật hoặc cửa «vào demo» trung thực.
3. Nút chết ở tạo hẹn / vote / lọc category — chúng là lời hứa trên UI chính.
4. Nối 05.01–05.03 vào allocator + QR (cổng 4), đừng vẽ OCR đẹp thêm.
5. Tạo hội/chuyến persist (cổng 3).
6. Bản EAS người khác cài được (cổng 1).
7. Nắn copy mockup (RuDi/Rủ Đi, 01.02, map, album 256) sau khi mạch trên không còn nói dối.

Làm 7 trước 1 là đánh bóng kịch bản.

---

## 8. Ô chưa quét — đừng đọc là pass

- iOS, máy thật, tablet
- Camera OCR, photo library, GPS check-in
- VietQR trên app ngân hàng Việt Nam
- Google / Apple / OTP nhà cung cấp
- `+` → «Luồng backend hiện tại» (`/legacy`)
- Push, sinh trắc, airplane, landscape
- Gửi chat bằng IME thật (adb không gõ được vào field RN)
- Hai user đồng thời, quyền hội viên vs khách
- Play Store / TestFlight / EAS production artifact

---

## 9. Bằng chứng session

- Charters: onboarding, discovery, chat/AI, outing, bill, memories, profile/finance + sheet tạo.
- Ảnh / dump UI: `/tmp/rudi-qa-20260902/` (ngoài git).
- Expo Go 54 vì đĩa đang SDK 54; HEAD `f63628d` vẫn khai SDK 57 — lần đầu emulator báo *Project is incompatible… SDK 57 vs SDK 54*.

**Không ký demo nói về tiền thật** cho đến khi B1 và B2 biến mất khỏi màn người dùng cầm trên tay.
