# PASS — #450 (allocator từ chối float và bool)

Đường vòng `model_construct` mà qa2 để hở ở #452 **đã bị đóng**, và đóng ở đúng chỗ
nó đáp xuống — không phải lớp thứ hai cho một cửa đã có rào.

```
verdict          PASS
protocol_version v1
đo tại           7496c3d  = 20a4607 (#450) ⊕ origin/main@cf16166
xác nhận lại     ba025e9  = 20a4607 (#450) ⊕ origin/main@0c04cb7   (main nhích 2 commit giữa lượt)
sha này          là cây GỘP, chưa merge. PR head 20a4607 chưa ở main.
blocker còn mở   không có
```

Main nhích hai lần trong lượt đo (`3a322a1` → `cf16166` → `0c04cb7`). Hai commit
mới (#455 màn thanh toán, #456 cổng ruff) **không đụng file nào của #450**; tôi vẫn
gộp lại lên `0c04cb7` và chạy lại các chặng có thể tương tác — xem mục 5.

---

## 1. Ba câu Lead hỏi, trả lời trước phần chi tiết

| # | Câu | Trả lời |
|---|---|---|
| 1 | `allocate()` giờ từ chối float **và** bool? | **CÓ.** 28/28 ô đo ra `AMOUNT_NOT_INTEGER`; bản trước vá 0/28 |
| 2 | Có đóng được đường `model_construct`, hay chỉ thêm lớp cho chỗ đã an toàn? | **ĐÓNG ĐƯỢC.** Và đóng thêm một đường thứ hai pydantic chưa bao giờ với tới |
| 3 | 41 golden vector còn xanh? danh sách slot tiền có suy ra từ corpus? | **Xanh. Có suy ra** — nhưng con số "41" trong mô tả PR không phải con số bị đầu độc; xem mục 4 |

---

## 2. Câu 1 — float và bool, đo bằng hành vi

Nền dương lấy từ chính corpus (vector G22, 7 slot tiền), không viết tay. Mỗi slot bị
đầu độc một lần bởi bốn hình dạng. Cùng một script chạy trên hai cây, chỉ đổi cây:

```
                          bản TRƯỚC vá      cây gộp có #450
số ô trả AMOUNT_NOT_INTEGER    0/28              28/28
```

Bản trước vá trả về gì ở 28 ô đó: `RECONCILIATION_MISMATCH` (đúng mã, sai lý do),
`DISCOUNT_EXCEEDS_ITEM`, `ZERO_AMOUNT`. Không ô nào nói được chuyện thật đã xảy ra.

**Ca tiền SAI im lặng — cái đáng lo nhất — tái lập được ở bản trước vá:**

```
                                        TRƯỚC vá                     SAU vá
total=True, item=True            -> TRẢ VỀ {a: 1, b: 0}       -> AMOUNT_NOT_INTEGER
even-split total=True            -> TRẢ VỀ {a: 1, b: 0}       -> AMOUNT_NOT_INTEGER
even-split total=300.5           -> TypeError THOÁT RA (→500) -> AMOUNT_NOT_INTEGER
even-split total=300.0           -> TypeError THOÁT RA (→500) -> AMOUNT_NOT_INTEGER
total=301, item=300.5            -> RECONCILIATION_MISMATCH   -> AMOUNT_NOT_INTEGER
```

`True` **thật sự thành một đồng và được trả về**, không ném gì. Đó là điều kiện
"đỏ trước khi sửa" — không có nó thì bản vá không chứng minh gì.

Một hệ quả tôi đo thêm, PR không nêu: `total_vnd=None` trước vá cũng thoát
`TypeError` → HTTP 500; sau vá ra `AMOUNT_NOT_INTEGER` → 422 sạch.

**Bool có được chặn riêng không, hay chỉ ăn theo?** `isinstance(True, int)` là `True`,
nên câu này phải đo riêng. Đột biến D2 — thay `vnd_violation(amount) == NOT_INTEGER`
bằng `isinstance(amount, int)` trần:

```
D2  quên chặn bool    cổng mới ĐỎ (SUBFAILED tại poison='bool_false')   41 golden vẫn xanh
```

Cổng **phân biệt được** "quên bool" với "quên hẳn". Bản vá dùng lại
`money._not_an_integer` (`isinstance(v, bool) or not isinstance(v, int)`) chứ không
viết lại `isinstance` tại chỗ — nên không sinh bản sao thứ 14 sau khi #437 vừa gộp 13.

---

## 3. Câu 2 — đường `model_construct`. Đây là câu quan trọng nhất

**Kết luận: #450 đóng được nó, và đây không phải lớp thứ hai cho cửa đã có rào.**

Lý do nằm ở *hướng*. Rào pydantic đứng ở biên HTTP. `model_construct` đi **vòng qua**
rào đó. Phép kiểm của #450 đặt ở **tầng domain**, tức là ở *phía dưới* chỗ đường vòng
đáp xuống. Nó không phải lớp thứ hai chồng lên rào — nó là lớp **thứ nhất** ở chỗ
trước đây không có lớp nào.

Đo bằng **chính probe của qa2 ở #452**, không sửa một dòng, chỉ đổi cây:

```
ĐO 3 — biên HTTP                 số thân phi-int lọt: 0/5   (nền dương 201: máy chủ sống)
                                 → #450 KHÔNG làm hỏng rào sẵn có

ĐO 4 — model_construct           _allocator_input(...)['total_vnd'] = 82000.5 (float)
                                 (rào có ép kiểu không? KHÔNG — vẫn là ống dẫn thuần)
                                 allocate(...) -> AMOUNT_NOT_INTEGER      ← ĐƯỜNG VÒNG BỊ ĐÓNG

ĐO 4 — đường thứ hai, bill        printed_total_vnd=None -> total_vnd cộng ra 90000.5 (float)
                                 allocate(...) -> AMOUNT_NOT_INTEGER
```

Đo lại chính hai ca đó trên bản **trước** vá, cùng cây, chỉ gỡ bản vá:

```
model_construct total=82000.5 -> TypeError thoát ra ngoài  (→ HTTP 500)
model_construct total=True    -> TRẢ VỀ {…: 1, …: 0}       ← đường vòng CÒN HỞ, và ra tiền sai
```

**Bằng chứng mạnh nhất: probe của qa2 tự khai phép đo của chính nó đã hỏng.** Nó được
viết ra để chứng minh cái lỗ; trên cây gộp nó không chứng minh được nữa:

```
TỰ KIỂM PHÉP ĐO
PHÉP ĐO NÀY HỎNG -- đừng đọc kết luận ở trên:
   !! ĐO 1: mọi ca đều bị chặn -- phát hiện của backend KHÔNG tái lập
   !! ĐO 2a: bool bị chặn -- khác kết luận backend
   !! ĐO 8: ca True tự khớp bị chặn -- kết luận cần viết lại
```

Dòng ĐO 8 đáng đọc kỹ. qa2 đã chỉ ra rằng `RECONCILIATION_MISMATCH` bắt được mấy ca
kia chỉ vì **may** (1 ≠ 60000), và nêu đúng hình dạng nó *không* bắt được — một bill
mà con số `True` tự khớp với chính nó. Trên cây gộp:

```
bill 1 món, amount=True, printed_total=True -> AMOUNT_NOT_INTEGER
```

Đó là ca duy nhất không có gì khác đỡ được, và #450 là thứ đỡ nó.

Ba call site `allocate()` trong `service.py` (3624 bill · 3636 propose · 3754 confirm)
đều bọc `except AllocationError -> ApiProblem(422)`, nên mã mới ra 422 chứ không 500.

---

## 4. Câu 3 — 41 golden vector, và danh sách slot có thật sự suy ra không

**41 vector còn xanh.** `tests/domain`: 746 passed, 4644 subtests, 0 failed.

**Danh sách slot CÓ suy ra**, không viết tay: `money_slots()` đi bộ mọi lá có khoá kết
thúc `_vnd` trong `input` của từng vector. Không tên trường nào được gõ ra.

**Một chỗ cần chỉnh cho đúng trong mô tả PR** (không phải blocker, là độ chính xác của
con số): PR viết "suy ra từ chính 41 golden vector", đọc như thể cả 41 đều bị đầu độc.
Đếm bằng máy:

```
tổng vector trong corpus              : 41
vector có khoá 'expect' (cổng đi qua) : 23      ← lọc bỏ 18 vector lỗi
vector cổng KHÔNG đi qua              : 18
tổng slot tiền cổng đầu độc           : 50
tổng ca độc = 50 slot × 4 hình dạng   : 200
```

Phép suy ra *đọc* cả corpus; phép *đầu độc* phủ 23/41. Con số 200 khớp với bảng đột
biến của PR (M1 → 201 failed = 200 + 1 ca ưu tiên). Không ai nói sai, nhưng chữ "41"
trong câu đó không phải mẫu số của phép đo.

**Phép đếm hai chiều `1 + len(items) + len(surcharges) + len(discounts)` là viết tay** —
và đó là điều đúng: một collection tiền thứ tư sẽ làm hai phép đếm lệch nhau → cổng đỏ
to, không im lặng.

### Một điểm yếu tôi tìm được, PR chưa thử (D1) — suggestion, KHÔNG phải blocker

Cả hai phép tự kiểm đều lấy sàn là `assertGreater(checked, 0)`. Tôi đột biến
`success_vectors()` để chỉ trả **vector đầu tiên**:

```
D1  tháo MỘT PHẦN: success_vectors() chỉ trả 1 vector    cổng mới: 7 passed — VẪN XANH
```

Sàn `> 0` chỉ bắt được **gỡ hẳn**, không bắt được **tháo một phần**. Corpus tụt từ 23
vector / 50 slot xuống 1 vector / 3 slot mà cổng không kêu. Đây là hình dạng repo này
đã gặp ("cổng một ca âm chỉ bắt gỡ hẳn").

Phân loại theo 5 loại blocker của charter: **không thuộc loại nào**. Hôm nay cổng đang
nạp đủ 50 slot và xanh; không có gì sai đang chạy. Đây là gia cố chống người sửa sau
này. Cách gỡ nếu ai muốn làm: ghim `checked` vào con số suy ra từ corpus
(`sum(len(money_slots(v)) for v in success_vectors()) * 4`) thay vì `> 0`.

Hai đột biến còn lại xác nhận cổng gác đúng hai chiều:

```
M0  bản vá nguyên vẹn                        cổng mới XANH   41 golden XANH
D1  tháo một phần corpus                     cổng mới XANH   ← lỗ, xem trên
D2  quên chặn bool (isinstance trần)         cổng mới ĐỎ     41 golden XANH
D3  dời phép kiểm xuống sau ZERO_AMOUNT      cổng mới ĐỎ     (ghim được ưu tiên)
```

---

## 5. Cổng đã chạy — số thật

Tại `7496c3d` (#450 ⊕ main@cf16166), cây sạch (`git status` rỗng trước mỗi lượt đo):

```
python3 -m pytest services/api/tests tests -q
  -> 2806 passed, 580 skipped, 5272 subtests passed        (327s)

580 skip KHÔNG được đọc là xanh. Chạy lại đúng tầng đó với Postgres thật:
scripts/postgres_tier.sh --keep    (database dùng một lần, không đụng schema lane khác)
  -> tests/postgres   523 passed, 0 skipped
  -> tests/qa          89 passed, 0 skipped

rồi chạy LẠI CẢ CỔNG với MOBILE_TEST_DATABASE_URL + MOBILE_REQUIRE_POSTGRES_TESTS=1:
  -> 3346 passed, 40 skipped, 5272 subtests passed         (457s)
     540 skip đã đóng. 40 skip còn lại là tầng Gemini live
     (cần GEMINI_API_KEY + MOBILE_REQUIRE_GEMINI_TESTS=1) — không liên quan diff này.

cd apps/mobile && npm test
  -> tests 1003 · pass 1003 · fail 0 · skipped 0

make gate
  -> ĐẠT 17   HỎNG 1   BỎ QUA 0
     đạt: guard guard-range ruff contract client-routes server-routes screens cors
          api migration pinned-import demo-watch shared mobile docker postgres e2e
     hỏng: hero-walk

$(scripts/ruff_pinned.sh) --version         -> ruff 0.9.2
  check <3 file đã sửa>                     -> All checks passed!      (exit 0)
  format --check <3 file đã sửa>            -> 3 files already formatted (exit 0)
python3 scripts/repo_guard.py tree HEAD     -> passed, 1296 file scan(s)
```

### `hero-walk` HỎNG là nợ có sẵn — đo, không phải tin lời PR

PR khẳng định chặng này đỏ sẵn trên main. Tôi không nhận khẳng định, tôi đứng lên
`origin/main` và chạy chính chặng đó:

```
git checkout origin/main            (0c04cb7)
scripts/gate.sh hero-walk           -> ĐẠT 0   HỎNG 1
   "lượt đi bộ chạy ở client cd1e97a, KHÔNG nằm trong HEAD 0c04cb7 — nhánh khác"

git merge-base --is-ancestor cd1e97a origin/main   -> KHÔNG
git merge-base --is-ancestor cd1e97a HEAD          -> KHÔNG
```

Chặng này đỏ **y hệt trên main khi không có #450**. Hiện vật đi bộ thuộc một nhánh
client khác. Không phải lỗi của PR này.

### Xác nhận lại trên main mới nhất (`ba025e9` = #450 ⊕ `0c04cb7`)

Main nhích thêm 2 commit giữa lượt đo, một trong đó (#456) **đổi chính cổng ruff**,
nên tôi gộp lại và chạy lại các chặng có thể tương tác:

```
gộp lại 20a4607 lên 0c04cb7   -> sạch, đúng 4 file, không xung đột
scripts/gate.sh ruff          -> ĐẠT
scripts/gate.sh contract      -> ĐẠT (139 lời gọi đều gửi X-Actor-ID)
scripts/gate.sh guard         -> ĐẠT
scripts/gate.sh migration     -> ĐẠT
pytest tests/domain -q        -> 746 passed, 4644 subtests
ma trận 28 ô                  -> 28/28 AMOUNT_NOT_INTEGER
```

---

## 6. Ô CHƯA quét — đọc phần này trước khi đọc chữ PASS là "đã kín"

- **Tầng Gemini live (40 skip)** — không chạy lượt này, không đặt `GEMINI_API_KEY`.
  Diff của #450 là 2 file domain + 1 test + 1 ADR, không chạm đường AI.
- **`budget.py`** — ô QA ghi là chưa quét ở #445, vẫn chưa quét. #450 không nhận là
  đã đóng nó. (`bill.py` thì tôi CÓ đo *đường đi vào allocate()* ở mục 3, và nó được
  phủ; module bill như một tổng thể thì vẫn chưa.)
- **Slot tiền không xuất hiện trong bất kỳ golden vector nào** (trường khai mặc định
  `None`) — máy đi bộ theo *giá trị* không thấy được. Chính docstring của cổng nói
  ra chuyện này; nó giữ khoảng trống **nhìn thấy được**, không đóng.
- **56 ô tiền khai trong `schemas.py`** (probe qa2, ĐO 8) — `allocate()` chỉ phủ các
  slot thuộc hợp đồng allocator. Tiền không bao giờ đi qua `allocate()` không được
  lượt này trả lời.
- **`hero-walk` cho nhánh này** — không chạy, và tôi **cố ý không** bôi xanh nó. Máy
  demo đứng ở main, một lượt đi bộ trên đó đo code của main chứ không đo phép kiểm
  đang cần chứng minh.
- **Mã QR quét bằng app ngân hàng thật** — vẫn là ô của leader, một điện thoại thật,
  15 phút. Không agent nào quét được mã QR.
- **Ma trận ảnh trang khách** — không quét; PR không chạm `app/web/`.

Và câu không được bỏ: repo này **chưa có bằng chứng hành vi nào** (ADR-0006). Một bộ
test xanh nói code làm đúng điều tác giả nghĩ; nó không nói người thật hiểu sản phẩm.

---

## 7. Phán quyết

**PASS.** #450 đóng được đường `model_construct` — đường mà qa2 đo là còn hở ở #452 —
và đóng nó ở tầng domain, chỗ đường vòng đáp xuống, chứ không phải chồng lớp lên rào
pydantic đã có. Nó còn đóng thêm đường bill mà pydantic chưa bao giờ với tới, gồm
đúng ca `True` tự khớp mà `RECONCILIATION_MISMATCH` không bắt được. Đối chứng đỏ→xanh
tái lập được hai chiều, 41 golden vector không đổi, ba tầng cổng xanh, `hero-walk` đỏ
sẵn trên main.

Không có blocker. Một suggestion (D1, sàn `> 0` của cổng mới) không thuộc năm loại
blocker và không cản merge.

## Hiện vật

- `services/api/tests/qa/qa-tt-0057-gac-450/probe_ma_tran_slot_tien.py` — ma trận
  slot × hình dạng, nền dương lấy từ corpus, tự đỏ nếu nền dương hỏng.
- `services/api/tests/qa/qa-tt-0057-gac-450/probe_duong_vong_model_construct.py` —
  ca tiền sai im lặng + đường vòng `model_construct`; chạy được trên cả hai cây.
- `services/api/tests/qa/qa2-082907-luat-1-o-allocator/probe_duong_di_cua_mot_so_tien.py`
  — của qa2, chạy nguyên vẹn, tự khai đã hỏng trên cây gộp.
