# rd-qa-05 — Diễn tập demo trên máy thật

- **commit đã đo:** `43ae65d` (main lúc 2026-08-29). Bốn cổng backend đo ở `7bb5e4e`;
  giữa chừng main nhảy lên `43ae65d` (#87 CORS, #81 Khám phá), nên **toàn bộ ma trận
  bấm sai và axe đã đo LẠI trên `43ae65d`**. Chỗ nào là số của `7bb5e4e` thì ghi rõ.
- **protocol_version:** v1
- **môi trường:** stack riêng `MOBILE_PROJECT=qa-rehearsal` (API 8399 / Postgres 5459),
  dữ liệu gieo lại từ đầu bằng `make demo` (Team Đà Lạt, 7 người, 3 đợt thu, 16 link khách).
  Bản web export ghim `EXPO_PUBLIC_API_URL`, đã kiểm chuỗi cổng trong bundle.
  Khung hình Pixel 7 390×844 qua device descriptor — **không** đọc bố cục từ ảnh
  `--window-size` (ghi chú Lead 04:27).
- **AI:** thật. Gemini đọc ảnh bill tổng hợp, 8/8 dòng, tổng đúng tuyệt đối.

---

## Kết luận một dòng

Hero path **chạy được từ đầu đến cuối và phần khó nhất làm rất tốt** — nhưng
**bộ container mà `make up` / `make demo` dựng ra KHÔNG chạy được AI**, và nút
Back của điện thoại sẽ **thoát app** ở bất kỳ điểm nào của luồng.

---

## 1. Cổng đã chạy thật (cây sạch, không sửa môi trường)

| Cổng | Kết quả | SHA |
|---|---|---|
| `python3 -m pytest services/api/tests tests -q` | **685 passed, 117 skipped**, 4422 subtests | 7bb5e4e |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **106 passed, 0 skipped** | 7bb5e4e |
| `apps/mobile` `npm test` (gồm bước bundle) | **129 pass, 0 fail** | 7bb5e4e |
| `npm run test:e2e` với `MOBILE_REQUIRE_E2E=1` | **2 pass, 0 fail, 0 skipped** | 7bb5e4e |
| CORS preflight từ origin trình duyệt thật | 204 + `access-control-allow-origin` đúng | 43ae65d |

`test:e2e` lần đầu **đỏ** ở `UNREADY_RECIPIENT_CHOICE_REQUIRED` vì tôi quên trỏ
`MOBILE_DATABASE_URL` vào stack của mình — seeder ghi sang database khác. Lỗi của
người chạy, không phải của PR; ghi ra vì nó sẽ cắn người tiếp theo.

---

## 2. Kịch bản demo từng bước, có thời lượng

Đo thật trên `43ae65d`, máy này, mạng này. Cột "đo được" là thời gian máy;
cột "nói" là khoảng nên dành để nói khi trình bày.

| # | Bước | Đo được | Nói | Ghi chú cho người trình bày |
|---|---|---|---|---|
| 1 | Mở app → màn mở đầu | 0.5s | 15s | "Rủ Đi — AI đi chơi, chia bill" |
| 2 | Đăng nhập → vỏ 5 tab | 0.1s | 20s | Bấm **một lần**. Xem §3.1. |
| 3 | Tab Khám phá (bản đồ + gợi ý) | ~0.3s | 45s | Mới thật từ #81 |
| 4 | Lướt 3 tab còn lại | 0.5s | 20s | Lên plan / Tin nhắn / Cá nhân còn là **vỏ** — nói ra |
| 5 | `[+]` → Tạo khoản chi → màn chụp bill | 0.1s | 15s | Bấm **một lần**. Xem §3.1. |
| 6 | Chụp bill → **AI đọc xong** | **6.4 – 7.9s** | 25s | Chỗ im lặng dài nhất. Nói trong lúc chờ. |
| 7 | Sửa tay một dòng, tổng tính lại | 0.7s | 30s | Điểm mạnh nhất của demo. Xem §4. |
| 8 | Tiếp tục → form khoản chi | 0.0s | 20s | Phải **gõ tay** người tham gia. Xem §3.5. |

**Tổng phần máy chạy: ~10s. Tổng buổi: ~3 phút 10s.**

Bước 6 là bước duy nhất người xem phải chờ. 6.4–7.9s là im lặng rất dài trên sân
khấu — chuẩn bị sẵn một câu để nói đè lên nó.

---

## 3. Chỗ vỡ khi bấm sai

Không cái nào làm **trắng màn hình**. Tôi đã đi tìm đúng thứ đó và không tìm ra —
đó là tin tốt và là câu trả lời trực tiếp cho đề bài.

### 3.1 — Bấm hai lần thì cú thứ hai LỌT XUỐNG nút bên dưới · **chưa sửa** · nên sửa trước demo

Sheet mở ra **ngay dưới ngón tay** và ăn luôn cú chạm thứ hai.

- Bấm hai lần "Đăng nhập bằng số điện thoại" → bảng chọn người hiện ra rồi
  **tự chọn hộ** người đầu danh sách. Đo được: `bảng chọn người còn mở? false | đã vào thẳng app? true`.
- Bấm hai lần `[+]` → menu mở rồi cú thứ hai trúng "Tạo nhóm", hiện thông báo
  *"Tạo nhóm" chưa dựng — mới có chỗ trong menu*.

Không crash, không mất tiền. Nhưng trên sân khấu nó làm app **tự nhảy một bước
mà người trình bày không bấm**, và người xem thấy một thông báo "chưa dựng" ngay
đầu buổi. Cách vá rẻ nhất: hoãn nhận chạm trên sheet ~300ms sau khi mở.

**Tái lập:** `tests/qa/rd-qa-05/02-rehearsal.spec.ts` ca `R2a`.

### 3.2 — Nút Back của điện thoại THOÁT APP · **chưa sửa** · rủi ro demo cao nhất

App **không đẩy một mục lịch sử nào**. Đo trên `43ae65d`:

```
shell     : {"url":"http://127.0.0.1:4799/","len":2}
chụp bill : {"url":"http://127.0.0.1:4799/","len":2}
```

URL không đổi, `history.length` không tăng. `grep -rn "BackHandler" apps/mobile/src apps/mobile/App.tsx`
ra **rỗng** — nút back cứng của Android cũng không ai nhận.

Hệ quả: đang ở màn kết quả nhận diện với 8 món vừa quét, vuốt back theo phản xạ
→ **ra khỏi app, mất sạch**, phải chụp lại bill từ đầu. Trên Android — mà đề bài
nói "điện thoại là chính" — back là nút được dùng nhiều nhất.

**Đính chính bộ đo của tôi:** lần chạy đầu tôi báo "Back → trắng màn hình 0 ký tự".
Sai. `page.goBack()` khi không có lịch sử thì rời khỏi app sang trang tôi mở trước
đó; trang trắng là lỗi bộ đo. Phát hiện thật là *không có lịch sử*, và nó vẫn
nghiêm trọng — chỉ nghiêm trọng theo cách khác. Ca test đã viết lại để đo
`history.length` thay vì đọc trang trắng.

**Tái lập:** ca `R3`.

### 3.3 — Mất mạng lúc AI đang đọc bill · **KHÔNG vỡ**

Cắt mạng đúng lúc upload:

> Không nối được http://127.0.0.1:8499. Máy chủ có đang chạy không?

Câu tiếng Việt rõ, nút "Chọn ảnh bill" vẫn còn để thử lại, nối mạng lại thì chạy
tiếp bình thường. `pageerror` = 0. Lỗi console duy nhất là
`net::ERR_INTERNET_DISCONNECTED` — **Chrome tự log, không phải app hỏng**.
Lần chạy đầu tôi tính nó là fail; đó là assert của tôi quá chặt, đã sửa.

### 3.4 — Xoay ngang · **KHÔNG vỡ**

Ba màn (mở đầu, vỏ tab, kết quả nhận diện) ở 844×390: `scrollWidth == clientWidth == 844`
cả ba. Không tràn ngang, không cắt nội dung.

### 3.5 — Sau khi quét bill xong, danh sách người **trống** · không phải lỗi, là ranh giới

Form khoản chi hiện "Chưa có ai." và "Ai trả trước: Nhập tên phía trên trước."
Thành viên Team Đà Lạt **không** được mang sang. Người trình bày phải gõ tay từng
người ngay giữa demo.

Đây đúng là chỗ PR #83 (món ăn + gán người) lấp vào, và #83 chưa vào main. Ghi ở
đây để lịch demo biết: **hôm nay đường đi bị đứt ở giữa bước 8**, và nếu #83 chưa
merge kịp thì bước "gán món cho người" phải nói thẳng là chưa có.

---

## 4. Câu hỏi của Lead: giao diện có ngụ ý con số đã được kiểm chứng không?

**Không. Nó nói đúng mức.** Đây là phần làm tốt nhất trong những gì tôi đo.

Khi tổng các món khớp dòng in trên bill:

> Khớp với dòng Tổng cộng in trên bill.

Câu đó khẳng định **hai con số bằng nhau**, không khẳng định **con số đúng**. Đúng
như backend đã nói ở #55.

Khi tôi xoá một món để tạo lệch 150.000đ, màn hình đổi ngay sang:

> Dòng "Tổng cộng" in trên bill là 1.215.000đ, nhiều hơn tổng các món 150.000đ.
> Có thể máy đọc sót một món hoặc đọc nhầm một chữ số.

Nêu cả khoảng lệch, cả nguyên nhân có thể, bằng tiếng Việt người thường đọc được,
và nằm ngay trên hai nút — không phải cuộn đi tìm.

**Ô nhập sửa được thật, và tổng tính lại theo TỪNG KÝ TỰ** (gõ phím thật, không
phải `fill()`):

```
gõ '2' -> value="2"      | tổng=1.065.002đ
gõ '0' -> value="20"     | tổng=1.065.020đ
gõ '0' -> value="200"    | tổng=1.065.200đ
gõ '0' -> value="2000"   | tổng=1.067.000đ
gõ '0' -> value="20000"  | tổng=1.085.000đ
gõ '0' -> value="200000" | tổng=1.265.000đ   (1.215.000 - 150.000 + 200.000 ✓)
```

Xoá một món: 1.215.000 → 1.065.000đ, đúng.

**Đính chính bộ đo:** lần đầu tôi dùng `locator.fill()` và ra một tổng sai
cỡ **150 tỉ đồng**, suýt lập phiếu bug tiền. `fill()` không mô phỏng đúng
`TextInput` của react-native-web. Gõ phím thật thì đúng tuyệt đối. Bộ đo sai,
không phải app sai.

Bấm hai lần "Tiếp tục" → **đúng một** `POST /receipts/scan`, không gọi lặp.

---

## 5. Phát hiện chặn — phân loại theo 5 loại blocker của charter

### B1 · `make up` / `make demo` dựng ra một stack KHÔNG chạy được AI
**Loại: vi phạm spec/cổng.** Chủ sản phẩm đã chốt "AI là THẬT".

`docker-compose.yml` không truyền `GEMINI_API_KEY` vào service `api`
(`grep -c GEMINI_API_KEY docker-compose.yml` = **0**). `.env` ở gốc repo chỉ được
compose dùng để thay biến trong chính file compose, không tự chui vào container.

**Bằng chứng — cùng một ảnh, cùng một commit, chỉ khác cái khoá:**

| Nơi gọi | Kết quả | Thời gian |
|---|---|---|
| Container `make demo` (`:8399`) | `422 receipt_unreadable` — *"Không đọc được bill. Vui lòng kiểm tra ảnh và thử lại."* | **2.5ms** |
| Tiến trình có khoá (`:8499`) | `200` — 8/8 món, `total_vnd: 1215000`, `totals_agree: true` | 7.06s |

Cũng đã kiểm bộ chung của cả đội: `docker exec mobile-local-api-1` →
`GEMINI_API_KEY set? NO`. Không phải riêng stack của tôi.

**Hậu quả:** 2.5ms và câu *"kiểm tra ảnh và thử lại"* trông **y hệt một tấm ảnh
chụp xấu**. Trên sân khấu, người trình bày sẽ chụp lại, thất bại lần nữa, rồi
chụp lần ba. Bước hero của demo chết mà không ai biết tại sao.

**Gỡ chặn:** thêm `GEMINI_API_KEY: ${GEMINI_API_KEY:-}` vào `x-api-env`, và cho
`/healthz` (hoặc `make smoke`) nói được là khoá có hay không — **không in giá trị**.
Nếu thiếu khoá thì thông báo lỗi phải phân biệt được "chưa cấu hình máy chủ" với
"ảnh xấu"; hai thứ đó hiện đang nói cùng một câu.

*Chủ sở hữu: devops (compose) + backend (thông báo lỗi). Ngoài quyền QA — tôi
chứng minh, không vá.*

### B2 · Nút Back thoát app, mất toàn bộ bill vừa quét
**Loại: vi phạm spec/cổng** (§3.2). Chưa có `BackHandler`, chưa đẩy lịch sử.
**Gỡ chặn:** bắt back ở `LuongKhoanChi` để lùi một bước trong máy trạng thái
(`ket-qua` → `chup-bill` → thoát luồng), thay vì để hệ điều hành đóng app.

### B3 · Ba vi phạm a11y nghiêm trọng trên đường demo
**Loại: vi phạm cổng.** Detector đã chứng minh còn sống trước khi tin bất kỳ số 0 nào:
trồng `<img>` thiếu alt + `<button>` không tên vào chính trang đang đo → axe từ
**0 → 2** vi phạm. Sau đó mới đọc kết quả thật.

| Màn | critical/serious |
|---|---|
| Mở đầu | 0 |
| **Vỏ 5 tab + Khám phá** | **3** |
| Chụp bill | 0 |
| Kết quả nhận diện | 0 |

1. **[critical] `aria-required-children`** — `<div role="tablist">` chứa nút `[+]`
   (`role="button"`). Tablist chỉ được chứa `role="tab"`. *Có từ #78/#85.*
2. **[critical] `aria-required-attr`** — 5 phần tử `role="radio"` thiếu `aria-checked`.
   **Mới từ #81.** Đây đúng là lỗi react-native-web nuốt `accessibilityState` đã gặp
   trước đây: đọc source thì đúng, chỉ bản render mới lộ.
3. **[serious] `aria-prohibited-attr`** — **12 chấm trên bản đồ** Khám phá là
   `<div aria-label="Tiệm Nướng Xóm Lào">` trần, không `role`. Trình đọc màn hình
   **không đọc được tên địa điểm nào**.

*Chủ sở hữu: frontend (#78 tablist) + backend/devops lane dựng #81.*

### Quan sát thêm, không phải blocker
12 chấm bản đồ dồn thành hai cụm sát nhau (8 chấm ở `left≈89%, top≈18-19%`,
4 chấm ở `left≈10%, top≈80%`). Nhìn trên màn 390px nhiều khả năng là một đống
chấm chồng lên nhau chứ không phải một bản đồ. Chưa xác nhận bằng mắt — xem §6.

---

## 6. Ô CHƯA QUÉT — đọc kỹ phần này

Phần quan trọng nhất của báo cáo. Những thứ dưới đây **chưa được chứng minh**:

- **Máy thật.** Toàn bộ đo trên **Chromium ở khung hình điện thoại**, không phải
  trên một chiếc Android/iOS thật. Đề bài rd-qa-05 nói "máy thật" — ô này **chưa
  đạt**. Chưa chạm được: cử chỉ vuốt back thật, bàn phím ảo che ô nhập, camera
  thật (bản web tự khai *"Trình duyệt không mở được camera"* và rơi về chọn ảnh),
  quyền truy cập ảnh, xoay máy thật.
- **Mã QR VietQR chưa được quét bằng app ngân hàng thật.** Vẫn nguyên trong ô chưa
  quét. Không agent nào quét được mã QR; cần leader, 15 phút, một điện thoại.
- **Nửa sau của luồng chưa đi:** form khoản chi → chia tiền → đợt thu → publish →
  trang khách, tôi **chưa đi bằng tay trên giao diện**. Nó có được `npm run test:e2e`
  phủ ở tầng API (2/2 pass), nhưng đó là HTTP, không phải ngón tay trên màn hình.
- **Bản đồ Khám phá chưa nhìn bằng mắt.** Cụm chấm chồng nhau ở §5 mới là suy ra
  từ toạ độ CSS, chưa mở ảnh ra xem.
- **Tin nhắn / Lên plan / Cá nhân / Tạo chuyến / Đăng kỷ niệm / Tạo nhóm** vẫn là
  vỏ. Đã tự khai là vỏ trên giao diện — đúng luật "vỏ không phải lỗi, giấu mới là lỗi".
- **Chỉ một ảnh bill, một lần đọc.** Gemini là bất định; 8/8 đúng **một lần** không
  phải tỉ lệ đọc đúng. Không suy ra được gì về bill mờ, bill chụp nghiêng, bill dài.
- **Chưa đo với dữ liệu nhóm thật của Team Đà Lạt** trong luồng chia tiền (§3.5 chặn).

Và câu không được bỏ: **repo này vẫn chưa có bằng chứng hành vi nào** (ADR-0006).
Bộ test xanh nói code làm đúng điều tác giả nghĩ; nó không nói người thật hiểu sản phẩm.

---

## 7. Đề nghị

Trước buổi demo, theo thứ tự:

1. **B1** — một dòng trong `docker-compose.yml`. Không sửa thì demo chết ở bước 6.
2. **B2** — bắt nút back trong luồng khoản chi.
3. **B3.2 + B3.3** — hai lỗi a11y mới của #81, còn nóng.
4. **§3.1** — hoãn nhận chạm trên sheet, nếu còn thời gian.
5. **rd-qa-05 phần còn nợ** — chạy lại đúng kịch bản §2 trên **một chiếc điện
   thoại thật** sau khi #83 vào main. Đó là ô lớn nhất còn trống.

Bộ diễn tập ở `tests/qa/rd-qa-05/`, kèm README ghi 4 cạm bẫy bộ đo đã dính —
trong đó 2 cái suýt thành phiếu bug sai.
