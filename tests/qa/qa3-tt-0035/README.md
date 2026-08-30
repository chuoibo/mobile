# QA F39/F42 — tường bài đăng trên tab Cá nhân, và bốn mức người đọc

```
protocol_version  v1
đo tại            4c6b2a2, rebase trên origin/main 267971e (#312 ĐÃ merge vào main)
người đo          lane qa3, qa3-tt-0035
kỹ năng đã gọi    e2e-testing · playwright-automation
lượt trước        #330 (qa-tt-0034) đi ba luồng còn lại của #312 và ghi phần này
                  là ô CHƯA quét: "bốn route F39/F42 của đợt 2 trong cùng PR --
                  Lead giao ba luồng, tường cá nhân cần lượt riêng."
```

Việc được giao có ba câu hỏi. Hai câu đầu — ba luồng bấm được không, F26 từ chối
ảnh không phải bill có tử tế không — **#330 đã trả lời và đã merge**, nên lượt này
không đo lại. Câu thứ ba là phần #330 tự ghi là chưa quét, và là toàn bộ lượt này.

**Trả lời ngắn: tường hiện đúng, luật quyền riêng tư đúng tới từng ô của ma trận —
nhưng người dùng app không có cách nào nhìn thấy điều đó.** Chi tiết ở PH-1.

---

## 1. Máy đã dựng — không bắn vào máy demo chung

`apps/mobile/src/api.ts` fallback về `http://localhost:8099`, là stack `make up`
dùng chung. Bắn vào đó là đo cây người khác dựng lần cuối.

```
database   mobile_qa3_tuong riêng, migrate bằng MOBILE_DATABASE_URL
           (KHÔNG phải MOBILE_TEST_DATABASE_URL — alembic/env.py bỏ qua biến TEST
           im lặng rồi migrate DB chung)          → 43 bảng, head d1e2f3a4b5c6
API        uvicorn 127.0.0.1:8352 trên database đó
bundle     expo export --clear, EXPO_PUBLIC_API_URL=http://127.0.0.1:8352,
           phục vụ tĩnh ở 127.0.0.1:8353
dữ liệu    seed_tuong.py — 4 người, mọi lệnh ghi đi qua HTTP, không INSERT
```

`npm ci` chạy trước, không `cp -al` node_modules từ worktree cũ: `puppeteer-core`
thiếu trong cây này và đó đúng là cái đã làm #330 đọc ra "PR làm đỏ 7 ca".

## 2. Vì sao fixture là bốn người này, không phải bảy người của demo

`scripts/seed_demo_data.py` xếp cả bảy người vào **một** nhóm và không kết bạn ai
với ai. Trên dữ liệu đó, `friends` và `group` không phân biệt được: một `can_read`
bỏ qua hoàn toàn audience vẫn trả lời đúng mọi hàng. Nên:

| người | kết bạn với Minh | trong nhóm của Minh |
|---|---|---|
| Minh | — (tác giả) | ✓ |
| Trang | ✓ | ✗ |
| Hải | ✗ | ✓ |
| Ngọc | ✗ | ✗ |

Trang và Hải là hai người làm mệnh đề của `app/domain/post_audience.py` **bác bỏ
được**: module tự nói bốn mức là *từ vựng chứ không phải cái thang*, và rằng
`friends` với `group` với tới hai tập **rời nhau**. Nếu chúng là thang, Hải đọc
được bài `friends`.

## 3. Hai nửa, vì app chỉ nhìn thấy một nửa

Tường trên Cá nhân đọc `GET /people/{id}/posts` với **chủ thể và người đọc là cùng
một người** — `layTuong` gọi `docTuongNguoi(personId, personId)`. Mọi hàng app từng
vẽ đều đi qua nhánh đầu của `can_read` ("tác giả đọc được tất cả, kể cả only_me").

Nên **đi trình duyệt một mình KHÔNG bác bỏ được F42.** Bấm "Bạn bè" rồi thấy bài
hiện trên tường của chính mình là quan sát y hệt cái bạn nhận được từ một bản
`can_read` trả `True` vô điều kiện. Vì thế lượt này chia hai:

- **Nửa A (trình duyệt)** — cái người viết bài thấy và bấm được.
- **Nửa B (HTTP)** — cái lời hứa trên bốn cái nút đó thật sự đáng giá bao nhiêu.

Nửa B hỏi thẳng máy chủ **vì không có màn nào để hỏi qua** (xem PH-1). Nó được ghi
là phép đo tầng HTTP, không được báo cáo như một lượt đi UI.

### Nửa A — trên Chromium thật, 390×844

`102 ok / 0 FAIL`, exit 0. Những phép kiểm đáng kể:

| kiểm | kết quả |
|---|---|
| mặc định khi mở ô soạn | `Chỉ mình tôi` (`aria-checked=true`) — khớp `DEFAULT_AUDIENCE` |
| bốn ô radio dọc, mỗi ô một câu nói ai **không** đọc được | có đủ ba câu phủ định |
| chọn `Một nhóm` mà chưa chọn nhóm | `Đăng` khoá (`aria-disabled=true`), và bấm vào **không gửi request nào** |
| bốn bài đăng | mỗi lần bấm gửi **đúng 1** request rời trình duyệt |
| sau khi đăng | mức người đọc quay về `Chỉ mình tôi` |

Thân request **đã rời trình duyệt** (bắt bằng `page.on("request")`, không đọc từ
biến của client):

```json
{"body": "Bài chỉ mình tôi đọc",  "audience": "only_me"}
{"body": "Bài cho bạn bè của tôi", "audience": "friends"}
{"body": "Bài cho nhóm của tôi",   "audience": "group", "context_id": "<nhóm thật>"}
{"body": "Bài ai cũng đọc được",   "audience": "public"}
```

`author_id` vắng ở cả bốn. `context_id` chỉ có ở `group`, và là id nhóm thật chứ
không phải chuỗi nào khác.

Nhãn trên thẻ được đọc **sau khi nạp lại trang**, có chủ ý: ô soạn không đóng sau
khi đăng, nên bốn nhãn vẫn nằm trên màn dưới dạng bốn ô radio, và đếm nhãn trong
`innerText` lúc đó sẽ XANH ngay cả khi không thẻ nào được vẽ. Sau khi nạp lại, mọi
thứ trên tường là do máy chủ trả về.

### Nửa B — cùng bốn bài, bốn người đọc

Cột là người đọc; ô là "có thấy bài này trên tường của Minh không".

| bài | Minh (tác giả) | Trang (bạn bè) | Hải (cùng nhóm) | Ngọc (không gì) |
|---|---|---|---|---|
| `only_me` | THẤY | không | không | không |
| `friends` | THẤY | **THẤY** | không | không |
| `group`   | THẤY | không | **THẤY** | không |
| `public`  | THẤY | THẤY | THẤY | THẤY |

Hai ô in đậm là chỗ tính rời nhau hiện ra: Trang đọc được `friends` mà không đọc
được `group`; Hải thì ngược lại. Không cái nào chứa cái kia.

Kiểm cả hai đường đọc, và chúng nhất quán: `GET /people/{id}/posts` (tường) và
`GET /posts/{id}` (một bài). Mọi lần từ chối đều là **404, không phải 403** — 403
sẽ tiết lộ rằng bài đó có tồn tại.

`GET /posts` (bảng tin) cũng thu hẹp đúng theo người đọc:

```
Minh   200 ['friends', 'group', 'only_me', 'public']
Trang  200 ['friends', 'public']
Hải    200 ['group', 'public']
Ngọc   200 ['public']
```

## 4. Bảng đột biến — 102 ô xanh không nói gì cho tới khi chúng biết đỏ

Mỗi hàng đột biến một mình, hoàn nguyên trước hàng sau. Gốc `102 ok / 0 FAIL`.

| # | đột biến | kết quả | đọc thế nào |
|---|---|---|---|
| M3 | `can_read`: `friends` → `is_friend or is_group_member` | **XANH** 102/0 | **tương đương, không phải lỗ hổng** — xem dưới |
| M4 | `can_read`: `group` → `is_group_member or is_friend` | **ĐỎ 2** | chỉ đỏ ở `GET /posts/{id}`; đường tường còn tầng SQL |
| M5 | SQL `_readable_by`: `friends` → `friendship OR membership` | **XANH** | tương đương, cùng lý do M3 |
| M6 | SQL `_readable_by`: `group` → `membership OR friendship` | **XANH** | phòng thủ hai lớp: `can_read` vẫn lọc sau SQL |
| M7 | **M4 + M6 cùng lúc** | **ĐỎ 3** | tường rò rỉ bài `group` cho Trang |
| M8 | `only_me` mở ở **cả hai** tầng | **ĐỎ 9** | đúng hàng `only_me`, đúng 3 người đọc, cả hai đường |
| M9 | `Tuong.tsx`: thẻ luôn gắn nhãn `Chỉ mình tôi` | **ĐỎ 6** | đúng 3 thẻ sai nhãn × 2 phép kiểm |
| C1 | `limit` mặc định 50 → 25 (giữ mọi tính chất) | **XANH** | đối chứng: bảng này không đỏ-với-mọi-thay-đổi |

