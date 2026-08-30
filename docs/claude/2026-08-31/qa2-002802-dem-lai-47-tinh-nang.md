# qa2-002802 — đo lại 47 tính năng trên bundle hiện tại, và tiền đề "không có tab bar" sai

- **Đo trên**: `main` tại `1161570`
- **Bundle web**: dựng từ chính `1161570`, `EXPO_PUBLIC_API_URL=http://localhost:8099`,
  phục vụ ở cổng riêng `127.0.0.1:8941`
- **Máy chủ**: `mobile-local-api-1` ở `:8099`
- **Trình duyệt**: Playwright Chromium 1194, khung 390×844, `--no-proxy-server`
- **Kỹ năng đã gọi**: `e2e-testing`
- **protocol_version**: v1
- **Ngày**: 2026-08-31

Đây là **kiểm kê hành vi**, không phải phán quyết PR. Không có verdict
`APPROVE` / `REQUEST_CHANGES` / `REJECT` trong tài liệu này.

Nền so sánh: `docs/claude/2026-08-30/qa-tt-0038-47-tinh-nang-bam-duoc.md`, đo trên
`ba510d8` và ra **30/47**.

---

## 0. Hai câu trả lời

### Câu 1 — persona vào bằng cửa Google có thấy điều hướng không?

**Có. Và cửa số điện thoại cũng có. Cả hai cửa đều vào cùng một sườn tab, và
điều đó đúng cả trên bundle mà lượt trước đã đo.**

Điều hướng ra ở **thanh tab dưới cùng**, hiện ngay khi vào shell — không cần
nhóm, không cần chọn persona, không cần bước nào trước đó. `AppRoot.tsx` có ba
lối vào (`onVao` của Google/Apple · `onBoQua` · `onSoDienThoai` → `DangKy`) và
cả ba đều `setDaVao(true)` rồi trả về cùng một `<VoTab>`. Không có gì bị gác
theo `nguoi`.

Đếm trên máy, cửa **số điện thoại**, không fragment không query:

```
role counts: {"button":8,"tab":4,"tablist":1,"radio":5}

  [ 788] div/tab "Khám phá: gợi ý chỗ đi cho nhóm"
  [ 788] div/tab "Lên plan: chuyến đi của nhóm"
  [ 788] div/tab "Tin nhắn: chat nhóm và AI"
  [ 788] div/tab "Cá nhân: hồ sơ và tài chính của bạn"
  [ 766] button/button "Tạo mới"
```

### Câu 2 — con số trên bundle hiện tại

| Vào bằng cửa nào | BẤM-ĐƯỢC | TẮC | KHÔNG-CÓ-ĐƯỜNG |
|---|---|---|---|
| **Google** → chọn người trong Team Đà Lạt | **32 / 47** | 5 | 10 |
| **Số điện thoại** → tài khoản mới tinh | **không còn tắc**; xem mục 4 | — | — |

`30 → 32`, hai hàng đổi nhãn, không hàng nào tụt:

- **F14 Invite Members**: KHÔNG-CÓ-ĐƯỜNG → **BẤM-ĐƯỢC**. Màn chuyến có nút
  "Mời thêm người vào chuyến", bấm ra `POST 201 /outings/{id}/invites`.
- **F26 Expense From Screenshot**: TẮC → **BẤM-ĐƯỢC**. `POST 200 /screenshots/scan`
  (lượt trước là `502`), đọc ra "QUAN NUONG XOM LAO · 450.000đ", và có nút
  "Chốt vào form nhập tay" dẫn tiếp.

---

## 1. Tiền đề của việc giao sai ở hai chỗ — kiểm trước khi làm, theo đúng luật leader đặt

### 1.1 "KHÔNG có tab bar" là điểm mù của phép đo, không phải của sản phẩm

Chạy **đúng một kịch bản** trên **hai** bundle, cùng script, cùng khung 390×844:

