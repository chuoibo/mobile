# rd-qa-24 · F16 (AI lịch trình) đã tồn tại chưa? — kiểm trước khi ai đó dựng lại

- protocol_version: v1
- verdict: **PASS** — F16 CÓ THẬT trên `main`, tính được vào độ phủ
- đo tại: `6c7d2ab`
- sha này: `6c7d2ab` **ĐÃ ở main** (là HEAD của `origin/main` lúc đo).
  Cây đo: `git diff origin/main --stat` **rỗng** trước và sau mọi phép đột biến.
- blocker còn mở: **không có**

## Lý do PASS, viết trước phần chi tiết

Lead hỏi đúng một câu: *"phần lớn F16 CÓ THỂ đã tồn tại — kiểm trước khi làm, đừng dựng
lại."* Câu trả lời là **đã tồn tại, cả hai nửa**, và tôi không kết luận bằng cách đọc code:
tôi gửi **đúng câu prompt in trong spec F16** vào máy chủ dựng từ `6c7d2ab`, với Gemini
thật, và nhận về một lịch trình có thật, được ground vào catalogue của máy chủ.

```
POST /contexts/{id}/ai-turn -> 200   spoke=True  reason=ok
card kind = itinerary
title     = Lịch trình Đà Lạt 2 ngày 1 đêm
```

Nửa giao diện cũng không phải vỏ: thẻ trong chat → nút **"Xem chi tiết kế hoạch"** →
màn `ChiTietKeHoach` vẽ đủ mọi chặng, có nút quay lại và có dòng ghi công AI.

**Đừng giao F16 cho ai dựng lại.** Việc còn lại là hai chỗ hở ở dưới, cả hai đều nhỏ.

## F16 đòi gì, và cái gì đang có

Spec (`feature_list.md` §F16) đưa một prompt và mong một lịch trình nhiều chặng có giờ.

| Mảnh | Ở đâu | Trạng thái |
|---|---|---|
| Route | `POST /contexts/{id}/ai-turn` | có, 200 |
| Model trả `kind:"itinerary"` | `app/api/companion_gemini.py` | có |
| Ground vào catalogue máy chủ | `app/domain/companion.py:_ground_itinerary` | có, fail-closed |
| Catalogue | `app/places/catalog.py` — 12 chỗ, **8 ở Đà Lạt** | có |
| Thẻ trong chat (3 chặng đầu + nút) | `screens/chat/TheKeHoach.tsx` | có |
| Màn chi tiết (đủ chặng) | `screens/chat/ChiTietKeHoach.tsx` | có |
| Nút mở màn chi tiết | `TinNhan.tsx:127` → `setKeHoachDangXem` | có, state thật |

Catalogue chứa đúng "Lưng Chừng Cafe" và "Tiệm Nướng Xóm Lào" — hai cái tên in trong ví dụ
của spec. Nó được dựng cho đúng prompt này.

## Đi bộ thật — prompt của chính spec

Máy chủ chạy từ cây `6c7d2ab`, DB riêng `qa24f16` (migrate từ đầu tới `e3b8c1d5720f`),
`GEMINI_API_KEY` thật. Ba phép kiểm rẻ trước khi tin số đo:
`/healthz` → 200 · `openapi.json | grep -c ai-turn` → 1 · cổng 8451 tự chọn sau khi
dò trống (cổng 8399 đã bị lane khác chiếm và trả 404 — đúng cái bẫy đã ghi trong memory).

```
prompt: "Đi Đà Lạt 2 ngày 1 đêm, 8 người, budget 2 triệu/người."

card kind = itinerary   |  stop count = 6
  Trưa ngày 1      Lẩu Gà Lá É Tao Ngộ
  Chiều ngày 1     Lưng Chừng Cafe
  Tối ngày 1       Tiệm Nướng Xóm Lào
  Tối muộn ngày 1  Chill Đêm Đà Lạt
  Sáng ngày 2      Sống Màu Workshop
  Trưa ngày 2      Nướng Ngói Trời Thông
```

