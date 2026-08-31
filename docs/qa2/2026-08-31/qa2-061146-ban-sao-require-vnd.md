# Đếm bản sao `require_vnd` theo HÌNH DẠNG — con số là 6, không phải 4

- task_id: `qa2-061146` (hậu tố lượt lược bớt: repo guard đọc dãy số dài liền nhau như số tài khoản)
- protocol_version: v1
- Đo trên `main` = `6def9a1` (đã kiểm lại: cùng kết quả ở `5d589e1` và `eda412d`)
- verdict: **NOT VERIFIED** cho mệnh đề "chỉ còn 4 bản sao" — đếm bằng trục khác ra **6**
- Blocker còn mở: không. Đây là phép đo nền, không chặn ai.

## Câu hỏi được giao

Backend báo `require_vnd` bị chép ít nhất **4 lần**, một bản nằm cùng file
`ledger.py`, dưới ~314 dòng, ném cùng mã lỗi. Lead giao tôi đếm lại bằng **trục
khác** vì "người vừa đếm sai là người dễ đếm sai lại theo cùng một trục".

## Trạng thái: PR gộp CHƯA tồn tại

Không có nhánh nào trên `origin` cho việc gộp, và PR backend đang mở duy nhất
(#416, `confirmed_total` nhận float) là việc khác. Nên **không có "sau bản vá"
để đo**. Cái đo được — và là cái làm cho con số 0 sau này có nghĩa — là **nền
trước bản vá**, đo bằng trục độc lập.

## Cách đếm: hình dạng, không phải tên

`tests/qa/qa2-061146-ban-sao-require-vnd/quet_ban_sao_kiem_tien.py` đọc AST của
toàn bộ `services/api/app/**/*.py`, không đọc tên hàm:

| Trục | Bắt cái gì |
|---|---|
| A | `isinstance(X, int)` / `isinstance(X, bool)` / `type(X) is int` |
| B | so sánh với hằng `0`: `< 0`, `<= 0`, `> 0`, `== 0` |
| C | `raise ...("<MÃ>")` với `<MÃ>` mang từ khoá tiền |

Một **ứng viên** = hàm có A **và** (B **hoặc** C) — đúng hình dạng của
`require_vnd`, bất kể nó tên gì.

Điểm mấu chốt: bộ từ vựng mã lỗi ở trục C được **phát hiện từ cây**, không giả
định trước. Nếu tôi hard-code `AMOUNT_NOT_INTEGER` thì tôi đã ra đúng con số 4
của backend — và mù đúng 3 bản sao bên dưới.

## Kết quả: 116 hit, 12 ứng viên, 6 bản sao THẬT trên tiền

`require_vnd` gốc ở `ledger.py:40`. Sáu chỗ khác tự kiểm tiền:

| # | Chỗ | Mã lỗi | Backend thấy? |
|---|---|---|---|
| 1 | `domain/ledger.py:349` `settlement_plan()` | `AMOUNT_NOT_INTEGER` | có |
| 2 | `payments/vietqr.py:72` `build_payload()` | `AMOUNT_NOT_INTEGER` + `NON_POSITIVE_AMOUNT` | có |
| 3 | `web/guest_view.py:79` `format_vnd()` | `AMOUNT_NOT_INTEGER` + `NEGATIVE_AMOUNT` | có |
| 4 | `domain/budget.py:39` `_non_negative_integer()` | `INVALID_BUDGET_INPUT` | **KHÔNG** |
| 5 | `domain/place_search.py:87` `_integer_dong()` | `place_search_budget_not_integer` | **KHÔNG** |
| 6 | `domain/suggestion.py:137` `_integer_dong()` | `suggestion_history_not_integer_dong` | **KHÔNG** |

Ba hàng dưới là tiền, và không phải tôi suy đoán — chính docstring của chúng nói:

- `budget.py`: *"accepting it would turn True into one đồng"*
- `place_search.py`: *"`True` is not a sum of money"*
- `suggestion.py`: *"**Money law 1**, at figures that only ever get displayed"*

Cả ba mang **đúng một dòng** logic của `require_vnd`:
`isinstance(value, bool) or not isinstance(value, int) or value < 0` → raise.
Chúng vô hình với mọi phép tìm neo vào `AMOUNT_NOT_INTEGER` hoặc vào tên
`require_vnd`.

Sáu ứng viên còn lại cùng hình dạng nhưng **không phải tiền** (member_count,
max_messages, khoảng cách km, đếm preference, headcount) — tôi không tính vào 6.

## Đối chứng dương: máy quét này cắn được

Con số 0 chỉ có nghĩa nếu máy quét chứng minh được nó xuống được. Gỡ **một** bản
sao thật (`vietqr.py` → gọi `require_vnd`), đo lại, rồi hoàn nguyên:

```
BASELINE               ung_vien_hinh_dang=12  raise_AMOUNT_NOT_INTEGER=4
SAU KHI GO 1 BAN SAO   ung_vien_hinh_dang=11  raise_AMOUNT_NOT_INTEGER=3
(hoan nguyen: 0 file ban)
```

## Cảnh báo cho PR gộp: bản sao cùng file KHÔNG "nguyên văn"

Backend mô tả bản sao ở `ledger.py` là chép nguyên văn. Nó không phải.
`settlement_plan` kiểm **số dư có dấu** — tổng phải bằng 0 nên phải có số âm —
còn `require_vnd` ném `NEGATIVE_AMOUNT` khi `value < 0`. Gộp thẳng:

```
- if isinstance(amount, bool) or not isinstance(amount, int):
-     raise LedgerError("AMOUNT_NOT_INTEGER")
+ require_vnd(amount)
```

```
89 failed, 34 passed, 21 subtests passed in 0.67s
```

Nền trước khi sửa: `34 passed, 10 subtests passed`. Nên bản sao mà backend nêu
đích danh lại chính là bản **không gộp thẳng được**: nó cần một tham số mới
(`allow_negative` / `signed`). Đó là hình dạng đã làm mù một cổng trong repo này
trước đây — export cũ mọc thêm tham số tiền không được gác.

## Ba mã lỗi kia có test ghim

Gộp 3 bản sao còn lại **không miễn phí** — mỗi mã lỗi đang bị test ghim:

- `place_search_budget_not_integer` → `tests/domain/test_place_search_grounding.py`, `tests/live/test_places_search_live.py`
- `suggestion_history_not_integer_dong` → `tests/domain/test_suggestion_grounding.py`, `tests/postgres/test_group_recap_postgres.py`
- `INVALID_BUDGET_INPUT` → `tests/domain/test_budget.py`

Đây là quyết định thiết kế cho backend + Lead, không phải việc tôi tự chốt.

## Một lỗi nhỏ bắt được kèm

`domain/suggestion.py:143` `_headcount()` ném
`suggestion_history_not_integer_dong` cho một **số người**. Sai số người thì báo
"không phải số nguyên đồng". Nhỏ, nhưng là mã lỗi nói dối.

## Cái phép đo này KHÔNG chứng minh

- Không chứng minh 6 bản sao đó **hành xử** giống `require_vnd` — chỉ chứng minh
  chúng cùng hình dạng. Hai trong số đó lệch thật (`settlement_plan` cho số âm,
  `_headcount` dùng `< 1`).
- Không quét ngoài `services/api/app/` (không quét test, không quét client).
- Không phải cổng CI. Nó là thước đo chạy tay; chưa có gì chặn bản sao thứ 7.
