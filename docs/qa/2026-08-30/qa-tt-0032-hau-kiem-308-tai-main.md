# PASS — hậu kiểm #308 (F39 Post + F42 Privacy) tại `main`

**Sáu kịch bản quyền riêng tư mà leader yêu cầu đo trên app thật đều đúng, tại chính SHA đã ship.
Không có blocker. Hai điều đáng biết mà lượt QA trước không chạm tới: ảnh của bài đăng được gác
bằng ACL của NHÓM chứ không phải của BÀI, và "bỏ kết bạn" không có route riêng.**

| | |
|---|---|
| protocol_version | v1 |
| PR | #308 · `frontend/rd-fe-36-post-va-privacy` — **đã merge** ở `7cc51cc` |
| **đo tại** | `28621549dbd3a9051de2ac26583db365934bd16f` (`2862154`) = `origin/main` lúc nhận việc |
| nhánh QA | `qa/qa-tt-0032-hau-kiem-308-f39-f42` |
| verdict | **PASS** (xác nhận sau merge) |
| blocker còn mở | không có |
| kỹ năng | `security-testing`, `e2e-testing` |

## 0. Việc này là lượt QA THỨ HAI cho #308 — và nó không thừa

#308 đã có một phán quyết PASS: **qa-tt-0029** (`65691ae`, PR #310). Tôi kiểm trước khi làm,
đúng như đề bài dặn. Nó không thừa vì hai lý do cụ thể:

1. **qa-tt-0029 đo ở `463a522`** — một cây gộp `1b22607 ⊕ 3e64ccf` **chưa từng trở thành commit**.
   Cái đã vào `main` là `7cc51cc` (squash), và từ đó `main` đã nhích thêm bốn commit
   (`fd5198b`, `b9df83f`, `edcb734`, `2862154`). Không ai đo F42 trên cây đó.
2. **Ba trong sáu mục leader hỏi chưa được đo trên app thật.** Đối chiếu:

| mục leader hỏi | qa-tt-0029 | lượt này |
|---|---|---|
| 1. `only_me` với bạn/cùng nhóm/người lạ, **đếm bản ghi** | đã đo trên app thật | đo lại tại SHA mới |
| 2. bài `group` của nhóm 1 không lọt sang nhóm 2 | đo một chiều (feed Cuong) | đo **hai chiều**, hai nhóm thật |
| 3. **bỏ kết bạn SAU khi đăng** | chỉ unit test (`test_unfriending_takes_the_post_back`) | **đo trên HTTP thật** |
| 4. rời nhóm sau khi đăng | đã đo trên app thật | đo lại tại SHA mới |
| 5. **lời mời kết bạn đang CHỜ** | chỉ unit test (`test_a_pending_request_is_not_friendship`) | **đo trên HTTP thật** |
| 6. **EXIF + ai lấy được URL ảnh** | chỉ một ô ở đường **ghi** (403) | **đo cả đường đọc, cả byte ảnh** |

---

## 1. Cổng đã thật sự chạy

