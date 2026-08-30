# "Bảy cửa tiền" của #416 là số ĐẾM ĐƯỢC, không phải tổng số đường thật

- **Việc**: lane backend, đo đạc theo yêu cầu của Lead (ưu tiên 2, không sửa code)
- **Đo tại**: `88c3259` (nhánh `backend/tu-vung-im-lang-cua-ai-turn`, dựng thẳng trên `origin/main@723abc8`)
- **PR được đo**: #416 tại head `2774f3e` — **chưa merge**, và tôi **không chạm** vào nhánh đó
  (đọc bằng `git fetch` + worktree detached ở `/tmp`, đã gỡ; `FETCH_HEAD` vẫn `2774f3e` sau khi đo)
- **Không sửa một dòng code sản phẩm nào.** Tài liệu này là toàn bộ hiện vật.

## Câu trả lời ngắn

**7 là số đường tôi đếm được, không phải tổng số đường thật.** Cụ thể hơn:
7 = `len(app.domain.ledger.__all__) - 2` (`LedgerError`, `require_vnd`).
Nó là số **tên export** của **một module**, không phải số chỗ tiền đi vào sổ cái.

Và Lead nghi đúng: **bản vá lặp lại đúng lỗi nó đang sửa**, chỉ ở một trục khác.

- Ca cũ `test_floats_and_bools_are_refused_everywhere` mù vì đếm theo **hàm** (1/7).
- Ca mới `EveryMoneyEntryPointRefusesAFloat` mù vì đếm theo **tên export**, trong khi
  tiền đi vào theo **tham số**. Một hàm có hai tham số tiền được "phủ đủ" chỉ bằng
  cách kiểm một tham số.

**Có đường thứ 8, và nó nằm trong chính hàm mà #416 vừa sửa.**

## Đường thứ 8: `obligation_status(declared_amount_vnd)`

