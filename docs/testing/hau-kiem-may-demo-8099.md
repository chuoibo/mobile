# Hậu kiểm máy demo `:8099` so với `main`

- **SHA đo:** `d63a4b1` (không phải `3e64ccf` như lúc giao việc — main đã đi thêm 4 commit: #315, #309, #314, #317)
- **Ngày:** 2026-08-30
- **Lane:** qa2 · Work ID `qa-tt-0031`
- **Kỹ năng dùng:** `e2e-testing`
- **Máy đo:** container `mobile-local-api-1`, ảnh `mobile-local/api:dev`, dựng lúc `2026-08-30T15:32:16+07`, chạy từ `16:13:01`
- **Cây đo:** worktree `/home/lakiet/agent-harness/wt/qa2`, `git status --porcelain` rỗng trước khi đo

## Kết luận một dòng

Máy demo **không tụt lại sau main**: `app/` trong container trùng từng byte với
`app/` của `d63a4b1`, đường hero chia bill đi hết 16/16 chặng, và `GET /places`
của #297 phục vụ 12/12 thẻ từ cache sau lần gọi model đầu tiên.

Nhưng ba ô quan trọng **chưa quét**, và một trong ba là đúng cái #297 sửa. Đọc
mục 5 trước khi coi đây là xanh toàn phần.

---

## 1. Đếm route — lệch bao nhiêu, lệch cái nào

**Lệch: 0.** Cả hai chiều.

| Phép đo | Máy demo `:8099` | `main` `d63a4b1` |
|---|---|---|
| Đường dẫn trong OpenAPI | **65** | **65** |
| Operation (GET/POST/PUT/PATCH/DELETE) | **76** | **76** |
| Chỉ có ở một bên | — | — |

```
only local: []
only demo : []
only local ops: []
only demo ops: []
```

### Một con số 70 và một cái bẫy đếm

Liệt kê thẳng `app.routes` ra **70 đường dẫn / 81 operation**, không phải 65/76.
Chênh lệch 5 **không phải drift** — đó là năm route `include_in_schema=False`,
nên chúng không bao giờ xuất hiện trong `openapi.json`. Đã gọi thật từng cái
trên demo:

```
/healthz                 200
/docs                    200
/redoc                   200
/openapi.json            200
/docs/oauth2-redirect    200
```

Ghi ra đây vì lượt đo đầu của chính tôi đọc 70-vs-65 thành "demo thiếu 5 route".
Đếm hai bên bằng hai phương pháp khác nhau là cách tự chế ra một sai lệch không
tồn tại. Con số dùng được là 65-vs-65, đo cùng một cách ở hai đầu.

### Đối chiếu với lượt hậu kiểm trước

`#314` (qa3) đếm **62 đường dẫn** tại `3e64ccf`. Nay 65. Chênh 3 là bốn decorator
trong `app/api/routes/posts.py` mà #308 thêm vào sau `3e64ccf`
(`POST /posts`, `GET /posts`, `GET /people/{id}/posts`, `GET /posts/{post_id}`
→ 3 đường dẫn duy nhất). Không có route nào biến mất.

## 2. Máy demo đứng trên commit nào

**Đây là phép kiểm quyết định, không phải phép đếm route.** Đếm route khớp vẫn
tương thích với một ảnh cũ, miễn là các commit sau đó không thêm route — đúng
kiểu hỏng đã xảy ra trước đây (62 = 62 trong khi ảnh cũ hơn HEAD).

```
tree hash services/api/app  @ origin/main   6c5e21a350a31f3e7ef73c9ba20c09a23685ab91

digest từng file (sha256 nội dung, sắp theo đường dẫn, bỏ __pycache__):
  main   services/api/app   4e6ff3d5dcc0f2cefd093ec9171303978729d9b8dd4e5fd13db2188f5e9ca43f   124 file
  demo   /srv/app           4e6ff3d5dcc0f2cefd093ec9171303978729d9b8dd4e5fd13db2188f5e9ca43f   124 file
```

Trùng khít. **Không cần dựng lại.**

Điểm đáng chú ý: ảnh dựng lúc `15:32:16`, còn commit mới nhất của main
(`d63a4b1`) vào lúc `16:51:28` — **sau** khi ảnh được dựng. Nếu chỉ nhìn dấu
thời gian thì phải kết luận là ảnh đã cũ. Digest nói khác: bốn commit vào sau
chỉ chạm `docs/` và `tests/qa/`, không chạm `app/`. Dấu thời gian trả lời sai
câu hỏi; digest trả lời đúng.

## 3. Đường hero chia bill trên demo — 16/16 chặng

`tests/qa/qa-tt-0031/di-bo-hero-tren-demo.mjs`, gọi qua chính client đã biên
dịch của app (`apps/mobile/dist-test/api.js`), 6.8 giây:

```
DAT   dat ten ba nguoi moi (PUT /people/{id})                       105ms
DAT   tao nhom moi (POST /contexts)                                  15ms
DAT   moi va nhan hai thanh vien con lai                             63ms
DAT   QUET BILL: anh -> mon (POST /receipts/scan)                  6341ms
DAT   GAN MON: bill + goi y cua AI (POST /bills)                     38ms
DAT   GAN MON: nguoi sua lai roi chot (PUT /bills/{id}/assignments)  29ms
DAT   TAO KHOAN CHI: allocator chia (POST /expenses)                 11ms
DAT   TAO KHOAN CHI: ghi vao so (POST /expenses/{id}/confirm)        22ms
DAT   DOT THU: tu choi khi nguoi nhan chua san sang                  15ms
DAT   DOT THU: luu tai khoan nhan cua CHINH nguoi ung tien            9ms
DAT   DOT THU: mo dot thu (POST /batches)                            19ms
DAT   DOT THU: phat envelope + VietQR (POST /batches/{id}/publish)   17ms
DAT   TRANG KHACH: GET /g/{token} render va khong lo tong nhom       36ms
DAT   TRANG KHACH: khach bao da chuyen (POST /g/{token}/da-chuyen)   11ms
DAT   NGUOI NHAN: confirm-receipt                                    10ms
DAT   CA NHAN: so du cap nhat (GET /contexts/{id}/balances)          16ms

DAT 16/16 chang — 6.8s
```

**Quét bill** — Gemini đọc ảnh tổng hợp ra 5 món, `needsReview=false`:

```
Cơm tấm sườn bì chả  x1 = 65000
Cơm tấm sườn nướng   x1 = 55000
Canh chua cá lóc     x1 = 45000
Trà đá               x4 = 20000
Bia Sài Gòn          x2 = 50000
tổng in trên bill = 235000
```

**Gán món** — `assignment_state` đi `ai_suggested` → `confirmed`. Phân biệt "AI
đoán" với "người đồng ý" còn nguyên trên máy thật, không chỉ trong test.

**Tiền** — kiểm bất biến trên cái máy chủ trả về, không tự chia lại:

```
78334 + 78333 + 78333 = 235000   (luật 2: Σ phân bổ = tổng)
cả ba đều Number.isInteger        (luật 1: số nguyên đồng)
người ứng tiền không tự nợ chính mình
```

**Cổng** — `UNREADY_RECIPIENT_CHOICE_REQUIRED` bắn thật, vì người ứng tiền của
lượt này là người mới tinh chưa có tài khoản nhận. Trên nhóm demo có sẵn thì
chặng này bị bỏ qua im lặng, nên nó chỉ có nghĩa khi đi bằng danh tính mới.

**VietQR** — 122 ký tự, mở đầu `000201`, kết thúc bằng CRC `6304xxxx`.

**Trang khách** — `GET /g/{token}` trả 200; phần của chính khách (`78.333`) **có**
trên trang; tổng cả nhóm (`235.000`) **không** có. Khẳng định phần dương trước
phần âm, vì một trang trắng làm phần âm pass rỗng tuếch.

### Bộ e2e có sẵn KHÔNG chứng minh được điều này, và đó là cố ý

Chạy `npm run test:e2e` với `EXPO_PUBLIC_API_URL=http://localhost:8099` và
`MOBILE_REQUIRE_E2E=1` cho **3 đạt / 4 hỏng**. Cả bốn cái hỏng là **điều kiện
tiên quyết, không phải lỗi sản phẩm**:

```
not ok 1,2,3  duong-bill      nhom co 9 thanh vien active, cho doi 3
not ok 6      vertical-slice  "day la mot database DA CO DU LIEU ... Chay
                               'scripts/e2e_slice.sh' -- no tu dung mot
                               PostgreSQL dung mot lan"
```

`vertical-slice.test.mjs` nói thẳng trong docstring: *"Pointing
`EXPO_PUBLIC_API_URL` at the shared 8099 stack by hand is the case this guard
catches"* — nó từ chối vì `saveBankRecipient` sẽ **ghi đè tài khoản nhận tiền
thật của bản demo** mà người khác sắp đem đi trình bày. Từ chối là đúng, và nó
`fail` chứ không `skip` theo đúng luật của chính file đó ("a skip reads like a
pass").

Hệ quả cần nói ra: **không cổng nào đang có trả lời được câu "đường hero còn
chạy trên máy sắp đem đi demo không"**. File `qa-tt-0031` tồn tại để lấp đúng
khoảng đó, bằng cách mint danh tính mới mỗi lượt thay vì mượn nhóm demo.

## 4. #297 — `GET /places` trên demo

**Dữ liệu đúng.** 12 địa điểm, 12/12 `match.source == "ai"`, verdict phân bố
`hop: 1 · tam: 3 · khong-hop: 8` — model được phép kết luận "không hợp" và
route in ra đúng như thế, không bẻ thành điểm số.

**Không hỏi lại model mỗi request:**

| Lượt | Thời gian |
|---|---|
| gọi nguội lần đầu | **21.80 s** |
| 8 lượt liên tiếp ngay sau | 0.029 · 0.003 · 0.060 · 0.002 · 0.002 · 0.002 · 0.002 · 0.002 s |
| 3 lượt sau khi qua cửa sổ 60 s | 0.003 · 0.002 · 0.002 s |

11 request sau lần đầu mua **0 lời gọi model**, nhanh hơn ~1000 lần. Và cache
không phục vụ bản rút gọn: 12/12 câu `reason` trùng từng ký tự với lượt nguội,
`source` vẫn là `ai` cả 12.

**Trần theo tiến trình là trần thật trên máy này.** `CachedReasonWriter` giữ
state trên `app.state`, tức mỗi tiến trình một bản; nếu demo chạy nhiều worker
thì trần bị nhân lên. Đã kiểm:

```
CMD=["uvicorn","app.api.main:app","--host","0.0.0.0","--port","8000"]
```

Không có `--workers` → một tiến trình → trần "một lời gọi mỗi địa điểm mỗi 60 s"
đúng nguyên văn trên demo.

### Nhưng đường mà #297 sửa thì CHƯA chạy trên demo

`grep -ci 'Gemini places'` trên log container = **0**. Không hàng nào bị model
từ chối trên máy này, nên `_refused_at` chưa bao giờ có phần tử, nên **cooldown
60 giây chưa từng được thực thi ở đây**. Cái tôi đo được trên demo là cache cho
hàng **đã trả lời** — không phải cache cho hàng **bị từ chối**, mà hàng bị từ
chối mới là thứ #297 sửa.

Không ép được nó chạy mà không sửa môi trường của máy demo (thu hồi khoá, khởi
động lại container), nên tôi để nguyên và ghi vào ô chưa quét.

Đóng ở tầng nguồn thay vì tầng demo — cùng đúng bộ code đó, digest đã chứng minh:

```
tests/api/test_places_reason_retry_storm.py     10 passed in 0.90s
```

Và cổng đó **có răng**, không phải trang trí. Đột biến `_may_ask` thành
`return True` (đúng hành vi trước #297: hàng bị từ chối hỏi lại mỗi request):

```
4 failed, 6 passed
  test_a_row_the_model_never_answers_is_asked_once_not_once_per_request
  test_the_model_is_asked_again_once_the_cooldown_rolls
  test_a_row_that_answers_on_the_retry_stops_costing_calls
  test_a_writer_that_raises_is_cooled_down_like_one_that_answers_nothing
```

Đỏ đúng bốn ca mang đúng tính chất đó, không phải đỏ vì hằng số phụ. Đã khôi
phục bằng `cp` (không phải `git checkout --`, vì file đo còn chưa commit) và
digest `app/` trở lại `4e6ff3d5...` như cũ.

## 5. Ô CHƯA QUÉT — đọc kỹ mục này

1. **Mã QR chưa được quét bằng app ngân hàng thật.** Chuỗi đúng EMVCo và đúng
   CRC vẫn có thể là chuỗi không app ngân hàng Việt nào nhận. 15 phút với một
   điện thoại thật, và chỉ leader làm được.
2. **Đường hàng-bị-từ-chối của #297 chưa chạy trên container demo** (mục 4).
   Đã đóng ở tầng nguồn kèm đột biến; chưa đóng ở tầng máy thật.
3. **Đường đồng thời (`_asking`) chưa đo trên demo.** Cache đã nóng sẵn nên
   `curl -P 20` lúc này chỉ đọc `_answered`. Muốn đo thật phải có tiến trình
   nguội, tức khởi động lại container dùng chung — không làm.
4. **Phép kiểm "không lộ phần của khách khác" bị bỏ qua trong lượt này.** Hai
   khách đều nợ đúng `78.333`, nên so chuỗi không phân biệt được "phần của mình"
   với "phần người kia". Cần một lượt có hai số tiền khác nhau mới kiểm được.
5. **Ma trận hình ảnh trang khách chưa quét lượt này** — trạng thái × sáng/tối ×
   320/390/1440 (ADR-0010 lane A). Lượt này chỉ khẳng định trên HTML.
6. **Nhóm demo có sẵn (9 thành viên) chưa đi lại đường hero.** Lượt này cố ý
   dùng nhóm mới để không ghi đè tài khoản nhận tiền của bản demo, nên dữ liệu
   demo dựng sẵn vẫn chưa có ai đi thử end-to-end.

## 6. Rủi ro còn mở, theo 5 loại blocker của charter

Không có blocker nào thuộc năm loại. Hai mục đáng để Lead biết, cả hai là
**suggestion**, không phải blocker:

- **Bộ e2e không phủ được máy demo** (mục 3). Dẫn chứng: 4/7 hỏng vì điều kiện
  tiên quyết. Hậu quả: mỗi lane muốn kiểm demo sẽ tự đâm vào đúng bức tường này
  và tốn một lượt. Tiêu chí gỡ: có `qa-tt-0031` trên main thì lần sau chạy thẳng.
- **`GET /places` gọi nguội tốn 21.8 giây.** Không sai gì cả — 12 địa điểm một
  lượt, và mọi request sau đó gần như tức thời. Nhưng nếu ai đó khởi động lại
  container ngay trước buổi trình bày thì người xem đầu tiên chờ 22 giây ở tab
  Khám phá. Cách rẻ nhất: gọi `curl :8099/places` một lần sau khi restart.

## 7. Câu không được bỏ

Repo này **chưa có bằng chứng hành vi nào**. ADR-0006 gác Giai đoạn 0 theo quyết
định có ý thức của chủ sản phẩm. 16/16 chặng ở trên nói rằng các mảnh nối được
với nhau trên máy sắp đem đi demo; nó không nói người thật hiểu sản phẩm.
