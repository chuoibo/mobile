# rd-qa-12 — cổng đầy đủ trên `main`, và đối chứng #121 trên một máy đã seed

Commit đã đo: `6b96b53` (`main`, gồm #121).
Ngày: 2026-08-29.

## Vì sao lượt này tồn tại

#121 **đã merge lúc 07:31 mà chưa có phán quyết QA nào** — lúc tôi mở
`gh pr list` nó còn OPEN với 0 comment, tới lượt kiểm sau thì đã nằm trên
`main`. Nên `main` đang mang code đường ghi chưa qua cổng. Lượt này chạy cổng
đầy đủ trên `main`, rồi đối chứng đúng lời hứa trung tâm của #121 thay vì tin
mô tả PR.

Không có blocker. Chi tiết ở dưới, gồm một cái bẫy đã đo được và một phán
quyết tôi tự rút giữa chừng.

## Cổng đầy đủ trên `main` @ `6b96b53` — xanh

Cả ba chạy với `TZ=UTC` (CI chạy UTC; đó là oracle tình cờ đã bắt lỗi múi giờ
ở #96, và mất CI là mất sự đa dạng môi trường đó).

| Lệnh | Kết quả |
|---|---|
| `TZ=UTC python3 -m pytest services/api/tests tests -q` | `958 passed, 197 skipped, 4580 subtests passed in 39.25s` |
| `TZ=UTC … MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q` | `174 passed in 8.98s` — **0 skipped** |
| `cd apps/mobile && TZ=UTC npm test` | `tests 328 · pass 328 · fail 0` |

197 skipped ở dòng một **không phải** là xanh: đó chính là tầng postgres tự bỏ
qua khi thiếu URL. Dòng hai là cùng tầng đó chạy thật với DB thật, nên con số
đáng tin là `174 passed / 0 skipped`, khớp đúng số #121 khai.

## Đối chứng 1 — bản trước #121 có thật sự hỏng không

Lùi **đúng một file sản phẩm**, giữ nguyên test:

```
$ git checkout 6b96b53~1 -- services/api/app/api/idempotency.py
$ TZ=UTC … pytest tests/api/test_idempotency.py tests/postgres/test_idempotency_postgres.py -q
9 failed, 29 passed in 2.65s

FAILED tests/postgres/…::test_the_app_replays_the_group_the_seed_created_instead_of_being_refused
FAILED tests/postgres/…::test_a_key_reserved_by_the_older_server_is_recognised_and_upgraded
E  assert 'f275ac36abbbe859fe4afb0ed0bdc8c90c8a164d7f4491d6824b0a73b42b5764' != 'f275ac36…'
```

Đỏ đúng chỗ, đúng route, đúng số #121 khai. Đây là test thật, không phải test giả.

## Đối chứng 2 — cái chưa ai đi: một máy ĐÃ SEED trước khi có bản sửa

Test tự động không dựng được ca này. `tests/api` chạy fake repo; `tests/postgres`
nói thẳng với database. Không tầng nào dựng lại được một **máy đã seed bằng
server đời cũ rồi nâng cấp server**. Đó lại đúng là mọi máy demo.

Nên tôi dựng thật: DB riêng `qa12seed`, migrate và seed bằng **code `ca7c464`
(main trước #121)**, rồi đổi server sang `6b96b53` trên **cùng database đó**.

Sau khi seed, vân tay của khoá `write:context` là `f275ac36…` — đúng chuỗi
xuất hiện trong ca đỏ ở trên. DB này là một máy demo tiền-sửa thật.

Ba phép thử trên cùng một khoá, `tests/qa/rd-qa-12/probe_may_da_seed.py`:

```
py bytes = b'{"display_name": "Team Đà Lạt"}'     # seed / thanNhuSeed
js bytes = b'{"display_name":"Team Đà Lạt"}'                       # JSON.stringify

PROBE 1  JSON.stringify   -> 422  idempotency_key_reuse
PROBE 2  thanNhuSeed      -> 201  id=b815c7b1-…  replayed=true
PROBE 3  JSON.stringify   -> 201  id=b815c7b1-…  replayed=true
```

Vân tay trong bảng đổi `f275ac36…` → `94f7d063…`, và `contexts` vẫn đúng **1
hàng** — replay, không phải ghi thêm nhóm thứ hai.

Kết luận: đường tương thích của #121 chạy đúng như mô tả, đo được, trên DB thật.

## Đối chứng 3 — đi bộ bằng trình duyệt thật, cross-origin

Bundle web dựng với `EXPO_PUBLIC_API_URL=http://127.0.0.1:8713`, `--clear`, và
**đã đếm lại trong bundle mà `index.html` trỏ tới**: 5 tham chiếu `8713`, 0
tham chiếu fallback `8099`. Phục vụ ở `:8714`, gọi API ở `:8713` — **khác
origin**, đúng thế trận bản web thật. Không cổng nào trong repo cưỡng chế CORS
(TestClient và node fetch đều không), nên chỉ chặng này trả lời được.

DB đặt lại về trạng thái tiền-sửa (`f275ac36…`, 1 nhóm) trước khi mở trình duyệt.

`#tab=tin-nhan&nguoi=minh`, Chromium 390×844:

```
200 PUT  /people/46b55e67-…
201 POST /contexts
200 GET  /contexts/b815c7b1-…/members
200 GET  /contexts/b815c7b1-…/messages?limit=50

lỗi console / network: (none)

Team Đà Lạt
7 thành viên
Chưa có tin nào trong nhóm này.
```

Nhóm mở ra là **nhóm đã seed** (`b815c7b1…`, 7 thành viên thật), không phải một
nhóm rỗng mới. Đây là bằng chứng người dùng cuối cùng mà #121 còn thiếu.

Ảnh chụp ngoài repo (repo guard fail closed với nhị phân):
`/tmp/qa12-anh/man-tin-nhan.png`, `man-nhom.png`, `man-nhom-sau-khi-bam.png`.

### a11y trên chính trang đã render

axe-core 4.12.0, `wcag2a + wcag2aa + wcag22aa`:

| Màn | violations | passes |
|---|---|---|
| Tin nhắn (sau khi mở nhóm) | **0** | 22 |
| Vào cửa → nhóm | **0** | 19 |
| Vào cửa → nhóm, sau khi bấm | **0** | 19 |

Đọc cho đúng: axe **không có luật tự động** cho 2.4.11 và 2.5.7, và chỉ phủ một
phần 2.5.8. "0 violations" nghĩa là 0 thứ axe biết cách hỏi, không phải "đạt
WCAG 2.2 AA".

## Một phán quyết tôi tự rút giữa chừng

Lần đi bộ đầu tôi mở `#vao=nhom`, thấy app tạo **nhóm "Team Đà Lạt" thứ hai**
với idempotency key `768d414c-2914-4c65-…` — một UUID **version 4**, ngẫu
nhiên, không phải v5 dẫn xuất. Tôi đã sắp ghi đó thành lỗi: đúng cái hỏng mà
comment trong `nhom.ts` cảnh báo ("inventing a fresh key would create a SECOND
Team Đà Lạt").

Sai. `#vao=nhom` là màn **vào cửa F03/F04 của #115**, không phải màn chat của
#119. Màn đó tên là "Lập hội mới" và **việc của nó đúng là tạo nhóm mới** —
khoá ngẫu nhiên là thiết kế, không phải lỗi. Màn chat nằm ở tab `tin-nhan`.

Tôi đã dọn nhóm thừa mình tạo ra và chạy lại trên đúng màn. Ghi lại đây vì
"hai màn cùng nói về nhóm, một cái tạo mới một cái replay" là chỗ lượt QA sau
sẽ vấp lại y hệt.

## Cái bẫy đã đo được — không chặn merge, nhưng sẽ nổ nếu ai đó dọn dẹp

`apps/mobile/src/screens/chat/nhom.ts` trên `main` hiện ghi, trong chính
docstring của nó:

> The durable fix is server-side … When that lands, `thanNhuSeed` should go and
> `JSON.stringify` should come back.

Bản sửa server **đã lands** — nó chính là #121, đã ở trên `main`. Nên một kỹ sư
frontend đọc file này trên `main` sẽ làm đúng điều nó bảo, và **PROBE 1 ở trên
là kết quả**: `422` trên mọi máy đã seed từ trước.

Câu phản-chỉ-dẫn ("đừng gỡ `thanNhuSeed` cho tới khi máy demo đã seed lại") chỉ
tồn tại trong **mô tả PR #121**. Mô tả PR không nằm trên `main`. Lead chỉ đọc
`main`.

Đây không phải blocker: `main` hôm nay chạy đúng, và đã đo. Nhưng nó là một
điều kiện gỡ chặn được ghi ở nơi không ai đọc lúc cần. Đề nghị rẻ nhất:
chuyển hai câu đó từ mô tả PR vào chính docstring `nhom.ts`. Việc đó thuộc
lane frontend, không phải của tôi — tôi chứng minh, không sửa.

## Ô CHƯA quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Vẫn nguyên, chỉ leader đóng
  được bằng một điện thoại thật.
- **Máy demo thật (`demo-api-1` / `/tmp/thu-demo`) chưa được kiểm.** Tôi cố ý
  không đụng vào stack của người khác. DB của nó có thể vẫn giữ vân tay byte
  thô — theo đo đạc ở trên thì nó sẽ tự lành ở lần mở màn Tin nhắn đầu tiên,
  nhưng **tôi chưa xác minh điều đó trên chính máy đó**.
- **Đường đua hai bộ mã hoá bắn cùng lúc** dưới cùng một khoá: chưa thử.
- **Điện thoại thật**: toàn bộ lượt này chạy ở Chromium desktop 390×844, không
  phải thiết bị thật.
- Chỉ quét a11y **3 màn**; các tab khác lượt này không đụng tới.
- Không chạy `npm run test:e2e` (lát cắt dọc) trong lượt này.

## Chạy lại

```bash
docker exec <pg> psql -U mobile -d mobile -c "CREATE DATABASE qa12seed OWNER mobile;"
git checkout ca7c464                    # main TRƯỚC #121
cd services/api && MOBILE_DATABASE_URL=…/qa12seed alembic upgrade head
MOBILE_DATABASE_URL=…/qa12seed python3 -m uvicorn app.api.main:app --port 8712
MOBILE_SEED_API_BASE_URL=http://127.0.0.1:8712 python3 scripts/seed_demo_data.py
git checkout main                       # 6b96b53, ĐÃ có #121
MOBILE_DATABASE_URL=…/qa12seed python3 -m uvicorn app.api.main:app --port 8713
python3 tests/qa/rd-qa-12/probe_may_da_seed.py
```

Trình duyệt: `EXPO_PUBLIC_API_URL=http://127.0.0.1:8713 npx expo export
--platform web --output-dir dist-qa12 --clear`, phục vụ ở `:8714`, rồi
`node tests/qa/rd-qa-12/di_bo_man_tin_nhan.mjs`.

Đếm lại số tham chiếu cổng trong bundle mà `index.html` trỏ tới trước khi tin
kết quả — `expo export` đã từng trả bundle cache và làm cả lượt đo vô nghĩa.

## Phán quyết

`PASS` — `main` @ `6b96b53` xanh ở cả ba cổng, và #121 chứng minh được cả ở
tầng test lẫn trên trình duyệt thật với một máy đã seed từ trước.
