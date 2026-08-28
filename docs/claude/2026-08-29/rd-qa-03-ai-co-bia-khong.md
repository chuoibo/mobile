# rd-qa-03 — AI có bịa không

**FAIL**

**Lý do (đọc dòng này trước):** AI **từ chối thật thà** với ảnh không phải bill —
5/5 ca đối nghịch trả về 0 món và API trả 422. Nhưng có **hai chỗ nó bịa, và cả
hai đều đi thẳng ra HTTP 200 như số đã kiểm**: (1) ảnh **thực đơn** — một bảng
giá, không phải giao dịch — được đọc thành bill 8 món, `confidence` 95–100%,
**không một cảnh báo nào**; (2) khi ảnh mờ, model **chế ra số tiền** và API vẫn
trả 200 — ở mức tin cậy 70–75% thì **7/8 dòng sai**, một dòng lệch 40.000đ, mà
cảnh báo duy nhất hiện ra lại **y hệt** cảnh báo của một lần đọc đúng.

- protocol_version: v1
- Nhánh chứa code được kiểm: `backend/doc-bill-bang-gemini`
- **SHA đã kiểm: `a18a2051f8cf9cceb283ac6589ab369959ecf0f7`** (chưa merge vào `main`)
- Model: `gemini-2.5-flash`, `temperature=0.0`, response schema ép kiểu
- Ngày chạy: 2026-08-29

---

## 1. Bốn câu hỏi của việc, trả lời thẳng

| Câu hỏi | Trả lời |
|---|---|
| Ảnh không phải bill → nói không đọc được, hay bịa 8 món? | **Nói không đọc được.** 5/5: trắng, phong cảnh, nhiễu, thơ, ảnh mờ → 0 món, `confidence 0.0`, HTTP 422 |
| Hỏi AI về quán không có trong DB → bịa tên quán? | **Tính năng này không tồn tại.** Không có route gợi ý địa điểm nào trong sản phẩm |
| `AI MATCH 95%` có tái lập được không? | **Con số đó không tồn tại trong code.** Nó chỉ nằm trong mockup/spec; ADR-0009 quyết định 5 đã cấm hiện % |
| `AI suggested 92%` có phải số thật không? | Số % duy nhất **có thật** là `confidence` của `/receipts/scan`. Nó **do model tự khai**, có bám theo độ rõ của ảnh, nhưng **không bám theo độ đúng** — và **trôi giữa các lần gọi** |

---

## 2. Ca đối nghịch — kết quả từng ca

Ảnh sinh từ code, seed cố định (`tests/qa/rd-qa-03/adversarial_probe.py`).
Không ảnh nào được commit.

**Đối chứng dương (bắt buộc phải có):** không có ca này thì "0 món" chứng minh
harness của tôi hỏng cũng tốt như chứng minh model thật thà.

| Ca | Món đọc ra | `confidence` | Kết cục |
|---|---|---|---|
| **CONTROL — bill thật trong mockup** | 8 | 0.98 | **200** — đúng 8/8 dòng, tổng 1.125.000 ✅ |
| Ảnh trắng | 0 | 0.0 | 422 `receipt_unreadable` ✅ |
| Ảnh phong cảnh | 0 | 0.0 | 422 ✅ |
| Nhiễu RGB | 0 | 0.0 | 422 ✅ |
| Trang thơ tiếng Việt | 0 | 0.0 | 422 ✅ |
| Trang thơ làm mờ | 0 | 0.0 | 422 ✅ |
| **Ảnh THỰC ĐƠN** | **8** | **0.95–1.00** | **200 — SAI** ❌ |

Đối chứng dương đọc đúng cả 8 dòng và đúng tổng in `1.125.000`, nên năm ca trả
0 món là **từ chối thật**, không phải đường ống hỏng.

---

## 3. Phát hiện 1 — ảnh thực đơn được nhận là bill

Đi qua HTTP thật (`POST /receipts/scan`, reader Gemini thật):

```
=== menu: HTTP 200
{"items": [{"name": "Pho bo tai", "quantity": 1, "unit_price_vnd": 65000, "line_total_vnd": 65000},
           ... 8 món ...],
 "items_total_vnd": 340000, "total_vnd": null, "totals_agree": null,
 "confidence": 95, "warnings": []}

=== landscape: HTTP 422
{"code": "receipt_unreadable", "detail": "Không đọc được bill. Vui lòng kiểm tra ảnh và thử lại."}
```

