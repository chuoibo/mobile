# PASS #491

**Lý do:** ba cổng đều xanh và **mọi con số PR khai đều tái lập được bằng phép đo
độc lập của tôi** — 13 cửa chưa mở → 5 (tôi tự tính lại trên cả hai cây), bốn
canary đều cắn đúng chiều, 4.56:1 khớp số học sRGB tôi tự tính. Bốn phát hiện
kèm dưới, **không cái nào là căn cứ FAIL**: (1) bản sửa tương phản của chính PR
**không có cổng nào giữ** — đặt `MO_KHI_BAN = 0` cho nút *tàng hình* thì cổng vẫn
1039/1039 xanh; (2) PR làm nền của `dot-bien-anh-ve.mjs` đỏ nên **bảng đột biến
đó nay không chạy được** — do PR gây ra, nhưng nó **từ chối to tiếng** chứ không
im lặng; (3) `npm test` trên nhánh này **flaky 1/4 lượt**, nên "1039/1039" không
phải một tín hiệu ổn định; (4) mô tả PR **hẹp hơn diff** — thiếu 3 công cụ mới
(~730 dòng), 1 test mới, 3 route `?man=` mới.

---

## Đo tại đâu

```
đo tại   b6205be216736f76f63b64d3ae69124def098d2c   (PR #491, frontend/imp-man-ket-qua-chia)
sha này  là nhánh CHƯA merge
nền      origin/main = 7fff89c  (merge-base = 7fff89c, tức nhánh đã ở trên main mới nhất)
đối chứng đo tại 7fff89c
cây      /home/lakiet/agent-harness/wt/qa, `git status` sạch ở mọi lượt đo
```

Chrome ghim tay cho mọi lượt quét URL:
`PUPPETEER_EXECUTABLE_PATH=/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome`

Kỹ năng đã gọi: `e2e-testing` (chặng 2 cổng rẻ · chặng 5 trang/màn · chặng 7 kết
luận) và `bug-reproduction` (đối chứng bản TRƯỚC · vòng reproduce→minimize ·
phân loại flaky vs môi trường vs không tái lập).

---

## 1. Ba cổng — số thật

| Lệnh | Cây | Kết quả |
|---|---|---|
| `python3 -m pytest services/api/tests tests -q` | b6205be | `2882 passed, 596 skipped, 5272 subtests passed in 307.93s` |
| `cd apps/mobile && npm test` | b6205be | `tests 1039 · suites 26 · pass 1039 · fail 0` |
| `cd apps/mobile && npm test` | 7fff89c (main) | `tests 1032 · pass 1032 · fail 0`, ×3 lượt |

596 skipped của cổng backend là tầng PostgreSQL — **lượt này chưa chạy**, xem mục
"chưa quét". PR không chạm backend nên con số này chỉ để chứng minh nhánh không
làm hỏng cái gì phía kia.

PR thêm 7 ca (1032 → 1039), đúng bằng `tests/be-ngang-may-quet.test.mjs`.

---

## 2. Claim đầu bài "13 cửa chưa mở → 5" — TÁI LẬP CHÍNH XÁC

Tôi không đọc con số của PR. Tôi trích lại chính phép tính của `cuaChuaMo()`
(`tools/quet-tab-url.mjs:531-541`) ra một script riêng và chạy trên **cả hai cây**:

```
########## MAIN 7fff89c ##########
route ?man= trong App.tsx: 13
cua tool CO mo           : 0  []
cua CHUA mo (13)         : binh-chon, binh-chon-hoa, doc-bill, doc-bill-chuan-bi,
                           goi-y-chia, ket-qua-thanh-toan, moi-vao-chuyen, mon-cua-toi,
                           nhan-dien, nhan-mat, tai-khoan-nhan, tai-khoan-nhan-duyet,
                           trang-thai

########## PR b6205be ##########
route ?man= trong App.tsx: 16
cua tool CO mo           : 11  [doc-bill, doc-bill-chuan-bi, dot-thu, dot-thu-da-phat,
                           goi-y-chia, ket-qua-thanh-toan, mon-cua-toi, nhan-dien,
                           nhap-khoan-chi, tai-khoan-nhan, tai-khoan-nhan-duyet]
cua CHUA mo (5)          : binh-chon, binh-chon-hoa, moi-vao-chuyen, nhan-mat, trang-thai
```

