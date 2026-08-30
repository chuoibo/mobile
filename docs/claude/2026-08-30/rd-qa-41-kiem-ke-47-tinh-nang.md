# rd-qa-41 — Kiểm kê 47 tính năng: có API / API đúng spec / có màn gọi

- **Đo trên**: `main` tại `a337a48` (worktree sạch `/tmp/qa41-main`)
- **protocol_version**: v1
- **Kỹ năng đã gọi**: `e2e-testing`, `bug-reproduction`
- **Ngày**: 2026-08-30

Đây là **kiểm kê**, không phải phán quyết PR. Không có verdict `APPROVE` /
`REQUEST_CHANGES` / `REJECT` trong tài liệu này.

---

## 0. Cách đo — và ba chỗ tôi cố ý không đoán

Leader nói kiểm kê trước đó là **ước lượng** (đọc 52 đường openapi rồi suy).
Kiểm kê này thay mỗi cột bằng một phép đo:

| Cột | Đo bằng gì | Không đọc từ đâu |
|---|---|---|
| **Có API** | Import `app.api.main:app` ở `a337a48`, liệt kê `(method, path)` từ chính router | Không đọc `openapi.json` của máy demo, không đếm PR merged |
| **API đúng spec** | Đọc handler + domain, rồi **bắn thật** vào API đang chạy | Không suy từ tên route |
| **Có màn gọi** | `grep` chuỗi đường dẫn trong **bundle web dựng từ `main`** (`expo export --clear`, 861 KB, 357 module) | Không đếm file `.tsx` tồn tại, không đếm PR |

**Máy dùng để bắn thật**: container `mobile-local-api-1` ở `:8099`. Trước khi tin
nó, tôi đối chiếu tập route của nó với `main`:

```
main ops 61 | 8099 ops 60
IN MAIN, NOT ON 8099:   GET /healthz     (không có trong openapi, không phải thiếu)
ON 8099, NOT IN MAIN:   (rỗng)
```

Ngang bằng tuyệt đối. Đây là phép kiểm bắt buộc — bộ nhớ đội đã ghi một lần máy
8099 tụt sau `main` 37/42 route và mọi số đo qua nó đều sai.

**Bundle**: `EXPO_PUBLIC_API_URL=http://localhost:8000 npx expo export --platform
web --output-dir /tmp/qa41-bundle --clear` → `index-154ca1e5….js` (816 KB) +
`index-553cf9c8….js` (45 KB). `--clear` bắt buộc: bộ nhớ đội ghi bundle cache trả
về bản cũ. Tôi **không** grep tiếng Việt trên bundle — chuỗi Unicode bị escape,
số 0 sẽ đọc y hệt "sạch". Chỉ grep đường dẫn ASCII.

**Ba chỗ tôi ghi "chưa xác định"** nằm ở mục 4. Tôi không lấp cho đủ bảng.

### Cổng đã chạy trên cây sạch tại `a337a48`

```
python3 -m pytest services/api/tests tests -q
  → 1845 passed, 365 skipped, 4736 subtests passed in 144.34s

python3 scripts/repo_guard.py tree HEAD
  → Repo guard passed tracked tree: 802 file scan(s).

alembic upgrade head --sql (offline, không cần DB)
  → exit 0
```

`365 skipped` **không phải là xanh**. Lượt này chạy không có
`MOBILE_TEST_DATABASE_URL`, nên mọi ca cần PostgreSQL thật đều tự bỏ qua và vẫn
thoát mã 0 — dòng skip cuối cùng in ra là
`set MOBILE_TEST_DATABASE_URL to run PostgreSQL repository tests`. Kiểm kê này
**không dựa vào tầng đó**: mọi câu về hành vi ở dưới đến từ đọc code và bắn HTTP
thật, không từ một ca live.

---

## 1. Bảng 47 hàng

Ký hiệu cột "API đúng spec": **✅ đúng** · **⚠️ lệch** (route có, hành vi khác cái
spec mô tả) · **❌ không** · **—** (không có API để hỏi).

