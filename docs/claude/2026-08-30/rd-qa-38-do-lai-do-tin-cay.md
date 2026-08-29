# rd-qa-38 — Đo lại độ tin cậy chụp bill sau #209

**Giả thuyết của leader SAI.** `sanitize_image` không sửa lỗi độ tin cậy. Nó xáo lại
đồng xu chứ không bẻ cong đồng xu, và trên một tấm bill nó làm hỏng hẳn: 100% → 0%.

Nhưng phép đo tìm ra **nguyên nhân thật**, và nguyên nhân đó không nằm ở tấm ảnh.

```
đo tại   208c1d3  (= tip origin/main, đã có #209)
nhánh    qa/rd-qa-38-do-lai-do-tin-cay
Gemini   thật, khoá thật, gemini-2.5-flash, temperature=0.0
290 lần gọi thật qua do-do-tin-cay.py + 42 lần qua soi-quantity.py + 11 lần qua HTTP
ảnh nằm ngoài repo: /tmp/rd-qa-37-wire2/, /tmp/rd-qa-38-anh/
```

---

## Câu 1 — Tỉ lệ đọc được là bao nhiêu? Vẫn hỏng.

**Đúng tấm bill cũ, đúng byte cũ.** File `xoay.jpg` mà rd-qa-37 đo 6/11 còn nguyên ở
`/tmp/rd-qa-37-wire2/xoay.jpg`, `sha256 43bcfa4a056f…`, 52.806 bytes — khớp chính xác
con số ghi trong báo cáo #207. Không phải một tấm bill tương tự; là **chính nó**.

Một chi tiết phải nói trước, vì nó loại bỏ một nửa giả thuyết ngay từ đầu: file này
**900×1200, không có EXIF, đã dựng đứng sẵn** (trình duyệt đã áp thẻ xoay khi re-encode
lúc rd-qa-37 bắt trên dây). Nên nhánh `exif_transpose` của `sanitize_image` là **no-op**
trên file này. Thứ duy nhất bộ lột đổi là JPEG re-encode — đúng phần leader nêu.

Đo trong **một tiến trình**, một reader, một ảnh; biến duy nhất là có gọi `sanitize_image`
hay không. Nhánh "trước" không phải chuyện kể về code cũ — nó là **đúng thân hàm**
`run_receipt_skill` trước #209, chép lại nguyên văn. Đây là revert-to-verify, không phải
so sánh hai thời đại.

```
# xoay-wire  52.806 bytes  900x1200  n=30/nhánh
trước #209   16/30 =  53.3%   [95% CI 36.1–69.8]   lỗi: INVALID_QUANTITY ×14
sau  #209    17/30 =  56.7%   [95% CI 39.2–72.6]   lỗi: INVALID_QUANTITY ×13
```

Hai khoảng tin cậy chồng gần như hoàn toàn. **Không có cải thiện.**

Và qua HTTP, trên uvicorn dựng từ chính cây có #209, đúng đường `/receipts/scan`:

```
lần 1 → 200 | 2 → 422 | 3 → 422 | 4 → 200 | 5 → 200 | 6 → 422
lần 7 → 200 | 8 → 200 | 9 → 200 | 10 → 422 | 11 → 422
                                        6/11 đọc được
```

**Sáu trên mười một.** Cùng con số rd-qa-37 đo trước khi #209 tồn tại.

Leader dặn "nếu vẫn hỏng thì đừng nể": vẫn hỏng.

**Vì sao phép đo của leader ra 22/22 mà vẫn thành thật.** Không ai đo sai. 22/22 đúng
với **tấm bill của leader**; 6/11 đúng với **tấm bill của rd-qa-37**. Khác biệt nằm ở
tấm bill, không nằm ở bộ lột — mục 4 nói rõ khác biệt đó là gì.

---

## Câu 2 — n bao nhiêu thì đủ? n=30 mỗi nhánh, nhưng đó không phải câu hỏi đúng.

**Vì sao 30:**

- **Quy tắc số ba.** 30/30 sạch cho cận trên 95% của tỉ lệ hỏng là 3/30 = **10%** —
  đúng bằng tiêu chí gỡ chặn rd-qa-37 đã viết ("≥20 lần, nếu vẫn <90% thì cần retry").
  n=20 chỉ đưa cận trên xuống 14%; n=11 xuống 24%. **11 lần không bao giờ chứng minh
  nổi một bản vá**, kể cả khi bản vá có thật.
- **Đủ lực để bác bỏ "không đổi".** Nếu tỉ lệ thật vẫn là 55%, xác suất thấy ≥27/30 là
  khoảng 2×10⁻⁶. Nên n=30 phân biệt dứt khoát "đã sửa" với "y nguyên".
