# qa-tt-0038 — 47 tính năng: bao nhiêu cái một NGƯỜI LẠ bấm được, trên máy demo thật

- **Đo trên**: `main` tại `ba510d8`
- **Máy chủ**: `mobile-local-api-1` ở `:8099` (máy demo thật, không fake, không unit test)
- **Bundle web**: dựng từ chính `ba510d8`, `EXPO_PUBLIC_API_URL=http://127.0.0.1:8099`
- **Trình duyệt**: Playwright Chromium, khung 390×844 (điện thoại), `--no-proxy-server`
- **Kỹ năng đã gọi**: `e2e-testing`
- **protocol_version**: v1
- **Ngày**: 2026-08-30

Đây là **kiểm kê hành vi**, không phải phán quyết PR. Không có verdict
`APPROVE` / `REQUEST_CHANGES` / `REJECT` trong tài liệu này.

---

## 0. Câu trả lời

Câu hỏi của leader không phải "route có tồn tại" và không phải "màn có gọi
route". Câu hỏi là: **mở app lên, bấm, có dùng được không.**

Và câu trả lời có **hai con số**, vì màn đầu tiên có hai cửa vào khác nhau, và
hai cửa đó dẫn tới hai sản phẩm khác nhau.

| Vào bằng cửa nào | BẤM-ĐƯỢC | TẮC | KHÔNG-CÓ-ĐƯỜNG |
|---|---|---|---|
| **"Đăng ký với Google"** → chọn một người trong Team Đà Lạt | **30 / 47** | 6 | 11 |
| **"Đăng nhập bằng số điện thoại"** → tài khoản thật, mới tinh | **7** đã đo được, rồi **tắc ở màn Tin nhắn** | — | — |

Con số leader nên mang đi là **30/47**, kèm đúng một câu: *30 đó chỉ có thật
nếu người dùng bấm nút Google và chọn một người có sẵn trong nhóm demo.* Người
nào đăng ký thật bằng số điện thoại của mình thì mất chat, mất AI, mất bình
chọn — xem mục 3.1, đó là phát hiện nặng nhất lượt này.

Ba con số cũ không thay được con số này: kiểm kê `rd-qa-41` đếm route và đếm
màn gọi route, và cả hai đều đúng mà vẫn không trả lời được câu hỏi này. Ví dụ
rõ nhất: `GET /contexts/{id}/map` **có** thật, `DaiBanDo.tsx` **có** gọi nó, và
người dùng bấm vào vẫn nhận 403.

---

## 1. Cách đo, và bằng chứng phép đo còn sống

Ba ràng buộc leader đặt ra, và chỗ chúng được giữ:

1. **Playwright trên máy demo thật.** Không fake repository, không unit test.
   Mọi số dưới đây đi kèm lời gọi HTTP thật tới `:8099`, ghi lại từ
   `page.on("response")`.
2. **Bắt đầu từ màn đầu tiên như người mới.** Mỗi lượt mở
   `http://127.0.0.1:8938/` **không fragment, không query**. Không dùng
   `#tab=`, `#vao=`, `#nguoi=` — những cái đó có thật trong `lien-ket.ts` và
   dùng được cho detector, nhưng người thật không gõ chúng. Không tiêm
   `localStorage`, không gọi thẳng API để nhảy chặng.
3. **Ba nhãn.** BẤM-ĐƯỢC · TẮC (ghi rõ tắc ở đâu) · KHÔNG-CÓ-ĐƯỜNG.

### Máy demo có đúng là `main` không

```
python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:8099 --ref origin/main
→ Máy demo khớp origin/main: 76 route, không thiếu, không thừa.
```

Bắt buộc kiểm cái này trước: bộ nhớ đội đã ghi một lần máy 8099 tụt sau `main`
37/42 route và mọi số đo qua nó đều sai.

### Bundle đang phục vụ có đúng bundle mình dựng không