| F## | Tên | Có API | API đúng spec | Có màn gọi | Ghi chú (bằng chứng) |
|---|---|---|---|---|---|
| F01 | Account Registration | `POST /identity/person-id`, `PUT /people/{id}` | ⚠️ | ✅ `DangKy.tsx`, `cong-api.ts` | **Không Apple, không Google, không OTP.** Route dẫn xuất id từ số ĐT bằng HMAC và trả về — không có bước nào xác minh người gọi sở hữu số đó, mà id trả về **chính là** `X-Actor-ID`. User data: chỉ `display_name` + avatar; không có email/dob/gender/city. **Trên máy demo route này trả 503** (mục 3.1) |
| F02 | Personal Profile | `GET /people/{id}/finance`, `/friends`, avatar | ⚠️ | ✅ `CaNhan.tsx` | Có avatar, display_name, `group_count`. **Thiếu**: bio, city, friend_count, trips_count, places_visited, memories_count |
| F03 | Add Friends | `POST /friends/lookup` | ⚠️ | ✅ `KetBan.tsx` | Spec liệt 5 cách; server có **1** (tìm theo số ĐT). QR + invite link là fragment link phía client (`ma-ban.ts`). Không có tìm theo username, không có contact sync. Cổng riêng tư: 30 req/phút, `PersonMatchResponse` không có trường số ĐT, thân request parse tay để 422 không echo số |
| F04 | Friend Request | `POST /friends/requests`, `.../respond`, `GET /people/{id}/friend-requests` | ✅ | ✅ `KetBan.tsx` | `Literal["pending","accepted","declined","blocked"]` khớp spec đúng 4 trạng thái |
| F05 | QR Friend Add | — (mã hoá phía client) | ⚠️ | ✅ `MaCuaToi.tsx` | Mã chứa person_id + tên, **không** chứa số ĐT (đúng). Nhưng spec vẽ `ru-di.app/u/kiet`; thực tế là fragment link, domain chưa đăng ký → quét bằng camera ngoài app **không mở được gì** |
| F06 | Create Group | `POST /contexts` + members + `PUT .../role` | ✅ | ✅ `Nhom.tsx` | id/display_name/created_by/created_at + members + role `member|admin`. Thiếu group avatar |
| F07 | Group Chat | `POST/GET /contexts/{id}/messages` | ⚠️ | ✅ `TinNhan.tsx` | **Bắn thật 10 loại spec liệt kê: 3 nhận, 7 từ chối 422** (mục 3.2). Không realtime — client phân trang bằng cursor |
| F08 | AI Member | `POST /contexts/{id}/ai-turn` | ✅ | ✅ `chat/ai.ts` | **Gemini thật.** Bắn thật: `spoke:true`, trả lời tiếng Việt, `author_id:null`. Grounding đúng: nó **từ chối bịa quán** ngoài catalogue 12 chỗ (mục 3.3). Cảnh báo: đây là route client phải gọi, không phải AI tự nói |
| F09 | Discover Places | `GET /places` | ⚠️ | ✅ `KhamPha.tsx` | 12 địa điểm seed, **4** danh mục. Spec liệt **14** danh mục. Dữ liệu tổng hợp (`app/places/catalog.py`), không phải nguồn địa điểm thật |
| F10 | Place Detail | `GET /places` (cùng payload) | ⚠️ | ✅ `ChiTietDiaDiem.tsx` | Có rating, address, price, distance, open_hours, traits, lat/lng, group_fit. **Thiếu**: photos (chỉ có `photo_count`, không URL ảnh), description, reviews |
| F11 | AI Place Match | `GET /places` → `match` | ⚠️ | ✅ `NhanAi.tsx` | **AI thật**: bắn thật ra `match.source == "ai"` cho cả 12, verdict phân bố `{hop, tam, khong-hop}`. **Lệch**: điểm được chấm so với một `GROUP` **hằng số cứng** (size 6, 250k, likes cố định) — không phải nhóm của người gọi. Spec nói "4/6 thành viên từng lưu các quán tương tự"; cái đó không tồn tại |
| F12 | NL Place Search | `POST /places/search` | ⚠️ | ✅ `CauAiHieu.tsx` | **AI thật**: câu "quan chill quan 2 … 200k/nguoi … 6 nguoi" → `{budget_per_person_vnd: 200000, group_size: 6, traits:["Chill","Ngoài trời"]}`. **Lệch**: không rút được vị trí (`max_distance_km: null`), kết quả đầu là quán ở **Đà Lạt** cho câu hỏi về **Quận 2** |
| F13 | Create Outing | `POST /contexts/{id}/outings` | ✅ | ✅ `TaoBuoiDi.tsx` | title, starts_on/ends_on, headcount, `budget_per_person_vnd` — khớp đủ 4 thứ spec vẽ |
| F14 | Invite Members | `POST /outings/{id}/invites`, `/revoke`, `POST /outing-invites/{token}/accept` | ✅ | ❌ **0 trong bundle** | Mời vào **nhóm** có màn (`/contexts/{id}/members`). Mời vào **buổi đi** thì cả ba route đều không màn nào gọi: `/invites`=0, `/revoke`=0, `/outing-invites`=0 |
| F15 | Outing Timeline | `PUT /outings/{id}/timeline` | ✅ | ✅ `DongThoiGian.tsx` | Chặng có `time_text` + thứ tự |
| F16 | AI Itinerary Generator | qua `/ai-turn` (card `itinerary`) | ⚠️ | ✅ `TheKeHoach.tsx` | Card lịch trình có thật và bị grounding về catalogue. **Lệch**: catalogue chỉ 12 chỗ (8 Đà Lạt, 4 TP.HCM) nên "Đà Lạt 2 ngày 1 đêm" chỉ rút được từ 8 dòng seed. Không có route riêng |
| F17 | Voting | ❌ không có route poll | ⚠️ | ✅ `MoBinhChon.tsx` | Đi vòng qua `ai_card` messages. Server **có** gác đúng phần của nó: `author_id` lấy từ header tin cậy, non-member 403. Nhưng **"một người một phiếu" là một phép fold ở client** (`binh-chon.ts`, `hop.set(m.author_id, …)`). Server nhận nhiều phiếu của cùng một người mà không từ chối; **không có aggregate phiếu phía server** |
| F18 | Receipt OCR | `POST /receipts/scan` | ✅ | ✅ `ChupBill.tsx` | **Gemini thật, đọc đúng.** Bắn ảnh bill tổng hợp: 5 dòng, `Beer x4` tách đúng đơn giá 60k, `items_total_vnd=770000`, `totals_agree=true` (mục 3.4) |
| F19 | Bill Item Detection | cùng route | ✅ | ✅ `KetQuaNhanDien.tsx` | `items[]` có `name/quantity/unit_price_vnd/line_total_vnd` — khớp JSON spec vẽ |
| F20 | Assign Food To Person | `PUT /bills/{id}/assignments` + `POST /expenses` scope `item` | ✅ | ✅ `App.tsx` → `luuGanMon` | Phép chia là allocator có sẵn, không viết lại |
| F21 | AI Person Recognition | ❌ | — | ❌ | Không có nhận diện khuôn mặt ở bất kỳ đâu. `grep` "face/khuôn mặt" trên `services/api/app/` ra **2 dòng, cả hai là comment**. `app/api/person_identity.py` là dẫn xuất id từ **số điện thoại**, không liên quan |
| F22 | Visual Food Participation | ❌ | — | ❌ | Không tồn tại |
| F23 | Confidence Score | có, nhưng khác nghĩa | ⚠️ | ❌ | Confidence có thật nhưng đo **độ rõ của ảnh bill** (0-100), và **cố ý không trả về client** (`ReceiptScanResponse` docstring: ADR-0009 quyết định 4). Cái spec vẽ — % cho từng người trên từng món, rồi AI hỏi "Linh có ăn pizza không?" — **không tồn tại** |
| F24 | Expense From Chat | ❌ **không route nào** | ❌ | ❌ | `app/domain/money_skill.py` + `app/api/money_skill.py` tồn tại nhưng **0 lời gọi** từ `app/api/routes/` hay `service.py`. Là code chết. Thêm nữa, prompt của companion cấm thẳng: *"Do not create an expense, obligation, payment, or financial action"* |
| F25 | Expense From Receipt | chuỗi scan → bill → assignments → expenses | ✅ | ✅ `App.tsx` | Đây là hero path, đã có e2e |
| F26 | Expense From Screenshot | ❌ (bị từ chối có chủ ý) | ❌ | — | Fail-closed: chỉ `document_type == "receipt"` mở cổng; bảng giá → `NOT_A_RECEIPT_PRICE_LIST`, còn lại → `NOT_A_RECEIPT`. Ảnh Grab/ShopeeFood/banking **bị từ chối theo thiết kế** |
| F27 | Smart Settlement | `POST /batches` | ⚠️ | ✅ `DotThu.tsx` | **Không có "minimum transfers".** `merge_obligations` chỉ cộng theo cặp `(sender, recipient)`; docstring **từ chối thẳng** việc bù trừ: *"Ha owing Nam and Nam owing Ha stay two separate obligations… section 8.8 makes an offset a social agreement"*. Đây là quyết định sản phẩm đã ghi, **mâu thuẫn với F27 như spec viết** — cần leader chốt bên nào thắng |
| F28 | Settlement Tracking | `GET /batches/{id}/obligations`, `POST /obligations/{id}/confirm-receipt` | ✅ | ✅ `DotThu.tsx` | 4 trạng thái `outstanding / partially_confirmed / confirmed / over_confirmed` — **giàu hơn** 3 trạng thái spec vẽ |
| F29 | Payment Link / QR | `POST /batches/{id}/publish`, `GET /g/{token}` | ✅ | ✅ `KetQuaThanhToan.tsx`, `MaVietQr.tsx` | VietQR EMVCo + CRC. **Chưa ai quét bằng app ngân hàng thật** — xem mục 4 |
| F30 | Group Memory | ❌ | — | ❌ | Không có kho sở thích theo người. "Kiet thích sushi / Linh ăn chay" không có chỗ nào lưu |
| F31 | Group Preference Profile | một phần, qua `/suggestion` | ⚠️ | ❌ | `summarise_history` đếm `top_categories` từ check-in — là **đếm**, không phải vector trọng số như spec vẽ (Japanese 0.91). Và chỉ có 4 danh mục để đếm. Điểm AI MATCH của F11 **không** dùng cái này, nó dùng hằng số cứng |
| F32 | Proactive Suggestion | `GET /contexts/{id}/suggestion` | ⚠️ | ❌ **0 trong bundle** | **API thật và tốt** — Gemini thật, basis do server tính, bắn thật ra `{"suggested":false,"reason":"no_history","source":"none"}` cho nhóm mới (đúng). Nhưng **không màn nào gọi** (`suggestion` xuất hiện 0 lần trong bundle) và **không có scheduler** — nó là GET, nên không có gì "chủ động" |
| F33 | Contextual Suggestions | qua `/ai-turn` | ⚠️ | ✅ `chat/ai.ts` | Phần "AI đọc mạch hội thoại rồi gợi ý" có thật. Phần "4 người đang online" **không có** — không có presence ở đâu cả |
| F34 | Budget Awareness | `GET /contexts/{id}/recap`, `/suggestion` basis | ⚠️ | ✅ `ngan-sach.ts` | Có `avg_per_person_vnd` và `in_progress` (chi tiêu chuyến đang diễn ra). **Thiếu** đúng cái spec vẽ: câu so sánh "quán này 450k/người, cao hơn mức nhóm thường chi 180k" — không nơi nào sinh ra so sánh đó |
| F35 | Group Memory Wall | `GET/POST /contexts/{id}/memories` | ⚠️ | ✅ `KyNiem.tsx` | Có photo + check-in trên một feed. **Thiếu** video và post. Riêng tư: non-member 403 (đo thật), ảnh bị dựng lại pixel nên EXIF/GPS không qua được biên (`app/media/images.py`) |
| F36 | Automatic Trip Album | ❌ | — | ❌ | `memories` **không có `outing_id`** — không có gì gom ảnh của một chuyến. `recap` liệt kê chuyến và ảnh **riêng rẽ** |
| F37 | AI Highlight Reel | ❌ | — | ❌ | Không tồn tại |
| F38 | Locket Style Widget | ❌ | — | ❌ | Không tồn tại (spec cũng ghi "Optional later") |
| F39 | Post | ❌ | — | ❌ | `MemoryCreateRequest.kind` chỉ có `photo|checkin`. Không post place/trip/memory |
| F40 | Reactions | ❌ | — | ❌ | `grep "reaction"` trên `schemas.py` + `db/models.py` = **0** |
| F41 | Comments | ❌ | — | ❌ | `grep "comment"` = **0** |
| F42 | Privacy (only me/friends/group/public) | ❌ | — | ❌ | `app/domain/visibility.py` có 3 mức nhưng là mức **cho đầu ra của AI** (`private_to_invoker / group_summary_private_details / group_visible`), không phải visibility của bài đăng. Mọi thứ hiện cứng ở "group-private" |
| F43 | Social Map | ❌ không có API | — | ⚠️ vỏ `DaiBanDo.tsx` | Component vẽ chấm từ lat/lng của **catalogue**, không có basemap (docstring nói thẳng). Không hiển thị "nơi bạn bè đã tới / trending / đã lưu" |
| F44 | Group Heatmap | ❌ | — | ❌ | Không tồn tại |
| F45 | Meet-in-the-middle | ❌ | — | ❌ | Không tồn tại |
| F46 | Group Check-in | `POST /contexts/{id}/checkins`, `POST /outing-stops/{id}/checkins`, `GET /outings/{id}/checkins` | ✅ | ✅ `CheckIn.tsx`, `LenPlan.tsx` | Cổng vị trí **đúng**: request chỉ mang `place_id`, toạ độ tra từ catalogue phía server → người gọi không tự khai được "nhóm đang ở 0.0, 0.0" |
| F47 | Automatic Place Detection | ❌ (từ chối có chủ ý) | ❌ | ❌ | Docstring `CheckinCreateRequest`: *"Reading the phone's GPS is F47 and is not built; taking coordinates from the body would let this route look like it had been"* |

