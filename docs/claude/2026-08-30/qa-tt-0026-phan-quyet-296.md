# Phán quyết QA — PR #296 tại SHA mới

**PASS**

Lý do, trước phần chi tiết: hai commit mới của #296 sửa đúng thứ tôi đã FAIL ở
qa-tt-0025 — cổng `quet-tab-url.mjs` giờ **xanh rc=0** tại chính SHA của PR, và
con số nó in ra là con số thật: tôi làm nó **đỏ được bằng hai đột biến khác
nhau** và **xanh lại bằng một đột biến giữ tính chất**. Phần sản phẩm (14 dòng,
đúng một file) tôi đo lại độc lập bằng thước đo mới, không dùng công cụ của PR:
màn chi tiết đi từ **0 pixel ảnh** lên **17.162 pixel ảnh**. Cổng đầy đủ xanh.

```
protocol_version  v1
đo tại            8625ed4 = #296(444526f9) ⊕ main(ca5e7e8), merge sạch không xung đột
sha này           LÀ NHÁNH CHƯA MERGE
verdict           PASS
blocker còn mở    không có
```

---

## 1. Vì sao phán quyết cũ hết hiệu lực

Ở qa-tt-0025 tôi FAIL #296 tại `6cf26b1`: cổng của chính PR đỏ với
`dia-diem: can 1 anh giai ma duoc, dang co 0 (els=265)`, trong khi mô tả PR khai
`rc=0, els=268, 1 anh`. Tác giả đẩy thêm hai commit **sau** phán quyết đó:

```
820db23  Ảnh không thật sự vẽ ra trong artifact được quét, và cột `anh` đếm nhầm node vô hình
444526f  Cột `anh` đếm từ pixel, vì phép "hỏi lại URL" đang hỏi chính cái stub đã giả
```

Cả hai chạm **duy nhất** `tools/` — không một dòng sản phẩm nào:

```
apps/mobile/tools/quet-tab-url.mjs         87 +-
apps/mobile/tools/soi-tuong-phan-anh.mjs  362 +-
apps/mobile/tools/tab-snapshots.mjs        75 +-
```

Nên câu hỏi của lượt này không phải "sản phẩm có chạy không" mà là **"máy đo
được sửa cho THẬT hay sửa cho XANH"**. Đó là chỗ tôi dồn toàn bộ công.

### Chẩn đoán của tác giả, và nó đúng

react-native-web dựng `<Image>` thành **HAI node**: một `<img>` ghim ở
`opacity: 0` chỉ để giải mã và bắn `onLoad`, và một `<div>` bọc ngoài mới là cái
**vẽ** ảnh, qua `background-image` inline. Stub cũ vá
`HTMLImageElement.prototype.src` — tức là nó trả lời cho **cái máy dò tải**,
không trả lời cho **cái máy vẽ**. Nên `naturalWidth` về 480 trong khi div quay số
ra `api.build-check.invalid` và không nhận được gì. Mọi hàng đếm
`naturalWidth > 0` đọc thành "có ảnh" trong khi khung đang vẽ dải màu danh mục.

Điều này cũng **huỷ thước đo cũ của chính tôi**: script đối chứng tôi dùng ở
qa-tt-0025 đếm bằng `naturalWidth > 0`. Ở bối cảnh của tôi nó tình cờ vẫn đúng
(tôi phục vụ bytes thật từ máy chủ thật nên **cả hai** node đều nhận được ảnh),
nhưng nó là thước đo sai nguyên tắc. Lượt này tôi thay hẳn — xem mục 3.

---

## 2. Cổng của PR: xanh, và tôi làm nó đỏ được

Cổng chạy tại `8625ed4`, có ghim Chrome, **hai canary bắt buộc đúng ở mọi lượt**:

```
canary xau        findings=5  exit=2   (cần > 0)   ĐỎ
canary sach       findings=0  exit=0   (cần = 0)   XANH
canary nang       findings=3  exit=2               ĐỎ
canary nang sach  findings=0  exit=0               XANH

kham-pha          els=625  1 anh giai ma duoc
dia-diem          els=268  1 anh giai ma duoc      <- hàng từng đỏ ở qa-tt-0025
tong findings: 0                             rc=0
```

`els` 265 → 268 (+3) đúng bằng cây con của một `<img>` — khớp với con số tôi đo
được ở lượt trước, và giờ đã có lời giải thích: painter nhận được bytes nên ảnh
thật sự dựng ra.

### Bảng đột biến — cổng phân biệt được, không phải lúc nào cũng đỏ

