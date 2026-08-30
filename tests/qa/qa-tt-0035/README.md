# qa-tt-0035 — Bốn màn hero qua kiểm hình ảnh thật

Đo tại `main` **7439b1d**, nhánh `qa/qa-tt-0035-kiem-hinh-anh-bon-man-hero`.
Bốn màn: `chup-bill` → `ket-qua` → `goi-y` → `ket-qua-thanh-toan`
(ChupBill → KetQuaNhanDien → GoiYChia → KetQuaThanhToan).

Ảnh chụp là **ảnh màn thật** (`page.screenshot` trên trang đã render), không phải
ảnh chụp DOM. `screen-snapshots.mjs` ghi HTML tuần tự hoá và tự nó nói rõ đó
không phải bản quét; bài học "Ảnh chụp DOM tạo finding giả" là lý do không dùng
đường đó ở đây.

## Vì sao bốn màn này chưa từng qua kiểm hình ảnh

Hai đường đo có sẵn hụt nhau **đúng ở bốn màn này**, và mỗi cái tự khai chỗ mù
của mình:

| Công cụ | Tới được bốn màn? | Lấy mẫu pixel ảnh? |
|---|---|---|
| `imp detect` qua `quet-man-sau-tap.mjs` | **có** (trang tự lái) | **không** — tính tương phản theo nền CSS |
| `soi-tuong-phan-anh.mjs` | **không** — điều hướng `#${man.frag}`, bốn màn này không có fragment | **có** |

Nên công cụ tới được thì không lấy mẫu pixel, công cụ lấy mẫu pixel thì không
tới được. `anh-bon-man-hero.mjs` nối hai cái đã có chứ không dựng máy quét thứ ba.

Con số chứng minh chỗ mù là có thật, không phải suy đoán: `soi-tuong-phan-anh.mjs`
ghi lại rằng dẹp `Scrim` về `[0,0,0]` — chữ nằm trên ảnh gần trắng, không có gì
chắn — mà quét URL vẫn ra `kham-pha findings= 0`.

## Kết quả trên cây sạch

```
chup-bill            tương phản tệ nhất 6.25:1   điểm chạm 0 dưới 44   tràn 0   che 0
ket-qua              tương phản tệ nhất 4.83:1   điểm chạm 3 dưới 44   tràn 0   che 0
goi-y                tương phản tệ nhất 4.55:1   điểm chạm 0 dưới 44   tràn 0   che 0
ket-qua-thanh-toan   tương phản tệ nhất 4.52:1   điểm chạm 0 dưới 44   tràn 0   che 0
                     VietQR: OpenCV giải lại ĐÚNG 102 ký tự payload TỪ ẢNH CHỤP
TỔNG: 4 phát hiện
```

## Bốn phát hiện

### PH-1 — Ba nút xoá món 28×44, và `hitSlop` không có tác dụng trên web
**Màn:** `ket-qua` (KetQuaNhanDien) · **Lane:** frontend · **Không phải blocker**

Ba nút `Xoá món ...` đo được **28×44** ở 390×844. Dưới 44 của Apple HIG (Android
xin 48dp); **đạt** WCAG 2.2 AA 2.5.8 vì mốc đó chỉ là 24×24.

Nguồn nói ngược lại, và đó mới là phần đáng báo. `KetQuaNhanDien.tsx:291-293`:

```
// Visually 28pt so the name column can have the space,
// but `hitSlop` keeps the touch target at 44.
hitSlop={DELETE_SLOP}          // { top: 8, bottom: 8, left: 8, right: 8 }
```

Câu đó đúng trên native và **sai trên web**. Đo bằng `tools/soi-hitslop.mjs`
(hit-test thật bằng `elementFromPoint`, không đọc thư viện):

```
nut 'Xoá món':  box = 28 x 44   padding = 0px/0px/0px/0px   ::before = none
  cách  1px: trượt    cách  6px: trượt    cách 12px: trượt
  cách  2px: trượt    cách  8px: trượt
  cách  4px: trượt    cách 10px: trượt
=> hitSlop KHÔNG tác dụng trên web: mọi điểm ngoài box đều trượt
```

Cùng lớp với bài học đã có: rnw nuốt `accessibilityState` nên không ra
`aria-checked`. **Chưa đo trên máy thật** — trên native `hitSlop` nhiều khả năng
đúng như comment nói.

### PH-2 — VietQR chỉ hiện 59% lúc màn vừa vẽ
**Màn:** `ket-qua-thanh-toan` · **Lane:** frontend · **Không phải blocker**

```
khối mã ở y=728, cao 196px, màn cao 844px -> chỉ 116/196px (59%) trong khung nhìn
```