---

## 2. Xếp hạng

### 2.1 THIẾU HẲN — 16 tính năng, không có API

`F21` nhận diện người · `F22` nhận diện ai ăn món gì qua ảnh bàn ăn ·
`F24` tạo khoản chi từ chat *(có thư viện domain nhưng không route nào gọi — code chết)* ·
`F26` khoản chi từ screenshot · `F30` AI nhớ sở thích từng người ·
`F36` album chuyến đi tự động · `F37` highlight reel · `F38` widget · `F39` post ·
`F40` reaction · `F41` comment · `F42` visibility bài đăng ·
`F43` social map *(chỉ có vỏ vẽ chấm ở client)* · `F44` heatmap ·
`F45` meet-in-the-middle · `F47` tự nhận biết đang ở đâu.

Hai trong số này bị **từ chối có chủ ý**, không phải quên: `F26` (ảnh screenshot) và
`F47` (GPS). Cả hai có comment giải thích tại sao. Đừng giao lại như bug.

### 2.2 CÓ VỎ / LỆCH SPEC — 19 tính năng có route nhưng hành vi khác cái spec mô tả

Xếp theo mức nguy hiểm khi demo:

| Mức | F## | Lệch ở đâu |
|---|---|---|
| **Cao** | F01 | Không OTP/Apple/Google. Biết số điện thoại = có `X-Actor-ID` của người đó |
| **Cao** | F27 | Không có "minimum transfers" — và việc không có là **quyết định sản phẩm đã ghi** (mục 8.8). Spec và code mâu thuẫn nhau, cần leader chốt |
| **Cao** | F17 | "Một người một phiếu" nằm ở client. Không có aggregate phiếu ở server |
| **Cao** | F32 | API tốt, **không màn nào gọi**, và không có scheduler nên không "chủ động" |
| **Cao** | F14 | Ba route mời-vào-buổi-đi, **0 màn gọi** |
| Vừa | F07 | 3/10 loại tin nhắn. Không realtime |
| Vừa | F11 | AI thật, nhưng chấm theo hồ sơ nhóm **hằng số cứng** |
| Vừa | F12 | AI thật, nhưng **không hiểu vị trí** — hỏi Quận 2 trả quán Đà Lạt |
| Vừa | F23 | Confidence có, nhưng đo độ rõ ảnh chứ không phải xác suất ai ăn món gì; và không trả về client |
| Vừa | F09 | 4/14 danh mục, 12 địa điểm seed |
| Vừa | F16 | Grounding tốt nhưng chỉ có 12 chỗ để dựng lịch trình |
| Vừa | F31 | Đếm danh mục ≠ vector sở thích, và F11 không dùng nó |
| Vừa | F34 | Có con số trung bình, không có câu so sánh spec vẽ |
| Thấp | F02 | 3/9 trường hồ sơ |
| Thấp | F03 | 1/5 cách kết bạn ở server |
| Thấp | F05 | Mã QR quét ngoài app không mở gì |
| Thấp | F10 | Không có ảnh thật, không có review, không có description |
| Thấp | F35 | Không có video, không có post |
| Thấp | F33 | Không có presence |