| Bundle | `[role="button"]` | `[role="tab"]` | `[role="tablist"]` |
|---|---|---|---|
| dựng từ `1161570`, cổng 8941 | 8 | **4** | **1** |
| bản đang phục vụ ở 8081 | 8 | **4** | **1** |

Thanh tab **có mặt trên cả hai**, kể cả bản mà lượt trước đo. Bảy nút được liệt
kê trong việc giao — *Tìm bằng AI · Xem tất cả (12) · 4 thẻ địa điểm · Xem bản đồ
của nhóm* — là đúng 7 phần tử `[role="button"]` **trừ nút [+] "Tạo mới"**. Bốn
tab không nằm trong tập đó: react-native-web phát chúng ra là `div[role="tab"]`
bên trong `div[role="tablist"]`, không phải `role="button"`. Một máy quét chỉ hỏi
`[role="button"]` sẽ không thấy tab nào và bảng kết quả trông y hệt một app không
có điều hướng.

Cùng họ với bài đã ghi trong bộ nhớ đội: đếm một proxy rồi đọc thành thứ cần đo.

### 1.2 "cao trang = cao khung (844)" không phải dấu hiệu gì cả

Đây là hình dạng bình thường của react-native-web: `document.documentElement`
đứng yên ở chiều cao khung, nội dung cuộn trong `ScrollView` bên trong. Bằng
chứng trong cùng một lần chụp: có control ở `y=1041` (nút "Xem bản đồ của nhóm")
trong khi `doc` vẫn báo `390x844`. Trang không bị cắt; chỉ có `scrollHeight` của
`documentElement` là không nói gì về nó.

### 1.3 Bundle ở 8081 **không** phải bản mới — nó thiếu ba lần merge

`ls` thư mục 8081 phục vụ: mọi file ghi lúc **00:05:37**. Trên `main`, ba commit
chạm `apps/mobile/src` merge **sau** mốc đó: `4d79f7c` (00:46), `9101e42` (00:55),
`7bd0198` (01:05). Kiểm bằng needle hai chiều trên chính bundle tải qua HTTP:

```
QuanTriNhom 0 · quan-tri 0 · ThanhTich 0 · thanh-tich 0 · MoiVaoChuyen 0 · moi-vao-chuyen 0
đối chứng dương cùng file: KhamPha 5 · VoTab 2 · AppRoot 2 · CaNhan 5 · contexts 62
```

Needle dương ra số khác 0 nên phép đếm còn sống; sáu needle kia bằng 0 vì mã đó
chưa có trong bundle. **Mọi con số đo qua 8081 lúc này là con số của `477cb71`,
không phải của `main`.** Bảng ở mục 3 dựng trên bundle riêng ở 8941, hash khớp:

```
curl http://127.0.0.1:8941/index.html → index-e2e4c33c23ce918471c1f34ad2c0d762.js
ls dist/_expo/static/js/web/         → index-e2e4c33c23ce918471c1f34ad2c0d762.js
```

---

## 2. Bằng chứng phép đo còn sống

```
CANARY SẠCH        : 4 controls · innerText 276 ký tự
CANARY XẤU (chặn .js): 0 controls · innerText 0 ký tự
```

Hai số khác nhau, nên trình duyệt thật sự nạp và chạy bundle. Bằng nhau thì cả
tài liệu này phải vứt.

Máy chủ đúng là `main`:

```
python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:8099 --ref origin/main
→ Máy demo khớp origin/main: 77 route, không thiếu, không thừa.
```

Mỗi lượt mở `http://127.0.0.1:8941/` **không fragment, không query**, không tiêm
`localStorage`, không gọi thẳng API để nhảy chặng.

---

## 3. Bảng 47 hàng, cửa Google

Cột **Đo lượt này?** phân biệt cái tôi tự bấm ở `1161570` với cái mang nguyên từ
`qa-tt-0038`. Hàng mang nguyên là hàng mà `git diff ba510d8..1161570` không chạm
màn của nó, và tôi ghi rõ chứ không trộn vào số đo.

