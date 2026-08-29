# rd-qa-22 · Đi bộ liên tục qua 8 tính năng trên `main`

- **commit**: `530212d` (`origin/main`, không lệch — `git log HEAD..origin/main` rỗng)
- **ngày**: 2026-08-29
- **câu hỏi**: PoC có kể được MỘT câu chuyện liền mạch không, hay là tám tính năng rời nhau?
- **kỹ năng đã dùng**: `e2e-testing`, `bug-reproduction`
- **kết luận một dòng**: cả 8 tính năng đều chạy thật, nhưng **app không có một khái niệm
  "nhóm đang mở" duy nhất** — và đúng chỗ đó làm đứt câu chuyện.

---

## 0. Môi trường — và một cái bẫy suýt làm sai cả báo cáo

Chạy trên bundle dựng từ `main` + DB riêng, tất cả tách khỏi 5 lane khác đang chạy trên máy.

| Thành phần | Giá trị | Cách xác minh là *của mình* |
|---|---|---|
| API | `localhost:8722`, project `qa22` | md5 6 file route trong container == worktree |
| Postgres | `localhost:5722`, volume `qa22_mobile-postgres-data` | volume mới, `contexts` = 1 hàng sau seed |
| Bundle | `/tmp/qa22-web`, `expo export --clear` | `EXPO_PUBLIC_API_URL` = 8722 đếm được 6 lần trong bundle |
| Web | `localhost:8763` | canary `QA22-CANARY-530212d` đọc lại được |

**Bẫy đã bắt được (đáng báo cho cả đội):** `docker-compose.yml` đặt
`image: mobile-local/api:dev` — **một tag dùng chung cho cả máy**. `docker compose up`
lần đầu của tôi nhận **ảnh cũ của lane khác**: nó không có `POST /places/search`, tức
là không có F12 — chính thứ commit `530212d` vừa thêm. Nếu tôi đi bộ ngay lúc đó, báo
cáo này sẽ ghi "F12 hỏng trên main" trong khi F12 hoàn toàn bình thường.

```
$ docker exec qa22-api-1 grep -c 'places/search' app/api/routes/places.py
0                     # ảnh cũ
$ docker build -t qa22/api:530212d services/api   # ảnh riêng, rồi override image:
$ docker exec qa22-api-1 grep -c 'places/search' app/api/routes/places.py
2                     # khớp worktree
```

Cùng loại: cổng 8723 đã bị lane khác chiếm — server tĩnh của tôi `exit 1` mà `curl`
vẫn trả `200`. Không đối chiếu canary thì tôi đã quét trang của người khác.

---

## 1. Đi từ A tới B: được / không được

Tất cả đều bằng **tay bấm** trong một phiên, không nhảy URL, trừ hai ô ghi rõ.

### Đi được

| # | Từ → tới | Bằng chứng |
|---|---|---|
| 1 | Đăng nhập → Khám phá (F09) | 12 chỗ, điểm AI thật (`AI MATCH 96%`), `200 GET /places` |
| 2 | Khám phá → Tìm bằng lời (F12) | `200 POST /places/search`; câu "nhóm 6 đứa… 200k/người" → AI tách đúng `200k/người · 6 người · Quán ăn local` |
| 3 | Khám phá → chi tiết địa điểm | thẻ đầy đủ, có phần "AI gợi ý" giải thích theo 4 trục |
| 4 | Lên plan → dòng thời gian (F15) | 3 chuyến seed, mở được cả 3 |
| 5 | **Tạo chuyến (F13) → dòng thời gian (F15)** | `201 POST /contexts/{id}/outings` rồi **rơi thẳng vào timeline** của chuyến vừa tạo — joint này tốt |
| 6 | Dòng thời gian → check-in chặng | `201 POST /outing-stops/{id}/checkins` → "Minh đã tới / Bạn đã tới" |
| 7 | Chat → AI gợi ý chỗ | `200 POST /ai-turn`, AI đề xuất 3 quán kèm giá/đánh giá/khoảng cách |
| 8 | AI gợi ý → mở bình chọn (F17) | `201 POST /messages`, thẻ bình chọn hiện trong luồng chat |
| 9 | **Bình chọn → kết quả (F17)** | bỏ phiếu → `1 phiếu`, 👑 dẫn đầu, `1/7 thành viên đã bỏ phiếu`, hiện ở **cả** tab Chat **và** tab Plan. Sống qua phiên mới. |
| 10 | Cá nhân → tài chính | `200 GET /people/{id}/finance`, số tính lại từ sổ, 8 giao dịch |
| 11 | Cá nhân → mã kết bạn (F05) | QR vẽ thật: ô trắng 202×202, 355 module |
| 12 | Quét mã → mời vào nhóm | *(qua URL)* `#ban=…&tenban=Minh` → thẻ "QUÉT ĐƯỢC MÃ KẾT BẠN · Minh · Mời vào nhóm" |

Câu hỏi Lead nêu sẵn — *"bình chọn xong không thấy kết quả ở đâu"* — **không phải vấn đề**.
F17 là mảnh liền mạch nhất trong tám mảnh.

### Không đi được