### 2.3 ĐỦ — 12 tính năng làm đúng thứ spec mô tả

`F04` friend request · `F06` tạo nhóm · `F08` AI member *(Gemini thật, grounding thật)* ·
`F13` tạo buổi đi · `F15` timeline · `F18` OCR bill *(Gemini thật, đọc đúng)* ·
`F19` tách món · `F20` gán món cho người · `F25` khoản chi từ bill ·
`F28` theo dõi thu tiền · `F29` VietQR · `F46` check-in.

Đọc con số 12 cho đúng: `F18/F19/F20/F25` là bốn hàng của **cùng một chuỗi hero**
(chụp bill → đọc món → gán người → thành khoản chi). Đếm theo đường đi độc lập thì
là 9, không phải 12.

**16 + 19 + 12 = 47.**

### 2.4 Route sống mà không màn nào gọi — 10 đường

Đo bằng `grep` trên bundle từ `main`, mỗi cái **0 lần xuất hiện**:

```
POST   /bills/{bill_id}/split          (app dùng POST /expenses thay thế)
GET    /bills/{bill_id}                (client function `docBill` không ai gọi)
GET    /contexts/{id}/suggestion        F32
POST   /outings/{id}/invites            F14
POST   /outings/{id}/invites/{id}/revoke
POST   /outing-invites/{token}/accept
POST   /bank-recipients                 (app dùng /people/{id}/bank-recipient)
GET    /bank-recipients/{recipient_id}
DELETE /contexts/{id}/members/{person_id}       (rời nhóm)
PUT    /contexts/{id}/members/{person_id}/role  (đổi vai trò)
```

