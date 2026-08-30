# QA — phán quyết PR #416 (Luật 1 ở sổ cái: confirmed_total nhận float)

- commit đo: `2774f3e8c78b5d0f193b7a71aa944218a1ead90a`
- sha này: nhánh chưa merge, dựng trên `origin/main@b9362d5`; main lúc đo đã ở `56e0f36`
- protocol_version: v1
- verdict: **FAIL**
- kỹ năng bắt buộc đã gọi: e2e-testing, bug-reproduction

## QA: FAIL

**Lý do (viết trước chi tiết):** bản vá là thật và đã kiểm chứng đỏ→xanh, nhưng con số **7 là đếm theo TÊN EXPORT, không phải theo THAM SỐ NHẬN TIỀN**. `obligation_status` có **hai** đầu vào tiền; PR probe và vá đúng một. Đầu vào còn lại — `declared_amount_vnd` — vẫn cho float và bool đi qua, **ở chính hàm mà PR lấy làm câu chuyện hậu quả**. Và ca chống mục ruỗng chỉ gác đúng một hướng mục; hai hướng liền kề, dễ xảy ra hơn, vẫn xanh.

đo tại `2774f3e8c78b5d0f193b7a71aa944218a1ead90a`
sha này là nhánh chưa merge, dựng trên `origin/main@b9362d5` (main nay đã ở `56e0f36`)

---

### Cái PR nói đúng, tôi xác minh độc lập

Đối chứng: lấy `ledger.py` của base `b9362d5`, giữ nguyên test mới của PR:

```
SUBFAILED(entry_point='confirmed_total')
SUBFAILED(entry_point='obligation_status')
FAILED ConfirmedTotalIsIntegerDong::test_a_float_confirmation_never_becomes_a_status
3 failed, 29 passed, 8 subtests passed
```

Trùng khít con số trong mô tả PR. Và bug gốc tái lập được ở base:

```
obligation_status(300000, [100000.1, 200000.2]) -> 'over_confirmed'   # trả đúng đủ, đọc thành trả thừa
type(confirmed_total([0.1, 0.2]))               -> float              # sai so với '-> int'
```

Cổng đầy đủ tại head, tôi chạy tay trong cây sạch:

| Cổng | Kết quả |
|---|---|
| `pytest services/api/tests tests -q` | **2681 passed, 580 skipped, 4908 subtests** |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **523 passed, 0 skipped** |
| `repo_guard.py tree HEAD` | passed, 1228 file scan(s) |
| `ruff check` (bản ghim 0.9.2) trên 2 file PR chạm | All checks passed |

Không có hồi quy. Bản vá `confirmed_total` là cải thiện thật.

---

### BLOCKER 1 — con số 7 đếm theo tên hàm, không theo cửa tiền

`__all__` có 9 tên, trừ `LedgerError` và `require_vnd` ra 7. Nhưng cửa tiền là **tham số**, không phải tên:

| hàm | tham số nhận tiền | được probe? | được `require_vnd` gác? |
|---|---|---|---|
| `obligation_status` | `receipt_confirmations` | có | có (PR này vá) |
| `obligation_status` | **`declared_amount_vnd`** | **KHÔNG** | **KHÔNG** — vẫn tự viết `<= 0` |
| `group_balances` | `obligations` | có | có |
| `group_balances` | `receipts` | không | có (dòng 241) — nên vẫn kín |

Chạy trên **chính head 2774f3e, bản vá đã có**:

```
obligation_status(3.5,  [{'amount_vnd': 3}])  -> LỌT  'partially_confirmed'
obligation_status(True, [{'amount_vnd': 1}])  -> LỌT  'confirmed'
obligation_status(3.0,  [{'amount_vnd': 3}])  -> LỌT  'confirmed'
```

Dòng thứ hai đáng chú ý: docstring của `require_vnd` viết `bool` bị từ chối riêng "because `isinstance(True, int)` is True in Python, and `True` would silently become one dong." Đó đúng là chuyện vừa xảy ra ở đây.

Hậu quả cùng hạng với bug PR vá, chỉ đảo chiều: `declared` là float nhỉnh hơn số nguyên thật thì người **đã trả đủ** bị đọc thành `partially_confirmed` — vẫn còn nợ.

**Mức nghiêm trọng, nói thẳng như PR đã nói:** cũng là lỗ hổng **tiềm ẩn**, không phải tiền đang chảy sai. Cả 4 call site (`repository.py:3849,4113`, `service.py:4213,4313`) đều truyền `obligation.amount_vnd` / `target.amount_vnd` — cùng cột `BigInteger`. Tôi cũng không dựng được ca tái lập qua HTTP.

### BLOCKER 2 — ca chống mục ruỗng gác đúng một hướng

D2/D3 tôi chạy lại, **cả hai đỏ thật**. Nhưng đó là hướng duy nhất nó nhìn. Hai hướng liền kề, và dễ mắc hơn:

| # | Đột biến | Kết quả |
|---|---|---|
| D1 | Hoàn nguyên bản vá | ĐỎ — 3 failed *(xác minh lại)* |
| D2 | Thêm export vào `__all__`, không thêm probe | ĐỎ — 1 failed *(xác minh lại)* |
| D3 | Xoá một probe khỏi `FLOAT_PROBES` | ĐỎ — 1 failed *(xác minh lại)* |
| M4 | Gỡ nhánh `bool` khỏi `require_vnd` | ĐỎ — nhưng do ca **CŨ** 1 cửa bắt, không phải ca mới |
| M5 | Gỡ nhánh float/str, giữ bool | ĐỎ — 8 failed |
| **M6** | **Thêm tham số tiền mới vào hàm đã export, không probe** | **XANH — 30 passed. `confirmed_total([{'amount_vnd':3}], 0.5)` -> `3.5`** |
| **M7** | **Thêm hàm tiền công khai mới, QUÊN `__all__`** | **XANH — 30 passed. `outstanding_after_refund(3, 0.5)` -> `2.5`** |

M7 là hướng dễ mắc nhất: cái neo là `__all__`, mà `__all__` cũng là một danh sách viết tay. Quên `__all__` dễ hơn nhớ nó, và lúc đó cổng im lặng.

Ghi thêm: ma trận loại-xấu × cửa. Ca cũ phủ 3 loại (`0.5`, `True`, `"100"`) × 1 cửa. Ca mới phủ **1 loại** (`0.5`) × 7 cửa. Không ca nào phủ 21 ô; PR đổi bề rộng loại lấy bề rộng cửa. Vì thế M4 chỉ còn ca cũ đỡ.

### Bất biến 1 — trả lời câu thứ ba

Còn giữ **trên đường PR chạm**: `confirmed_total` trả `int` thật, tổng các `int` không sinh float. Chưa giữ trên `obligation_status.declared_amount_vnd`: phép so ở dòng 202–206 vẫn có thể là so float với int. Không rò float ra ngoài (trả `str`), nhưng **quyết định** thì lấy từ một giá trị float.

---

### Tiêu chí gỡ chặn

Một dòng, tôi đã thử và xác minh (không commit):

```python
require_vnd(declared_amount_vnd)          # thêm dòng này
if declared_amount_vnd <= 0:
    raise LedgerError("NON_POSITIVE_OBLIGATION")
```

- chặn cả `3.5`, `True`, `3.0` → `AMOUNT_NOT_INTEGER`
- **giữ nguyên** `NON_POSITIVE_OBLIGATION` cho số 0 (đúng lý lẽ PR đã dùng cho `NON_POSITIVE_CONFIRMATION`)
- `grep` toàn repo: `NON_POSITIVE_OBLIGATION` chỉ có đúng 1 chỗ `raise`, không ca nào phụ thuộc
- bộ ledger vẫn `30 passed, 10 subtests passed`

Kèm theo:
1. Thêm probe cho `declared_amount_vnd` (probe hiện khoá theo tên hàm, cần khoá theo **cửa**).
2. Ca chống mục ruỗng: neo vào chữ ký hàm (`inspect.signature`) thay vì `__all__`, hoặc — nếu giữ `__all__` — thì hạ tên lớp và mô tả xuống đúng cái nó chứng minh được, đừng để chữ "Every" bảo lãnh phần nó không nhìn.

Điểm (2) là phần tôi thấy quan trọng nhất. Chẩn đoán gốc của PR này đúng: **một cái tên hứa "everywhere" làm người sau thôi kiểm lại.** Ca mới tên `EveryMoneyEntryPointRefusesAFloat` đang hứa đúng như vậy, ở phạm vi rộng hơn nhưng vẫn chưa phải "every". Vá nốt cửa còn lại thì cái tên trở thành thật, và PR này giải quyết đúng thứ nó đặt ra.

### Ghi chú không phải blocker

`ruff format --check` đỏ trên `tests/domain/test_ledger.py`, **nhưng nợ có sẵn**: base `b9362d5` cũng exit=1. Phần lớn diff format nằm ở vùng PR không chạm. PR có thêm 1 chỗ mới chưa format (`test_the_declared_return_type_holds`). Theo CLAUDE.md thì không format cả cây, và CI chưa gate ruff — nên đây là gợi ý, không phải blocker.

### Ô chưa quét

- Lát cắt dọc `npm run test:e2e` và trang khách: không chạy. Thay đổi thuần domain, không chạm `app/web/` hay route, nên tôi đánh giá rủi ro thấp — nhưng nói rõ là **chưa quét**.
- Mã VietQR quét bằng app ngân hàng thật: chưa, như mọi lượt trước.
- `app/domain/` ngoài `ledger.py` (allocator/bill/budget): không quét lượt này. Kết quả âm về allocator trong mô tả PR tôi **không** kiểm lại.
