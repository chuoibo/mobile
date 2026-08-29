# rd-qa-29 · Đối chứng PR #162 (rd-fe-18 + rd-fe-19)

`FAIL` — nhưng đọc tiếp, phần lớn PR này ĐÚNG và ĐÁNG lấy.

**Lý do FAIL, một câu:** commit thứ hai (`128df69`) đã bị `#176` làm trước và `#176`
đã vào `main` lúc 15:20, nên `#162` giờ **xung đột thật ở 3 file** và không merge
được; commit thứ nhất (`2a8eaf4`, cổng em-dash) thì **không** xung đột, tôi đã
cherry-pick lên `main` hiện tại và chạy cổng đầy đủ: **506/506 pass**.

Đây không phải lỗi của tác giả `#162`. Hai nhánh sửa cùng một câu chữ, viết ra hai
câu khác nhau, và nhánh kia về đích trước.

## Đo tại đâu

```
128df697  head PR #162 — nhánh CHƯA merge, rẽ khỏi main tại 6c7d2ab
f995873   main lúc tôi bắt đầu đo   (đã hết hạn giữa lượt)
ab458d9   main lúc tôi kết thúc     (đã nuốt #175 #164 #173 #176)
47ca911   main@ab458d9 ⊕ cherry-pick 2a8eaf4  <- hiện vật tôi đề nghị lấy
```

Bốn worktree sạch riêng, đã gỡ sau khi xong. `main` đổi **hai lần** giữa lượt đo
này; mọi số dưới đây ghi rõ nó đứng trên cây nào.

## Phần ĐẠT — cổng em-dash (`2a8eaf4`) không phải đồ trang trí

Tôi không tin mô tả PR, tôi tự dựng ma trận đột biến. Bảy phép, chạy trên cây sạch:

| # | Đột biến | Mong đợi | Thật |
|---|---|---|---|
| M1 | em-dash vào chuỗi literal (`src/assignment.ts`) | ĐỎ | **ĐỎ** exit=1 |
| M2 | em-dash vào JSX text (`src/navigation/MenuTao.tsx`) | ĐỎ | **ĐỎ** exit=1 |
| M3 | em-dash vào mảnh template (`` `Đã nhận diện — ${read} món` ``) | ĐỎ | **ĐỎ** exit=1 |
| M4 | em-dash vào `a11yLabel` tab Khám phá (`src/navigation/tabs.ts`) | ĐỎ | **ĐỎ** exit=1 |
| M5 | em-dash vào **chú thích tiếng Anh** | XANH (không dương tính giả) | **XANH** exit=0 |
| B1 | làm mù phép quét (glob `.tsx?` hỏng) | ĐỎ | **ĐỎ** `chỉ thấy 0 file nguồn` |
| B2 | thôi thu chuỗi literal khỏi AST | ĐỎ | **ĐỎ** ca fixture bắt |

M5 là phép quan trọng nhất và là thứ mô tả PR không nhắc: cổng này quét **bằng AST**
chứ không grep, nên nó phân biệt được `— ` trong docstring tiếng Anh với `—` trong
câu người dùng đọc. Một cổng grep sẽ hoặc sai hoặc phải tắt.

B1/B2 là lý do tôi tin số 0 của nó. Cổng quét mã nguồn chết theo một kiểu rất im
lặng: phép quét đọc phải 0 file rồi báo "0 vi phạm", và "0" đó trông y hệt "sạch".
Hai ca tự kiểm trong chính file test bắt được cả hai đường chết.

**Số thật, đo bằng chính bộ thu của cổng, trên `src/` (82 file, 5736 đoạn chữ):**

```
main@ab458d9 (HÔM NAY, chưa vá)   22 em-dash trong 13 file
main ⊕ 2a8eaf4 (47ca911)           0 em-dash trong  0 file
```

22 chỗ đó vẫn còn nguyên trên `main` lúc tôi viết dòng này. Bốn trong số đó là
`a11yLabel` của cả bốn tab, tức câu trình đọc màn hình đọc lên:

```
navigation/tabs.ts:42  Khám phá — gợi ý chỗ đi cho nhóm
navigation/tabs.ts:52  Lên plan — chuyến đi của nhóm
navigation/tabs.ts:58  Tin nhắn — chat nhóm và AI
navigation/tabs.ts:64  Cá nhân — hồ sơ và tài chính của bạn
```

Cổng đầy đủ trên hiện vật `47ca911` (main hôm nay ⊕ đúng commit này, không gì khác):

```
cd apps/mobile && npm test      506/506 pass, 0 fail, 0 skipped
npx tsc --noEmit                exit 0
```

**Sai lệch nhỏ trong mô tả PR:** nói "22 chỗ trong 12 file", tôi đếm 22 chỗ trong
**13** file. Con số 22 đúng; số file lệch 1. Không phải blocker, chỉ ghi cho khớp sổ.

## Phần ĐẠT — lỗi rd-fe-19 CÓ THẬT, và tôi tái lập được trên sản phẩm đã render

Đây không phải đọc mã nguồn. Tôi dựng bundle web của **cả hai cây**, mở bằng
Chrome thật ở khung 390×844 (kích thước điện thoại), rồi đi bộ đúng đường người
dùng đi: `Bỏ qua vào app` → `Tạo mới` → `Tạo khoản chi` → chọn ảnh bill →
`Tiếp tục` → dừng ở "Gợi ý chia theo người" **khi chưa thêm ai**. Đó là đúng
khoảnh khắc câu chặn hiện ra.

```
main (trước sửa)
  câu hiện ra    "Chưa có ai trong nhóm. Thêm người bằng nút + ở trên."
  số nút "+"     0
  nút thật đang mở  Thêm Minh vào nhóm | Thêm Trang vào nhóm | Thêm Hải vào nhóm
                    Thêm Ngọc… | Thêm Đức… | Thêm Linh… | Thêm Quân vào nhóm

merge #162
  câu hiện ra    "Chưa có ai trong nhóm. Chọn người đã ăn bữa này ở danh sách trên."
  số nút "+"     0
  nút thật đang mở  (y hệt trên)
```

Ảnh chụp cả hai xác nhận bằng mắt: **không có nút `+` nào trên màn**, trong khi
danh sách chip chọn người ("Ai đã ăn bữa này? Chọn trong nhóm.") mở sẵn ngay đầu
màn. Câu cũ chỉ người dùng đi tìm một cái nút không tồn tại. Lỗi có thật.

Ba đột biến trên cổng `cau-chan-tro-dung-nut.test.mjs`:

| # | Đột biến | Thật |
|---|---|---|
| M7 | **trả câu cũ về** (`Thêm người bằng nút + ở trên.`) | **ĐỎ** — đỏ cả ca 1 lẫn ca 2 |
| M8 | câu mới trung tính, không trỏ vào đâu (`Thử lại sau nhé.`) | **ĐỎ** ca 2 |
| M9 | **gỡ nút chọn người khỏi màn**, giữ nguyên câu chữ | **ĐỎ** ca 2 |

M9 là phép chứng minh cổng này bắc cầu **markup ↔ markup** chứ không ghim chuỗi:
câu chữ không đổi một ký tự mà vẫn đỏ, vì thứ nó trỏ tới biến mất.

## Phần ĐẠT — `screen-snapshots.mjs` thật sự đi lại được

Mô tả PR nói dev tool này chết từ `#113` và không ca test nào chạy nó. Tôi giữ
**cùng một bundle** rồi đổi **dụng cụ đo**:

```
bản tool trên main   exit=1  2/9 file   TimeoutError ở clickAria → addPersonOnMatrix
bản tool của #162    exit=0  9/9 file
```

9 file nội dung **khác nhau đôi một** (0 cặp trùng), nên không phải 9 bản chụp của
cùng màn camera — đúng kiểu chết mà chính docstring của file cảnh báo.