Số học khớp và đáng ghi rõ vì nó không hiển nhiên: tool mở **11** cửa nhưng chỉ
**8** trong đó là route có sẵn trên main; 3 cửa còn lại (`nhap-khoan-chi`,
`dot-thu`, `dot-thu-da-phat`) là route **chính PR tạo ra** (App.tsx 13 → 16
route). `13 − 8 = 5`. Nên "8 cửa mới" trong mô tả và "13 → 5" là **hai con số
nhất quán**, không phải hai cách đếm cùng một thứ.

Và 5 cửa còn lại đúng là ngoài đường tiền, như PR nói.

---

## 3. Máy quét chạy thật — canary cắn được thì số 0 mới có nghĩa

`node tools/quet-tab-url.mjs`, viewport 390x844, Chrome ghim tay → **EXIT=2**.

```
== doi chung may quet (viewport 390x844) ==
  canary xau        findings=5 exit=2   (can > 0)     ← ĐỎ ĐƯỢC
  canary sach       findings=0 exit=0   (can = 0)
  canary nang       findings=3 exit=2   cham day trang=co
  canary nang sach  findings=0 exit=0   (can = 0)
```

Bốn canary đều cắn đúng chiều, nên các số 0 dưới đây là số đo chứ không phải một
máy quét mù. **11/11 cửa mới dựng được màn thật và needle OK** — cột `els` cho
thấy không cửa nào rơi vào panel lỗi:

```
nhap-khoan-chi   els=71   needle OK      dot-thu           els=73   needle OK
dot-thu-da-phat  els=74   needle OK      doc-bill-chuan-bi els=54   needle OK  findings=1
doc-bill         els=54   needle OK  findings=1
nhan-dien        els=102  needle OK      goi-y-chia        els=209  needle OK
mon-cua-toi      els=59   needle OK      tai-khoan-nhan    els=96   needle OK
tai-khoan-nhan-duyet els=39 needle OK    ket-qua-thanh-toan els=619 needle OK

cua ?man= App.tsx dinh tuyen ma luot nay KHONG mo (5): binh-chon-hoa, trang-thai,
                                          nhan-mat, moi-vao-chuyen, binh-chon
tong findings tren cac man: 2
```

---

## 4. Số học tương phản — tự tính lại, khớp

Tôi tính độc lập bằng công thức luminance sRGB, không dùng số của PR:

```
alpha=0.40  -> pixel 102 (#666666)  tương phản trên nền đen = 3.66:1
alpha=0.46  -> pixel 117 (#757575)  tương phản trên nền đen = 4.56:1
```

Cả hai khớp từng chữ số với PR. Bậc 4.5:1 được vượt.

**Một sắc thái Lead nên biết, PR có nói nhưng dễ đọc lướt qua:** con số 4.56:1 là
của **lõi nét chữ đã phủ kín**. Chính máy quét của PR vẫn báo
`pixel contrast 1.1:1 median 2.9:1 (need 4.5:1)` trên nhãn đó. Median 2.9:1 ứng
với pixel ~87 (alpha ~0.34) — đúng dải khử răng cưa của chữ nhỏ trên một stack
opacity 0.46, nên lời giải thích của PR nhất quán. Nhưng phát biểu đúng là **"lõi
chữ vượt 4.5:1"**, không phải "nhãn này đã đạt bậc". PR không nói quá — nó khai
đúng cả median 2.4 → 2.9 — chỉ là tiêu đề PR gọn hơn số đo.

---