```
expo export --platform web --output-dir /tmp/qa38-bundle --clear
→ index-7196da6451925beeead3985c15032fad.js (873KB) + index-b6f8…(45KB)

curl http://127.0.0.1:8938/index.html | grep -o 'index-[a-f0-9]*\.js'
→ index-7196da6451925beeead3985c15032fad.js
```

Hash khớp. Đây là phép kiểm chống "cổng bị chiếm": một `curl` ra 200 chỉ chứng
minh **có ai đó** trả lời trên cổng đó, không chứng minh đó là cây mình vừa
dựng. Cổng 8938 là cổng riêng của lượt này; 8081 đang phục vụ bundle từ
scratchpad của phiên khác và **không** được dùng để đo.

### Hai canary — bằng chứng phép đo chưa chết

Leader cảnh báo máy này có proxy chặn localhost cho cả `curl` lẫn Chrome, và
dấu hiệu duy nhất nhận ra là canary XẤU và canary SẠCH ra **cùng một con số**.
Đã chạy cả hai, cùng một script, cùng một URL:

| Canary | Cách làm hỏng | Kết quả |
|---|---|---|
| **SẠCH** | không làm gì | `4 controls`, innerText có "Rủ Đi", "Đăng ký với Google"… |
| **XẤU** | `page.route("**/*.js", abort)` — chặn bundle | `0 controls`, innerText **rỗng** |

Hai số khác nhau → phép đo còn sống. Nếu chúng bằng nhau thì mọi con số dưới
đây phải vứt đi.

Biến môi trường đã đặt cho mọi lượt: `no_proxy=127.0.0.1,localhost`,
`NO_PROXY` tương ứng, và Chrome chạy với `--no-proxy-server
--proxy-bypass-list=*`.

### Một cái bẫy của chính phép đo, ghi lại để lượt sau không mất giờ

`document.body.innerText` trên react-native-web **không đọc**: giá trị của
`<input>`, và nội dung của overlay menu `[+]`. Có lúc màn hình đã đổi mà
innerText không đổi gì. Vì vậy mỗi bước dump **hai** thứ: innerText **và** danh
sách control kèm `value`. Nếu chỉ đọc innerText, menu `[+]` sẽ bị đọc thành
"bấm không ăn" và bốn tính năng sau nó bị chấm nhầm thành KHÔNG-CÓ-ĐƯỜNG.

### Một finding mình đã suýt nộp, và nó là lỗi của mình

Lượt đầu tôi kết luận "màn kết quả thanh toán hiện QR mà **không** có
`POST /batches/{id}/publish` — QR là fixture". Sai. Đó là `head -60` của chính
tôi cắt mất dòng cuối của log. Chạy lại, ghi ra file, đọc hết:
`POST 200 /batches/0383dd7a…/publish` có thật, và QR là envelope thật.

Ghi lại vì nó đúng loại lỗi làm hỏng một báo cáo QA: công cụ đọc của người đo
im lặng cắt bằng chứng, và con số sai đi thẳng vào kết luận.

---

## 2. Bảng 47 hàng

Cột "Bấm được?" đo trên cửa **Google → chọn người trong Team Đà Lạt**. Cột cuối
ghi bằng chứng: lời gọi HTTP thật, hoặc chữ hiện trên màn hình.