Màn mới `ket-qua-thanh-toan` là màn QR thật, không phải trạng thái từ chối:

```
Tổng hoá đơn 480.000đ · 3 món · 3 người
Minh đã ứng tiền 160.000đ | Trang 160.000đ | Hải 160.000đ
Trang trả cho Minh 160.000đ | Hải trả cho Minh 160.000đ
Quét để thanh toán · VIETQR · NAPAS 247 · Minh •••• 8888 VietinBank
```

Ba luật tiền giữ trên chính màn đã render: `160.000 × 3 = 480.000` (luật 2), số
nguyên đồng (luật 1), và người ứng tiền **không tự nợ mình** — Minh không có dòng
"trả cho" nào. Mã QR vẽ bằng 596 `<div>`, không phải `<svg>`; **chưa ai quét nó
bằng app ngân hàng thật.**

## Vì sao vẫn FAIL: `128df69` đã bị `#176` làm trước

`#176` (rd-fe-22) merge vào `main` lúc **15:20**, đúng lúc tôi đang đo `#162`. Nó
sửa **cùng một câu chặn**, bằng một câu khác:

```
main (#176)   "Chưa chọn ai đã ăn bữa này. Chạm tên người trong danh sách nhóm ở trên."
PR  (#162)    "Chưa có ai trong nhóm. Chọn người đã ăn bữa này ở danh sách trên."
```

Hai cách hiện thực cho **một lỗi**. Hệ quả đo được:

```
git merge 128df697 vào main@ab458d9
  CONFLICT (content) apps/mobile/src/assignment.ts
  CONFLICT (content) apps/mobile/tests/assignment.test.mjs
  CONFLICT (content) apps/mobile/tools/screen-snapshots.mjs
gh pr view 162 → mergeable: CONFLICTING, mergeStateStatus: DIRTY
```

Và `main` đã có sẵn phần còn lại của `128df69`:

- `tools/screen-snapshots.mjs` trên main **đã có** bước `ket-qua-thanh-toan`;
- `tests/di-bo-luong-chinh.test.mjs` trên main **đã gác** câu chặn
  (`!html.includes("Chưa chọn ai đã ăn bữa này")`) và nhãn `Mã VietQR`.

Nên `128df69` giờ là công đã trả rồi. Gộp nó vào sẽ **ghi đè câu của `#176`** bằng
câu của `#162` — không phải vì câu nào hay hơn, mà vì ai giải xung đột cuối.

## Tiêu chí gỡ chặn — tôi đã chạy sẵn, chỉ cần làm lại

```bash
git checkout -b frontend/rd-fe-18-cong-em-dash origin/main
git cherry-pick 2a8eaf44          # sạch, không xung đột
cd apps/mobile && npm test        # 506/506 (tôi đã chạy: 47ca911)
```

Bỏ hẳn `128df69`. Nếu tác giả thấy câu của `#162` tốt hơn câu của `#176` thì đó là
một PR câu chữ riêng, một dòng, để người ta so hai câu chứ không phải so hai diff.

## Phát hiện — cổng em-dash mù với `App.tsx`

Không phải blocker (không thuộc 5 loại của charter, và trạng thái hiện tại sạch),
nhưng nó ăn thẳng vào lý do cổng này tồn tại.

`sourceFiles()` chỉ đi cây `apps/mobile/src`. `App.tsx` nằm **ngoài** cây đó, và nó
không nhỏ:

```
App.tsx    206 đoạn chữ · 24 đoạn có dấu tiếng Việt · 0 em-dash
index.ts     2 đoạn chữ ·  0 ·                        0
```

Đột biến B3: nhét em-dash vào một chuỗi tiếng Việt người dùng đọc trong `App.tsx`
(`"Tạo khoản chi"`) → cổng **XANH, exit=0**. Cùng loại chữ, cùng loại file, cổng
không thấy.

