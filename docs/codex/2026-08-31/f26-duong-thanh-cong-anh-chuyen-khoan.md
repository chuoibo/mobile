# F26 — đường THÀNH CÔNG của "ảnh chụp màn hình → khoản chi", chạy thật một lần

```
protocol_version  v1
đo tại            43dc45a = origin/main, KHÔNG sửa một dòng mã sản phẩm
                  nhánh này chỉ thêm một probe mà pytest không thu (không có tiền tố test_)
máy chủ           uvicorn dựng bởi scripts/e2e_slice.sh --keep từ chính cây này,
                  PostgreSQL 16 dùng một lần, Gemini THẬT (GEMINI_API_KEY từ .env)
người đo          lane backend, việc "F26 đường thành công" (backend-022247)
kỹ năng đã gọi    superpowers:test-driven-development · superpowers:systematic-debugging
                  superpowers:verification-before-completion
```

Lead hỏi ba câu. Trả lời ngắn trước, bằng chứng ở dưới.

1. **Đường thành công đã bao giờ chạy chưa?** Rồi — và bây giờ đã chạy trên **ảnh
   chuyển khoản ngân hàng**, thứ chưa ai đo. Lượt F26 duy nhất có hồ sơ trước đây
   (`tests/qa/qa-tt-0034`, 2026-08-30) đọc ảnh Grab và ShopeeFood rồi **dừng ở thẻ
   kết quả**. Hai điều chưa ai đo: máy đọc làm gì với ảnh *banking*, và con số nó
   đọc ra có vào được sổ không. Lượt này đo cả hai.
2. **Đọc ra được số tiền không?** **Có, đúng từng đồng.** `450.000 VND` → `450000`,
   `180.000 VND` → `180000`. Số nguyên đồng, không qua float.
3. **Đọc ra được NGƯỜI NHẬN không?** **Không — và đó là cố ý, không phải lỗi.**
   Contract F26 **không có trường người nhận**. `app/domain/screenshot.py` từ chối
   cả lượt đọc nếu model trả về khoá trông giống danh tính (`recipient` nằm ngay
   trong `_IDENTITY_KEY_FRAGMENTS`) → `422 screenshot_model_named_a_person`.
   Cái duy nhất trả về là `merchant`, và trên màn chuyển khoản nó **không ổn định**:
   xem phát hiện PH-1.
4. **Kết quả có vào được sổ không?** **Có** — nhưng không tự động. `KetQuaQuetAnh`
   bấm "Chốt" chỉ **đổ số vào form nhập tay** (`occasion = merchant`,
   `amount = total_vnd`); người dùng chọn ai chia rồi mới gửi. Tôi đi đúng đường
   đó bằng HTTP thật: `POST /expenses` → `confirm` → số dư đọc lại từ sổ đã đổi.

---

## 1. Bằng chứng — output thật, không tóm tắt

Ảnh mẫu do chính probe vẽ ra từ hằng số trong code: không bill thật, không số tài
khoản thật, không tên người thật (`NGUYEN VAN MAU`, `QUAN NUONG SO 7`, số tài khoản
che `**** **** 8901`). Ảnh **không** vào Git — repo guard fail closed với binary, và
đó là câu trả lời đúng.

Hai ảnh **giống hệt nhau về bố cục**, chỉ khác tên người nhận: một bên là quán, một
bên là người. Đó là điều kiện để so sánh có nghĩa.

```
POST /screenshots/scan  [quán ăn] -> 200
  {"source": "banking", "merchant": "QUAN NUONG SO 7",
   "total_vnd": 450000, "occurred_on": "2026-08-30", "needs_review": true}

POST /screenshots/scan  [người]   -> 200
  {"source": "banking", "merchant": "Ngân hàng Mẫu (DEMOBANK)",
   "total_vnd": 180000, "occurred_on": "2026-08-30", "needs_review": true}
```

Chạy hai lượt, cách nhau vài phút, `temperature=0`: **hai lượt ra chữ giống hệt
nhau**, kể cả cái sai ở PH-1. Nên PH-1 không phải một lần model lỡ tay.

Rồi con số đó đi vào sổ:

```
--- vào sổ từ ảnh [quán ăn] ---
  POST /expenses            -> 201
  allocation                {payer: 150000, bạn A: 150000, bạn B: 150000}
  Σ phân bổ                 450000                <- đúng bằng total_vnd, luật 2
  POST .../confirm          -> 201
  ghi vào sổ                version 1, tổng 450000
  sổ · Người trả trước       spend 150000  settled 150000  outstanding 0
  sổ · Bạn A                 spend 150000  settled 0       outstanding 150000
  sổ · Bạn B                 spend 150000  settled 0       outstanding 150000

--- vào sổ từ ảnh [người] ---
  POST /expenses            -> 201
  Σ phân bổ                 180000
  POST .../confirm          -> 201
  ghi vào sổ                version 1, tổng 180000
  sổ · Người trả trước       spend 210000  settled 210000  outstanding 0
  sổ · Bạn A                 spend 210000  settled 0       outstanding 210000
  sổ · Bạn B                 spend 210000  settled 0       outstanding 210000
```