Bộ nhớ đội đã ghi: *"route không ai gọi thì tính năng chưa tồn tại"*. Mười đường
này là ứng viên cho lane frontend, không phải cho lane backend.

---

## 3. Bằng chứng bắn thật

### 3.1 F01 — sign-in chết trên máy demo vì thiếu khoá

```
POST /identity/person-id {"phone": "…"}
  → 503 {"code":"identity_key_missing",
         "detail":"Máy chủ chưa cấu hình khoá danh tính nên chưa đăng nhập được."}
```

Nguyên nhân, đo trong chính container (chỉ in độ dài, không in giá trị):

```
$ docker exec mobile-local-api-1 python3 -c "…"
MOBILE_PERSON_ID_KEY present len= 0
GEMINI_API_KEY       present len= 39
```

`docker-compose.yml` **có** khai `MOBILE_PERSON_ID_KEY: ${MOBILE_PERSON_ID_KEY:-}`.
Host `/home/lakiet/mobile/.env` chỉ có `GEMINI_API_KEY` và `TOKEN_ROUTER_KEY`.

**Đây là lỗi cấu hình, không phải lỗi code.** Code trên `main` đúng: nó chọn 503
thay vì rơi về digest không khoá. Nhưng hệ quả là **bước đầu tiên của hero path
(đăng nhập bằng số điện thoại) đang chết trên máy demo**. Nếu buổi demo đi qua màn
`DangKy`, nó sẽ dừng ở đó.