Hôm nay nó chưa sai, nên cổng không nói dối. Nhưng đây đúng là đường trôi mà file
test tự nhận nó sinh ra để chặn. Sửa rẻ: cho `sourceFiles` nhận thêm `App.tsx` và
`index.ts` ở gốc `apps/mobile`, hoặc đổi gốc quét lên một cấp và loại trừ
`node_modules`/`dist*`/`tools`.

## Quan sát, KHÔNG phải lỗi

Ảnh chụp cho thấy bảng món trên bản merge trông rỗng trong khi bản main còn thấy
dòng "Lẩu thái 280.000". Tôi **không** nộp cái này thành phiếu lỗi, vì đo bằng DOM
thì cả ba món đều có mặt ở cả hai cây, hai lượt chạy, kết quả y hệt:

```
MAIN  lần 1,2   3/3 món trên DOM   hộp cuộn clientHeight=179 scrollHeight=326
MERGE lần 1,2   3/3 món trên DOM   hộp cuộn clientHeight=164 scrollHeight=326
```

Câu chặn mới dài hơn nên xuống hai dòng, ăn mất 15px chiều cao của hộp cuộn bảng
món, đẩy dòng đầu xuống dưới mép nhìn thấy của hộp. Nội dung còn nguyên và cuộn
được. Đây là dương tính giả kinh điển của phép đo ảnh trên vùng cuộn — đo hộp chứa
trước, rồi mới kết luận.

## Ô CHƯA quét

Phần này quan trọng ngang phần trên.

| Ô | Trạng thái |
|---|---|
| `tests/postgres` | **chưa chạy** — 264 skipped. `#162` không chạm file backend nào, nên ngoài phạm vi, nhưng vẫn là chưa chạy |
| `npm run test:e2e` (lát cắt dọc có server + DB thật) | **chưa chạy** |
| 4 câu chặn còn lại (món chưa ai nhận, món 0đ, …) | **chưa quét** — cổng mới cố ý không phủ, tôi cũng chưa kiểm chúng trỏ đúng chỗ |
| iOS / Android thật | **chưa quét** — chỉ đo bundle web |
| Chủ đề tối, khung 320 và 1440 | **chưa quét** — chỉ 390×844 sáng |
| `imp detect` trên 9 màn | **chưa tự chạy lượt này** — số trong mô tả PR là của tác giả, tôi không đối chứng canary |
| Trình đọc màn hình đọc `a11yLabel` mới | **chưa quét** — tôi đọc chuỗi, không nghe máy đọc |
| **Mã VietQR quét được bằng app ngân hàng thật** | **chưa quét** — chỉ leader trả lời được, bằng điện thoại thật |

Và câu không được bỏ: repo này **chưa có bằng chứng hành vi nào** (ADR-0006). Bộ
test xanh nói code làm đúng điều tác giả nghĩ; nó không nói người thật hiểu sản phẩm.

## Lệnh đã chạy

```
python3 -m pytest services/api/tests tests -q      1198 passed, 264 skipped, 4591 subtests   (main@f995873 ⊕ #162)
python3 scripts/repo_guard.py tree HEAD            passed, 611 file scan(s)
cd apps/mobile && npm test                         504/504   (main@f995873 ⊕ #162)
cd apps/mobile && npm test                         506/506   (main@ab458d9 ⊕ 2a8eaf4 = 47ca911)
npx tsc --noEmit                                   exit 0    (cả hai cây)
node --test tests/dau-gach-dai.test.mjs            3/3 · 7 đột biến: 6 ĐỎ đúng chỗ, 1 XANH đúng chỗ
node --test tests/cau-chan-tro-dung-nut.test.mjs   3/3 · 3 đột biến ĐỎ
node tools/screen-snapshots.mjs                    bản #162 exit=0 9/9 · bản main exit=1 2/9
đi bộ trình duyệt 390×844                          2 bundle × 1 lượt + 2 bundle × 2 lượt đo DOM
```