## 5. PHÁT HIỆN 1 — bản sửa tương phản không có cổng nào giữ (đột biến sống sót)

`MO_KHI_BAN` chỉ xuất hiện ở đúng một file, không test nào, không tool nào:

```
src/screens/ChupBill.tsx:54   const MO_KHI_BAN = 0.46;
src/screens/ChupBill.tsx:236  opacity: busy ? MO_KHI_BAN : ...
src/screens/ChupBill.tsx:288  opacity: busy ? MO_KHI_BAN : ...
src/screens/ChupBill.tsx:471  opacity: busy ? MO_KHI_BAN : ...
```

Hai đột biến, cả hai **sống sót**:

| đột biến | tới được bản dựng? | cổng |
|---|---|---|
| `0.46 → 0.40` (lùi đúng bản sửa của PR) | có | `pass 1039 · fail 0` |
| `0.46 → 0` (**nút tàng hình lúc bận**) | có — bundle chứa `opacity:0` | `pass 1039 · fail 0` |

Kiểm tương đương trước khi kết luận: đột biến **không phải no-op** — grep bản
dựng `.expo-build-check/_expo/static/js/web/index-*.js` ra `opacity:0` sau khi
đột biến. Nó tới được sản phẩm, và không cổng nào thấy.

**Đây KHÔNG phải hồi quy của #491.** Trước PR hằng số này còn chưa tồn tại, nên
cũng chẳng có gì để gác. Ghi ra vì nó là thứ có thể hành động được: một lần sửa
sau, ai đó đưa nút về 0.40 hoặc thấp hơn, và mọi dấu xanh vẫn nguyên.

**Tiêu chí gỡ:** một ca đo pixel thật của nhãn ở trạng thái `busy` (máy móc đã có
sẵn — `soi-tuong-phan-anh.mjs`, và `quet-tab-url.mjs` đã mở đúng cửa `doc-bill`).

---

## 6. PHÁT HIỆN 2 — #491 làm tắt bảng đột biến `dot-bien-anh-ve.mjs`

PR tự khai điều này. Tôi xác nhận, và xác nhận thêm phần PR không nói: **nguyên
nhân là của chính PR**, không phải nợ có sẵn.

`tools/dot-bien-anh-ve.mjs:128-153` chạy `node tools/quet-tab-url.mjs` làm nền và
đòi `ma=0`:

```js
const sach = chay();                       // spawnSync("node", ["tools/quet-tab-url.mjs"])
console.log(`nen sach: ma=${sach.ma} (can 0)`);
if (sach.ma !== 0) throw new Error("nen sach da do san -- moi con so duoi deu vo nghia");
```

Tôi đo được máy quét ở b6205be trả **EXIT=2**, `tong findings: 2`. Hai finding đó
đến từ `doc-bill` và `doc-bill-chuan-bi` — **hai cửa không tồn tại trên main**
(danh sách cửa của main đúng 6 cái: `ai-khong-tra-loi-duoc`, `ca-nhan-tuong`,
`diem-hen-ket-qua`, `kham-pha-mo-rong`, `ky-niem-binh-luan`, `nhap-chi-tu-chat`,
và cả 6 đều ra 0 finding trong lượt quét của tôi). Nên trước PR tổng là 0 và
`dot-bien-anh-ve.mjs` chạy được; sau PR nó ném.

**Vì sao vẫn không phải blocker:** nó **từ chối to tiếng, kèm thông báo đúng**.
Kiểu hỏng phải chặn là bảng đột biến âm thầm chấm điểm trên cây đỏ rồi in xanh —
cái đó không xảy ra ở đây. Và cả hai đều là tool chạy tay, không nằm trong
`npm test` hay `make gate`.

**Tiêu chí gỡ:** một quyết định trước lần dùng sau của `dot-bien-anh-ve.mjs` —
hoặc nó nhận một nền đỏ đã biết, hoặc hai finding kia được xử lý. PR đã ghi rõ
`hook-admin.mjs ignore-value low-contrast` từ chối luật này nên đường bịt bằng
ignore không mở.