### 3.2 F07 — 10 loại tin nhắn spec liệt kê, bắn thật từng loại

```
text      -> 201
image     -> 201
ai_card   -> 201
video     -> 422   literal_error on body.kind
sticker   -> 422   literal_error on body.kind
location  -> 422   literal_error on body.kind
poll      -> 422   literal_error on body.kind
reaction  -> 422   literal_error on body.kind
reply     -> 422   extra_forbidden on body.reply_to
mention   -> 422   extra_forbidden on body.mentions
```

### 3.3 F08 — Gemini trả lời thật, và từ chối bịa

Sau khi post một tin người thật (`"Toi nay nhom minh 6 nguoi an gi o quan 1?
Budget duoi 300k moi nguoi, thich do nuong ngoai troi."`):

```
POST /contexts/{id}/ai-turn -> 200  spoke: True  reason: ok  author_id: None
card: {"kind":"text","payload":{"text":"Mình tìm thấy một số địa điểm ăn uống ở
Quận 1 nhưng chưa có quán nào vừa là đồ nướng ngoài trời mà lại có mức giá dưới
300k/người trong danh sách hiện có. Các bạn có muốn mình tìm thử các quán nướng
trong nhà, hoặc các quán ngoài trời với món ăn khác không?"}}
```

Hai điều đọc được từ một câu trả lời: model **thật sự chạy**, và grounding **thật
sự chặn** — nó không bịa ra quán nướng Quận 1 mà nói thẳng là danh sách không có.