**M3/M5 xanh là câu trả lời ĐÚNG, và đây là chỗ dễ báo nhầm thành lỗ hổng.**
`service.py` truyền `is_group_member = record.context_id is not None and ...`, còn
`check_writable` + ràng buộc `audience_matches_target` bắt bài `friends` phải có
`context_id` NULL. Nên với mọi hàng sản phẩm có thể tạo ra, `is_group_member` **luôn
False** ở bài `friends`, và `is_friend or False` chính là `is_friend`. Bản SQL tương
đương vì `Membership.context_id == Post.context_id` với NULL không bao giờ đúng.
Nói cách khác: lỗi bậc thang mà module cảnh báo **không cắm vào được ở riêng dòng
đó** — hình dạng dữ liệu đã chặn nó. M4/M7 là chiều cắm được, và chúng đỏ.

**M6 xanh mà M7 đỏ là bằng chứng có hai lớp, không phải bằng chứng cổng mù.**
`list_person_posts` lọc bằng SQL (`_readable_by`) rồi lọc lại bằng `can_read`
(`_readable_posts`). `read_post` chỉ có một lớp — nên M4 đỏ ở đó mà không đỏ ở
tường. Harness này đi cả hai đường, nên nó thấy cả hai.

## 5. Ảnh chụp màn thật

`page.screenshot()` của Chromium ở 390×844 và 320×844 — không phải ảnh chụp DOM.
Ảnh **để ngoài Git** (repo guard fail closed với binary; ADR-0010 6.5), ở
`/tmp/qa3-anh/`:

```
01-o-soan-bon-muc-390.png   ô soạn, bốn ô radio dọc kèm câu giải thích
02-tuong-bon-bai-390.png    tường sau khi đăng, thẻ mang nhãn "Công khai"/"Một nhóm"
03-tuong-bon-bai-320.png    như trên ở 320px, chữ không tràn, nhãn còn nguyên
```

Lượt chụp **đầu tiên sai và đã sửa**, ghi lại vì nó là một cách hỏng sạch sẽ:
`full_page=True` không làm gì ở đây — react-native-web đặt thân tab trong một vùng
cuộn *bên trong*, nên document không cao lên và "cả trang" là một khung hình của
thẻ ảnh đại diện. Ba tấm ảnh đầu là ảnh của phần tài chính, trong khi **mọi phép
kiểm chữ về tường đều xanh**. Bản sửa cuộn `Tường của bạn` vào khung trước khi chụp.

## 6. Phát hiện

Không cái nào thuộc 5 loại blocker của charter. PH-1 là loại đáng đọc nhất.

### PH-1 · Bốn mức người đọc chưa có hậu quả nào nhìn thấy được trong app

Đây không phải lỗi của #312, và **không phải lỗi quyền riêng tư** — luật đúng, ma
trận ở mục 3 chứng minh điều đó. Nó là chuyện phạm vi, và nó làm một câu trong mô tả
PR đọc rộng hơn thực tế.

Trên `origin/main 267971e`, đếm lời gọi ngoài `api.ts`:

| hàm client | route | số màn gọi |
|---|---|---|
| `dangBai` | `POST /posts` | 1 (`tuong.ts`) |
| `docTuongNguoi` | `GET /people/{id}/posts` | 1 (`tuong.ts`), luôn `(personId, personId)` |
| `docBangTin` | `GET /posts` | **0** |
| `docBai` | `GET /posts/{post_id}` | **0** |

Ghép hai sự thật lại:

1. tường chỉ đọc bài **của chính mình, với tư cách chính mình** → mọi mức người đọc
   trông y hệt nhau với tác giả;
2. không màn nào đọc bài của **người khác**.

⇒ Chọn `Chỉ mình tôi` hay `Công khai` cho ra **cùng một màn hình**, ở mọi chỗ trong
app. Người dùng không có đường nào để thấy, kiểm, hay tin lời hứa mà bốn cái nút
vừa đưa ra. Bốn câu giải thích ("Ai mở app cũng đọc được") mô tả một hậu quả có
thật ở máy chủ và **chưa quan sát được** trong sản phẩm.

Mô tả #312 có nói ý này ("bảng tin chưa có màn riêng cho người dùng bấm vào"), nên
đây là xác nhận kèm số, không phải phản bác.

### PH-2 · Cổng "route máy chủ không ai gọi" đếm ở tầng `api.ts`, không tới màn