| F## | Tên | Nhãn | Đo lượt này? | Bằng chứng |
|---|---|---|---|---|
| F01 | Account Registration | BẤM-ĐƯỢC | ✅ | `POST 200 /identity/person-id` → `PUT 201 /people/{id}` → vào thẳng shell |
| F02 | Personal Profile | BẤM-ĐƯỢC | ✅ | `GET 200 /people/{id}/avatar` + `/posts` + `/finance` |
| F03 | Add Friends | BẤM-ĐƯỢC | ➖ | Nút "Mở màn kết bạn" có trên Cá nhân; `KetBan.tsx` không đổi từ `ba510d8` |
| F04 | Friend Request | BẤM-ĐƯỢC | ➖ | cùng màn, cùng lý do |
| F05 | QR Friend Add | BẤM-ĐƯỢC | ✅ | Khối "Mã kết bạn của bạn" hiện trên Cá nhân. Quét bằng camera thật: **chưa chứng minh** |
| F06 | Create Group | BẤM-ĐƯỢC | ✅ | `POST 201 /contexts` mỗi lượt vào shell; `[+] → Tạo nhóm` có trong sheet |
| F07 | Group Chat | BẤM-ĐƯỢC | ✅ | `POST 201 /contexts/{id}/messages`, tin hiện trong luồng |
| F08 | AI Member | BẤM-ĐƯỢC | ⚠️ | Thẻ AI thật có trong luồng (3 quán, địa chỉ, giá). Lượt này **không lấy được câu trả lời mới**: cửa nhịp đầy — mục 4.1 |
| F09 | Discover Places | BẤM-ĐƯỢC | ✅ | `GET 200 /places`, 12 chỗ, 4 nhóm phân loại |
| F10 | Place Detail | BẤM-ĐƯỢC | ✅ | Địa chỉ, giờ mở, khoảng giá, tag, 4 dòng lý do AI |
| F11 | AI Place Match | BẤM-ĐƯỢC | ✅ | 96% / CHƯA HỢP / 81% / 67% phân biệt được. Vẫn chấm theo nhóm seed — mục 4.2 |
| F12 | NL Place Search | BẤM-ĐƯỢC | ➖ | Ô "Tìm bằng lời" + nút "Tìm bằng AI" có; `KhamPha.tsx` không đổi |
| F13 | Create Outing | BẤM-ĐƯỢC | ➖ | Nút "Tạo chuyến mới" có trên Lên plan |
| F14 | Invite Members | **BẤM-ĐƯỢC** ⬆ | ✅ | `POST 201 /outings/{id}/invites` → "Đã mời người này vào chuyến", có cả "Tạo link mời" và "Thu hồi" |
| F15 | Outing Timeline | BẤM-ĐƯỢC | ✅ | Màn chuyến có 5 chặng + form "Thêm chặng" (Giờ · Nhãn · Tên quán) |
| F16 | AI Itinerary Generator | **TẮC** | ✅ | `POST 200 /ai-turn` ×5, màn trả lời "Rủ Đi AI vừa trả lời mấy lượt liền… đang tạm nghỉ"; tab Plan vẫn "Chưa có kế hoạch nào" — mục 4.1 |
| F17 | Voting | BẤM-ĐƯỢC | ✅ | Thẻ bình chọn 👑 "1 phiếu" · "1/7 thành viên đã bỏ phiếu" · nút "Mở bình chọn mới" |
| F18 | Receipt OCR | BẤM-ĐƯỢC | ✅ | `POST 200 /receipts/scan`, Gemini đọc **4/4 món**, tổng 450.000đ khớp tuyệt đối |
| F19 | Bill Item Detection | BẤM-ĐƯỢC | ✅ | 4 dòng có tên/SL/thành tiền, cả ba ô sửa tay được |
| F20 | Assign Food To Person | BẤM-ĐƯỢC | ✅ | Ma trận người × món, chọn 3 người rồi tick từng ô |
| F21 | AI Person Recognition | KHÔNG-CÓ-ĐƯỜNG | ✅ | `NhanMatTrenAnh` chỉ được render bởi `?man=nhan-mat` (App.tsx:1483). 0 call site trong luồng |
| F22 | Visual Food Participation | KHÔNG-CÓ-ĐƯỜNG | ✅ | `MonCuaToi` chỉ được render bởi `?man=mon-cua-toi` (App.tsx:1435). `nhanMonCuaToi` 0 call site ngoài `api.ts` |
| F23 | Confidence Score | KHÔNG-CÓ-ĐƯỜNG | ✅ | Màn "Kết quả nhận diện" in "Đã nhận diện 4 món", không con số tin cậy nào |
| F24 | Expense From Chat | **TẮC** | ✅ | `POST 200 /messages/{id}/expense-draft` đọc đúng "tien nuong · 360.000đ · Người trả: Minh · Người chia: 7 người", rồi "bạn còn phải chốt" và nút duy nhất là **"Đóng"** |
| F25 | Expense From Receipt | BẤM-ĐƯỢC | ✅ | `POST 201 /expenses` → `POST 201 /expenses/{id}/confirm` |
| F26 | Expense From Screenshot | **BẤM-ĐƯỢC** ⬆ | ✅ | `POST 200 /screenshots/scan` (trước là 502) → "QUAN NUONG XOM LAO · 450.000đ" + nút "Chốt vào form nhập tay" |
| F27 | Smart Settlement | BẤM-ĐƯỢC | ✅ | 450.000 ÷ 3 = 150.000×3, Σ khớp tuyệt đối, người ứng tiền không tự nợ mình |
| F28 | Settlement Tracking | BẤM-ĐƯỢC | ✅ | `POST 201 /batches` → "0/2 lượt chuyển xong", từng dòng "chưa gửi" |
| F29 | Payment Link / QR | BẤM-ĐƯỢC | ✅ | `POST 200 /batches/{id}/publish` → thẻ VIETQR · NAPAS 247 + bảng "ai chuyển cho ai" |
| F30 | Group Memory | KHÔNG-CÓ-ĐƯỜNG | ➖ | Không có kho sở thích theo người; `KyNiem.tsx` không đổi |
| F31 | Group Preference Profile | KHÔNG-CÓ-ĐƯỜNG | ➖ | Không màn nào hiện |
| F32 | Proactive Suggestion | KHÔNG-CÓ-ĐƯỜNG | ✅ | `git grep suggestion` ngoài `api.ts`: chỉ khớp comment, **0 call site** |
| F33 | Contextual Suggestions | BẤM-ĐƯỢC | ➖ | Thẻ AI trong luồng chat là kết quả của đường này |
| F34 | Budget Awareness | BẤM-ĐƯỢC | ✅ | "Đã tiêu 4.200.000đ / ngân sách 6.300.000đ · Còn 2.100.000đ" trên từng chuyến; Cá nhân có tổng chi / đã trả / còn nợ |
| F35 | Group Memory Wall | BẤM-ĐƯỢC | ✅ | Màn Kỷ niệm hiện ảnh nhóm + nút "Thêm ảnh" |
| F36 | Automatic Trip Album | KHÔNG-CÓ-ĐƯỜNG | ✅ | Recap từng chuyến có (chặng + tiền đã chia), khối "Ảnh của nhóm" vẫn rời — hai khối không nối |
| F37 | AI Highlight Reel | KHÔNG-CÓ-ĐƯỜNG | ✅ | `git grep reel` ngoài `api.ts`: 0 call site |
| F38 | Locket Style Widget | KHÔNG-CÓ-ĐƯỜNG | ✅ | `Widget.tsx` có, nhưng `setLuongWidget(true)` chỉ tới từ `moWidgetNgay`, tức fragment `#vao=widget`. Không nút nào trong shell |
| F39 | Post | BẤM-ĐƯỢC | ✅ | Nút "Viết lên tường" + bài cũ hiện trên Cá nhân |
| F40 | Reactions | BẤM-ĐƯỢC | ✅ | Đếm ♥ 1 hiện trên tường Kỷ niệm |
| F41 | Comments | BẤM-ĐƯỢC | ➖ | Đếm bình luận hiện trên từng ảnh; lượt này không gõ thêm |
| F42 | Privacy 4 mức | BẤM-ĐƯỢC | ✅ | Bài trên tường mang nhãn "Công khai" / "Chỉ mình tôi" |
| F43 | Social Map | **TẮC** | ✅ | `GET 403 /contexts/1aa00000-…/map` → "Bạn không còn trong nhóm này" |
| F44 | Group Heatmap | **TẮC** | ✅ | `GET 403 /contexts/1aa00000-…/heatmap`, cùng gốc |
| F45 | Meet-in-the-middle | **TẮC** | ✅ | `GET 200 /areas`, chọn 2 khu chạy tốt, bấm "Tìm chỗ gặp" → "Bạn không còn trong nhóm này" |
| F46 | Group Check-in | BẤM-ĐƯỢC | ✅ | Màn chuyến có 5 nút "Đã tới". Thẻ địa điểm nói rõ điều kiện: "Chưa có nhóm nào đang mở trong phiên này" |
| F47 | Automatic Place Detection | KHÔNG-CÓ-ĐƯỜNG | ➖ | Từ chối có chủ ý |

