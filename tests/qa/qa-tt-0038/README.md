# Phán quyết QA — PR #348 (F38 màn widget, `rd-fe-38`)

**FAIL.**

Lý do, viết trước phần chi tiết: **#348 thêm hai module trong cùng một thư mục chỉ
khác nhau chữ hoa thường** — `src/screens/widget/Widget.tsx` và
`src/screens/widget/widget.ts`. Trên macOS hoặc Windows đó là **một** đường dẫn, nên
clone hỏng trước khi có compiler nào chạy; trên máy này `tsc --noEmit` từ chối cặp đó
bằng `TS1149` và thoát mã 2. Đây đúng hình dạng lỗi mà #353 vừa vá cho main
(`Tuong.tsx` / `tuong.ts`) và #348 dựng lại nó với một cặp tên khác.

Bản thân **màn hình thì đạt**: nó vẽ được, ảnh giải mã thật, không tràn ngang, không
cắt chữ ở 320/360/390. Chỉ có tên file chặn merge, và tiêu chí gỡ chặn đã được đo.

## Đo tại đâu

| | |
|---|---|
| Nhánh PR | `frontend/rd-fe-38-man-widget` @ `cdb38f5` |
| Cây đã đo | **cây gộp** `cdb38f5` ⊕ `origin/main@2489284` = `617152b` (merge sạch, không xung đột) |
| SHA này | là nhánh **chưa merge** — `merge-base --is-ancestor origin/main HEAD` trả "SAU main" cho `cdb38f5` |
| Đối chứng | `origin/main@2489284` trong worktree sạch riêng (`git worktree add /tmp/base348`) |

Lý do phải đo trên cây gộp chứ không phải trên đầu nhánh: #348 cắt trước #353 sáu
commit, và **cổng bắt được lỗi này chỉ tồn tại trên main**. Xem mục "vì sao tác giả
không thấy" bên dưới.

## Phát hiện — chặn merge

**Loại blocker: vi phạm spec/cổng** (charter mục 5 loại). Cây gộp làm main đỏ.

```
apps/mobile/src/screens/widget/Widget.tsx
apps/mobile/src/screens/widget/widget.ts
```

`tsc --noEmit` trên cây gộp:

```
tests/widget.test.mjs(189,29): error TS1149: File name
  '.../dist-test/screens/widget/Widget.js' differs from already included file
  name '.../dist-test/screens/widget/widget.js' only in casing.
  Imported via "../dist-test/screens/widget/widget.js" from tests/widget.test.mjs
  Imported via "./widget.js" from dist-test/screens/widget/Widget.js
  Imported via "../dist-test/screens/widget/Widget.js" from tests/widget.test.mjs
TSC_EXIT=2
```

Chính `tests/widget.test.mjs` của PR nạp **cả hai** kiểu chữ — dòng 26 và 97 lấy
`widget.js`, dòng 189 lấy `Widget.js`. Nên đây không phải một cặp nằm im: nó được
kéo vào cùng một program.

Hậu quả: không phải chuyện thẩm mỹ tên file. Trên filesystem không phân biệt hoa
thường (macOS mặc định, Windows), hai file này là một — người checkout ra được một
bản cây **thiếu một trong hai module**, và lỗi xuất hiện ở chỗ không liên quan gì
tới widget.

## Đối chứng hai chiều

Bắt buộc, vì worktree của tôi có 20 thư mục `dist-qa*` chưa track của chính tôi và
chúng là nguồn đỏ giả đã biết. Nếu không chạy chiều "trước" thì con số đỏ này không
quy được cho ai.