| F## | Tên | Bấm được? | Bằng chứng / tắc ở đâu |
|---|---|---|---|
| F01 | Account Registration | **BẤM-ĐƯỢC** | Cửa số ĐT: `POST 200 /identity/person-id` → `PUT 201 /people/{id}` → vào thẳng shell. App tự ghi "Google và Apple chưa nối thật" |
| F02 | Personal Profile | **BẤM-ĐƯỢC** | `GET 200 /people/{id}/finance` + `/avatar` + `/posts`. Ô Kỷ niệm/Đánh giá ghi thẳng "chưa có" |
| F03 | Add Friends | **BẤM-ĐƯỢC** | Tìm bằng chính số đã đăng ký ở lượt trước → hiện đúng "Khach QA38" (tài khoản tôi tạo ở lượt trước, cửa khác) |
| F04 | Friend Request | **BẤM-ĐƯỢC** | Bấm gửi → "Lời mời bạn đã gửi (1)". Chiều nhận lời cần máy của người kia, một người đi bộ không đóng được |
| F05 | QR Friend Add | **BẤM-ĐƯỢC** | Mã hiện ở Cá nhân; màn Nhóm có ô "Mã hoặc đường dẫn" nhận mã dán vào. **Chưa chứng minh** quét bằng camera thật |
| F06 | Create Group | **BẤM-ĐƯỢC** | `POST 201 /contexts` → `GET 200 /contexts/{id}/members` |
| F07 | Group Chat | **BẤM-ĐƯỢC** | `POST 201 /contexts/{id}/messages`. **Tắc hoàn toàn ở cửa số ĐT** — mục 3.1 |
| F08 | AI Member | **BẤM-ĐƯỢC** | `POST 200 /ai-turn`, Gemini thật trả lời tiếng Việt kèm 3 quán có địa chỉ. Cùng cảnh báo 3.1 |
| F09 | Discover Places | **BẤM-ĐƯỢC** | 12 chỗ, 4 nhóm phân loại, `GET 200 /places` |
| F10 | Place Detail | **BẤM-ĐƯỢC** | Địa chỉ, giờ mở, giá, tag, lý do AI |
| F11 | AI Place Match | **BẤM-ĐƯỢC** | "AI MATCH 96%" + 4 lý do (BUDGET/SỞ THÍCH/NHÓM/KHOẢNG CÁCH). Nhưng chấm theo **nhóm demo cố định** — mục 3.2 |
| F12 | NL Place Search | **BẤM-ĐƯỢC** | "quan nuong duoi 200k cho 4 nguoi" → AI tách đúng 200k / 4 người / quán ăn local / đồ nướng, trả 0 chỗ kèm giải thích. **15,2s** — mục 3.5 |
| F13 | Create Outing | **BẤM-ĐƯỢC** | `POST 201 /contexts/{id}/outings` |
| F14 | Invite Members | **KHÔNG-CÓ-ĐƯỜNG** | Màn chuyến không có nút mời. `grep` cả `apps/mobile/src`: chỉ có `outing-invites/{token}/accept`, **không call site nào tạo lời mời** |
| F15 | Outing Timeline | **BẤM-ĐƯỢC** | Thêm chặng "21:00 Cafe khuya" → `PUT 200 /outings/{id}/timeline`, chặng hiện ra. **Nhưng xoá sạch check-in** — mục 3.3 |
| F16 | AI Itinerary Generator | **TẮC** | Hỏi thẳng "lên giúp lịch trình chi tiết từng giờ" → `POST 200 /ai-turn`, đợi 45s, **AI không nói gì**. Tab Plan vẫn "Chưa có kế hoạch nào" |
| F17 | Voting | **BẤM-ĐƯỢC** | Mở bình chọn 2 chỗ → bỏ phiếu → 👑 "1 phiếu", "1/7 thành viên đã bỏ phiếu" |
| F18 | Receipt OCR | **BẤM-ĐƯỢC** | `POST 200 /receipts/scan`, Gemini thật đọc đúng **4/4 món** trên ảnh tôi tự dựng, tổng 405.000đ khớp tuyệt đối |
| F19 | Bill Item Detection | **BẤM-ĐƯỢC** | 4 dòng có tên/SL/thành tiền, sửa tay được trước khi chốt |
| F20 | Assign Food To Person | **BẤM-ĐƯỢC** | Ma trận người × món, tick được từng ô |
| F21 | AI Person Recognition | **KHÔNG-CÓ-ĐƯỜNG** | Không có lối vào nào trong app |
| F22 | Visual Food Participation | **KHÔNG-CÓ-ĐƯỜNG** | — |
| F23 | Confidence Score | **KHÔNG-CÓ-ĐƯỜNG** | Không hiện con số tin cậy nào cho người dùng |
| F24 | Expense From Chat | **TẮC** | `POST 200 /messages/{id}/expense-draft` đọc **đúng**: "tien lau · 400.000đ · Người trả: Minh · Người chia: 7 người". Thẻ ghi "**bạn còn phải chốt**" và nút duy nhất là **"Đóng"** — mục 3.4 |
| F25 | Expense From Receipt | **BẤM-ĐƯỢC** | Chụp → nhận diện → gán → chia → ghi sổ, `POST 201 /expenses/{id}/confirm` |
| F26 | Expense From Screenshot | **TẮC** | `POST 502 /screenshots/scan`. Log máy chủ: `screenshot reader failed (RuntimeError)`. Màn hiện "Bộ đọc ảnh chụp màn hình đang không trả lời" |
| F27 | Smart Settlement | **BẤM-ĐƯỢC** | 405.000 ÷ 3 = 135.000×3, Σ khớp tuyệt đối, không lệch đồng nào |
| F28 | Settlement Tracking | **BẤM-ĐƯỢC** | Màn đợt thu: "0/2 lượt chuyển xong", từng dòng "chưa gửi" |
| F29 | Payment Link / QR | **BẤM-ĐƯỢC** | `POST 200 /batches/{id}/publish` → thẻ VietQR/NAPAS 247 → link khách `GET 200 /g/{token}` mở được |
| F30 | Group Memory | **KHÔNG-CÓ-ĐƯỜNG** | Không có kho sở thích theo người |
| F31 | Group Preference Profile | **KHÔNG-CÓ-ĐƯỜNG** | Không có màn nào hiện |
| F32 | Proactive Suggestion | **KHÔNG-CÓ-ĐƯỜNG** | `grep "/suggestion"` trong `apps/mobile/src` + `App.tsx` = **0 call site**. Route có, không ai gọi |
| F33 | Contextual Suggestions | **BẤM-ĐƯỢC** | AI đọc câu trong nhóm rồi trả 3 quán trong catalogue, không bịa quán ngoài |
| F34 | Budget Awareness | **BẤM-ĐƯỢC** | Mỗi chuyến: "Đã tiêu 4.200.000đ / ngân sách 6.300.000đ · Còn 2.100.000đ". Cá nhân: tổng chi / đã trả / còn nợ |
| F35 | Group Memory Wall | **BẤM-ĐƯỢC** | `POST 201 /photos` → `POST 201 /memories` → ảnh hiện lại |
| F36 | Automatic Trip Album | **KHÔNG-CÓ-ĐƯỜNG** | Kỷ niệm có recap từng chuyến (chặng + tiền), nhưng **ảnh không gắn vào chuyến nào** — hai khối rời nhau |
| F37 | AI Highlight Reel | **KHÔNG-CÓ-ĐƯỜNG** | — |
| F38 | Locket Style Widget | **KHÔNG-CÓ-ĐƯỜNG** | — (spec cũng ghi "Optional later") |
| F39 | Post | **BẤM-ĐƯỢC** | `POST 201 /posts`, bài hiện trên tường kèm nhãn mức riêng tư |
| F40 | Reactions | **BẤM-ĐƯỢC** | ♡ → ♥ 1, `POST 201 /memories/{id}/reactions` |
| F41 | Comments | **BẤM-ĐƯỢC** | `POST 201 /memories/{id}/comments`, hiện "Minh · Anh dep qua" |
| F42 | Privacy 4 mức | **BẤM-ĐƯỢC** | Chọn "Công khai" → bài hiện đúng nhãn "Công khai". Đủ 4 mức |
| F43 | Social Map | **TẮC** | `GET 403 /contexts/1aa00000-…/map` → "Bạn không còn trong nhóm này" — mục 3.2 |
| F44 | Group Heatmap | **TẮC** | `GET 403 /contexts/1aa00000-…/heatmap`, cùng nguyên nhân |
| F45 | Meet-in-the-middle | **TẮC** | Form chọn khu vực chạy tốt, bấm "Tìm chỗ gặp" → "Bạn không còn trong nhóm này" |
| F46 | Group Check-in | **BẤM-ĐƯỢC** | `POST 201 /outing-stops/{id}/checkins` → "Minh đã tới". **Nhưng mất sạch khi ai đó thêm chặng** — mục 3.3 |
| F47 | Automatic Place Detection | **KHÔNG-CÓ-ĐƯỜNG** | Từ chối có chủ ý |