### 3.4 F18/F19 — OCR đọc đúng một hoá đơn tổng hợp

Ảnh PNG dựng bằng PIL trong `/tmp` (không phải bill thật, không vào Git):

```
POST /receipts/scan -> 200
items: Bò nướng 1×220.000 · Mì Ý 1×160.000 · Salad 1×90.000
       Beer 4×60.000 = 240.000 · Coke 2×30.000 = 60.000
items_total_vnd: 770000   total_vnd: 770000
totals_agree: true   total_difference_vnd: 0   needs_review: false   warnings: []
```

`Beer x4 240.000` được tách đúng thành đơn giá 60.000 — model không chỉ OCR, nó
chia. Số nguyên đồng ở mọi trường.

### 3.5 Cổng riêng tư — bắn thật member vs người ngoài

```
                member   nonmember
memories        200      403
recap           200      403
balances        200      403
messages        200      403
suggestion      200      403
members         200      403
outings         200      403
finance  (self) 200      403  (người khác đọc tài chính của bạn)
friends  (self) 200      403
bank-recipient  404      403  (404 = chưa cài; người ngoài không phân biệt được)
```

Không có ô nào thủng trong phạm vi tôi quét. Ba loại dữ liệu nhạy cảm:

- **TIỀN** — `finance`, `balances`, `recap`, `bank-recipient`: đều self-only hoặc
  member-only, đo thật ở trên.