| Cây | `apps/mobile/tests/ten-module-trung-chu-hoa.test.mjs` |
|---|---|
| `origin/main@2489284` sạch (`/tmp/base348`, không có `dist-qa*`) | **2 pass / 0 fail** |
| Cây gộp `617152b` (#348 ⊕ main) | **2 fail** — cả hai ca |
| Cây gộp + đổi tên một file | **2 pass / 0 fail** |

Chiều "trước" xanh là thứ biến "cây gộp đỏ" thành "**#348** làm đỏ", chứ không phải
"máy tôi bẩn" hay "main đang đỏ sẵn".

`origin/main` không có file nào dưới `apps/mobile/src/screens/widget/`
(`git ls-tree -r origin/main` trả rỗng) — cả hai file đến từ #348.

## Vì sao tác giả không thấy, và vì sao đó không phải lỗi của họ

Cổng bắt lỗi này — `apps/mobile/tests/ten-module-trung-chu-hoa.test.mjs` — **không
tồn tại trên nhánh #348**:

```
git ls-tree -r --name-only cdb38f5 -- apps/mobile/tests/ten-module-trung-chu-hoa.test.mjs
(rỗng)
```

Nó lên main ở #353, **sau** khi #348 được cắt. Nên `npm test` của tác giả trên nhánh
của họ xanh thật, và Git không báo xung đột nào: hai PR không đụng chung một dòng
nào. Đây là hình dạng "hai PR không xung đột vẫn làm main đỏ" — thứ duy nhất nhìn ra
được là chạy cổng trên **cây gộp**, không phải trên đầu nhánh.

## Tiêu chí gỡ chặn — đã đo, không phải đề xuất suông

Đổi tên một trong hai file cho khác nhau nhiều hơn một chữ cái hoa, rồi sửa hai chỗ
nạp nó. Tôi đã làm thử trong cây nháp (không commit lên nhánh của #348) để chứng minh
đây là toàn bộ việc phải làm:

1. `src/screens/widget/widget.ts` → `src/screens/widget/widget-du-lieu.ts`
2. `Widget.tsx:63` — `from "./widget"` → `from "./widget-du-lieu"`
3. `tests/widget.test.mjs` dòng 26 + 97 — `screens/widget/widget.js` → `screens/widget/widget-du-lieu.js`

Kết quả sau đúng ba sửa đó, trên cây gộp:

```
node --test tests/ten-module-trung-chu-hoa.test.mjs   ->  2 pass / 0 fail
npm test                                              ->  783 pass / 0 fail
```

**783/783.** Không có ca đỏ nào khác nấp sau hai ca này — nên đây là blocker duy nhất
của PR, và sửa xong là hết.

Tên `widget-du-lieu` chỉ là tên tôi dùng để đo. Tác giả chọn tên nào cũng được, miễn
không chỉ khác nhau chữ hoa thường.

## Màn hình thì đạt — `di-bo-widget.mjs`

Hai câu mà các tầng assert trong `apps/mobile/tests/widget.test.mjs` không với tới,
vì cả hai nói về **cái được vẽ ra** chứ không phải cây phần tử. Chạy trên cây gộp
**đã áp bản đổi tên** (tức trạng thái tác giả sắp đẩy):

```
  dat   vw=320  anh giai ma=1  le trai/phai=16/16  tran=khong  tac gia=co  caption=co
  dat   vw=360  anh giai ma=1  le trai/phai=16/16  tran=khong  tac gia=co  caption=co
  dat   vw=390  anh giai ma=1  le trai/phai=16/16  tran=khong  tac gia=co  caption=co
DAT: man widget ve duoc o 320/360/390, khong tran, khong cat
```

Hai chỗ phép đo này cố ý không đi đường dễ:

- **`naturalWidth > 0`, không phải "có thẻ `<img>`".** Một tấm ảnh hỏng vẫn có hộp
  layout và vẫn trả về một rectangle. Chỉ `naturalWidth` mới nói byte đã giải mã.
  `anh giai ma=1` là khẳng định **dương** — nó biến ba chữ "khong tran" phía sau
  thành phép đo thật chứ không phải một trang trắng đang im lặng.
- **Tràn ngang đo bằng `scrollWidth` vs `clientWidth` + rectangle của thẻ, không đo
  bằng mắt trên ảnh chụp.** Khung là `width: "100%"` + `aspectRatio: 1` trong một
  scroller có padding — đúng công thức thường đẩy một khung vuông quá mép phải ở
  320pt. Ảnh chụp ở 320 **trông** sát mép vì lề phải rơi ra ngoài góc bo, và đọc một
  defect ra từ tấm ảnh đó là cách nộp một finding giả. Số đo nói: lề 16/16 đối xứng,
  `scrollW == vw`.
- Mỗi khung nhìn đi qua `about:blank` trước. Đổi mỗi fragment thì màn không remount,
  và khung sau sẽ bị đo trên layout của khung trước.

## Ô CHƯA quét — phần quan trọng nhất của báo cáo này

- **`npm run test:e2e`** (lát cắt dọc thật qua uvicorn + Postgres): **chưa chạy** lượt
  này. #348 là màn client và không đụng route, nhưng tôi không đo nên không nói nó xanh.
- **`tests/postgres`**: **chưa chạy** với `MOBILE_REQUIRE_POSTGRES_TESTS=1`. Cổng
  backend lượt này in `551 skipped` và **skipped không phải xanh**. #348 không có
  migration nào nên tôi không coi đây là rủi ro, nhưng nó vẫn là ô trống.
- **Widget trên máy thật, cạnh màn khoá** — nơi tính năng này thực sự sống. Không
  quét được bằng bất cứ thứ gì trong repo.
- **Chủ đề tối** và **trình đọc màn hình** trên màn này: chưa quét.
- **Trạng thái `photo: null`** (một 200 hợp lệ, không phải lỗi): mới có assert cây
  phần tử, tôi **chưa** nhìn nó được vẽ ra.
- Mã QR quét bằng app ngân hàng thật: vẫn nguyên là ô chưa quét của cả sản phẩm.

## Cách chạy lại

```bash
git checkout -B kiem-348 cdb38f5 && git merge --no-edit origin/main
python3 -m pytest services/api/tests tests -q
cd apps/mobile && npm test

# màn hình, sau khi đã đổi tên file:
cd apps/mobile && npm run build:check
PUPPETEER_EXECUTABLE_PATH=<chrome> node ../../tests/qa/qa-tt-0038/di-bo-widget.mjs
```

Cổng backend trên cây gộp, để so: `2583 passed, 551 skipped, 4902 subtests passed`
trong 226.67s — xanh, không bị #348 chạm tới.