Thực đơn **không phải giao dịch**: không ai gọi cả 8 món, không ai trả 340.000đ,
trên giấy không in tổng. Nhưng màn hình nhận được 8 món kèm đơn giá và một con số
340.000đ — **không phân biệt được** với một bill thật.

Vì sao lọt, hai nguyên nhân cộng lại:

1. **Prompt mặc định ảnh là bill.** `vision_gemini.py` mở đầu bằng
   `"Read this receipt and return only the fields in the response schema."`
   Nó *khẳng định* đây là receipt. Không có câu nào kiểu "nếu đây không phải
   hoá đơn thì trả items rỗng". Model làm đúng việc được giao — việc đó sai.
2. **`read_receipt` không có cổng "không in tổng".** Khi `total_text` là `None`,
   domain đặt `total_vnd=None`, `totals_agree=None` và **không thêm cảnh báo nào**
   (`app/domain/receipt.py`). Nghịch lý: bill *có* in tổng mà lệch thì **được**
   cảnh báo; tài liệu **không có gì đối chứng** thì **im lặng**. Ca ít bằng chứng
   hơn lại nhận ít cảnh báo hơn.

Đây là lỗi thật ngoài đời, không phải ca phòng thí nghiệm: ở quán, **thực đơn nằm
ngay trên bàn cạnh tờ bill**. Đây là ảnh chụp nhầm dễ xảy ra nhất.

---

## 4. Phát hiện 2 — ảnh mờ thì model chế số, API vẫn trả 200

Cùng một tờ bill, chỉ tăng Gaussian blur. Ground truth từ đối chứng dương:
`[219000, 149000, 128000, 198000, 79000, 79000, 28000, 94000]`, tổng in `1.125.000`.

| Blur | `confidence` | Đọc ra | Đúng? |
|---|---|---|---|
| r=0 | 0.98 | `[219, 149, 128, 198, 79, 79, 28, 94]`k | ✅ đúng cả 8 |
| r=4 | 0.95 | 8 món | — |
| **r=8** | **0.70–0.75** | `[219, 145, 129, 199, 75, 75, 28, 54]`k | ❌ **7/8 dòng sai**, dòng cuối lệch **40.000đ** |
| **r=12** | **0.30–0.40** | `[270, 140, 150, 180, 110, 70, 80, 30]`k | ❌ **sai toàn bộ**, tổng đọc thành 1.130.000 |

Cả bốn mức đều **HTTP 200**. Không có ngưỡng `confidence` nào chặn.

Chỗ nguy hiểm nhất nằm ở mức r=8: model đọc **đúng** tổng in `1.125.000` nhưng
**sai** các dòng. Cảnh báo duy nhất trả về là:

> "Tổng in trên bill chênh +193000 đồng so với tổng các dòng; giữ nguyên cả hai số."

Mà lần đọc **đúng** cũng sinh ra một cảnh báo cùng dạng (chênh +151.000, vì tờ
bill trong mockup vốn đã không cộng khớp). **Người dùng không có cách nào phân
biệt** "bill này vốn không khớp" với "AI đọc sai bốn dòng".

**Vì sao đây là chuyện tiền, không phải chuyện UX:** luồng hero là
*AI đọc từng món → gán món cho người → AI chia*. Allocator có 41 golden vector
tính tay và nó **không sai**. Nhưng 41 vector đó chứng minh phép chia đúng trên
**đầu vào đã cho**. Chia đúng một con số bịa vẫn ra một con số bịa — chia chính
xác tuyệt đối 54.000đ cho một món giá 94.000đ. Ba luật tiền không bị vi phạm ở
tầng domain, và tiền vẫn sai trên màn hình.

---

## 5. Con số `confidence` — nó là gì và không là gì

**Có tái lập được không? Không hoàn toàn.** 5 lần gọi giống hệt nhau, cùng ảnh,
`temperature=0.0`:

```
CONTROL-bill   conf=[0.98, 0.98, 0.98, 0.98, 0.98]   spread=0.00   (ổn định)
menu           conf=[1.00, 1.00, 0.95, 0.95, 0.95]   spread=0.05   (trôi)
```

Cùng một ảnh, cùng tham số, con số hiện cho người dùng đổi giữa **100%** và
**95%**. `temperature=0.0` không đảm bảo tất định.

**Nó có bám vào cái gì thật không?** Có một nửa: nó **bám theo độ rõ** của ảnh
(0.98 → 0.95 → 0.75 → 0.40 khi tăng blur). Nhưng nó **không bám theo độ đúng**:

- ở **0.70–0.75**, 7/8 dòng đã sai;
- ở **0.95–1.00**, một tờ **thực đơn** được nhận là bill.