`210000 = 150000 + 60000` — số dư cộng dồn đúng hai khoản chi, và nó đến từ
`GET /people/{id}/finance`, tức là **tính lại từ sổ**, không phải từ cache của
màn hình. Luật 3 giữ nguyên.

## 2. Cái này KHÔNG chứng minh gì

- **Không** chứng minh app điện thoại vẽ ra đúng những số này. Tôi gọi HTTP, không
  bấm màn. Đường bấm trên `App.tsx` (chọn ảnh → `quetAnhChupMan` → `KetQuaQuetAnh`
  → Chốt → form) đã đọc mã và đã có người đi qua ở qa-tt-0034, nhưng **không phải
  lượt này** và **không phải trên ảnh chuyển khoản**.
- **Không** chứng minh model ổn định qua các bản Gemini khác, qua ảnh chụp app ngân
  hàng thật (giao diện tối, tiếng Anh, layout khác), hay qua ảnh chụp bị cắt.
- **Không** chứng minh người thật hiểu tấm thẻ kết quả.
- Hai ảnh, một bố cục. Bố cục ngân hàng Việt Nam thật thì nhiều hơn hai.

## 3. Phát hiện

### PH-1 · Chuyển khoản cho MỘT NGƯỜI thì tên khoản chi thành tên ngân hàng

Theo 5 loại blocker của charter thì đây **không** phải blocker: không sai tiền,
không rò rỉ, không hỏng cổng. Là **suggestion**, nhưng đúng thứ sẽ hiện lên màn
trong buổi demo nên tôi để lên đầu.

Cùng một bố cục, cùng một nhãn `Người nhận`:

| ảnh | `Người nhận` in trên ảnh | `merchant` máy chủ trả |
|---|---|---|
| chuyển khoản cho quán | `QUAN NUONG SO 7` | `QUAN NUONG SO 7` ✔ |
| chuyển khoản cho người | `NGUYEN VAN MAU` | `Ngân hàng Mẫu (DEMOBANK)` ✘ |

Vì `merchant` là thứ `onChot` đổ vào ô "Khoản chi" của form, khoản chi trong sổ sẽ
mang tên **"Ngân hàng Mẫu (DEMOBANK)"** thay vì thứ gì đó nói lên bữa ăn.

Đây **không phải model lỗi** — nó đang làm đúng điều prompt dặn:
`screenshot_gemini.py` viết thẳng *"Do not name any person"*, nên gặp tên người ở
ô `merchant` nó né sang thứ khác trên màn. Nói cách khác, luật "danh tính không bao
giờ đến từ model" (đúng, giữ nguyên) trả giá bằng việc **chuyển khoản P2P — đúng
cái người ta làm khi trả tiền cho bạn — cho ra một cái tên vô nghĩa.**

Không đề xuất sửa ở PR này: đổi prompt là đổi hành vi một cửa tiền, và tôi chưa có
đủ ảnh để biết bản sửa nào không làm hỏng ca Grab/ShopeeFood đang chạy tốt. Nếu Lead
muốn, hướng rẻ nhất là để `merchant` rỗng khi `source == "banking"` và cho form
dùng **nội dung chuyển khoản** ("Tra tien an toi thu Bay") làm tên gợi ý — chữ đó
do chính người dùng gõ lúc chuyển tiền, không phải danh tính model bịa ra.

### PH-2 · `occurred_on` đọc đúng ngày, kể cả khi ảnh ghi dd/mm/yyyy

`30/08/2026 21:15` → `"2026-08-30"`. Không nhầm sang tháng 8 ngày 30 kiểu Mỹ. Ghi
lại vì đây là chỗ dễ sai và lượt này nó đúng.

## 4. Chạy lại

```bash
scripts/e2e_slice.sh --keep                    # in ra URL của API dùng một lần
cd services/api
set -a; . <gốc repo>/.env; set +a              # GEMINI_API_KEY
python3 tests/live/probe_f26_bank_transfer.py --api http://127.0.0.1:<port>
```

Probe không có tiền tố `test_` nên `pytest` **không** thu nó: nó gọi mạng, tốn tiền,
và phụ thuộc một bản model không ai ghim. Cùng quy ước với
`tests/live/probe_document_gate.py` đã có sẵn.