**Tổng: 30 BẤM-ĐƯỢC · 6 TẮC · 11 KHÔNG-CÓ-ĐƯỜNG.**

---

## 3. Sáu phát hiện

### 3.1 — Đăng ký thật bằng số điện thoại thì mất luôn màn Tin nhắn *(nặng nhất)*

Đây là con đường một người lạ **thật sự** đi: bấm "Đăng nhập bằng số điện
thoại", nhập số của mình, đặt tên. App nói thẳng đó là cửa thật: *"Đăng nhập
bằng số điện thoại là thật: nó tạo tài khoản trên máy chủ."* Và nó thật:
`POST 200 /identity/person-id` → `PUT 201 /people/{id}`.

Người đó tạo nhóm của mình (`POST 201 /contexts`), mời hai người bạn
(`POST 201 /contexts/{id}/members` × 2). Rồi bấm tab **Tin nhắn**:

```
Nhóm chat
Chưa vào được nhóm
Không ghi được tên người
Đã thử: http://127.0.0.1:8099/people
Mã: 0
Chi tiết: không có người "980ebea7-330f-854d-a57e-e246874a7950"
          trong nhóm demo, không bịa một người khác
```

Gõ tin nhắn rồi bấm **Gửi**: **không có một lời gọi HTTP nào**. Không
`POST /messages`, không lỗi, không gì cả. Nút bấm được, và không xảy ra chuyện gì.