Ghi chú thiết kế đáng biết: **"ngày" không có trên dây**. Wire chỉ có một mảng `stops`
phẳng với `time_text` là chuỗi tự do; model tự nhét "ngày 1"/"ngày 2" vào `time_text`.
Nên nhiều ngày *hiển thị* được nhưng không *cấu trúc hoá* được — app không thể nhóm theo
ngày, không thể có tab ngày. Đây là lựa chọn có ý thức (comment trong `TheKeHoach.tsx` nói
thẳng "There is no day tab and no total, because the wire has neither"), không phải lỗi.

## Phát hiện 1 — máy chủ **cắt câm** lịch trình ở 6 chặng (suggestion, không phải blocker)

`MAX_STOPS = 6` trong `app/domain/companion.py`. Schema gửi cho Gemini **không hề khai giới
hạn nào** (`"stops": types.Schema(type=ARRAY, items=_STOP_SCHEMA)` — không maxItems). Nên
model tự do trả về nhiều hơn 6, và máy chủ lặng lẽ vứt phần thừa: `stops[:MAX_STOPS]`,
không cờ, không câu nào nói cho người dùng biết.

**Tái lập tất định, không cần AI** (`ground_card` với 8 chặng hợp lệ):

```
stops sent in  = 8
stops came out = 6
SILENTLY DROPPED = ['stop-7', 'stop-8']
payload keys = ['title', 'stops']      <- không có cờ báo đã cắt
```

**Và nó cắn thật với người dùng thật.** Cùng máy chủ, Gemini thật, một câu hỏi hoàn toàn
hợp lý cho F16:

```
prompt: "Lên lịch trình Đà Lạt 2 ngày 1 đêm thật chi tiết, nhóm 8 người,
         ghi rõ từng khung giờ sáng trưa chiều tối của cả hai ngày."

MODEL PLANNED 8 stops; USER RECEIVES 6

1. Sáng ngày 1     An Cafe Đà Lạt           delivered
2. Trưa ngày 1     Lẩu Gà Lá É Tao Ngộ      delivered
3. Chiều ngày 1    Khu vui chơi DREAMpark   delivered
4. Tối ngày 1      Tiệm Nướng Xóm Lào       delivered
5. Đêm ngày 1      Chill Đêm Đà Lạt         delivered
6. Sáng ngày 2     Sống Màu Workshop        delivered
7. Trưa ngày 2     Tiệm Nướng Xóm Lào       >>> DROPPED
8. Chiều ngày 2    Lưng Chừng Cafe          >>> DROPPED
```

Người dùng hỏi "cả hai ngày" và nhận một kế hoạch **đứt ở trưa ngày 2**, không có một chữ
nào nói rằng nó đã bị cắt. Nhìn từ màn hình, đó không giống một giới hạn — nó giống AI chỉ
nghĩ được tới đó.

Vì sao tôi xếp nó là **suggestion** chứ không phải blocker: không sai tiền, không lộ dữ
liệu, không hỏng tính hợp lệ thí nghiệm, và cắt thì fail-closed chứ không bịa. Nhưng F16 là
tính năng "2 ngày 1 đêm" và ví dụ của chính spec đã có 6 chặng cho **riêng ngày 1** — nên
với đúng đề bài của nó, giới hạn 6 không bao giờ đủ.

Gỡ chặn rẻ nhất, chọn một (việc của lane backend, không phải của tôi):
- nâng `MAX_STOPS` lên đủ cho hai ngày (≥12), hoặc
- khai `maxItems` trong schema Gemini để model tự gói gọn trong 6 thay vì bị cắt sau lưng, hoặc
- trả một cờ `truncated: true` để app nói được "kế hoạch còn dài hơn".

## Phát hiện 2 — **không cổng nào giữ F16** (suggestion)

Đây là mục 4 của chu kỳ thường trực: chọn một dấu xanh và làm hỏng thứ nó lẽ ra phải bảo vệ.
Hai phép đột biến, **cả hai đều không ai kêu**:

| # | Đột biến | Kỳ vọng | Đo được |
|---|---|---|---|
| M1 | `TheKeHoach.tsx:77` — `the.kind === "itinerary"` → `false` | ĐỎ | **typecheck** bắt (TS2339/TS18047), chưa tới được test → không kết luận được |
| M1b | `the.chang.slice(0, 3)` → `slice(0, 0)` — thẻ hiện **0 chặng**, vẫn typecheck sạch | ĐỎ | **493 pass / 0 fail — XANH** |
| M2 | `companion.py` — `MAX_STOPS = 6` → `3` | ĐỎ | **1165 passed / 254 skipped — XANH** |

M1b là cái đáng lo: thẻ lịch trình có thể render **rỗng hoàn toàn** trên giao diện mà toàn
bộ 493 ca vẫn xanh. M2 nghĩa là con số 6 — thứ vừa gây ra Phát hiện 1 — **không bị ghim bởi
bất kỳ ca nào**; ai đó hạ nó xuống 3 ngày mai và cổng vẫn xanh.

Sau mỗi phép: khôi phục từ bản sao `/tmp`, `git diff --stat` **rỗng**. Không phép nào để lại rác.

## Cổng đã chạy tại `6c7d2ab`

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | `1165 passed, 254 skipped, 4590 subtests passed` (64s) |
| `cd apps/mobile && npm test` | `493 tests, 493 pass, 0 fail, 0 skipped` |
| `alembic upgrade head` (DB `qa24f16`) | EXIT=0, tới `e3b8c1d5720f` |
| `/healthz` · `grep -c ai-turn openapi.json` | `200` · `1` |

`254 skipped` là tầng `tests/postgres` tự bỏ qua vì lượt này không đặt
`MOBILE_TEST_DATABASE_URL` cho pytest — **skip không phải xanh**, và tôi khai nó ra ở đây.
Tầng đó đã được chạy đủ (`224 passed`, 0 skipped) ở rd-qa-23 trên **chính SHA này**.

## Ô CHƯA QUÉT — khai đầy đủ

- **Chưa đi bộ F16 bằng trình duyệt thật.** Tôi chứng minh UI tồn tại và nối đúng bằng
  cách đọc đường dây (`TheKeHoach` → `onXemChiTiet` → `setKeHoachDangXem` → `ChiTietKeHoach`)
  cộng với `npm test` xanh. Tôi **chưa** dựng bundle rồi bấm nút bằng chuột. M1b cho thấy
  đúng vì sao ô này quan trọng: bộ test không nhìn thấy thẻ rỗng.
- **Chưa chạy trên điện thoại thật.**
- **Chưa quét a11y** màn `ChiTietKeHoach` (không chạy `imp detect`, nên không có canary,
  nên tôi không nộp con số nào về nó).
- **Chỉ 3 lượt gọi Gemini.** Gemini bất định; 3 lượt không phải tỉ lệ. `temperature=0.0`
  giúp nhưng không đảm bảo.
- **Chưa thử prompt ngoài Đà Lạt.** Catalogue có 8/12 chỗ ở Đà Lạt; một prompt "đi Vũng Tàu"
  gần như chắc chắn không ground nổi. Chưa đo, nên chưa báo.
- **Chưa đo lịch trình 3 ngày trở lên.**

## Kết luận cho Lead

**F16 tính được vào độ phủ.** Cả API lẫn màn gọi đều có thật và nối vào nhau — đúng tiêu
chuẩn "đếm tính năng phải có cả API lẫn màn gọi". Còn **năm** tính năng nữa tới đích ~60%,
không phải sáu.

Hai phát hiện trên đều là suggestion, không chặn gì. Nếu chỉ sửa được một thứ trong quỹ thời
gian còn lại, sửa `MAX_STOPS`: nó rẻ nhất và nó là thứ duy nhất người xem demo sẽ thấy tận mắt.