**Tổng: 32 BẤM-ĐƯỢC · 5 TẮC · 10 KHÔNG-CÓ-ĐƯỜNG.**
Đo tay lượt này: 36 hàng. Mang nguyên từ `qa-tt-0038`: 11 hàng, đều là hàng mà
diff không chạm màn của nó.

---

## 4. Bốn chỗ con số này không nói hết

### 4.1 F16 — cái tắc tôi đo được **không phải** cái tắc vừa được sửa

`qa-tt-0038` thấy F16 im lặng 45 giây. Lượt này màn trả lời hẳn hoi:

```
POST 200 /contexts/{id}/ai-turn   (×5, trong đó 1 lượt sau khi gửi 12 tin người thật)
màn: "Rủ Đi AI vừa trả lời mấy lượt liền trong nhóm này nên đang tạm nghỉ."
tab Plan trong chat: "Chưa có kế hoạch nào trong nhóm này."
```

Câu chữ đó ánh xạ **một-một** tới `reason === "asked_too_often"` trong
`src/screens/chat/ai.ts:125`, tức cổng nhịp của `plan_turn`
(`window_messages: 20`, `max_ai_messages_per_window: 3`) — không phải lỗi
grounding. Nên hàng này là **TẮC ở cổng nhịp**, và lượt này tôi **không chứng
minh được** đường lịch trình chạy hay không chạy.