- **VỊ TRÍ** — check-in chỉ nhận `place_id`, toạ độ tra phía server; `lat/lng`
  không có trên `CheckinCreateRequest` lẫn `StopCheckinResponse`, cả hai đều có
  docstring nói rõ tại sao. Suggestion cũng không trả `lat/lng`.
- **ẢNH** — `sanitize_image` dựng lại pixel bằng `Image.frombytes`, nên EXIF/GPS
  của điện thoại không qua được biên lưu trữ. Ảnh bill đi thẳng vào Gemini và
  **không** được ghi ra log (`routes/receipts.py` chỉ ghi mã lỗi).

---

## 4. Ô tôi KHÔNG xác định được — ghi ra thay vì đoán

1. **Mã VietQR có quét được bằng app ngân hàng Việt thật không.** `test_vietqr.py`
   kiểm chuỗi EMVCo và CRC; một chuỗi đúng CRC vẫn có thể là chuỗi không app nào
   chấp nhận. Không agent nào quét được mã QR. **Chỉ leader trả lời được**, 15
   phút với một điện thoại thật trên `python3 -m app.web.preview`.

2. **Tầng `tests/postgres` chưa chạy trong lượt này** — 365 ca skip. Kiểm kê này
   không dựa vào tầng đó, nhưng nghĩa là mọi câu tôi nói về hành vi persistence
   đến từ đọc code + bắn HTTP, không từ ca live.

3. **Chất lượng đầu ra AI qua nhiều lượt.** Tôi bắn mỗi surface AI **một lần**.
   F08/F11/F12/F18 đều trả lời đúng ở lượt đó. Một lượt không nói gì về tỉ lệ ảo
   giác, về việc F12 có *luôn* bỏ qua vị trí hay chỉ lần này, hay về hành vi khi
   Gemini timeout. Muốn con số thì cần `ai-system-testing` với N lượt.

4. **Bản web ≠ bản điện thoại.** Cột "có màn gọi" đo trên bundle **web** dựng từ
   `main`. Đường dẫn native (`camera/native.ts`, `expo-image-picker`) không nằm
   trong bundle web. Một tính năng ✅ ở cột đó vẫn có thể hỏng trên điện thoại.

5. **Tôi không kiểm màn hình bằng mắt.** Không ảnh chụp, không ma trận
   trạng thái × sáng/tối × 320/390/1440. Cột "có màn gọi" chỉ chứng minh **có mã
   gọi route đó trong bundle** — không chứng minh màn đó render được, đọc được,
   hay bấm được.

---

## 5. Hai chỗ đáng đưa lên leader trước khi giao việc tiếp

**(a) F27 là mâu thuẫn spec-vs-quyết-định, không phải thiếu code.**
`merge_obligations` từ chối bù trừ **có chủ ý**, viện mục 8.8 ("bù trừ là một thoả
thuận xã hội mà mọi bên phải đồng ý, không phải tiện lợi số học"). Spec F27 lại vẽ
đúng cái bù trừ đó. Giao "làm F27" cho backend mà không chốt trước sẽ ra một PR
phá một bất biến đã ghi. **Cần một câu quyết định, không cần một task.**

**(b) Năm route tốt đang chờ một màn, không chờ backend.**
`F32` suggestion, `F14` ba route mời buổi đi, và `/contexts/{id}/members` DELETE +
role. Backend đã xong; nếu giao tiếp cho backend thì lane đó viết thêm route không
ai gọi. Việc này thuộc **frontend**.

---

## 6. Câu bắt buộc

Repo này **chưa có bằng chứng hành vi nào** (ADR-0006, Giai đoạn 0 bị gác theo
quyết định của chủ sản phẩm). `1845 passed` nói code làm đúng điều tác giả nghĩ.
Nó không nói người thật hiểu sản phẩm, và bảng trên không đo điều đó.