Tab Tin nhắn phân giải người dùng theo **nhóm demo có sẵn**, không theo nhóm
người đó vừa tạo. Người tự đăng ký không nằm trong nhóm demo, nên màn chat từ
chối — và kéo theo F07, F08, F33, F16, F17, F24 (mọi thứ sống trong chat).

**Tái lập** (~40 giây):
1. `http://127.0.0.1:8938/` → "Đăng nhập bằng số điện thoại"
2. Số bất kỳ chưa dùng + tên bất kỳ → "Tiếp tục"
3. Bấm tab "Tin nhắn"

Loại blocker: **vi phạm spec/cổng**. Hậu quả: cửa đăng ký duy nhất có thật lại
dẫn tới một app mất một nửa. Tiêu chí gỡ chặn: tab Tin nhắn dùng nhóm của phiên
hiện tại; người vừa tạo nhóm phải chat được trong chính nhóm đó.

### 3.2 — Tab Khám phá ghim cứng một `context_id`, và bản đồ trả 403

Mọi lượt, ở mọi cửa vào, tab Khám phá gọi:

```
GET 200 /places?context_id=1aa00000-aaaa-4aaa-8aaa-0000a0000001
```

`1aa00000-…` là nhóm seed, không phải nhóm của phiên (`5cacfdee-…`). Với danh
sách quán thì không ai thấy gì lạ. Bấm **"Xem bản đồ của nhóm"** thì thấy ngay:

```
GET 403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/map
GET 403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/heatmap
→ "Bạn không còn trong nhóm này" (hiện hai lần)
```

Câu đó sai với sự thật: người dùng **chưa bao giờ** ở trong nhóm đó. Cùng
nguyên nhân làm "Tìm chỗ gặp" (F45) chết ở bước cuối, sau khi người dùng đã
ngồi chọn xong khu vực xuất phát cho từng người.

Hệ quả im lặng hơn, và đáng lo hơn: **"AI MATCH 96%" đang chấm theo ngân sách
và sở thích của một nhóm mà người dùng không thuộc về.** Con số hiện ra rất
thuyết phục và nó không nói về nhóm của người đang nhìn nó.