- 12/12 và 22/22 cho cận trên 26% và 15% — **cùng chuồng với 55%**, không loại được nó.

**Nhưng câu hỏi đúng không phải n.** Phương sai ràng buộc kết luận nằm **giữa các tấm
bill**, không nằm giữa các lần gọi trên một tấm. Bảy tấm ảnh đo hôm nay trải từ 0% tới
100% **trên cùng một bản code**. Nên thiết kế đúng là **nhiều ảnh ở n≈20**, không phải
nhiều lần hơn trên một ảnh. Một tấm ảnh tổng hợp ở n=100 vẫn không nói được gì về tấm
thứ hai — và đó chính xác là chuyện đã xảy ra giữa 22/22 và 6/11.

---

## Câu 3 — Ảnh khác thì sao? Cải thiện không tồn tại, và có chiều ngẫu nhiên.

Tất cả ở n=20/nhánh (trừ `xoay` n=30), cùng tiến trình, cùng reader:

| Ảnh | Là gì | trước #209 | sau #209 | Đổi |
|---|---|---|---|---|
| `xoay` | đúng file 6/11 của rd-qa-37 | 53.3% | 56.7% | ≈ 0 |
| `ro` | bill rõ, bắt trên dây | **0%** | **55%** | +55 |
| `nghieng` | bill chụp nghiêng, sáng lệch, nhiễu | **55%** | **0%** | **−55** |
| `mo-nhe` | bill hơi mờ | 55% | 55% | 0 |
| `dai` | bill dài 20 món, giấy nhiệt 720×1860 | **100%** | **0%** | **−100** |

Bốn chiều khác nhau, gồm **hai lần đi lùi**, một lần lùi từ hoàn hảo về không.
`sanitize_image` không làm ảnh dễ đọc hơn. Nó làm ảnh **khác đi**, và kết quả lật theo.

Cần nói rõ: `nghieng` và `dai` là ảnh **tổng hợp làm cho giống ảnh chụp** (biến đổi phối
cảnh, dải sáng lệch, nhiễu cảm biến) — không phải ảnh chụp bill giấy thật bằng điện
thoại thật. Ô đó vẫn chưa quét.

---

## 4. Nguyên nhân thật — và nó không phải cái ảnh

**153/153 lần hỏng trong 290 lần gọi đều là một mã duy nhất: `INVALID_QUANTITY`.**
Không một lần nào là lỗi thị giác. Không một lần nào mô hình nói "tôi không đọc được".

`_read_quantity` (`app/domain/receipt.py:143`) coi **thiếu khoá** là "một phần món này",
nhưng coi **chuỗi rỗng** là số lượng hỏng — và ném `INVALID_QUANTITY` cho **cả hoá đơn**.
Bắt được trên dây, mô hình có **ba** cách nói "dòng này không in số lượng":

```
xoay.jpg  không lột   12 lần:  35× bỏ khoá        25× ''       → 5/12 lần dính
xoay.jpg  có lột      12 lần:  48× bỏ khoá        6× 'X4'  6× 'X2'  → 6/12 lần dính
dai.jpg   không lột    6 lần: 120× bỏ khoá                    → 0/6 dính  (đọc 20/20)
dai.jpg   có lột       6 lần:                60× ''  60× 'null'  → 6/6 dính  (đọc 0/20)
```

Chuỗi `'null'` — bốn ký tự chữ — là mô hình viết chữ "null" vào ô số lượng. `''` và
`'null'` và bỏ khoá **nói cùng một điều**. Chỉ một trong ba được chấp nhận.

Một chuỗi rỗng trên **một** dòng huỷ **cả năm** dòng. Bốn món kia đọc đúng, tiền đúng,
và bị vứt đi cùng.

**Phép thử tách bạch.** Cùng số tiền, cùng món, chỉ khác cách in số lượng, đo trên
`main` hôm nay (nhánh `sau`):

| Ảnh | Số lượng in thế nào | Đọc được |
|---|---|---|
| `xoay` / `ro` / `nghieng` | nằm trong **tên món**: "Trà đá **x4**" | 0–57% |
| `cot-sl` | có **cột SL** riêng: `Trà đá │ 4 │ 20.000` | **20/20 = 100%** |
| `khong-x` | **không in** số lượng ở đâu cả | **20/20 = 100%** |

Hai tấm 100% ấy có **cùng tiền, cùng món, cùng kích thước** với tấm 0–57%. Nếu chất
lượng ảnh là nguyên nhân, hai tấm này phải chập chờn như tấm kia. Chúng không.

**Ba luật tiền vẫn nguyên.** 137 lần đọc được cho **đúng một** tổng cho mỗi bill
(235.000 / 1.490.000) và đúng số món. Không lần nào ra số sai. Đây vẫn là lỗi độ tin
cậy, không phải lỗi tiền — kết luận này giống rd-qa-37 và được 290 lần gọi củng cố.