Cái này là về **cổng của chính tôi** (`scripts/check_server_routes_called.py`, PR
#333, chưa merge): nó quét `apps/mobile/src/api.ts`. Một route có hàm client thì
được tính là "đã được gọi", **kể cả khi không màn nào gọi hàm đó**.

Hậu quả cụ thể: `/posts` và `/posts/{post_id}` được cổng tính là sống, trong khi
theo bảng PH-1 chúng có 0 màn gọi. Con số "0 route chết (trước là 7)" đúng ở tầng
`api.ts` và **rộng hơn thực tế ở tầng màn** đúng hai route.

Đây là đúng cái bẫy repo đã ghi: *route không ai gọi thì tính năng chưa tồn tại* —
và một hàm client không ai gọi là cùng một lớp lỗi, lùi thêm một tầng. Tiêu chí gỡ:
cổng đếm lời gọi từ `src/screens/**` chứ không chỉ từ `api.ts`, hoặc khai hai con số
riêng. Tôi sẽ nhận việc này nếu Lead xếp lịch.

### PH-3 · Đường một lớp và đường hai lớp không cân nhau

`GET /people/{id}/posts` và `GET /posts` lọc **hai lần** (SQL `_readable_by`, rồi
`can_read`). `GET /posts/{post_id}` lọc **một lần** (`can_read`). M4 chứng minh hậu
quả: một lỗi chỉ ở `can_read` rò rỉ qua đường một bài và **không** rò rỉ qua tường.

Không phải defect — phòng thủ nhiều lớp là tốt. Nhưng nó có nghĩa là một bộ test chỉ
đi đường danh sách sẽ **mù** với hồi quy ở `can_read`, và ngược lại. Đáng ghi vào
chỗ nào đó cạnh `_readable_by`, nơi đã có sẵn ghi chú "Change either and change both".

### PH-4 · Không có ô chọn ảnh, đúng như mô tả PR

`image_url` đi đúng hợp đồng ở tầng client nhưng ô soạn không có nút chọn ảnh, nên
đường đó chưa người dùng nào đi được. #312 đã tự nói ra; ghi lại cho đủ.

## 7. Cổng đã chạy — số thật, cây sạch, sau khi rebase lên `267971e`

| cổng | kết quả |
|---|---|
| `cd apps/mobile && npm test` | `# tests 749 · # pass 749 · # fail 0 · # skipped 0` |
| `python3 -m pytest services/api/tests tests -q` | `2492 passed, 547 skipped, 4857 subtests` |
| `MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q` | `440 passed` — **0 skipped** |
| `bash scripts/gate.sh ruff` | `ĐẠT` |
| `$(scripts/ruff_pinned.sh) check tests/qa/qa3-tt-0035/` | `All checks passed!` |
| `python3 scripts/repo_guard.py staged` | `Repo guard passed` |
| `di_bo_tuong.py` (app thật) | `102 ok · 0 FAIL` · exit 0 |

547 skip là tầng PostgreSQL khi thiếu `MOBILE_TEST_DATABASE_URL`; hàng dưới nó là
cùng tầng đó chạy thật với 0 skip.

Lượt đo bị **rebase giữa chừng**: `origin/main` đi từ `23e34d7` lên `267971e` (7
commit, gồm #133 thêm migration vote) trong lúc tôi đang đo. Mọi con số ở trên và
toàn bộ ma trận mục 3 đã được **chạy lại từ đầu** trên cây sau rebase — dựng lại
bundle, migrate lại database (43 bảng, head `d1e2f3a4b5c6`), seed lại, đi lại.

## 8. Ô CHƯA quét

- **Ba luồng F24/F14/F26 và việc F26 từ chối ảnh không phải bill** — #330 đã đo và
  đã merge; lượt này cố ý không đo lại.
- **Điện thoại thật.** Chỉ chạy Chromium trên web.
- **Chế độ tối · Firefox/WebKit.** Chỉ sáng, chỉ Chromium.
- **Tường của người khác qua UI.** Không tồn tại màn đó (PH-1), nên không đo được
  bằng trình duyệt. Nửa B đo ở tầng HTTP và chỉ nên đọc như vậy.
- **Huỷ kết bạn rồi đọc lại.** `post_audience.py` nói rõ `friends` **không** đóng
  băng lúc ghi, nên huỷ kết bạn phải lấy lại quyền đọc. Chưa đo — cần một hàng nữa
  trong fixture.
- **Rời nhóm rồi đọc lại.** Cùng lớp câu hỏi với dòng trên.
- **Bài của nhiều tác giả.** Cả bốn bài đều do Minh viết; bảng tin trộn nhiều tác
  giả chưa được đi.
- **413 / 429 / body 5000 chữ.** Chưa đâm.
- **Mã QR quét bằng app ngân hàng thật.** Vẫn mở, như mọi lượt trước — không agent
  nào đóng được câu này.

Lượt này nộp phát hiện, **không ký verdict** (ADR-0010 6.3).
