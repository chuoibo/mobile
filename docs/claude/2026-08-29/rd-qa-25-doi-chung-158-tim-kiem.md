# rd-qa-25 · Đối chứng #158 (bug-191433): ô tìm kiếm Khám phá gửi X-Actor-ID

- protocol_version: v1
- verdict: **PASS** (nghiệm thu sau merge)
- đo tại: `6c7d2ab` (bản SAU) và `df3f1a1` (bản TRƯỚC), cả hai đánh vào **cùng một máy chủ**
- sha này: `6c7d2ab` **ĐÃ ở main** (`origin/main` = `6c7d2ab` lúc đo). `df3f1a1` cũng đã ở
  main — nó là commit ngay trước #158, tức đúng trạng thái hỏng mà PR nói nó sửa.
- blocker còn mở: **không có**

## Lý do PASS, viết trước phần chi tiết

Lỗi có thật, tái lập được, và bản sửa đúng là thứ chữa nó. Tôi không nhận lời hứa của PR:
tôi dựng **hai bundle web riêng biệt** từ hai commit thật, cho cả hai bắn vào **một máy chủ
duy nhất chạy mã main không sửa**, rồi đi bộ bằng trình duyệt thật. Chỉ bundle khác nhau.

- **TRƯỚC (`df3f1a1`)**: header đi ra là `null`, máy chủ trả **401**, và màn hình in nguyên
  `{"code":"authentication_required","detail":"Missing X-Actor-ID"}` kèm địa chỉ API nội bộ.
  Tìm kiếm bằng lời **chết 100%** trên main trong 16 phút giữa #155 và #158.
- **SAU (`6c7d2ab`)**: header đi ra là personId thật, **200**, màn hiện panel "AI hiểu câu
  của bạn" (ngân sách 300k/người · 6 người · quán ăn local · đồ nướng, ngoài trời) và 2 chỗ.

Ba trạng thái mới đều được kiểm bằng **429 thật từ limiter thật**, không stub cái gì.
Ba phép đột biến lên bản sửa đều **ĐỎ**. Một phát hiện kèm dưới là **suggestion**
(trạng thái `bi-tu-choi` hôm nay không có đường nào tới được), không phải blocker.

## Đo trên cái gì

| | TRƯỚC | SAU |
|---|---|---|
| commit | `df3f1a1` | `6c7d2ab` |
| bundle | `dist-qa23-before`, sha js `a00651fc409f` | `dist-qa23-after`, sha js `b12e65eec700` |
| máy chủ | **cùng một** uvicorn tại `127.0.0.1:8177` | mã `6c7d2ab`, `git status services/api` = 0 file đổi |
| DB | Postgres dùng chung `mobile` | 64 người / 14 nhóm |
| AI | Gemini **thật** | `GEMINI_API_KEY` đọc từ `.env` ngoài repo, không in ra đâu cả |

Bundle dựng bằng `expo export --platform web --clear`, `EXPO_PUBLIC_API_URL=http://127.0.0.1:8177`.
Bản TRƯỚC dựng trong worktree riêng tại `df3f1a1` với `node_modules` **hardlink** (`cp -al`),
không symlink — symlink làm `expo export` chết.

Đếm chuỗi để chứng minh hai bundle thật sự khác nhau, không phải cache:

| chuỗi | TRƯỚC | SAU |
|---|---|---|
| `127.0.0.1:8177` (URL tôi ghim) | 5 | 5 |
| `localhost:8099` (mặc định — phải là 0) | 0 | 0 |
| `X-Actor-ID` | 7 | **8** |
| `chua-biet-la-ai` / `bi-tu-choi` / `qua-nhieu-lan` | 0 / 0 / 0 | **2 / 2 / 2** |

## 1. Máy chủ: hợp đồng hai đầu

```
POST /places/search  không header  -> 401 {"code":"authentication_required","detail":"Missing X-Actor-ID"}
POST /places/search  có X-Actor-ID -> 200  source=ai, 2 chỗ
```

## 2. Đi bộ bằng trình duyệt thật (Chromium, khung 390×844)

Cùng một câu: `quán nướng ngoài trời cho 6 người dưới 300k`. Đăng nhập → chọn Minh →
Khám phá → gõ → Enter.

**TRƯỚC — màn hình:**

```
Máy chủ trả lỗi 401
Máy chủ từ chối yêu cầu này. Câu bạn viết không phải nguyên nhân.
Chi tiết: {"code":"authentication_required","detail":"Missing X-Actor-ID"}
Đã thử: http://127.0.0.1:8177/places/search
```