`ledger.py:197` (bản của #416) tự viết `if declared_amount_vnd <= 0` thay vì gọi
`require_vnd` — **đúng cái hình dạng** mà #416 tìm ra ở `confirmed_total`, cách đó
52 dòng, trong cùng một file, ở tham số bên cạnh.

Đo trên `ledger.py` của head #416 (`2774f3e`):

```
--- probe A: obligation_status, float ở ô CONFIRMATIONS (cái FLOAT_PROBES kiểm) ---
  LedgerError AMOUNT_NOT_INTEGER          <-- từ chối

--- probe B: obligation_status, float ở ô DECLARED (không ai kiểm) ---
  declared=3.5          RETURNED 'partially_confirmed'   <-- KHÔNG lỗi
  declared=3.0          RETURNED 'confirmed'             <-- KHÔNG lỗi
  declared=300000.7     RETURNED 'partially_confirmed'   <-- KHÔNG lỗi
  declared=True (bool)  RETURNED 'over_confirmed'        <-- KHÔNG lỗi
```

`declared_amount_vnd` là **mệnh giá của nghĩa vụ** — con số trả lời "người này nợ
bao nhiêu". `True` đi qua thành 1 đồng, nên mọi khoản đã xác nhận > 1 đồng đọc ra
`over_confirmed`.

### Bảng đầy đủ ở mức THAM SỐ (không phải mức hàm)

`ledger.py` có **9 tham số tiền**, không phải 7 cửa. 8 từ chối float, 1 nhận:

| # | tham số tiền | float `0.5` | gác bởi | có trong `FLOAT_PROBES`? |
|---|---|---|---|---|
| 1 | `obligations_from_allocations(allocations.values)` | `AMOUNT_NOT_INTEGER` | `require_vnd` | có |
| 2 | `merge_obligations(obligations[].amount_vnd)` | `AMOUNT_NOT_INTEGER` | `require_vnd` | có |
| 3 | `confirmed_total(confirmations[].amount_vnd)` | `AMOUNT_NOT_INTEGER` | `require_vnd` (#416 thêm) | có |
| 4 | `obligation_status(receipt_confirmations)` | `AMOUNT_NOT_INTEGER` | qua `confirmed_total` | có |
| **5** | **`obligation_status(declared_amount_vnd)`** | **`'over_confirmed'`** | **KHÔNG CÓ GÌ** (`<= 0` tự viết) | **KHÔNG** |
| 6 | `group_balances(obligations[].amount_vnd)` | `AMOUNT_NOT_INTEGER` | `require_vnd` | có |
| 7 | `group_balances(receipts.values)` | `AMOUNT_NOT_INTEGER` | `require_vnd` | **KHÔNG** (probe chỉ đưa float vào ô `obligations`) |
| 8 | `settlement_plan(balances.values)` | `AMOUNT_NOT_INTEGER` | isinstance tự viết | có |
| 9 | `settlement_suggestions(balances.values)` | `AMOUNT_NOT_INTEGER` | uỷ quyền `settlement_plan` | có |

Hàng 7 đáng ghi riêng: `group_balances` có **hai** ô tiền, probe đưa float vào một ô
và xanh. Ô kia may mà có `require_vnd`. Đó là **cùng một lỗ hổng cấu trúc** với hàng 5,
chỉ khác là lần này bản vá tình cờ đúng.

### Ca chống mục ruỗng của #416 không thể bắt được đường 8

`test_the_probe_list_covers_every_export_that_takes_money` so `set(FLOAT_PROBES)` với
`set(ledger.__all__)`. Nó gác **tên**, nên nó xanh khi một export CÓ SẴN mọc thêm một
tham số tiền không được gác.

**Đột biến D4** (chạy trong worktree detached ở `/tmp/wt416`, đã gỡ; nhánh #416 không bị chạm):
cho `merge_obligations` thêm một tham số tiền mới `rounding_fee_vnd`, cộng thẳng vào
`amount_vnd`, không kiểm gì.

```
D4 mutation applied: merge_obligations gained an unguarded money parameter
30 passed, 10 subtests passed in 0.03s        <-- XANH

merge_obligations([...], 0.5) -> amount_vnd = 100.5   <-- float đã vào sổ cái
```

Đối chiếu: D2 của #416 (thêm một **export** mới, không thêm probe) thì **ĐỎ**.
Vậy cổng phân biệt được "export mới" nhưng mù với "tham số mới" — và đường 8 đang
sống đúng trong điểm mù đó. Chính bộ ca của #416 xanh `30 passed, 10 subtests passed`
trong khi đường 8 mở.

## Mức nghiêm trọng — nói thẳng, giống #416

**Tiềm ẩn, không phải tiền đang chảy sai.** Bốn chỗ gọi `obligation_status` đều lấy
`declared_amount_vnd` từ `obligation.amount_vnd` / `target.amount_vnd`:

```
app/api/repository.py:3849   obligation.amount_vnd     (cột DB)
app/api/repository.py:4113   obligation.amount_vnd     (cột DB)
app/api/service.py:4213      target.amount_vnd         (dataclass từ repository)
app/api/service.py:4313      target.amount_vnd         (dataclass từ repository)
```

Quét cơ học `app/db/models.py`: **21/21 cột tiền là `BigInteger`**, 0 cột không nguyên.

```
21 money columns:  19 × Mapped[int] <- BigInteger,  2 × Mapped[int | None] <- BigInteger
non-integer-typed money columns: NONE
12 tên cột: amount_vnd, budget_per_person_vnd, discount_amount_vnd, fee_amount_vnd,
  items_total_vnd, line_total_vnd, printed_total_vnd, shipping_amount_vnd,
  subtotal_amount_vnd, total_amount_vnd, unit_price_vnd, vat_amount_vnd
```

Nên trên đường production, float không lên tới đó — **cùng hạng nghiêm trọng với
chính phát hiện của #416**, không hơn. Một lưu ý: `amount_vnd: int` trong 14 dataclass
của `repository.py` là **annotation của dataclass**, Python không cưỡng chế lúc chạy;
nó là tài liệu, không phải cổng. Ở fake repository (`tests/api/conftest.py`) giá trị
là bất kỳ cái gì test nhét vào.

## Bản đồ đầy đủ: mọi chỗ tiền đi TỪ NGOÀI VÀO

Đo cơ học, không liệt kê tay. Con số phụ thuộc vào **hạt** bạn chọn — và đó chính là
bài học, nên tôi ghi cả ba tầng thay vì chọn một con số.

| tầng | dân số | cách lấy dân số | chặn float? | cổng |
|---|---|---|---|---|
| Wire, **request body** | **13** trường | đi vòng `app.routes` → `body_field` → model lồng nhau | có, `Field(strict=True)` | `test_money_wire_type_gate.py` — **cơ học**, sàn `>= 13`, 4 hình dạng xấu mỗi trường |
| Wire, **query param** | **1** (`/contexts/{id}/budget?candidate_per_person_vnd`) | đi vòng `dependant.query_params` | có | `test_budget.py::test_group_budget_rejects_an_invalid_candidate_query` — **viết tay**, `["-1","180000.0","true","not-money"]` → 422 |
| Wire, **response** | **41** trường | đi vòng response models | có | `test_money_response_type_gate.py` — **cơ học**, sàn `>= 41` |
| `domain/ledger.py` | **9 tham số** (7 export) | `__all__` + đọc chữ ký | **8/9** | #416 `FLOAT_PROBES` — cơ học ở mức TÊN, viết tay ở mức THAM SỐ |
| `domain/allocator.py` | `total_vnd`, `items[].amount_vnd`, `surcharges`, `discounts` | — | **KHÔNG** | không có cổng riêng — chỉ dựa vào wire |
| `domain/receipt.py` `normalize_vnd` | tiền do **model đọc từ ảnh bill** | — | có, `ReceiptError` | `test_receipt_normalize.py::NoFloatEverAppears` |
| `domain/suggestion.py` `_integer_dong` | tiền do **model sinh** | — | có | `suggestion_history_not_integer_dong` |
| `domain/place_search.py` `_integer_dong` | ngân sách do **model sinh** | — | có | `place_search_budget_not_integer` |
| `db/models.py` | **21 cột** | quét regex `_vnd` | có, `BigInteger` | Postgres |
| `api/repository.py` dataclass | 14 chỗ `amount_vnd: int` | — | **KHÔNG** (annotation không cưỡng chế) | — |

### Hai điểm mù cấu trúc trong chính các cổng cơ học

1. **`test_money_wire_type_gate.py` chỉ đi qua `route.body_field`.** Query param, path
   param, header **không nằm trong dân số của nó**, không phải vì ai đó bỏ sót mà vì
   vòng lặp không đi qua đó. Tôi đo lại bằng `dependant.query_params` trên cả 90
   `APIRoute` và tìm ra đúng **1** trường tiền dạng query. Nó **được gác đúng** và
   **có test**, nhưng test đó là một `parametrize` viết tay trên một route — nếu route
   thứ hai mọc thêm query param tiền, không cổng nào biết.

   ```
   APIRoutes: 90
   money-named query/path/header params: 1
     /contexts/{context_id}/budget  [query] candidate_per_person_vnd
   ```

   Probe hành vi trên đúng annotation của tham số đó:

   | giá trị gửi lên | kết quả |
   |---|---|
   | chuỗi toàn chữ số | nhận, thành `int` |
   | chuỗi có dấu chấm thập phân (đuôi `.0`) | 422 |
   | chuỗi có dấu chấm thập phân (đuôi `.5`) | 422 |
   | `float` nguyên | 422 |
   | `float` lẻ | 422 |
   | `True` | 422 |
   | chữ số Ả Rập-Ấn Độ | 422 |

2. **`allocator.allocate` không có cổng kiểu nào của riêng nó.** Đã đo bằng golden
   vector `01_even_split.json`:

   ```
   baseline (input golden nguyên bản)   ACCEPTED -> {'a':100000,'b':100000,'c':100000}
   total_vnd = 0.5                      TypeError: slice indices must be integers   <-- 500, không phải 422
   total_vnd = True (bool)              ACCEPTED -> {'a':1,'b':0,'c':0}             <-- chia 1 đồng, im lặng
   ```

   Docstring của `test_money_wire_type_gate.py` đã nói đúng chuyện này. Ghi lại ở đây
   để nó nằm cạnh những đường khác chứ không chỉ nằm trong một docstring.

## Kết luận và đề xuất

1. **Trả lời Lead:** 7 là số đếm được, không phải tổng. Ở mức tham số, `ledger.py`
   có 9; 8 được gác; **đường thứ 8 là `obligation_status(declared_amount_vnd)`**.
2. **Đề xuất sửa (chưa làm, chờ Lead quyết vì #416 đang bị qa gác):**
   - `obligation_status` gọi `require_vnd(declared_amount_vnd, positive=True)` thay
     `<= 0` tự viết. `NON_POSITIVE_OBLIGATION` giữ nguyên cho ca zero, đúng như #416
     đã làm với `NON_POSITIVE_CONFIRMATION`.
   - Đổi `FLOAT_PROBES` từ khoá-theo-**export** sang khoá-theo-**(export, tham số)**,
     và ca chống mục ruỗng đối chiếu với chữ ký hàm (`inspect.signature`) chứ không
     chỉ với `__all__`. Đó là cách duy nhất để D4 ở trên đỏ được.
   - Nếu Lead muốn một cổng thật cho query param tiền: mở rộng dân số của
     `test_money_wire_type_gate.py` sang `dependant.query_params`, sàn `>= 1`.
3. **Kết quả âm, ghi để không ai đo lại:** ngoài `ledger.py`, mọi cửa tiền domain khác
   tôi probe được (`normalize_vnd`, hai `_integer_dong`, query param ngân sách) **đều
   từ chối float**. `allocator.allocate` là ngoại lệ và nó đã được ghi nhận từ trước.
