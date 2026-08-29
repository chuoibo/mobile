# rd-qa-33 · PASS #188 — màn mở đầu bây giờ thật sự bị chụp, và bản trước nó thật sự không

`PASS`. Lỗ hổng #188 mô tả tái lập được nguyên văn trên cùng một bundle: công cụ ở
commit cha chạy `exit 0` và ghi ra **9 file không có `mo-dau.html`**; công cụ sau
#188 ghi ra **10 file, `mo-dau.html` 30 224 byte và nội dung đúng là màn mở đầu**.
Cổng mới không phải thứ duy nhất giữ nó — gỡ đúng một dòng `snapshot()` mà vẫn giữ
tên trong `STEPS` thì cổng mới **vẫn xanh**, nhưng `di-bo-luong-chinh.test.mjs` đỏ
với đúng câu cần đọc. Ba finding `imp detect` trên `mo-dau` là thật, không phải
lỗi màn: đo trên app sống, phần bị cắt là trang trí tràn viền **đối xứng tuyệt
đối** và **không chứa chữ nào**.

- **đo tại** `2d61e39`
- **sha này** ĐÃ ở main (`2d61e39` chính là merge commit của #188)
- **bản đối chứng** `ad5e13f` — commit cha, tức trạng thái trước #188
- **protocol_version** v1 · **verdict** `PASS` · **blocker còn mở**: không có

#188 đã được merge lúc 16:13:22Z, trước khi có phán quyết này. Nó rơi đúng loại 2
trong luật Lead chốt lúc 22:49 (PR test/cổng thuần, 0 dòng sản phẩm — diff chỉ
chạm `apps/mobile/tools/` và `apps/mobile/tests/`), và Lead **có** ghi đột biến lên
PR trước khi merge. Không có gì phải kêu. Báo cáo này là soi lại trên `main`.

---

## 1. Cổng đầy đủ trên main, cây sạch

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **1278 passed, 287 skipped**, 4597 subtests, 78,84s |
| `cd apps/mobile && npm test` | **508 pass / 0 fail**, 0 skipped |

287 ca skip là tầng `tests/postgres` — thiếu `MOBILE_TEST_DATABASE_URL`. Đó là
tầng **chưa chạy**, không phải tầng xanh. Không có gì trong #188 chạm tới nó.

## 2. Lỗ hổng trước #188, tái lập trên cùng một bundle

#188 chỉ đụng `tools/` và `tests/`, nên bundle `expo export` ở `ad5e13f` và
`2d61e39` là **một**. Nên phép đối chứng sạch nhất là giữ nguyên bundle, chỉ đổi
công cụ — bất kỳ khác biệt nào còn lại là do chính PR.

```bash
git show ad5e13f:apps/mobile/tools/screen-snapshots.mjs > /tmp/qa33-tool-truoc.mjs
cp /tmp/qa33-tool-truoc.mjs apps/mobile/tools/screen-snapshots.mjs
node tools/screen-snapshots.mjs --out /tmp/qa33-truoc     # exit 0
```

| | file walk ghi ra | có `mo-dau.html`? |
|---|---|---|
| **trước** `ad5e13f` | 9 — `chup-bill` là file đầu tiên | **không** |
| **sau** `2d61e39` | 10 — `mo-dau` là file đầu tiên | có, 30 224 byte |

Bản trước thoát mã **0**. Đó chính là kiểu hỏng CLAUDE.md ghi tên: công cụ ghi
đúng những file nó biết rồi báo thành công, và một màn chưa quét trông y hệt một
màn quét sạch.

`mo-dau.html` sau #188 đúng là màn mở đầu, không phải vỏ tab:

| chuỗi | có trong file |
|---|---|
| `AI đi chơi, chia bill thông minh` (tagline) | có |
| `Bỏ qua` | có |
| `Khám phá` / `Chụp bill` / `Tạo khoản chi` | **không** — chưa sang màn sau |
| `<script>` còn sót | 0 |
| `<style>` (CSS runtime của rnw) | 1 |

## 3. Cổng mới giữ được cái gì, và cái gì giữ nó

Đột biến quan trọng nhất không phải cái Lead đã chạy. Lead gỡ `mo-dau` khỏi
`STEPS` **và** gỡ waypoint — bốn ca đỏ. Nhưng đường quay lại lỗi cũ rẻ hơn thế
nhiều: **giữ nguyên cả hai cái tên, chỉ gỡ đúng một dòng `await snapshot(...)`**.

```
đột biến: xoá `await snapshot(page, outDir, step);` ngay sau waypoint mo-dau
  tests/di-qua-hay-chup.test.mjs   ->  3 pass / 0 fail   (XANH — mù với ca này)
  npm test (cả bộ)                 ->  506 pass / 2 fail
```

Hai ca đỏ đến từ `tests/di-bo-luong-chinh.test.mjs`, và câu chữ của nó đúng chỗ:

```
not ok 129 - đi bộ hết luồng chia tiền, từ chụp bill tới trang khách
not ok 130 - mỗi màn của luồng để lại một file quét được
  error: 'màn "mo-dau" không được viết ra. Chưa quét và quét sạch trông giống
          hệt nhau, nên đây là đỏ.'
```

Kết luận đọc cho đúng: `di-qua-hay-chup.test.mjs` **không** là cổng giữ màn
mo-dau. Nó là cổng bắt **khai ý định** — thêm chặng thì phải quyết định. Cổng thật
sự đòi file là `di-bo-luong-chinh.test.mjs`, đã có từ trước, và nó tự bám theo
`STEPS` nên #188 đưa `mo-dau` vào `STEPS` là đủ để nó được gác. Hai cổng ăn khớp;
chỉ đừng đọc cái đầu thành cái thứ hai.

### Một lỗ còn hở ở cổng mới — suggestion, không phải blocker

`changTrongWalk()` bắt chặng bằng `/\bstep = "([^"]+)"/g`, chỉ nhận **nháy kép**.

```
đột biến: thêm  step = 'man-moi-chua-ai-quet';  vào thân drive(), không khai đâu cả
  tests/di-qua-hay-chup.test.mjs  ->  3 pass / 0 fail   (XANH)
```

Và không có gì chuẩn hoá kiểu nháy: `apps/mobile` lẫn gốc repo đều **không có**
`.prettierrc` hay cấu hình eslint nào. Một màn mới thêm bằng nháy đơn sẽ vô hình
với cả hai cổng — `di-bo-luong-chinh` chỉ duyệt `STEPS`/`EXTRA`, nên nó cũng không
biết chặng đó tồn tại. Đúng họ lỗi #188 sinh ra để đóng, mở lại bằng một dấu nháy.

Không phải blocker (không thuộc 5 loại: không chạm spec đang chạy, không chạm
tiền, không chạm riêng tư, không hỏng tính hợp lệ thí nghiệm, tái lập được).
Sửa một dòng — cho lớp ký tự nhận cả ba kiểu nháy thay vì chỉ nháy kép:

```js
const rows = [...than[1].matchAll(/\bstep\s*=\s*["'`]([^"'`]+)["'`]/g)].map((m) => m[1]);
```

## 4. Ba finding trên `mo-dau` — số đo khớp, lời giải thích thì không hẳn

Chạy lại đúng như PR mô tả, hai canary mỗi lượt (bắt buộc, quét theo **file**):

| | finding | exit |
|---|---|---|
| canary **xấu** (`tests/qa/rd-qa-21/canary-xau.html`) | 1, có số đo thật `1.2:1 — text #eeeeee on #ffffff` | **2** |
| canary **sạch** | 0 | 0 |
| `mo-dau.html` | **3** | **2** |

Ba finding trùng khít PR: `body clips a positioned child`,
`div.css-g5y9jx.r-633pao clips a positioned child`, `Primary font: roboto`.

PR gọi cả ba là "nhiễu đã biết của phép đo". Quét cả 10 màn của walk cho thấy
điều đó **chỉ đúng với một trong ba**:

| rule | có ở mấy màn / 10 |
|---|---|
| `Primary font: roboto` | **10/10** — nhiễu hệ thống, đúng như PR nói |
| `children flush again` (css-g5y9jx) | 4/10 |
| `clips a positioned child` | **1/10 — chỉ mo-dau** |

Một finding chỉ xuất hiện ở đúng màn đang xét thì không thể gọi là nhiễu của
phép đo bằng lập luận "màn nào cũng có". Nên tôi đo thẳng trên **app sống**,
scripts còn nguyên, thay vì tranh luận trên file đã gỡ script —
`tests/qa/rd-qa-33/do-mo-dau-song.mjs`:

```
390x844 -> 3 phần tử bị cắt, chữ bên trong: ['', '', '']
    div.css-g5y9jx.r-633pao  {trai: 55, phai: 55}  hộp 499x95
    div.css-g5y9jx.r-633pao  {trai: 35, phai: 35}  hộp 460x88
    div.css-g5y9jx.r-633pao  {trai: 31, phai: 31}  hộp 452x304
320x568 -> 3 phần tử bị cắt, chữ bên trong: ['', '', '']
    div.css-g5y9jx.r-633pao  {trai: 45, phai: 45}  hộp 410x95
    ...
```

Tràn **đối xứng tuyệt đối** hai bên, ở cả hai khung nhìn, và **không phần tử nào
chứa chữ**. Đó là trang trí tràn viền có chủ đích (mặt trời, dải đồi, đèn lồng —
xem ảnh chụp), không phải nội dung bị mất. Kết luận của PR — không có lỗi thật
trên màn này — **đứng vững**; chỉ lý do là khác: không phải "phép đo bịa ra", mà
"cắt thật nhưng cắt đúng thứ được phép cắt".

Script tự chứng minh nó đỏ được, không chỉ xanh được:

```
node tests/qa/rd-qa-33/do-mo-dau-song.mjs --canary   -> exit 2
    conChu: "CANARY: chu nay bi cat mat mot ben", biCat: {trai: 140}
node tests/qa/rd-qa-33/do-mo-dau-song.mjs            -> exit 0
    "khong co chu nao bi cat tren mo-dau"
```

## 5. Đi bộ như người dùng — 390×844 và 320×568

Ảnh ở `/tmp/rd-qa-33-mo-dau-390.png` và `/tmp/rd-qa-33-mo-dau-320.png` (không vào
git: ảnh là binary, repo guard fail closed, và ADR-0010 mục 6.5).

Cả hai khung nhìn: bố cục giữ, không tràn chữ, không cắt nội dung, tiếng Việt có
dấu đọc được, ba nút đăng nhập và câu giải thích "vỏ" đều hiện đủ. `docH == winH`
ở 390 — không có thanh cuộn ngoài ý muốn.

Một thứ nhìn thấy khi đi bộ, **không phải lỗi của #188**: câu cuối màn mở đầu
mang dấu gạch dài — "Google và Apple chưa nối thật **—** bấm vào sẽ mở danh sách
Team Đà Lạt...". Trên `main` hiện **không có cổng em-dash nào** (đã grep
`apps/mobile/tests/`). Cổng đó nằm ở **#162**, đang mở, đã có phán quyết `FAIL`
của tôi ở rd-qa-29 với ghi chú là nửa cổng đáng lấy. Đây là dữ liệu cho #162 chứ
không phải phiếu lỗi mới: nếu cổng em-dash được lấy, nó phải phủ cả `MoDau` —
màn đầu tiên người dùng thấy.

## 6. Ô CHƯA quét

- `vao-app` và `menu-tao` — khai `PASS_THROUGH` trong #188, tức **vẫn chưa được
  đo lần nào**. Lời khai là ghi nhận chỗ trống, không phải bác bỏ nó.
- Chủ đề **tối** của `mo-dau`: chưa quét. Cả hai lượt trên đều ở chủ đề sáng.
- Khung nhìn 1440 (web): chưa quét cho màn này.
- Trình đọc màn hình / điều hướng bàn phím trên `MoDau`: chưa quét ở lượt này.
- Nút "Đăng ký với Google" / "Apple" là **vỏ** theo đúng lời màn hình tự khai;
  không kiểm hành vi đăng nhập thật.
- Tầng `tests/postgres`: 287 ca skip, chưa chạy ở lượt này.
- **Mã VietQR chưa được quét bằng app ngân hàng thật.** Không agent nào đóng được
  câu này; cần leader và một điện thoại.

## 7. Lệnh chạy lại được

```bash
git checkout 2d61e39
python3 -m pytest services/api/tests tests -q
cd apps/mobile && npm test
export PUPPETEER_EXECUTABLE_PATH=/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome
node tools/screen-snapshots.mjs --out /tmp/walk          # phai co mo-dau.html
node ../../tests/qa/rd-qa-33/do-mo-dau-song.mjs --canary # exit 2
node ../../tests/qa/rd-qa-33/do-mo-dau-song.mjs          # exit 0
~/.claude/skills/impeccable-pipeline/scripts/imp detect --json /tmp/walk/mo-dau.html
```

Kỹ năng đã dùng: `e2e-testing` (chặng 2 cổng rẻ, chặng 5 nhìn bằng mắt, chặng 7
kết luận + ô chưa quét), `bug-reproduction` (tái lập bản trước bằng công cụ ở
commit cha trên cùng bundle; đột biến gỡ `snapshot()` để kiểm cổng nào thật sự
đỏ; canary chứng minh script đo đỏ được).