Mã **đúng và quét được** (xem dưới). Vấn đề thuần bố cục: đây là màn cuối đường
demo, thứ leader sẽ bấm tới nhiều nhất, và phần thưởng của cả luồng bị cắt mất
41% khi màn vừa hiện. Người dùng phải cuộn rồi mới chĩa app ngân hàng vào được.

Phát hiện này suýt không tồn tại: **giải mã được không có nghĩa là nhìn thấy**.
`page.screenshot({clip})` cắt vượt ra ngoài viewport, nên một mã nằm dưới fold
giải mã y hệt một mã nằm giữa màn. Hai câu hỏi giờ đo tách nhau — hình học lấy
lúc **màn vừa vẽ**, giải mã lấy **sau khi cuộn mã vào hẳn**.

### PH-3 — Danh sách món trên `goi-y` nằm dưới fold của khung cuộn TRONG màn
**Màn:** `goi-y` (GoiYChia) · **Lane:** frontend · **Quan sát, không phải lỗi pixel**

Lúc màn vừa vẽ, thẻ danh sách món trông **rỗng**: chỉ có chữ `Giá` ở góc phải.
`Đã nhận diện 3 món` và `Tổng cộng 480.000đ` vẫn hiện đúng.

Hình học (`tools/soi-mon-tang-hinh.mjs`):

```
khung cuộn:  y=403  cao 164px  overflow: hidden auto   (nội dung 326px)
mép cắt   :  y=567
"Giá"     :  y=527  -> trong khung, HIỆN
"Lẩu thái":  y=569  -> dưới mép cắt 2px, KHÔNG hiện
"280.000" :  y=571     "Nước sâm" y=613 ...
```

Hàng đầu tiên nằm **dưới mép cắt đúng 2px**, nên không có hàng nào ló ra để báo
cho người dùng biết còn nội dung bên dưới. Cuộn tới thì các món hiện bình thường
và đo được **15.79:1** — thừa AA.

**Đây không phải lỗi vẽ, và suýt bị báo thành lỗi vẽ.** Thước đo lần đầu kết
luận sáu chuỗi "có trong DOM, không lên pixel nào" — đúng lớp ảo giác
`che-chu.mjs` tồn tại để bắt, repo này đã dính ba lần. Giờ công cụ cuộn tới rồi
mới kết luận.

### PH-4 — Ba chuỗi sát ngưỡng AA
**Màn:** `goi-y`, `ket-qua-thanh-toan` · **Lane:** frontend · **Không phải blocker**

| Chuỗi | Đo được | Ngưỡng | Dư |
|---|---|---|---|
| `3 món · 3 người` | 4.52:1 | 4.5 | +0.02 |
| `← Đóng` | 4.55:1 | 4.5 | +0.05 |
| `Đã nhận diện 3 món` | 4.83:1 | 4.5 | +0.33 |

Tất cả **ĐẠT**. Ghi lại vì hai cái đầu chỉ dư 0.02 và 0.05 — đổi một nấc màu là
trượt, và không cổng nào khác trong repo đo được chỗ này.

`Kit.tsx:224` tự tính `split` trên `splitSoft` là **4.83:1**; phép đo pixel độc
lập ra **đúng 4.83:1**. Đó là đối chứng cho thước đo, không phải cho màn.

## VietQR: có ra pixel thật không?

**Có, và quét được.**

```
VietQR: OK -- 196x196px, 436 module-view, OpenCV giải lại ĐÚNG 102 ký tự payload TỪ ẢNH CHỤP
```

`MaVietQr.tsx` vẽ **mỗi module một View**, nên DOM có hàng trăm `div` dù không có
gì lên kính — đếm `div` hay tìm `<img>` đều không chứng minh được gì. Nên phép
kiểm là: chụp vùng mã từ màn đã render, đưa cho **OpenCV** (không chung dòng code,
không chung tác giả với `src/ui/qr.ts`), và đòi đúng payload đã gửi đi.

Đột biến `vietqr-trang` chứng minh phép kiểm này không mù:

```
module đổi #000000 -> #fffffe (gần như trắng)
-> [KHÔNG GIẢI ĐƯỢC] 196x196, 436 module-view -- OpenCV không đọc được ký tự nào
```

**436 module-view vẫn nguyên trong DOM** trong khi pixel không đọc được gì. Một
phép kiểm đếm DOM sẽ cho mã trắng trơn đi qua.

**Không chứng minh:** app ngân hàng thật có bắt được mã trên màn điện thoại thật
trong quán ăn thiếu sáng hay không. Cái đó cần điện thoại, tài khoản và camera.

## Canary — vì sao mấy con số 0 ở trên đáng tin