---

## 7. PHÁT HIỆN 3 — `npm test` flaky, nên "1039/1039" không phải tín hiệu ổn định

Ca đỏ luôn là **một ca duy nhất**:

```
not ok 283 - đường vào Món của tôi, trên trang render thật
  tests/duong-vao-mon-cua-toi.test.mjs:164
  kịch bản đi bộ "mở Món của tôi" HỎNG:
    het gio cho "Danh sách gửi lên thay hết món bạn nhận trước đó"
  duration_ms: 21369
```

Ngân sách chờ là hằng số cứng **20000ms** (`tools/quet-man-sau-tap.mjs:595`,
`if (b.cho) await cho(b.cho, b.ms || 20000)`), và lượt hỏng đo 21369ms — tức nó
trượt ngân sách chứ không phải màn hỏng.

Bảng đếm, cùng một giao thức:

| cây / cách chạy | đỏ / lượt |
|---|---|
| `npm test` trên main 7fff89c | **0 / 3** |
| `npm test` trên b6205be, không đột biến | **1 / 4** |
| `npm test` trên b6205be, có đột biến `MO_KHI_BAN` | **2 / 3** |
| chỉ `node --test` (bundle dựng sẵn, không build:check ngay trước) | **0 / 10** |
| chỉ file đó, chạy một mình | **0 / 5** |

Phân loại theo `bug-reproduction` bước 7: **flaky theo tải**, không phải
environment-specific và không phải data-dependent — cùng commit, cùng máy, vừa
xanh vừa đỏ. Mọi lượt đỏ đều là lượt có `build:check` chạy ngay trước; 10 lượt
chỉ `node --test` không đỏ lần nào.

**Chưa quy được trách nhiệm cho #491, và tôi nói thẳng là chưa.** 1/4 so với 0/3
không đủ số lượt để tách. Tôi có đi tìm đường nhân quả và **không tìm thấy**:
PR có sửa `tools/quet-man-sau-tap.mjs` — đúng module ca này import — nhưng diff
chỉ thêm `cauHinhTrinhDuyet()` (ở mặc định trả đúng literal cũ), export thêm
`serverGiuNhip`, và thay literal viewport bằng lời gọi hàm đó. `MAN_SAU_TAP` và
`trangTuLai` không đổi, nên kịch bản đi bộ là **cùng một kịch bản**.

Hậu quả cho cả đội, và đây mới là phần quan trọng: mọi báo cáo "npm test xanh"
trên repo này — của tôi lượt này cũng vậy — đang mang một xác suất đỏ giả khoảng
1/4 khi chạy qua `npm test`. Một lượt đỏ ở ca này **không** nên đọc thành
"nhánh làm hỏng đường vào Món của tôi".

**Tiêu chí gỡ:** ngân sách 20s ở `quet-man-sau-tap.mjs:595` thành thứ đo được
(hoặc nới, hoặc chờ theo sự kiện thay vì theo đồng hồ). Không thuộc sở hữu của
lane frontend một mình — cần Lead phân.

---

## 8. PHÁT HIỆN 4 — mô tả PR hẹp hơn diff

Charter: *"Leader chỉ đọc `main`, nên mô tả PR phải nói cái gì đổi và vì sao."*
Mục "Cái gì đổi" của #491 nói **hai** việc. Diff so với main có **mười** file:

| file | trạng thái | có trong mô tả? |
|---|---|---|
| `apps/mobile/tools/quet-tab-url.mjs` | M (+234) | có |
| `apps/mobile/src/screens/ChupBill.tsx` | M | có |
| `apps/mobile/App.tsx` | M (+107, **3 route `?man=` mới**) | chỉ gián tiếp |
| `apps/mobile/tools/do-tran-chu.mjs` | **A (+450)** | không |
| `apps/mobile/tools/dot-bien-tran-chu.mjs` | **A (+180)** | không |
| `apps/mobile/tools/do-be-ngang-tieu-de.mjs` | **A (+100)** | không |
| `apps/mobile/tests/be-ngang-may-quet.test.mjs` | **A (+191)** | không |
| `apps/mobile/tools/quet-man-sau-tap.mjs` | M (single-source viewport) | không |
| `apps/mobile/tests/moi-man-co-duong-do.test.mjs` | M | không |
| `.gitignore` | M | không |

Bảy dòng cuối là công việc thật và có vẻ tốt — commit log của nhánh mô tả chúng
đầy đủ. Vấn đề chỉ là chúng **không có trong phần Lead đọc**. ~730 dòng công cụ
mới đi vào main dưới một tiêu đề nói về chuyện khác.

Đây là **suggestion**, không phải blocker: không thuộc 5 loại của charter.
**Tiêu chí gỡ:** thêm một đoạn vào mô tả PR liệt kê 4 file mới và 3 route mới.

---

## 9. Ô CHƯA QUÉT — đọc kỹ mục này

| ô | vì sao chưa |
|---|---|
| `tests/postgres` | lượt này không dựng Postgres; cổng backend in `596 skipped` |
| `npm run test:e2e` | không dựng uvicorn; lát cắt dọc thật **chưa chạy** |
| **Mã QR quét bằng app ngân hàng thật** | không agent nào quét được; chỉ leader, 15 phút, một điện thoại |
| 5 cửa còn lại: `binh-chon`, `binh-chon-hoa`, `moi-vao-chuyen`, `nhan-mat`, `trang-thai` | ngoài đường tiền, PR cố ý để lại |
| 3 công cụ mới (`do-tran-chu.mjs`, `dot-bien-tran-chu.mjs`, `do-be-ngang-tieu-de.mjs`) | **~730 dòng, tôi chưa chạy dòng nào**; chúng không nằm trong `npm test` |
| Tương phản trên **thiết bị thật / ánh sáng thật** | tôi chỉ tính số học và đọc số của detector |
| `dot-bien-anh-ve.mjs` bảng đột biến | **không chạy được** — đó chính là phát hiện 2 |
| Chủ đề sáng, khung nhìn 320 và 1440 | lượt quét chỉ chạy 390x844 |

---

## 10. Phân loại theo 5 loại blocker của charter

| phát hiện | loại | phán |
|---|---|---|
| 1 — tương phản không có cổng | không thuộc 5 loại (là nợ có sẵn, không phải hồi quy) | suggestion |
| 2 — `dot-bien-anh-ve` tắt | *sát* loại "vi phạm spec/cổng", nhưng cổng **từ chối to tiếng**, và là tool chạy tay ngoài `make gate` | suggestion, cần quyết định trước lần dùng sau |
| 3 — `npm test` flaky 1/4 | *sát* loại "không tái lập được", nhưng **chưa quy được cho #491** | báo Lead, không chặn #491 |
| 4 — mô tả hẹp hơn diff | không thuộc 5 loại | suggestion |

Không blocker nào mở. → **PASS**.

---

## 11. Chạy lại

```bash
bash tests/qa/qa-tt-0006/do_cong_491.sh
```

Script chạy lại: hai cổng ở cả hai cây, phép tính cửa chưa mở trên cả hai cây,
số học tương phản, và hai đột biến `MO_KHI_BAN`. Phần quét URL cần Chrome ghim
tay và mất ~10 phút nên script chỉ in lệnh, không tự chạy.

---

Và câu không được bỏ: **repo này chưa có bằng chứng hành vi nào** (ADR-0006).
1039 ca xanh nói code làm đúng điều tác giả nghĩ. Nó không nói người thật mở màn
`ChupBill` lúc đang bận thì có đọc được nhãn nút hay không.

`protocol_version`: v1 · `verdict`: **PASS** · blocker còn mở: **không**