---

## 5. Phát hiện của leader về `receipt_unreadable` — ĐÚNG, với hai đính chính

**Là nhánh bắt tất cả: đúng.** Con số là **7 mã**, không phải 8, trên tổng **13** mã
(không phải 12). Sáu mã có nhánh riêng: `UNSUPPORTED_IMAGE_TYPE`, `IMAGE_TOO_LARGE`,
`RECEIPT_TOO_BLURRY`, `RECEIPT_READER_NOT_CONFIGURED`, `NOT_A_RECEIPT`,
`NOT_A_RECEIPT_PRICE_LIST`. Bảy mã rơi vào `receipts.py:109`:

```
EMPTY_IMAGE · INVALID_CONFIDENCE · INVALID_QUANTITY · INVALID_RECEIPT
INVALID_RECEIPT_ITEM · NO_ITEMS_READ · UNREADABLE_AMOUNT
```

**Không log gì cả: đúng, và tệ hơn leader nghĩ.** 11 lần gọi thật lên uvicorn, 5 lần
hỏng, log máy chủ đầy đủ chỉ có:

```
INFO: 127.0.0.1:46644 - "POST /receipts/scan HTTP/1.1" 422 Unprocessable Content
```

`grep -ci "quantity|invalid|unreadable|ReceiptError"` trên log → **0 dòng**.

Và đây là phần đo được ngoài dự tính: một request có `X-Actor-ID` **sai định dạng** —
không liên quan gì tới bill, chưa từng chạm Gemini — sinh ra **dòng log y hệt**:

```
INFO: 127.0.0.1:47706 - "POST /receipts/scan HTTP/1.1" 422 Unprocessable Content
```

Nên log hiện tại không phân biệt nổi "header hỏng" với "AI không đọc được bill". Khi
đường hero hỏng 45%, người trực không có gì trong tay.

### Mã nào đáng một câu khác — trả lời theo số đo, không theo cảm giác

1. **`INVALID_QUANTITY` — không nên là lỗi người dùng thấy, ở bất kỳ câu chữ nào.**
   100% số lần hỏng đo được. Mô hình đã đọc đúng bill; tầng domain vứt nó đi. Sửa
   `_read_quantity` đọc chuỗi trắng như "không có" là thay đổi **giá trị cao nhất**
   đo được trên đường hero. Nhận thêm `'null'` và `'x4'`/`'X4'` thì đóng nốt phần còn lại.
2. **`UNREADABLE_AMOUNT` — leader đúng, đáng một câu riêng.** "Đọc được tên món, không
   đọc được tiền" là việc người dùng xử được (gõ tay số tiền), khác hẳn "ảnh không phải
   bill". Hôm nay hai thứ ra cùng một câu.
3. **`NO_ITEMS_READ` — đáng một câu riêng.** Mô hình nói đây là hoá đơn nhưng không thấy
   dòng nào: thường là ảnh cắt mất phần món. "Chụp lại cho thấy đủ danh sách món" là
   lời khuyên dùng được; "kiểm tra ảnh và thử lại" thì không.
4. **`EMPTY_IMAGE` · `INVALID_RECEIPT` · `INVALID_RECEIPT_ITEM` · `INVALID_CONFIDENCE` —
   không phải lỗi của người chụp.** Đây là reader trả về payload sai hợp đồng, tức lỗi
   phía máy chủ. Bảo người dùng "kiểm tra ảnh" là chỉ sai hướng — họ sẽ chụp lại mãi.
   rd-qa-05 đã đo đúng kiểu hỏng này một lần rồi.

**Cảnh báo khi sửa: log MÃ, không bao giờ log nội dung bill.** Ảnh bill và bản chép
của nó đều là dữ liệu riêng tư. Có một ca giữ đúng điều này (mục 6).

---

## 6. Cổng để lại — và bằng chứng chúng là cổng thật

`tests/qa/rd-qa-38/test_ma_loi_bill.py`, 12 passed + 2 xfailed, **tất định**, không
mạng, không khoá: fake reader phát lại đúng hình dạng quan sát được từ mô hình thật.

Hai `xfail(strict=True)` đã được chứng minh là cổng thật bằng cách nối bản vá ứng viên
vào rồi gỡ ra — không phải bằng một dòng đỏ:

```
12 passed, 2 xfailed     main @ 208c1d3, cây sạch
  ↓ nối bản vá `_read_quantity` đọc chuỗi trắng như "không có"
2 failed, 11 passed, 1 xfailed
   → test_quantity_rong_nen_doc_nhu_khong_co  XPASS(strict) → FAILED
   → test_quantity_rong_pha_huy_ca_hoa_don    đỏ đúng như docstring hứa
   → ca log VẪN xfail — hai cổng độc lập với nhau
  ↓ gỡ ra, nối bản vá logging `_log.warning("... code=%s", exc.code)`
1 failed, 12 passed, 1 xfailed
   → test_ma_loi_co_trong_log  XPASS(strict) → FAILED
   → test_log_khong_bao_gio_chua_noi_dung_bill VẪN XANH — bản vá đúng đi lọt
  ↓ đổi sang bản vá XẤU: log cả nội dung đọc được
1 failed  → test_log_khong_bao_gio_chua_noi_dung_bill  ĐỎ
  ↓ gỡ hết
git status services/api/ → sạch;  12 passed, 2 xfailed
```

Dòng áp chót là phần đáng giá: ca riêng tư **không phải** thứ trang trí xanh vĩnh viễn —
nó bắt được bản vá "log cho dễ debug" và chỉ để bản vá chỉ-log-mã đi qua.

---

## 7. Cổng đã chạy

```
python3 -m pytest services/api/tests tests -q
  → 1394 passed, 328 skipped, 2 xfailed, 4622 subtests passed  (89.70s)
python3 scripts/repo_guard.py tree HEAD   → Repo guard passed tracked tree: 692 file scan(s)
migration render ra DDL (không cần DB)    → ok
ruff check tests/qa/rd-qa-38/             → All checks passed
```

## 8. Ô CHƯA QUÉT — phần quan trọng nhất

- **Bill giấy thật, điện thoại thật: chưa.** Mọi ảnh đều sinh bằng Pillow, kể cả hai tấm
  "giống ảnh chụp". Kết luận về nguyên nhân (`quantity_text`) không phụ thuộc vào điều
  này — nó đo ở hình dạng payload, không ở chất lượng ảnh — nhưng **các con số tỉ lệ thì có**.
- **Mã VietQR chưa từng quét bằng app ngân hàng thật.** Vẫn nguyên trong ô chưa quét
  cho tới khi leader cầm điện thoại thật kiểm (ADR-0010 mục 8).
- **Chưa đo trên điện thoại thật** — toàn bộ đo qua HTTP và trong tiến trình.
- **Chưa thử bill có cột SL viết tay, bill nhiều trang, bill ngoại tệ.**
- **`tests/postgres` không chạy trong lượt này** (328 skipped). Việc này không chạm
  tầng persistence, nhưng nói ra để không ai đọc dấu xanh trên thành phủ kín.
- **Chưa đo `image/webp` và `image/png`** trên đường bill — chỉ JPEG.

## 9. Phân loại theo 5 loại blocker

| # | Phát hiện | Loại | Hậu quả | Tiêu chí gỡ chặn |
|---|---|---|---|---|
| 1 | `_read_quantity` giết cả hoá đơn vì một `quantity_text` rỗng | **type-4** hỏng tính hợp lệ | 45% lượt trên đường hero báo sai cho người dùng, trong khi AI đã đọc đúng | Nhận chuỗi trắng (và `'null'`, `'x4'`) như "không in số lượng"; `test_quantity_rong_nen_doc_nhu_khong_co` XPASS |
| 2 | 7 mã → 1 câu, máy chủ không log mã nào | **type-5** không tái lập được | Không ai chẩn đoán được lượt hỏng; header sai và bill không đọc được cùng một dòng log | Log **mã** (không log nội dung); `test_ma_loi_co_trong_log` XPASS, ca riêng tư vẫn xanh |
| 3 | `UNREADABLE_AMOUNT` / `NO_ITEMS_READ` dùng chung câu với "không phải bill" | suggestion | Người dùng chụp lại vô ích thay vì gõ tay số tiền | — (đề xuất, không chặn) |
| 4 | `sanitize_image` đổi tỉ lệ đọc theo chiều ngẫu nhiên (100%→0% trên `dai`) | **type-4** | Bản vá riêng tư là đúng và phải giữ, nhưng nó **không** là bản vá độ tin cậy; đừng ghi công nhầm | Sau khi sửa #1, đo lại 5 ảnh × n=20 hai nhánh |

**#209 vẫn nên ở lại.** Nó sửa đúng thứ nó nói là sửa (GPS không còn sang Gemini).
Đính chính duy nhất là đừng ghi cho nó một chiến công thứ hai mà nó không lập.

## 10. Nhắc lại điều không được bỏ

Repo này **chưa có bằng chứng hành vi nào** (ADR-0006, Giai đoạn 0 bị gác theo quyết
định của chủ sản phẩm). 290 lần gọi thật nói rằng code làm đúng điều tác giả nghĩ và chỉ
ra chỗ nó không làm đúng; chúng **không** nói người thật hiểu sản phẩm này.