| lệnh | kết quả |
|---|---|
| `make gate` | **ĐẠT 14 · HỎNG 0 · BỎ QUA 0** — `guard guard-range ruff contract client-routes cors api migration pinned-import shared mobile docker postgres e2e` |
| `python3 -m pytest services/api/tests tests -q` | **2370 passed, 477 skipped, 4847 subtests** (sau khi định dạng 2 script của chính lượt này — xem §5) |
| `tests/postgres`, DB riêng `qa_tt_0032`, `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **419 passed, 0 skipped** |
| chặng `e2e` trong `make gate` | **7/7, `skipped 0`** — chạy thật, không phải `t.skip` |
| `$(scripts/ruff_pinned.sh)` 0.9.2 trên `tests/qa/qa-tt-0032/` | `All checks passed!` · `2 files already formatted` |
| `alembic heads` trên DB riêng | **một head** `a7d3f2b81c56`, 40 bảng |

`477 skipped` là tầng postgres bị bỏ qua trong lượt chạy chung, và tôi **không** đọc nó là xanh:
tầng đó chạy riêng ở dòng thứ ba với biến bắt buộc, ra **0 skipped**.

DB `qa_tt_0032` là DB **riêng của lượt này**, tạo mới và migrate bằng `MOBILE_DATABASE_URL`
(không phải `MOBILE_TEST_DATABASE_URL` — biến đó bị `alembic/env.py` bỏ qua im lặng và sẽ migrate
nhầm DB dùng chung). DB chung `mobile` không bị đụng tới.

---

## 2. Đi bộ trên app THẬT — 105 phép kiểm, 0 thất bại

`tests/qa/qa-tt-0032/di-bo-f42-thu-hoi-va-anh.py`. uvicorn thật ở `127.0.0.1:8153`, PostgreSQL
thật, HTTP thật. Mọi khẳng định phủ định **đếm bản ghi**, không đếm status: một feed rò một hàng
vẫn trả 200.

Sáu người, hai nhóm, năm bài (bốn audience + một bài `group` của nhóm thứ hai), ba bề mặt đọc.

| người đọc | quan hệ với An | `GET /posts` | `GET /people/{An}/posts` | `GET /posts/{id}` |
|---|---|---|---|---|
| An | tác giả | cả 5 bài | cả 5 | 200 × 5 |
| Ban | bạn ĐÃ chấp nhận, không ở nhóm nào | friends · public | như trái | 404 cho 3 bài còn lại |
| Cuong | thành viên ACTIVE của G1 | group_g1 · public | như trái | 404 cho 3 bài còn lại |
| Duyên | người lạ, biết id | public | public | 404 cho 4 bài còn lại |
| **Phúc** | **lời mời CHƯA trả lời** | **public** | **public** | **404 cho 4 bài còn lại** |
| **Em** | **ACTIVE ở G2, KHÔNG ở G1** | **group_g2 · public** | **như trái** | **404 cho 3 bài còn lại** |

### Mục 1 — `only_me` không rời khỏi tác giả
Không người nào trong năm người còn lại thấy bài `only_me`, ở **cả ba** bề mặt, kể cả trên tường
cá nhân của chính An. Khẳng định bằng **hiệu tập hợp**: `feed ∩ bài-bị-giấu = ∅` và
`wall ∩ bài-bị-giấu = ∅`, chứ không chỉ bằng status.

### Mục 2 — hai chiều, không phải một
Em (G2) không thấy `group_g1`; Cuong (G1) không thấy `group_g2`. Đo cả hai chiều vì một chiều chỉ
chứng minh bộ lọc tồn tại, không chứng minh nó lọc theo **đúng** nhóm.

### Mục 3 — bỏ kết ban SAU khi đăng, quyền mất NGAY
Trước: Ban đọc được bài `friends`. An `block` cạnh đã ACCEPTED → cạnh về `blocked`. Sau: feed và
tường của Ban tụt về đúng `{public}`, `GET /posts/{friends}` thành **404**. Không đụng một dòng
nào của bài viết. `friends` **không** bị đóng băng lúc ghi.

### Mục 4 — rời nhóm SAU khi đăng
Cuong tự gọi `DELETE /contexts/{G1}/members/{Cuong}` → feed/tường tụt về `{public}`,
`GET /posts/{group_g1}` thành **404**.

### Mục 5 — lời mời đang CHỜ không mua được gì
Phúc có một cạnh `pending` thật (khẳng định qua `GET /people/{Phuc}/friend-requests`, đúng một
hàng, state `pending`) và vẫn chỉ thấy `public`. Gửi lời mời **không** phải tự cấp quyền đọc.

### Mục 6 — ảnh trong bài
- **EXIF bị tước.** Ảnh nguồn được dựng có `Make` / `Model` / `Software` / **khối GPS (tag 34853)**,
  và phép kiểm khẳng định ảnh nguồn **thật sự mang EXIF trước khi gửi** — không có dòng đó thì mọi
  khẳng định sau là rỗng. Byte máy chủ trả về: không còn chuỗi nào trong ba chuỗi mồi,
  `len(getexif()) == 0`, không còn tag 34853, và **byte trả về khác byte đã gửi** (ảnh được dựng
  lại thật, không phải lưu nguyên).
- **Đường ghi từ chối ảnh của nhóm mình không ở trong**: Duyên đăng bài kèm ảnh của G2 → **403**.
- **Đường đọc**: xem §3, phát hiện A.

---

## 3. Hai điều đáng biết — không phải blocker

### A. ACL của ảnh là của NHÓM, không phải của BÀI · phân loại: **suggestion**

`image_url` bị kiểu `RelativePhotoUrl` ghim vào đúng dạng `/contexts/{id}/photos/{id}`, và
`read_context_photo` gác bằng `view_group_memories` + `is_group_member`. Nghĩa là **quyền đọc bài
và quyền đọc ảnh của bài là hai tập khác nhau**, lệch theo cả hai chiều. Cả hai đều đo được:

| tình huống | đọc được BÀI | lấy được BYTE ẢNH |
|---|---|---|
| bài `public` + ảnh của G2, người đọc là Duyên (người lạ) | **200**, payload có `image_url` | **403** |
| bài `only_me` + ảnh của G2, người đọc là Em (ở trong G2) | **404** | **200** |
| bài `only_me` + ảnh của G2, người đọc là Cuong (ngoài G2) | 404 | 403 |

**Vì sao đây không phải rò rỉ.** Chiều thứ hai trông đáng sợ nhưng không cấp thêm gì: tấm ảnh đã
nằm trong kho của G2 và đã đọc được bởi mọi thành viên G2 **từ lúc upload, trước khi bài tồn tại**.
Gắn nó vào một bài `only_me` không mở thêm quyền cho ai. Nội dung của bài (`body`) vẫn 404. Không
có route nào liệt kê ảnh của một nhóm, nên id ảnh cũng không tự phát tán.

**Vì sao vẫn đáng mở quyết định.** Hai hệ quả thật:

1. **Audience hẹp nhất không thể mang ảnh riêng tư.** Không có kho ảnh thuộc-về-người nào mà bài
   được trỏ tới — `/people/{id}/avatar` có tồn tại nhưng kiểu `RelativePhotoUrl` từ chối nó. Một
   bài `only_me` có ảnh **buộc phải** mượn kho của một nhóm, tức là cả nhóm đó xem được ảnh.
2. **Bài `public`/`friends` sẽ hiện ảnh vỡ.** Đúng những người tác giả chọn để xem lại nhận 403 khi
   tải ảnh. Hôm nay chưa ai thấy vì chưa màn nào render ảnh của bài; **ngày tường cá nhân bắt đầu
   vẽ `image_url` thì nó thành lỗi nhìn thấy được.**

**Tiêu chí đóng:** một ADR trả lời "ảnh của bài thuộc về ai" — hoặc kho ảnh theo người, hoặc
đường đọc ảnh cũng hỏi `post_audience.can_read`, hoặc chấp nhận và chặn ở tầng UI. Đây là câu hỏi
spec, không phải bug của #308: #308 giữ đúng mọi lời nó hứa.

### B. "Bỏ kết bạn" không có route riêng · phân loại: **fyi**

Đường duy nhất kết thúc một tình bạn ACCEPTED qua HTTP là
`POST /friends/requests/{id}/respond` với `decision: "block"`. `decline` chỉ hợp lệ từ `PENDING`
(`app/domain/friendship.py:191`). Nó hoạt động và thu hồi quyền đọc ngay — mục 3 ở trên đi bằng
chính đường này. Nhưng từ mà sản phẩm có là **"chặn"**, không phải "bỏ kết bạn", và client sẽ cần
biết điều đó. Nếu UI định làm nút "huỷ kết bạn" nhẹ nhàng thì hôm nay **không có trạng thái cho nó**.

### C. Lỗi cũ vẫn mở, không đo lại
Ghi 2xx trước khi giao dịch commit (~0.5% đọc-lại-ngay ra 404) — qa-tt-0029 đã tái lập và đã
chuyển phiếu cho backend. Có sẵn trên `main` từ trước #308. Lượt này **không** đo lại.

---

## 4. Cổng của lượt này có răng không — 7 đột biến, 0 lọt

`tests/qa/qa-tt-0032/bang-dot-bien.py`. Mỗi hàng sửa cây thật, **khởi động lại server**, chạy lại
đúng lượt đi bộ ở §2, rồi khôi phục từ bản gốc giữ trong RAM. Mọi neo được kiểm **khớp đúng một
lần** trước khi ghi — một neo khớp hai chỗ sẽ vá bản sao không ai nhìn và báo XANH giả.

Lượt đi bộ này là **hộp đen**: nó nói chuyện HTTP và không thấy tầng nào trả lời. Nên bảng có hai
loại hàng, và chỗ khác nhau mới là chỗ có thông tin:

| đột biến | muốn | được | |
|---|---|---|---|
| **M0** đảo thứ tự hai nhánh OR trong SQL (**giữ nguyên nghĩa**) | GREEN | GREEN | ĐẠT |
| M1 domain: `friends` bỏ qua `is_friend` (**chỉ tầng domain**) | RED | RED (5 ô đỏ) | ĐẠT |
| **M2** sql: bỏ `state == ACCEPTED` (**chỉ tầng SQL**) | **GREEN** | **GREEN** | ĐẠT |
| M3 **cả hai** bản sao luật `friends` bị nới | RED | RED (11 ô đỏ) | ĐẠT |
| M4 **cả hai** bản sao luật `group`: rời nhóm vẫn đọc được | RED | RED (11 ô đỏ) | ĐẠT |
| M5 media: `sanitize_image` trả về đúng byte đã nhận | RED | RED (6 ô đỏ) | ĐẠT |
| M6 service: `read_context_photo` thôi hỏi tư cách thành viên | RED | RED (2 ô đỏ) | ĐẠT |

Baseline trước mỗi hàng: `105 phép kiểm, 0 thất bại`. `git status` sau khi chạy: sạch.

Bốn điều bảng này nói mà một bảng toàn đỏ không nói được:

1. **M0 XANH.** Bảng đang phản ứng với *tính chất*, không phải với "có ai vừa sửa file". Không có
   hàng này thì mọi hàng đỏ còn lại vô nghĩa.
2. **M2 XANH là kết quả ĐÚNG, không phải một lỗ.** Nới riêng mệnh đề SQL thì `ApiService` vẫn chạy
   `post_audience.can_read` trên từng hàng trước khi serialise, nên bề mặt HTTP không đổi. Đây là
   lời khai "hai bản sao, bên hẹp hơn thắng" trong mô tả #308 được **kiểm ở bề mặt người dùng thật
   sự chạm vào**. Muốn biết tầng nào gác cái gì thì đọc bảng của qa-tt-0029; bảng này trả lời câu
   khác.
3. **M1 đỏ dù chỉ đụng domain** — vì `GET /posts/{id}` là đường đọc duy nhất không có SQL thu hẹp
   đứng trước. Đúng chỗ #308 đã tự vá ở commit thứ hai của nó.
4. **M5 và M6 đỏ ở đúng 6 và 2 ô.** Hai cổng ảnh là hai cổng khác nhau và hỏng khác nhau: một cái
   làm EXIF sống sót, một cái mở byte ảnh cho người ngoài nhóm. Nếu chúng đỏ cùng một tập ô thì
   phép kiểm ảnh của tôi mới chỉ là một phép kiểm viết hai lần.

---

## 5. Phép thử của tôi hỏng, không phải sản phẩm

Lượt chạy `pytest` đầu tiên ra `1 failed`: `test_no_new_unformatted_file_under_tests_qa` từ chối
**hai script của chính lượt QA này**. Không phải lỗi sản phẩm — cổng đang làm đúng việc của nó.
Sửa bằng đúng binary mà cổng dùng để chấm (`$(scripts/ruff_pinned.sh)` 0.9.2, không phải `ruff`
trên PATH), thêm một sửa `F541`. Sau đó: `4 passed`, và lượt đi bộ chạy lại vẫn `105/0`.

---

## 6. Ô CHƯA quét — phần quan trọng nhất của báo cáo

- **Không có màn hình nào được nhìn.** Lượt này dừng ở tầng HTTP. Tường cá nhân vẽ bốn route bài
  đăng (`rd-fe-37`) **không** nằm trong phạm vi — nghĩa là chưa ai xác nhận bốn mức audience
  *hiển thị* đúng như *cưỡng chế*. Hệ quả A ở §3 sẽ chỉ nhìn thấy được ở đó.
- **Đua (race).** Không đo "đọc đúng lúc bị bỏ kết bạn" hay hai lượt `block` đồng thời. Chỉ khoá
  thật của PostgreSQL trả lời được, và tôi không dựng ca đó.
- **Liệt kê id ảnh.** Không có route liệt kê ảnh của nhóm nên tôi không đo được id ảnh có rò qua
  đường khác (memory wall, message) hay không. "Không tìm thấy đường" ≠ "không có đường".
- **`X-Actor-*` vẫn là chỗ tạm.** Giả header của người khác thì vào được. Đã ghi trong `CLAUDE.md`,
  không nộp lại như phát hiện mới.
- **Giới hạn nhịp** trên `POST /posts` và `POST /contexts/{id}/photos`: chưa đâm.
- **Mã QR quét bằng app ngân hàng thật**: vẫn chưa ai làm, không liên quan lượt này nhưng vẫn mở.
- **Chưa có bằng chứng hành vi nào** (ADR-0006). Bộ test xanh nói code làm đúng điều tác giả nghĩ;
  nó không nói người thật hiểu bốn mức audience này khác nhau ở đâu.

---

## 7. Tái lập

```bash
docker exec mobile-local-postgres-1 psql -U mobile -d postgres \
  -c "CREATE DATABASE qa_tt_0032 OWNER mobile;"
cd services/api && MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/qa_tt_0032' \
  python3 -m alembic upgrade head
MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/qa_tt_0032' \
  MOBILE_MEDIA_ROOT=/tmp/qa-tt-0032-media \
  python3 -m uvicorn app.api.main:app --host 127.0.0.1 --port 8153 &

python3 tests/qa/qa-tt-0032/di-bo-f42-thu-hoi-va-anh.py http://127.0.0.1:8153   # 105/0
python3 tests/qa/qa-tt-0032/bang-dot-bien.py                                    # 7 hàng, 0 lọt
```
