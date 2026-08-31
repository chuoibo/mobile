# FAIL bảng đếm 47 bản 1 — ba ô E đều sai, và phép đếm mới ra E=0

**Lý do, trước phần chi tiết:** bản 1 xếp F05/F16/F22 vào cột `E` = "không có
route nào". Gọi thật vào máy chủ dựng từ `f8fbf49`: cả ba đều **200**. Nguyên nhân
không phải thiếu route mà là **đơn vị đếm**: bản 1 đi tìm route mang *khái niệm đặc
trưng* của tên tính năng ("QR", "itinerary", "visual detection"), không tìm route
phục vụ *dữ liệu* tính năng đó dùng. Không tìm thấy → tập rỗng → in ra thành "máy
chủ không có gì". Đếm lại bằng đơn vị dữ liệu: **47/47 tính năng CÓ API**, `E = 0`.

- **task_id**: `qa-004201` / `19171001` (tách đôi: repo guard đọc chuỗi liền thành số 14 chữ số)
- **đo tại**: `f8fbf490cd85fa1c35c4a298c19aa1faff017014`
- **sha này**: **ĐÃ ở `origin/main`** (`git rev-parse origin/main` = cùng giá trị)
- **hiện vật bị phán quyết**: `docs/claude/2026-08-31/qa-114244-dem-tu-so-47.md`
  + `apps/mobile/tests/qa-114244/anh-xa-f-route.json` (bản 1, của chính tôi)

---

## 1. Tái lập lỗi — bản 1 hỏng ở đâu, chứng minh bằng lệnh

Máy chủ **của tôi**, dựng từ `f8fbf49`, cổng 8477 (không dùng container demo 8099).

```
F16  GET  /contexts/{id}/outings   -> 200   Chuyến Đà Lạt tháng 6 | 2026-06-14 | headcount 7
F05  GET  /people/{id}/friends     -> 200   {"friends":[]}
F22  POST /bills/{id}/my-items     -> 200   5 món | assignment_state = confirmed
ĐỐI CHỨNG ÂM  GET /flights         -> 404
```

Bản 1 ghi cho cả ba: `"routes": []`.

### Nguyên nhân, chính xác hơn "đo route theo tên"

Ba route trên **đã nằm trong bản đồ bản 1** — nhưng gắn cho tính năng **hàng xóm**:

| route | bản 1 gắn cho | tính năng bị bỏ rỗng |
|---|---|---|
| `GET /people/{person_id}/friends` | F03 Add Friends | **F05** QR Friend Add |
| `GET /contexts/{context_id}/outings` | F13 Create Outing | **F16** AI Itinerary |
| `POST /bills/{bill_id}/my-items` | F20 Assign Food To Person | **F22** Visual Food |

Nên lỗi không phải "không tìm ra route". Lỗi là **hai bước nối nhau**:

1. Mỗi route được gắn cho tính năng có *tên* giống nó nhất → tính năng dùng chung
   dữ liệu với hàng xóm không nhận được gì.
2. Tập rỗng được in thành cột `E` = *"không có route nào"* — một lời khai về **máy
   chủ**, trong khi thứ đo được chỉ là **từ vựng trong tiêu đề tính năng**.

Bước 2 mới là bước giết người. Bước 1 chỉ làm bảng xấu; bước 2 biến nó thành một
câu sai về sản phẩm, và đó là câu suýt làm cả đội đi xây lại ba thứ đã có.

Bằng chứng cho bước 1: `POST /receipts/scan` **được** dùng chung cho F18/F19/F23 —
vì cả ba tiêu đề đều nhìn thấy chữ "receipt". Việc dùng chung xảy ra đúng khi tên
gợi ý, không xảy ra khi tên không gợi ý. Đó là dấu vân tay của phép so tên.

---

## 2. Đơn vị đếm mới

Tách một trục đã bị gộp thành **hai trục rời nhau**:

| trục | nghĩa | nguồn |
|---|---|---|
| `du_lieu_routes` | route ĐỌC/GHI dữ liệu mà **đoạn spec** của tính năng gọi tên | danh từ tài nguyên trích từ thân spec, không từ tiêu đề |
| `nang_luc_route` | route **dành riêng** cho năng lực đặc trưng, hoặc `null` | đọc mã nguồn handler |

- `A` = có cả hai · `P` = có dữ liệu, chưa có route năng lực riêng · `E` = **không
  route nào chạm dữ liệu**.
- Một route được phép phục vụ **nhiều** tính năng.
- Mọi route khai trong bản đồ đều bị lọc lại qua `/openapi.json` **sống**. Route
  gõ sai / tưởng tượng / đã bị gỡ sẽ rụng và đẩy tính năng về `E`.