Loại blocker: **vi phạm spec/cổng**. Tiêu chí gỡ chặn: Khám phá dùng context
của phiên; F43/F44/F45 trả dữ liệu chứ không trả 403.

### 3.3 — Thêm một chặng vào lịch trình là xoá sạch check-in của cả nhóm

Trên màn chuyến đi, bấm "Đã tới" ở chặng đầu:

```
POST 201 /outing-stops/5d3f54dc-3bf6-475f-a991-fe3e115e0f20/checkins
→ màn hiện "Minh đã tới" / "Bạn đã tới"
```

Rồi thêm một chặng mới:

```
PUT 200 /outings/b8ab5f7f-…/timeline
→ chặng mới hiện ra, và "Minh đã tới" BIẾN MẤT
```

Không phải hiển thị cũ. Mở lại màn chuyến, client gọi lại
`GET 200 /outings/{id}/checkins` và check-in vẫn không có. Hỏi thẳng máy chủ:

```
GET /outings/b8ab5f7f-…/checkins  →  {"checkins": []}

stop id hiện tại: 9e0c6a4f… / ba174f83… / 7fe1aef2… / 6b003525… / ec1143d0…
stop id đã check-in: 5d3f54dc…      ← không còn tồn tại
```

`PUT /timeline` **thay toàn bộ chặng bằng id mới**, nên mọi check-in gắn vào id
cũ rơi ra khỏi `GET /checkins` — mất, không cảnh báo, không hỏi lại.

Tái lập được **2/2 lần**. Trong một nhóm thật, một người sửa lịch trình là xoá
mốc "đã tới" của tất cả những người còn lại.

Loại blocker: **không tái lập được → đã tái lập; xếp vào hỏng dữ liệu người
dùng**. Tiêu chí gỡ chặn: `PUT /timeline` giữ nguyên id của chặng không đổi,
hoặc dời check-in theo; ca live ở `tests/postgres` chứng minh check-in sống sót
qua một lượt sửa lịch trình.

### 3.4 — F24 đọc đúng khoản chi rồi không cho chốt

Gõ vào nhóm: *"Toi vua tra 400000 tien lau cho ca nhom"*. Bấm "Tách tiền":

```
POST 200 /contexts/{id}/messages/{mid}/expense-draft
```

AI đọc **đúng**: `tien lau · 400.000đ · Người trả: Minh · Người chia: Đức,
Minh, Trang, Quân, Hải, Linh, Ngọc`. Rồi thẻ ghi:

```
Cần xem lại
Chưa ghi khoản chi nào. Đây mới là bản đọc, bạn còn phải chốt.
[ Đóng ]
```

Nút duy nhất trên thẻ là **Đóng**. App bảo người dùng "bạn còn phải chốt" và
không có chỗ nào để chốt. Phần khó (Gemini đọc câu tiếng Việt thành khoản chi
có người trả và người chia) đã chạy đúng; thiếu đúng một cái nút.

Loại blocker: **suggestion**, không phải blocker — nhưng là món rẻ nhất trong
danh sách này để biến một TẮC thành BẤM-ĐƯỢC.

### 3.5 — Tìm bằng AI mất 15 giây, và màn chờ không nói còn bao lâu

```
POST /places/search "quan nuong duoi 200k cho 4 nguoi"  → 200 in 15,17s
POST /places/search "cafe view dep"                     → 200 in  6,30s
```

Lượt Playwright đầu tôi đợi 22 giây và màn vẫn "Đang hỏi AI…" nên tôi suýt chấm
F12 là TẮC. Đợi 60 giây thì nó ra, và ra **đúng**. Người thật không đợi 22 giây
cho một ô tìm kiếm.

Đây là suggestion, nhưng ghi lại vì nó là cái bẫy sẵn cho lượt QA sau: **F12
trông y hệt một màn treo.**

### 3.6 — Màn chia tiền in UUID thay cho tên người

Ở màn "Gợi ý chia theo người", khối "Trước bữa này, nhóm còn nợ nhau":