| # | Từ → tới | Thiếu đúng cái gì |
|---|---|---|
| **A** | **Check-in địa điểm (F46) → Tường kỷ niệm (F30)** | check-in ghi vào nhóm này, tường đọc nhóm khác — **và** tường tự khai là không vẽ check-in. Repro 3/3 ở §2. |
| **B** | **Đăng nhập → nhóm mình đang có** | Không có đường nào. Minh là thành viên seed của Team Đà Lạt (7 người, 3 chuyến, 5 khoản chi) nhưng màn nhóm chỉ có "Lập hội mới". |
| **C** | **Nhóm thật → gợi ý của Khám phá** | `GET /places?context_id=1aa00000-…` — id **chưa từng có hàng trong `contexts`**; route làm `del context_id` (`places.py:303`). |
| **D** | **Bình chọn thắng → thành chuyến** | Không có nút nào. `ChiTietKeHoach` chỉ có "Quay lại đoạn chat"; nơi duy nhất tạo `outing` là form ở tab Lên plan. |
| **E** | **Chỗ đã chọn ở Khám phá → chuyến / chặng** | Chi tiết địa điểm không có "thêm vào chuyến". "Lưu địa điểm" là `useState`, chỉ trong phiên (màn tự nói ra). |
| **F** | **Quét mã khi chưa đăng nhập (F05)** | Cụt hẳn: "Chưa biết bạn là ai nên chưa mở được nhóm", nút duy nhất là "Đóng", không có đường tới đăng ký. Đây là **ca dùng chính** của F05 — người quét là người chưa có tài khoản. |

---

## 2. Nguyên nhân gốc: app có **hai** khái niệm "nhóm đang mở" cùng lúc

Đây là phát hiện chính, và nó giải thích A, B, C cùng một lúc.

| Màn | Nhóm nó dùng | Cách lấy |
|---|---|---|
| Lên plan · Tin nhắn · Kỷ niệm | `76367b53…` **Team Đà Lạt (seed)** | `POST /contexts` replay theo idempotency key |
| Khám phá · Check-in (F46) | nhóm **vừa tạo trong phiên**, hoặc không có | state trong `AppRoot` |
| Khám phá (gợi ý) | `1aa00000…` **không tồn tại** | hằng số trong `api.ts` / `places.ts` |

Hệ quả người dùng nhìn thấy: F46 bảo *"Bấm [+] rồi Tạo nhóm"*. Làm theo thì được một
nhóm **mới, rỗng**, trùng tên. Sau lượt đi bộ này, màn Cá nhân hiện
**"Nhóm của bạn (6) · 6 nhóm đang hoạt động"** — 6 nhóm đó là rác do chính hướng dẫn
trong app đẻ ra.

```
$ docker exec qa22-postgres-1 psql -U mobile -d mobile -tAc \
   "select display_name,(select count(*) from memberships m where m.context_id=c.id) from contexts c"
Team Đà Lạt|7      <- seed, có toàn bộ lịch sử
Team Đà Lạt|1      <- do tôi bấm "Tạo nhóm" tạo ra
Hội Walk|1 · Hội Walk|1 · Hội Walk|1 · Hội QA22|1 …
```

### Repro tối thiểu cho A (tất định, 3/3 giống hệt)

`/tmp/qa22-driver/repro-checkin-wall.mjs` — ba bước, đều bằng bấm tay:

1. `[+]` → "Tạo nhóm" → mở nhóm *(đúng câu app bảo làm)*
2. Khám phá → Tiệm Nướng Xóm Lào → "Nhóm đang ở đây"
3. `[+]` → "Kỷ niệm nhóm"

```
RUN 1..3 (giống hệt nhau)
  check-in hứa      : "…Nó thành một mốc trên tường kỷ niệm của nhóm…"
  check-in GHI vào  : 06d63feb… / d83c4eb1… / 038ca431…
  tường ĐỌC từ      : 76367b53-7020-4b97-84c2-38ce2fc8f9ff   (cả 3 lần)
  cùng nhóm?        : NO
  tường tên nhóm    : Team Đà Lạt          (không phải nhóm vừa check-in)
  tường hiện check-in: NO
  tường tự khai     : "Ảnh, video và check-in … chưa có kho lưu nào đứng sau,
                       nên không được vẽ ra ở đây."
```

Hai màn nói ngược nhau, và **câu của tường đã lỗi thời**: kho lưu *có thật* —
`POST /contexts/{id}/checkins` ghi vào bảng `memories`, đọc lại được bằng
`GET /contexts/{id}/memories?kind=checkin`; chính màn chi tiết địa điểm đọc nó và
hiện "1 lần". Tường chỉ là **chưa đọc**.

Thêm: có **hai hệ check-in không biết nhau** — check-in địa điểm (`memories`) và
check-in chặng (`outing_stop_checkins`). Tôi check-in chặng "Nướng sân thượng" thành
công (`outing_stop_checkins` = 1 hàng, timeline hiện "Minh đã tới"), nhưng tường vẫn
vẽ cả hai chặng y hệt nhau dưới nhãn "Đã tới" — nhãn đó chỉ là danh sách chặng, không
phản ánh ai đã tới.