Danh từ tài nguyên cho cả 47 đoạn spec do agy đọc `product/feature_list.md`
(1826 dòng). **Không tin digest**: tôi kiểm máy số dòng agy khai cho từng F so với
đầu đề thật trong file — **47/47 khớp, 0 sai**. Đó là bằng chứng agy đã đọc thật.

---

## 3. Kết quả

```
A=43   P=4   E=0     (tổng 47)
CÓ API (A+P) = 47/47
```

**Bốn ô `P`** — có API cho dữ liệu, chưa có route cho năng lực đặc trưng:

| ô | năng lực còn thiếu | dữ liệu đã có route |
|---|---|---|
| F05 QR Friend Add | sinh/quét mã QR trỏ tới profile | `/friends/lookup`, `/people/{id}/friends`, `/friends/requests` |
| F16 AI Itinerary | AI **sinh** lịch trình theo giờ | `/contexts/{id}/outings`, `PUT /outings/{id}/timeline` |
| F22 Visual Food | AI nhìn ảnh bàn ăn suy ra ai ăn gì | `/contexts/{id}/photos`, `/bills/{id}/my-items`, `/bills/{id}/assignments` |
| F47 Auto Place Detection | tự đối chiếu GPS với địa điểm rồi hỏi xác nhận | `/areas`, `/places`, `/contexts/{id}/checkins` |

F47 **không do Lead chỉ ra** — phép đếm mới tự tìm ra. Đó là dấu hiệu đơn vị mới
đang làm việc chứ không chỉ chép lại ba đáp án đã biết.

Cơ sở cho ba dòng `null`, đọc từ mã nguồn chứ không từ tên:

- **F05**: `grep -rniE '\bqr\b' app/api/` chỉ ra VietQR của đường thanh toán —
  năng lực **khác**. Không route nào sinh hay nhận QR trỏ tới một người.
- **F16**: `app/api/service.py:2236 replace_outing_timeline` ghi audit
  `edit_outing_timeline` — nó **lưu** lịch trình, không **sinh**.
  `POST /contexts/{id}/ai-turn` là AI nhóm dùng chung, không dành riêng.
- **F22**: `face-boxes` nhận diện **người** (F21), không có gì nhìn **món ăn**.

### Một ô nữa bản 1 đúng số nhưng sai bằng chứng

**F42 Privacy.** Bản 1 gắn `PUT /contexts/{id}/members/{person_id}/role` +
`DELETE .../members/{person_id}` — quyền **thành viên nhóm** — chỉ vì tiêu đề là
"Privacy". Spec F42 nói về **phạm vi hiển thị bài đăng** (Only me / Friends /
Group / Public). Trường thật là `audience`, đọc từ `PostCreateRequest` và
`PostResponse` trong `/openapi.json`. Cùng lớp lỗi, lần này không đổi con số nhưng
đổi hẳn bằng chứng — nghĩa là lớp lỗi này rộng hơn ba ô Lead bắt được.

---

## 4. Đối chứng — cả hai chiều

Một phép đếm trả "CÓ API" cho mọi thứ thì vô dụng y như phép đếm cũ. Nên có **hai**
đối chứng, và cả hai chạy qua **đúng hàm phân loại** đang dùng cho 47 ô:

```
--- ĐỐI CHỨNG DƯƠNG (Lead bắt buộc) ---
F05 -> P  ĐẠT      F16 -> P  ĐẠT      F22 -> P  ĐẠT

--- ĐỐI CHỨNG ÂM (phép đếm còn phân biệt được không) ---
G01 [bịa] Đặt vé máy bay -> E  ĐẠT
G02 [bịa] Ví tiền trong app -> E  ĐẠT
G03 [bịa] Gọi xe -> E  ĐẠT
```

Ba tính năng bịa khai route (`/flights`, `/wallet`, `/rides`) không có trên máy
chủ; bộ lọc openapi làm chúng rụng về rỗng → `E`. **`E = 0` chỉ có nghĩa vì `E`
vẫn với tới được.**

**Đột biến bảng đồ** — ép F05 về `[]` đúng như bản 1:

```
F05 -> E  TRƯỢT
TRƯỢT: F05 vẫn bị xếp E: phép đếm vẫn hỏng, đừng nộp
EXIT=1
```

khôi phục → `TẤT CẢ ĐỐI CHỨNG ĐẠT`, `EXIT=0`. Đỏ trước, xanh sau, trên cùng một
lệnh.

---

## 5. Ô CHƯA quét — phần quan trọng nhất

- **`E=0` nói về ĐĂNG KÝ route, không nói route chạy đúng.** Gọi thật 39 route
  `GET` điền được tham số: **27 × 200**, còn lại 403/404/422 vì id giả của tôi,
  **không ô nào vì route chưa đăng ký**.