Quan trọng cho leader: **`c5c74d5` (F16, thiếu khoá `title` làm vứt cả thẻ) merge
lúc 01:57, tức SAU khi tôi đo xong.** Bản vá đó không nằm trong con số 32 ở trên,
và nó vá đúng cái `qa-tt-0038` gặp. Đây là hàng đáng đo lại đầu tiên khi
`mobile-local-api-1` được dựng lại — nó có thể thành 33.

### 4.2 Ba hàng TẮC còn lại vẫn cùng một gốc, không hàng nào tự khỏi

F43 · F44 · F45 chết vì tab Khám phá ghim cứng `context_id=1aa00000-…` (nhóm
seed) trong khi phiên đang ở `5cacfdee-…`. Không đổi so với `qa-tt-0038` mục 3.2.
Hệ quả im lặng vẫn nguyên: **"AI MATCH 96%" đang chấm theo ngân sách và sở thích
của một nhóm mà người dùng không thuộc về.**

### 4.3 F21 và F22 có màn, có route, và không có đường bấm

Hai màn mới `NhanMatTrenAnh` và `MonCuaToi` chỉ được render từ `?man=nhan-mat` và
`?man=mon-cua-toi` trong `App.tsx`, kèm dữ liệu fixture đóng băng. Chính comment
trong file nói rõ mục đích: cửa cho máy quét, "no route from here into the
product". Với người cầm điện thoại thì hai tính năng này chưa tồn tại.