```
e3a44e25-4547-508a-8f4d-9b2495c3325f trả Minh 453.666đ
Trang trả Minh 314.334đ
Trang trả Hải 8.499đ
cdadf49b-b6a8-5631-8b9d-aee6a7d532de trả Hải 261.666đ
4421b3f8-26a6-5827-a7e7-548c5a4a10f9 trả Hải 192.000đ
```

**3/5 dòng** hiện UUID thô. Số tiền đúng; chỉ tên là không phân giải được —
những người này đến từ các phiên demo trước, không nằm trong danh sách thành
viên nhóm hiện tại, và màn không có đường lùi nào ngoài in thẳng id ra.

Loại blocker: **suggestion** (không sai tiền), nhưng nó nằm trên đúng màn hero
mà leader sẽ demo.

---

## 4. Ô chưa quét — phần quan trọng nhất

- **Mã VietQR có quét được bằng app ngân hàng thật không.** Không agent nào trả
  lời được. Vẫn mở, vẫn cần một điện thoại thật trong tay leader.
- **Mã kết bạn (F05) quét bằng camera thật.** Chỉ chứng minh được mã hiện ra và
  ô dán nhận chuỗi.
- **Chiều nhận lời mời kết bạn / lời mời nhóm.** Cần máy thứ hai; một người đi
  bộ không đóng được.
- **Cửa "Đăng ký với Apple"** — không bấm. Cửa Google đã đủ để lộ hình dạng.
- **Ngoài khung 390×844.** Không quét 320 / 1440, không quét chủ đề tối, không
  chạy axe. Lượt này đo *bấm được hay không*, không đo *nhìn có ổn không*.
- **Con đường số-điện-thoại sau màn Tin nhắn.** Nó tắc ở đó nên 40 tính năng
  còn lại chưa ai đo trên cửa vào đó. Con số 30 **không** áp dụng cho cửa này.
- **Sửa/xoá bài viết, thu hồi mức riêng tư sau khi đăng.**
- **Đường thất bại của trang khách** (link hết hạn, đã thu hồi, "Số tiền không
  đúng", "Tôi không phải Trang") — mở được trang, không đi tiếp các nhánh đó.

---

## 5. Tôi đã ghi gì vào máy demo

Lượt này ghi thật vào `:8099`, phải nói ra để lượt sau không đọc nhầm:

- 1 người mới: `Khach QA38` (số bịa dạng `09xx…`, tên bịa, không phải người thật)
- ~8 nhóm mới tên "Hoi QA38" / "Team Đà Lạt" (mỗi lượt walk sinh một nhóm)
- vài khoản chi "Bua toi QA38" 405.000đ đã ghi sổ + đợt thu đã phát
- 1 chuyến "Chuyen QA38", vài chặng "Cafe khuya" thêm vào chuyến tháng 6
- vài bài viết trên tường Minh, 2 ảnh + 1 reaction + 1 comment trong Kỷ niệm
- 1 lời mời kết bạn Minh → Khach QA38

Không xoá gì, không `make clean`. Sổ cái append-only còn nguyên. Ảnh dùng để
scan là ảnh hoá đơn **tôi tự dựng bằng PIL**, không phải bill thật, không có dữ
liệu người thật.

---

## 6. Chạy lại

```bash
export no_proxy=127.0.0.1,localhost NO_PROXY=127.0.0.1,localhost

python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:8099 --ref origin/main

cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 \
  npx expo export --platform web --output-dir /tmp/qa38-bundle --clear
cd /tmp/qa38-bundle && python3 -m http.server 8938 --bind 127.0.0.1 &

curl --noproxy '*' -s http://127.0.0.1:8938/index.html | grep -o 'index-[a-f0-9]*\.js'
# phải khớp hash expo vừa in ra, nếu không thì cổng đang bị người khác chiếm
```

Script đi bộ và toàn bộ log/ảnh nằm ở `/tmp/qa38/` (ngoài repo — ảnh là binary
và repo guard fail closed với binary). 56 ảnh chụp màn hình, mỗi bước một tấm.