| đột biến | mong đợi | thực tế |
|---|---|---|
| **M1** vô hiệu MutationObserver cấp bytes cho painter (giữ nguyên bản vá `<img>`, tức giữ nguyên lời nói dối cũ) | ĐỎ | **ĐỎ** — `anh=0`, rc=1 |
| **M2** sản phẩm ngừng vẽ ảnh (`Anh.tsx`: `veAnh = false`) | ĐỎ | **ĐỎ** — `anh=0`, rc=1 |
| **M3** giữ tính chất: đổi hẳn tấm ảnh sang tông xanh lạnh, vẫn là ảnh thật | XANH | **XANH** — `anh=1`, rc=0 |
| control (cây sạch, dựng lại) | XANH | **XANH** — rc=0 |

**M1 là hàng quan trọng nhất.** Nó dựng lại đúng con bug cũ: `<img>` vẫn được stub
trả lời (`naturalWidth` vẫn 480), chỉ painter là không có gì. Thước đo cũ sẽ đọc
thành "1 ảnh". Thước đo mới trả về **0**. Đó là bằng chứng bản sửa nhắm đúng gốc.

Tôi có nghi ngờ riêng và đã kiểm: `linear-gradient` **cũng là** một
`background-image`, mà bộ đếm mới thu khung ứng viên từ `[style*='background-image']`
rồi gán `backgroundImage = "none"` và so pixel — nên trên nguyên tắc một thẻ chỉ
có dải màu danh mục cũng có thể bị đếm thành ảnh. **Nghi ngờ này sai**: M1 trả về
`anh=0` chứ không phải 1. Bộ đếm phân biệt được ảnh với dải màu.

Khôi phục sau mỗi đột biến, đã kiểm bằng md5 và `git status` rỗng.

---

## 3. Đối chứng sản phẩm — thước đo mới, không dùng công cụ của PR

`tests/qa/qa-tt-0026/di-bo-magenta.mjs`. Không import gì từ `tools/` của PR, và
không dùng lại phép so-hai-ảnh-chụp của PR. Nó phục vụ một tấm ảnh **magenta
đặc `rgb(255,0,255)`** — màu không có trong bảng màu sản phẩm — rồi **đếm pixel
magenta trên ảnh chụp trang đã hợp thành**. Dải màu không tạo ra được màu đó,
scrim không tạo ra được, và không bản vá `HTMLImageElement.prototype` nào đưa
được nó lên màn.

Hai bundle `expo export --clear`, chỉ khác **đúng một file** (`ChiTietDiaDiem.tsx`
lấy từ `origin/main` cho bản trước), đều đã kiểm chuỗi `localhost:8137` nhúng
được (6 hit mỗi bên). Máy chủ là uvicorn dựng từ chính cây này.

```
                    kham-pha              dia-diem
trước (main)     2089 px  CÓ ẢNH        0 px  KHÔNG CÓ ẢNH   els=283
sau  (#296)      2089 px  CÓ ẢNH    17162 px  CÓ ẢNH         els=286
```

Đỏ-trước / xanh-sau, trên tấm ảnh thật, ở thước đo miễn nhiễm với cái bẫy hai
node. `els` 283 → 286 khớp đúng +3 của mục 2.

**Một cái bẫy tôi tự rơi vào và ghi lại đây vì nó sẽ cắn người sau:** lượt đầu
tôi dùng `dia-diem=p-1` lấy từ fixture của PR. Với máy chủ thật, `p-1` không
tồn tại nên app **rơi về Khám phá**, và cả hai hàng in ra **số liệu giống hệt
nhau** (`els=633 chars=713 magenta=2089`) ở **cả hai** bundle — đọc y hệt "màn
chi tiết render ảnh tốt ở cả trước lẫn sau". Phải dùng id thật
(`p-tiem-nuong-xom-lao`) mới lộ ra khác biệt. Fragment không phân giải được là
một dạng xanh giả im lặng.

---

## 4. Blocker của Lead: máy đo tương phản giờ có gánh thật

Lead REQUEST_CHANGES vì "máy đo tương phản không đo trên pixel ảnh thật lần nào".
`soi-tuong-phan-anh.mjs` (viết lại 362 dòng trong hai commit này) **giờ đo thật**,
và tôi chứng minh nó gánh được tải:

```
cây sạch                          rc=0
  kham-pha  6.63:1  TREN ANH   "Tiệm Nướng Xóm Lào"
  dia-diem  6.01:1  TREN ANH   "Tiệm Nướng Xóm Lào"

M4: Scrim [0, 0.18, 0.72] -> [0,0,0]     rc=1  HONG
  kham-pha  6.63 -> 1.46:1   ĐỎ
  dia-diem  6.01 -> 2.66:1   ĐỎ
```

Gỡ scrim là gỡ đúng thứ tài liệu nói scrim tồn tại để làm, và máy đo nổ. Đây là
điều `imp detect` không bắt được (nó tính tương phản theo nền CSS, không lấy mẫu
pixel của ảnh) — đúng như PR khai, và tôi đã tự kiểm chứ không đọc lại lời khai.