---

## 3. Cổng đã chạy thật

| Cổng | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **1122 passed, 254 skipped**, 4582 subtests, 55.51s |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` (DB 5722) | **224 passed, 0 skipped**, 16.71s |
| Lỗi console trình duyệt suốt lượt đi bộ | **0** |
| Preflight CORS từ `localhost:8763` | `204`, `access-control-allow-origin` đúng origin |

254 `skipped` ở dòng đầu chính là tầng postgres — chạy riêng với DB của tôi thì
**0 skipped**. Đây vẫn là tầng CI không chạy.

---

## 4. Ô CHƯA quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Không agent nào làm được; cần
  leader, một điện thoại, 15 phút. VietQR nằm ngoài 8 tính năng của việc này nên tôi
  cũng **chưa** đi lát cắt tiền (`/expenses` → `publish` → trang khách).
- **Điện thoại thật.** Toàn bộ ở web 390×844. Không có iOS/Android, không bàn phím ảo.
- **Sáng/tối và 320 / 1440.** Chỉ quét 390 sáng.
- **Trình đọc màn hình / tương phản.** Không chạy `accessibility-testing` lượt này.
- **Nhiều người cùng lúc.** Bình chọn chỉ mới 1 người bỏ phiếu; chưa thử 2 thiết bị
  tranh nhau, chưa thử hoà phiếu.
- **F05 quét bằng camera thật.** Tôi dán URL, không chĩa camera vào ô vuông.
- **Ảnh/video của F35.** Chưa có kho ảnh nên không có gì để quét.

---

## 5. Phân loại theo 5 loại blocker của charter

| # | Phát hiện | Loại | Đề nghị |
|---|---|---|---|
| A | Check-in hứa lên tường, tường không bao giờ hiện | **vi phạm spec** — hai màn nói ngược nhau | Blocker nếu demo có đi qua kỷ niệm. Rẻ nhất: cho tường đọc `GET /memories?kind=checkin` **và** sửa câu "chưa có kho lưu". |
| B | Không có đường vào nhóm đã có; hướng dẫn trong app đẻ nhóm rác | **vi phạm spec** | Nặng nhất về mặt kể chuyện. Cần một "nhóm đang mở" dùng chung cho mọi màn. |
| C | `context_id` bị `del`, tiêu đề vẫn nói "của nhóm" | suggestion (đã ghi rõ trong code) | Sửa **câu chữ** trước khi sửa code: đừng nói "của nhóm" khi chưa đọc nhóm. |
| D | Bình chọn thắng không thành chuyến | suggestion | Một nút "Chốt → tạo chặng" là mắt xích còn thiếu giữa trụ 3 và trụ 2. |
| F | Quét mã khi chưa đăng nhập → cụt | **vi phạm spec** | Thêm đúng một nút "Đăng ký / chọn người" trên màn đó. |

Không có phát hiện nào thuộc loại **sai tiền** hay **quyền riêng tư**. Ba luật tiền
xanh ở cả hai tầng; màn Cá nhân đọc lại từ sổ và khớp.

---

## 6. Trả lời thẳng câu Lead hỏi

**PoC kể được một câu chuyện liền mạch không?**

Chưa — nhưng chỗ đứt không phải ở tính năng, mà ở **một khái niệm còn thiếu**.

Có **hai đoạn liền mạch, mỗi đoạn tự nó đẹp**:

- *Chat → AI gợi ý → bình chọn → kết quả* (F17) — trọn vẹn, thuyết phục.
- *Tạo chuyến → dòng thời gian → thêm chặng → đã tới* (F13/F15) — trọn vẹn.

Nhưng **hai đoạn đó không nối vào nhau** (D), và **Khám phá đứng ngoài cả hai** (C, E):
chỗ AI chấm điểm không đi tới chuyến nào, và check-in không về tường nào (A).

Nếu chỉ sửa **một** thứ trước hạn 31/08: **cho cả app dùng chung một "nhóm đang mở",
và nhóm đó mặc định là nhóm người dùng đã ở trong.** Một thay đổi đó gỡ A, B và C cùng
lúc, và biến sáu màn rời thành một đường đi.

---

## Tái lập lại toàn bộ

```bash
set -a && . /home/lakiet/mobile/.env && set +a
MOBILE_PROJECT=qa22 MOBILE_API_PORT=8722 MOBILE_POSTGRES_PORT=5722 \
  docker compose -f docker-compose.yml -f /tmp/qa22-override.yml up -d --wait   # override ghim image riêng
docker compose ... run --rm demo                                                # seed 7 người / 3 chuyến
cd apps/mobile && EXPO_PUBLIC_API_URL=http://localhost:8722 \
  npx expo export --platform web --output-dir /tmp/qa22-web --clear
cd /tmp/qa22-web && python3 -m http.server 8763 --bind 127.0.0.1
cd /tmp/qa22-driver && node repro-checkin-wall.mjs 1                            # repro §2
```

Ảnh chụp lượt đi bộ ở `/tmp/qa22-shots/` (ngoài repo — repo guard chặn binary).
Toàn bộ dữ liệu là seed tổng hợp, không có dữ liệu người thật.