dây: `{"actorHeader":null}` → `{"status":401}`

**SAU — màn hình:** panel *AI hiểu câu của bạn* + *Kết quả cho câu của bạn — 2 chỗ*,
`AI MATCH 96%`, Tiệm Nướng Xóm Lào (~200–250k/người), Nướng Ngói Trời Thông.

dây: `{"actorHeader":"46b55e67-932b-5415-a5ee-08fb2641a4ff"}` → `{"status":200}`

Đây là phần quan trọng nhất của lượt này: **cùng máy chủ, cùng câu, chỉ khác bundle.**
Nên 401 ở trên không thể đổ cho môi trường.

## 3. Ba trạng thái mới — trạng thái nào tới được, trạng thái nào không

| trạng thái | tới được? | bằng chứng |
|---|---|---|
| `chua-biet-la-ai` | **CÓ** — nút *Bỏ qua* ở màn đầu | màn in "Chưa biết bạn là ai…", và **0 request** tới `/places/search` (đợi 12 giây, đủ để model kịp trả lời nếu có gọi) |
| `qua-nhieu-lan` | **CÓ** | bắn 13 lần thật với UUID của Minh → **12×200, 1×429**. Rồi tìm trong trình duyệt trong cùng cửa sổ 60 giây → 429, màn in "Bạn vừa tìm hơi nhiều" |
| `bi-tu-choi` (401/403) | **KHÔNG** | xem §5 |

Với `qua-nhieu-lan`, câu chữ hứa "câu bạn viết vẫn còn nguyên ở trên" — **đúng**: ảnh chụp
cho thấy ô tìm kiếm vẫn giữ nguyên câu. Và câu tiếng Anh của limiter
(`Too many searches; at most 12 per 60 seconds.`) **nằm lại trên dây**, không lên màn.

## 4. Đột biến — bản sửa có được cổng nào giữ không

Ba phép, mỗi phép hoàn nguyên đúng một nửa của #158, chạy `npm test` trong `apps/mobile`:

| đột biến | kết quả |
|---|---|
| bỏ `"X-Actor-ID": opts.actorId` khỏi headers | **ĐỎ** — 492 đạt / **1 hỏng** |
| bỏ nhánh `if (res.status === 429)` | **ĐỎ** — 492 đạt / **1 hỏng** |
| bỏ chặn `if (!opts.actorId)` | **ĐỎ** — typecheck `TS2769`, `EXIT=2` |

Đột biến thứ ba đỏ ở tầng kiểu chứ không ở tầng test: bỏ cái chặn thì `opts.actorId` thành
`string | undefined` trong headers và TypeScript từ chối. Nghĩa là cái chặn đó được **kiểu**
cưỡng chế, không chỉ được test canh — mạnh hơn một ca test.

Khôi phục xong, cây sạch trở lại (`git status apps/mobile/src` rỗng, file `diff` giống hệt
bản sao lưu), và `npm test` xanh lại 493/493.

## 5. Phát hiện — `bi-tu-choi` là trạng thái chết (suggestion, không phải blocker)

`get_actor` (`app/api/deps.py:52`) **không kiểm người có tồn tại không**. Đo thật:

```
X-Actor-ID: <UUID hợp lệ toàn số 0 — chắc chắn không phải người thật>  -> 200
X-Actor-ID: khong-phai-uuid                                            -> 422
```

(UUID toàn số 0 viết mô tả chứ không viết thẳng: repo guard chặn chuỗi 32 chữ số,
và nó chặn đúng — luật đó tồn tại để số tài khoản không lọt vào Git.)

Và `search_places` không phân quyền gì. Nên khi client đã gửi một UUID hợp lệ thì
**401/403 không thể xảy ra**; khi chưa có `actorId` thì client đã chặn từ trước và không gọi
mạng. Hệ quả: màn *"Máy chủ chưa nhận ra bạn"* hôm nay không có đường nào tới được, và chưa
ai từng nhìn thấy nó.

Không phải blocker (nó là phòng thủ cho ngày có gateway thật, và đúng theo 5 loại của
charter thì đây không thuộc loại nào). Nêu ra vì hai lý do: (a) nó là câu chữ chưa từng
được người nào đọc, (b) nếu sau này ai đó thêm kiểm tra "người này có thật không" vào
`get_actor` thì trạng thái này **lập tức sống dậy** — và lúc đó nó là đường đi chính của
mọi người dùng có personId cũ trong máy.