Nói cách khác: `confidence` là "chữ có rõ không", người dùng sẽ đọc nó thành
"số có đúng không". Hai thứ đó **đã được đo là khác nhau**.

Điểm cần ghi công cho thiết kế hiện tại: `TheDeXuat.tsx` **cố ý không hiện %**
(ADR-0009 quyết định 5 — *"A percentage invites a rule"*). Quyết định đó đúng, và
`/receipts/scan` đang đi ngược lại nó bằng cách trả `confidence: 0–100` ra API.

---

## 6. Ba chỗ AI khác — trạng thái thật

| Bề mặt | Trạng thái | Bịa được không |
|---|---|---|
| Đọc bill (`/receipts/scan`) | **Thật**, Gemini live | **Có** — mục 3 và 4 |
| AI đọc chat rút khoản chi (`money_skill.py`) | **Thật**, có rào | **Đã chặn** — mọi khoản chi phải trích dẫn message nguồn; ungrounded bị bỏ (fail closed), kiểm cả ở server lẫn `extraction.ts` |
| AI gợi ý quán ăn | **Không tồn tại** | Không có route, không có code. Mockup có, sản phẩm không |

Rào grounding của luồng chat là cách làm đúng, và nó **chính là thứ luồng ảnh bill
đang thiếu**: mỗi con số phải chỉ được về chỗ nó đọc ra.

---

## 7. Phân loại blocker (charter, 5 loại)

**Loại 2 — sai tiền.** Cả hai phát hiện.

- **Dẫn chứng:** mục 3 và 4, SHA `a18a205`, chạy lại bằng
  `tests/qa/rd-qa-03/adversarial_probe.py`.
- **Hậu quả:** số tiền bịa vào thẳng đầu vào của allocator; nhóm bạn chia một
  con số chưa ai từng trả.
- **Tiêu chí gỡ chặn** (việc của lane backend, **không phải của tôi** — QA chứng
  minh, không sửa):
  1. Prompt không được mặc định ảnh là bill; phải cho model đường thoát "đây
     không phải hoá đơn" và `read_receipt` phải từ chối đường đó.
  2. `total_text is None` phải sinh cảnh báo — không có tổng in thì không có gì
     đối chứng các dòng.
  3. Phải có ngưỡng `confidence`: dưới ngưỡng thì từ chối, hoặc trả về ở dạng
     người dùng buộc phải nhập tay, không phải dạng số đã kiểm.
  4. Cảnh báo "tổng lệch" phải phân biệt được *bill vốn không khớp* với
     *đọc không chắc*.

---

## 8. Ô CHƯA quét — đọc kỹ phần này

- **Ảnh bill thật chụp bằng điện thoại thật.** Toàn bộ kết luận trên chạy trên
  tờ bill **vẽ trong mockup**. Giấy thật có nếp gấp, bóng, in kim mờ, chữ nghiêng.
  Chưa ai chụp một tờ bill thật đưa vào đường này.
- **Bill nhiều trang, bill có giảm giá / VAT / phí phục vụ.** Chưa quét.
- **Ảnh chụp nghiêng, ngược sáng, chụp qua màn hình.** Chưa quét.
- **`tests/postgres`: 63 skipped** trong lượt gate (không có DATABASE_URL).
  Skip không phải xanh — nhưng không ca nào trong đó chạm luồng đọc bill.
- **Prompt injection qua ảnh** (chữ trong ảnh ra lệnh cho model). Chưa quét.
- **Mã QR quét bằng app ngân hàng thật.** Vẫn chưa ai làm — ngoài phạm vi việc
  này, ghi lại để không bị coi là đã phủ.
- **Chi phí và độ trễ** của `/receipts/scan` dưới tải. Chưa đo.

---

## 9. Lệnh đã chạy

```bash
# Cổng repo, trên SHA đang kiểm, cây sạch
cd /tmp/qa03/wt && python3 -m pytest services/api/tests tests -q
# → 534 passed, 63 skipped, 4281 subtests passed in 13.20s

# Ca đối nghịch + đối chứng dương (Gemini thật)
set -a; . /home/lakiet/mobile/.env; set +a
python3 tests/qa/rd-qa-03/adversarial_probe.py

# Đường HTTP thật, reader Gemini thật
# menu → 200 (8 món, confidence 95, warnings [])
# landscape → 422 receipt_unreadable
```

`GEMINI_API_KEY` đọc từ `.env` ngoài repo, không in ra log, không vào Git.
Không ảnh nào được commit.