---

## 5. Cổng đầy đủ

```
python3 -m pytest services/api/tests tests -q
  2172 passed, 420 skipped, 4797 subtests passed in 149.45s

cd apps/mobile && npm test
  tests 705 · pass 705 · fail 0 · skipped 0
```

420 skipped là **tầng PostgreSQL chưa chạy** (thiếu `MOBILE_TEST_DATABASE_URL`).
Skip không phải xanh. PR này không chạm một dòng backend nào nên tầng đó không
liên quan tới phán quyết, nhưng tôi ghi ra chứ không nuốt.

---

## 6. Không chặn — nhưng Lead cần biết bốn điều

**6.1 Tiêu đề nói quá.** "Ảnh thật lên Khám phá" — nhưng Khám phá **đã** render
ảnh từ trước PR này: 2089 px magenta ở **cả hai** bundle. Thay đổi thật của PR là
**màn chi tiết**, và diff sản phẩm nói đúng chuyện đó: 14 dòng, truyền
`uri={place.photoUrl}` vào khung 248pt vốn đã tồn tại mà không ai nối dây.

**6.2 Máy chủ thật vẫn chưa gửi `photo_url`.** Đo tại `8625ed4`:

```
GET /places -> 12 địa điểm, 0 có photo_url
khoá của bản ghi: [... photo_count ...]   — không có khoá photo_url
```

Nên **hôm nay, với backend thật, không một tấm ảnh địa điểm nào hiện ra** trên
bất kỳ màn nào. Cái PR chứng minh là "khung đã sẵn sàng cho ngày trường đó tồn
tại", và mọi phép đo ảnh trong PR (kể cả của tôi) đều phải **tự chèn** `photo_url`
vào mới đo được. Chuyện này được ghi thẳng trong code (`KhamPha.tsx`) chứ không
bị giấu — nhưng nó có nghĩa là đường hero "mở app → Khám phá thấy ảnh" vẫn **chưa
đóng**, và chỗ còn thiếu nằm ở backend, không ở frontend.

**6.3 Hai cổng ảnh này không được cổng nào gọi.** `quet-tab-url.mjs` và
`soi-tuong-phan-anh.mjs` chỉ được nhắc tới trong **comment**; không có trong
`npm test`, `scripts/`, `Makefile`, hay `.github/`. PR **có khai** điều này (mục
cuối mô tả: "chạy tay… nên không nằm trong `npm test`"), nên đây là hạn chế đã
công bố chứ không phải lời nói dối. Tôi vẫn nêu vì nó là **hình dạng thứ bảy**
Lead vừa tự đặt tên: cổng đúng, chạy đúng, không ai gọi. Hai máy đo tốt nhất cho
tính năng ảnh hiện chỉ chạy khi có người nhớ ra.

**6.4 Chưa có chữ thật nào nằm trên ảnh.** Cả ba phép đo `TREN ANH` đều mang nhãn
`[phep-thu]` — chữ do chính máy đo chèn vào để hỏi "một caption ở đây sẽ tốn bao
nhiêu". Bố cục hiện tại đã dời tên quán ra **ngoài** khung ảnh. Nên scrim đang
được giữ cho một nhu cầu **tương lai**, và lời biện minh trong docstring của
`AnhDiaDiem` ("every card puts its name over the bottom of this block") đã cũ so
với bố cục. PR nêu đúng chuyện này ở mục cuối và cố ý không sửa kèm. Hàng
`ky-niem` đo được **3.89:1 — dưới ngưỡng AA** nhưng không bị gác, vì khung đó
không khai `chuTrenAnh`; với chữ `[phep-thu]` thì đó là lựa chọn hợp lý, nhưng nó
sẽ thành nợ thật vào ngày ai đó đặt caption lên tường kỷ niệm.

---

## 7. Ô CHƯA quét

- **Tầng PostgreSQL** — 420 ca skip, không chạy. PR không chạm backend.
- **Chặng docker** — không chạy. PR không đổi khai báo route nào (chỉ 1 `.tsx` +
  `tools/`), nên ràng buộc mới của Lead không áp dụng; và main đang có sự cố
  docker riêng (bug-115311) mà devops đang xử.
- **Thiết bị thật** — mọi phép đo ở 390x844 trong Chromium headless. Chưa mở trên
  điện thoại thật lần nào.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm. Không liên quan PR
  này nhưng vẫn là ô mở của sản phẩm.
- **Ảnh từ backend thật** — không quét được, vì `photo_url` chưa tồn tại (6.2).
- **Chủ đề tối và các khung nhìn 320 / 1440** — chỉ quét 390x844 sáng.