## 6. Cổng đầy đủ tại `6c7d2ab`, cây sạch

| lệnh | kết quả |
|---|---|
| `TZ=UTC python3 -m pytest services/api/tests tests -q` | **1165 passed, 254 skipped**, 4590 subtests |
| `cd apps/mobile && npm test` | **493 tests, 493 pass, 0 fail, 0 skipped** |

254 `skipped` là tầng `tests/postgres` (thiếu `MOBILE_TEST_DATABASE_URL` ở lượt chạy này).
**Skip không phải xanh.** Tầng đó đã chạy **0 skipped / 224 passed** ở lượt rd-qa-23 tại
đúng SHA này và main chưa nhúc nhích từ đó, nên tôi không chạy lại; con số 224 là **trích
dẫn lượt trước**, không phải đo lượt này.

## 7. Ô CHƯA quét

- **Điện thoại thật.** Mọi phép đo trên là Chromium desktop ở khung 390×844, không phải
  máy Android/iOS thật.
- **Mã QR bằng app ngân hàng thật** — vẫn còn nguyên là ô chưa quét (ADR-0010 mục 8),
  không liên quan việc này nhưng chưa ai đóng.
- **429 ở tầng nhiều replica.** Limiter nằm trong bộ nhớ mỗi tiến trình; tôi đo một
  tiến trình. Hai replica là hai cửa sổ, tức trần gấp đôi — module tự khai điều này và
  tôi **không** kiểm.
- **Cửa sổ 60 giây có tự mở lại không.** Tôi chứng minh nó đóng ở lần thứ 13; tôi
  **không** ngồi đợi 60 giây để chứng minh nó mở lại.
- `bi-tu-choi` không quét được vì không tới được (§5).

## Ghi chú cho người đo sau: đừng grep chuỗi hiển thị trong bundle

Grep `'Bạn vừa tìm hơi nhiều'` trong bundle ra **0** — và grep một chuỗi tiếng Việt *có từ
trước* (`'Câu tìm kiếm chưa dùng được'`) cũng ra **0**. Chữ tiếng Việt không nằm nguyên dạng
trong bundle. Nếu tôi dừng ở đó tôi đã kết luận nhầm là "bản sửa không lên bundle".

Cái grep được là **định danh trạng thái** (`chua-biet-la-ai`, `qua-nhieu-lan`, `bi-tu-choi`)
và tên header. Dùng chúng để đối chiếu bundle, đừng dùng câu chữ hiển thị.

## Ghi chú: lượt khác ghi vào worktree của tôi giữa chừng

Lúc 21:06 commit `2fda512` (việc F16 của rd-qa-24) xuất hiện trên `HEAD` của worktree này
trong khi tôi đang đo. Nó **không chạm mã sản phẩm** (0 file dưới `apps/mobile/src`,
`services/api/app`, `packages/`) — chỉ hai file docs và một probe QA — nên mọi phép đo ở
trên tại `6c7d2ab` vẫn đứng vững.

Tôi **không** gộp nó vào nhánh này: nhánh của tôi được dựng lại thẳng từ `6c7d2ab`, và việc
F16 còn nguyên trên nhánh `qa/rd-qa-24-f16-lich-trinh-ai` (chưa đẩy). Ai chạy lượt đó cần
biết là nó vẫn đang nằm cục bộ.

## Tái lập

```bash
# máy chủ tại đúng SHA, có AI thật
set -a && . /home/lakiet/mobile/.env && set +a
MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
  python3 -m uvicorn app.api.main:app --port 8177     # chạy trong services/api/

# bundle TRƯỚC: worktree riêng tại df3f1a1, node_modules hardlink (KHÔNG symlink)
git worktree add /tmp/qa23-before df3f1a1
cp -al apps/mobile/node_modules /tmp/qa23-before/apps/mobile/node_modules
cd /tmp/qa23-before/apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8177 \
  npx expo export --platform web --output-dir dist-qa23-before --clear

# đi bộ (cần playwright + chromium đã ghim trong script)
node tests/qa/rd-qa-25/di-bo-walk.mjs  http://127.0.0.1:8178 TRUOC
node tests/qa/rd-qa-25/di-bo-walk.mjs  http://127.0.0.1:8179 SAU
node tests/qa/rd-qa-25/di-bo-boqua.mjs http://127.0.0.1:8179 BOQUA
```

Ảnh chụp để ngoài repo (`/tmp/qa23-*.png`) — repo guard fail closed với binary.