- **404 không phân biệt được "route không có" với "tài nguyên không có".**
  `GET /places/{id}` (route có thật) và `GET /flights` (bịa) **đều trả 404**. Nên
  lời gọi thật chỉ là *bằng chứng bổ trợ*; thứ phân định là `/openapi.json`. Ai
  đọc 404 thành "chưa có tính năng" sẽ lặp lại đúng lỗi bản 1 theo chiều ngược.
- **`P` không nói năng lực đó KHÓ hay DỄ.** F05 thiếu một route sinh QR (nhỏ);
  F22 thiếu một mô hình thị giác đọc món ăn (lớn). Bảng này không xếp hạng công sức.
- **Phép đếm này không chạm ĐƯỜNG BẤM.** Nó chỉ trả lời "máy chủ có gì", không trả
  lời "người dùng bấm tới được không".
- Trục `nang_luc_route` là **phán đoán của tôi**, ghi từng dòng kèm `ghi_chu` trong
  `anh-xa-f-route-v2.json` để cãi được từng ô. Trục `du_lieu_routes` thì máy kiểm
  được (lọc qua openapi sống).
- Mã VietQR **vẫn chưa ai quét bằng app ngân hàng thật**.

> **Con số 26/47 "bấm tới được" đo trên RN Web trong Chrome, CHƯA đo trên native.**
> Con số 47/47 "có API" trong tài liệu này thì đo trên **máy chủ HTTP thật** nên
> không phụ thuộc web hay native — nhưng nó cũng vì thế **không** bảo lãnh gì cho
> màn hình native.

---

## 6. Điều này đổi gì cho giai đoạn cuối

Lead hỏi: khoảng cách 26→47 nằm ở đâu.

**Không ô nào trong 47 bị chặn vì thiếu API cho dữ liệu.** 43 ô có cả route dữ
liệu lẫn route năng lực. 4 ô còn thiếu đúng một năng lực đặc trưng, và **không ô
nào cần dựng lại tầng dữ liệu từ đầu**.

Nghĩa là khoảng cách nằm ở **đường bấm** — nhưng xin nói rõ giới hạn: đó là kết
luận về *phía máy chủ không phải nút thắt*, rút ra từ bảng này. Con số đường bấm
(26/47) đến từ phép đo RN Web và **chưa đo lại trên native**, nên "khoảng cách nằm
hoàn toàn ở đường bấm" vẫn chưa được chứng minh từ hai đầu — mới chỉ loại trừ được
đầu API.

---

## 7. Chạy lại

```bash
cd services/api && python3 -m uvicorn app.api.main:app --port 8477 --host 127.0.0.1 &
# đợi "Application startup complete", và kiểm KHÔNG có "address already in use"
MOBILE_QA_API=http://127.0.0.1:8477 python3 tests/qa/qa-004201/dem_lai_47.py
# exit 0 = mọi đối chứng đạt; exit 1 = một đối chứng trượt; exit 2 = bản đồ khai route ma
```

Cần Postgres đang chạy để phần gọi thật ra 200; riêng bảng 47 chỉ cần
`/openapi.json` nên chạy được không cần dữ liệu.

Cổng repo tại `f8fbf49`: `python3 -m pytest services/api/tests tests -q`
→ **2888 passed, 614 skipped, 5272 subtests passed in 283.34s** (614 skipped là
tầng PostgreSQL thiếu `MOBILE_TEST_DATABASE_URL` — skip không phải xanh).

Ghi lại một cái bẫy đã cắn tôi giữa lượt này, vì nó sẽ cắn người khác: lượt chạy
cổng đầu tiên của tôi ra **2978 passed / 5275 subtests** — con số đó **không phải
của `f8fbf49`**, mà của `afd9b98` (nhánh devops đang mở, hơn main 18 commit). Cây
làm việc dựng từ đó. Chênh 90 ca. Số nào cũng "xanh", và không dòng nào trong bản
in nói cho biết nó đo ở cây nào.

Cùng loại bẫy, lần thứ hai trong lượt: `kill <pid>` giết vỏ shell chứ không giết
tiến trình uvicorn con. Máy chủ **cũ** (mã của cây devops) vẫn giữ cổng 8477,
`curl /healthz` vẫn trả `{"status":"ok"}`, còn phiên bản mới thoát lặng lẽ với
`[Errno 98] address already in use` nằm trong log. Nếu tin dấu 200 đó thì mọi số
trong tài liệu này là số của cây khác. Cách kiểm rẻ:

```bash
ss -ltnp | grep 8477                          # pid đang giữ cổng có phải pid mình vừa tạo không
grep -c "address already in use" <log>        # phải là 0
```