Đây là tầng thứ ba của cùng một bài học đã ghi: route có → hàm client có → **màn
có** → vẫn có thể không ai bấm tới được. Đếm "màn có gọi route" là đếm thiếu một
vế.

### 4.4 Cửa số điện thoại: chỗ tắc nặng nhất lượt trước đã hết

`qa-tt-0038` mục 3.1: người tự đăng ký bấm tab Tin nhắn thì màn từ chối, và bấm
Gửi **không sinh lời gọi HTTP nào**. Đo lại ở `1161570`, cùng kịch bản, số mới:

```
POST 200 /identity/person-id → PUT 201 /people/{uuid}
→ shell 4 tab (mục 0)
→ tab Tin nhắn: "Team Đà Lạt · 8 thành viên", luồng chat tải được
→ gõ + Gửi: POST 201 /contexts/5cacfdee-…/messages     ← lượt trước là con số 0
   kèm POST 201 /contexts/{id}/members + POST 200 /memberships/{id}/accept
→ tab Lên plan: GET 200 /outings + /recap
→ tab Cá nhân: GET 200 /finance + /posts  (avatar 404 = trạng thái rỗng đúng)
```

Nên câu "cửa số ĐT tắc ở 7" **hết hiệu lực**. Người tự đăng ký được ghép vào
chính nhóm demo, nên họ nhìn thấy cùng một sản phẩm với cửa Google.

**Ô chưa quét, nói thẳng:** tôi **không** đi hết 47 hàng ở cửa số điện thoại. Tôi
đo shell, đo đúng hàng từng chặn (F07), và đo ba tab còn lại tải dữ liệu sống.
Con số 47 hàng cho cửa đó vẫn là ô trống, và ai muốn dùng nó thì phải đi lại.

---

## 5. Ô chưa quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Chỉ leader đóng được, 15 phút
  với một điện thoại. Mọi assert trong repo chỉ kiểm chuỗi EMVCo và CRC.
- **F16 sau `c5c74d5`** — máy demo `:8099` khi tôi đo còn là bản trước bản vá.
- **47 hàng ở cửa số điện thoại** — xem 4.4.
- **Cửa "Bỏ qua"** (vào shell với `nguoi = null`) — chưa đo hàng nào.
- **F05 quét mã bằng camera thật**, **F41 gõ bình luận mới**, **F12 câu tìm tiếng
  Việt mới** — mang nguyên từ lượt trước, không tự bấm lại.
- Khung 320 và 1440, chủ đề tối: lượt này chỉ đo 390×844 sáng.

## 6. Rủi ro còn mở, theo 5 loại blocker của charter

| # | Loại | Dẫn chứng | Hậu quả | Tiêu chí gỡ chặn |
|---|---|---|---|---|
| 1 | vi phạm spec/cổng | Khám phá ghim `context_id=1aa00000-…`; F43/F44/F45 nhận 403 | AI MATCH chấm theo nhóm người dùng không thuộc về; 3 tính năng chết ở bước cuối | Khám phá dùng context của phiên; ba route trả dữ liệu |
| 2 | vi phạm spec/cổng | F24 đọc đúng khoản chi rồi chỉ có nút "Đóng" | App bảo "bạn còn phải chốt" và không có chỗ chốt | Thẻ có đường sang form khoản chi |
| 3 | không tái lập được → **đã tái lập** | F21/F22 chỉ tới được bằng `?man=` | Hai tính năng tính vào độ phủ mà người dùng không chạm được | Có nút trong luồng bill, hoặc ghi thẳng là màn cho máy quét |

Ba mục trên đều **không** phải phát hiện mới của lượt này; chúng là hàng cũ đo
lại và vẫn còn.

---

## 7. Câu không được bỏ

Repo này chưa có bằng chứng hành vi nào (ADR-0006). Bảng trên nói *một máy quét
bấm được bao nhiêu nút và máy chủ trả gì*. Nó không nói người thật hiểu sản phẩm,
và nó không nói mã QR quét được.