Một máy đo mù in ra đúng thứ mà một màn sạch in ra. Nên mỗi phép đo bị bắt phải
đỏ bằng một lỗi **viết vào nguồn thật, qua một lần build thật**:

```
bundle sạch: d78b3bb1ca1c

tương phản  ket-qua             DO   [DUOI AA] 1.05:1 (cần 4.5) "Đã nhận diện 3 món"
điểm chạm   ket-qua             DO   [DUOI WCAG 24] 17x44 "Xoá món Lẩu thái"
vietqr      ket-qua-thanh-toan  DO   [KHÔNG GIẢI ĐƯỢC] 436 module-view, 0 ký tự
che chữ     ket-qua-thanh-toan  DO   [CHE CHU] "Quét để thanh toán" bị che

bundle khôi phục: d78b3bb1ca1c        4/4 đột biến bị bắt
```

**Một đột biến mỗi lượt, không phải bốn cùng lúc.** Bốn cái cùng lúc làm cả bảng
đỏ và chứng minh ít hơn vẻ ngoài: một luật quá nhạy đỏ với mọi thứ trông y hệt
bốn luật mỗi cái bắt đúng lỗi của mình. Mỗi đột biến ở đây phải ra **đúng hình
dạng finding của nó**.

Rebuild là bắt buộc: `dot-bien-scrim.mjs` ghi lại cái bẫy — sửa `.tsx`, bỏ
rebuild, đo bundle cũ, ra số y hệt và exit 0. Ở đây mỗi đột biến đều rebuild, đối
chiếu hash bundle đổi, và hai đột biến màu còn ghim một mã hex không thể có trong
bundle sạch.

## Hai lần thước đo tự sai — ghi lại vì cả hai đều ra số đẹp

**1. Đọc `color` từ CSS làm rơi alpha.** App viết chữ phụ là
`rgba(255,255,255,0.62)`; bỏ alpha thành trắng đục, nên **cả chín** chuỗi của
`chup-bill` đều báo `21.00:1` — điểm tuyệt đối, và mù đúng với lớp lỗi cần bắt.
Sửa: không đọc màu/alpha/nền từ CSS nữa, lấy mực từ pixel đổi nhiều nhất giữa
hai lần chụp (có chữ / ẩn chữ).

**2. Lấy min tương phản trên cả dải pixel phủ mực làm lệch thấp ~4%.** Chữ trắng
trên nền đen ra `20.12:1` thay vì `21.00:1`, và `← Đóng` ra `4.45:1` trong khi
giá trị thật là `4.555:1` — tức là **chế ra một ca trượt AA cho một chuỗi đang
đạt**. Nâng DPR lên 4 rồi 8 không đổi số, đó là cái loại trừ độ phân giải và chỉ
vào phép thống kê. Sửa: mực là pixel phủ **nhiều nhất**, chỉ nền mới lấy tệ nhất.

Sau khi sửa, thước đo khớp số học tay: trắng/đen `21.00:1`; alpha 0.62 → mực
`rgb(158,158,158)` (0.62×255 = 158.1); alpha 0.55 → `rgb(140,140,140)`.

## Ô chưa quét

- **Điện thoại thật.** Tất cả số ở trên là Chromium headless 390×844 DPR2.
  `hitSlop` (PH-1) gần như chắc chắn khác trên native.
- **Chế độ tối**, Firefox/WebKit, cỡ chữ hệ thống phóng to, 320px.
- **Trình đọc màn hình** — file này không đo aria/tiêu điểm.
- Chỉ **một** trạng thái mỗi màn: một bill, ba người ăn, sáng, tiếng Việt.
- Bill thật chụp bằng camera: `chup-bill` trên web rơi vào nhánh "Trình duyệt
  không mở được camera", nên khung ngắm thật chưa ai đo.
- **`tests/moi-man-co-duong-do.test.mjs` (của #331) vẫn khai bốn màn này là
  `chuaDo`.** Câu đó giờ chỉ còn đúng với probe URL. File nằm ở
  `apps/mobile/tests/` là của lane frontend nên tôi **không sửa** — đã báo Lead.

## Chạy lại

```bash
cd apps/mobile && npm ci && npm run build:check
node tools/anh-bon-man-hero.mjs                    # 4 màn, exit 1 nếu có phát hiện
ANH_MAN=goi-y ANH_CHITIET=1 node tools/anh-bon-man-hero.mjs   # một màn, từng chuỗi
node tools/dot-bien-anh-bon-man.mjs                # canary, ~6 phút, 5 lần build
node tools/soi-hitslop.mjs                         # PH-1
node tools/soi-mon-tang-hinh.mjs                   # PH-3
```

Ảnh ra ở `apps/mobile/.anh-bon-man/` (đã `.gitignore` — ảnh bill không vào Git).
