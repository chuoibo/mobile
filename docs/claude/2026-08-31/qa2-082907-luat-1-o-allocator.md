# Luật 1 ở allocator: xác nhận, nhưng bán kính hẹp hơn — và ba chỗ lệch với backend

- task: `qa2-082907` (hậu tố lượt `64105401`; tách ra vì repo guard đọc chuỗi 14 chữ
  số liền là số tài khoản)
- nhánh: `qa2/kiem-muoi-cong-can-duoc-khong`
- neo: `main` tại `6766249`, nhánh rebase lên đúng mốc đó. (Đo lần đầu ở `5cfcefa`;
  main nhích 3 commit giữa lượt — `127f84e`, `316c6c2`, `6766249` — không commit nào
  chạm `app/domain/`, và probe chạy lại ở mốc mới ra **cùng con số**.)
- protocol_version: v1
- verdict: **XÁC NHẬN phát hiện của backend** — `allocate()` không cưỡng chế luật 1.
  Nhưng bán kính **không** tới được từ HTTP, và hình dạng thiệt hại khác với mô tả.
- skill: `bug-reproduction` (tái lập trước khi sửa, nền dương + đối chứng ở mỗi tầng)
- probe: `services/api/tests/qa/qa2-082907-luat-1-o-allocator/probe_duong_di_cua_mot_so_tien.py`

## Trục đo — cố tình KHÁC backend

Backend đếm **call site** của `allocate()`. Tôi đếm **rào chắn dọc đường đi của một
số tiền**: `route → schema → service → allocator`, ở mỗi tầng hỏi đúng một câu — một
`float` (hay `bool`) có đi qua tầng này mà không đổi không?

Hai trục ra cùng một câu trả lời cho câu hỏi trung tâm, và lệch nhau ở ba chỗ. Ba chỗ
lệch đó là phần đáng đọc.

## Xác nhận: có, luật 1 không được cưỡng chế ở `allocate()`

`_validate_structure` (`services/api/app/domain/allocator.py:52`) kiểm `< 0`, `== 0`,
`> MAX_AMOUNT_VND`. Không có phép kiểm kiểu nào. Không gọi `require_vnd` lần nào.
`app/domain/allocator.py` không import `app/domain/money.py`.

Docstring ngay đầu file nói ngược lại điều code làm:

> money is integer dong -- no float anywhere, not even in intermediates

## Chỗ lệch 1 — không phải "đi qua được", mà là BA kết cục

12 ca phi-int trên 4 ô tiền (`total_vnd`, `items[]`, `surcharges[]`, `discounts[]`)
× (`float .0`, `float lẻ`, `bool True`). Nền int ở cả 4 ô đều ra đúng trước.

```
12 ca phi-int trên 4 ô tiền: {'ok': 3, 'error': 6, 'crash': 3}
```

| ô tiền | float .0 | float lẻ | bool True |
|---|---|---|---|
| `total_vnd` | **crash** TypeError | **crash** TypeError | **ok** Σ=1 |
| `items[].amount_vnd` | ok Σ=100000 | error RECONCILIATION_MISMATCH | error |
| `surcharges[].amount_vnd` | ok Σ=110000 | error | error |
| `discounts[].amount_vnd` | **crash** AttributeError | error | error |

`crash` là loại riêng và nó quan trọng: `allocate()` hứa dict-vào/dict-ra cộng
`AllocationError`, còn `app/api/service.py` chỉ bắt `AllocationError`. Một
`TypeError` thoát ra khỏi domain là **500**, không phải 422.

```
File "app/domain/allocator.py", line 238, in _apportion
    gainers = ranked[:deficit]
TypeError: slice indices must be integers or None or have an __index__ method
```

## Chỗ lệch 2 — 6/12 ca bị chặn là MAY, không phải phòng thủ

`RECONCILIATION_MISMATCH` bắt được 6 ca chỉ vì probe đổi **một** ô còn các ô khác giữ
`int`, nên tổng không khớp. Một client tuần tự hoá **mọi** số tiền thành float thì các
số vẫn khớp nhau và phép đối chiếu số học không còn gì để bắt. Đo hình dạng đó:

```
mọi ô float .0, khớp nhau    -> crash  TypeError
mọi ô float lẻ, khớp nhau    -> crash  TypeError
```

Đối chiếu số học chỉ so số với số; nó không có ý kiến gì về kiểu. Ở bill cũng vậy —
một bill một món mà `amount=True` và `printed_total=True` **tự khớp với chính nó**:

```
bill 1 món, amount=True, printed_total=True -> ok: {'a': 1, 'b': 0}
```

## Chỗ lệch 3 — ca tiền SAI thật sự chỉ có một, và nó là `bool`

Trong 12 ca, đúng **một** ca vừa đi lọt vừa trả về con số sai:

```
allocate(total_vnd=True) -> ok: {'a': 1, 'b': 0, 'c': 0}   Σ = 1
```

Một hoá đơn thành 1 đồng, chia ba, không cảnh báo gì. Hai ca "ok" còn lại
(`items` và `surcharges` với `float .0`) trả về **đúng số** — `Fraction(100000.0)`
là chính xác — nên chúng là vi phạm luật 1 chứ chưa phải tiền sai.

Cùng repo, cùng `app/domain/`, cùng luật 1, hai hàm trả lời ngược nhau:

```
require_vnd(True)      -> LedgerError(AMOUNT_NOT_INTEGER)
require_vnd(100000.0)  -> LedgerError(AMOUNT_NOT_INTEGER)
allocate(total_vnd=True)     -> đi qua, 1 đồng
```

## Bán kính: KHÔNG tới được từ HTTP

Lead bảo backend đo bán kính trước khi cưỡng chế. Đây là số liệu.

App FastAPI thật + fake repository, `POST /expenses`:

| thân JSON | HTTP |
|---|---|
| int 82000 (nền dương) | **201** |
| float 82000.0 | 422 `int_type` |
| float 82000.5 | 422 `int_type` |
| bool `true` | 422 `int_type` |
| chuỗi `"82000"` | 422 `int_type` |
| item `amount_vnd` float | 422 `int_type` |

```
Số thân phi-int lọt qua biên HTTP: 0/5
Số bản ghi khoản chi được tạo: 1 (nền dương = 1)
```

`MoneyVnd = Annotated[int, Field(strict=True)]` (`app/api/schemas.py:24`) giữ được
thật, đo bằng hành vi chứ không đọc metadata. 56 ô `*_vnd` trong `schemas.py`, 10 ô
optional, ô optional cũng bị bắt.

**Nhưng rào chỉ dày đúng một lớp.** Bỏ qua pydantic bằng `model_construct` rồi đo
phần còn lại:

```
_allocator_input(...)['total_vnd'] = 82000.5 (float)
allocate(...) -> crash: TypeError
```

`_allocator_input` chỉ đổi tên khoá, không ép kiểu. `allocator_input_from_bill` cũng
vậy — docstring của nó tự nói *"arranges; it never computes"*. Giữa pydantic và
`allocate()` không còn ai kiểm nữa.

Nên đây **không** phải lỗ hổng khai thác được từ ngoài hôm nay. Nó là **lỗ hổng ngủ**:
nó thức dậy khi có người gọi `allocate()` mà không đi qua route — script seed, demo
reset, một service nội bộ, một job, hay chính test.

## Trả lời câu hỏi 2 của đề bài: 41 vector golden

```
file: 6   vector: 41   lá số: 156
lá KHÔNG phải int: 0
```

**Không vector nào dùng giá trị phi-int.** Không phải là "phát hiện riêng quan trọng
hơn cả bug" như Lead phòng hờ — nó là **lý do** corpus không bao giờ bắt được lỗi này:
41 vector kiểm phép **TÍNH** trên đầu vào hợp lệ, không kiểm phép **NHẬN**.

Phụ: 41 vector phủ 16/19 mã lỗi. Ba mã không có vector nào:
`INVALID_ENTITY_ID`, `AMOUNT_TOO_LARGE`, `INVALID_KIND`.
(`AMOUNT_TOO_LARGE` có ca ở `test_allocator_properties.py:267`.)

## Vì sao nó sống sót: hai cổng đang gác luật 1, không cổng nào nhìn thấy allocator

**Cổng A** — `tests/test_one_money_check.py`, đếm **BẢN SAO** của phép kiểm:

```
SCOPE = ('domain', 'payments', 'api', 'db')
allocator.py NẰM TRONG scope của cổng A: True
phép kiểm tìm thấy trong allocator.py: không có
```

Cổng A khẳng định *"không ai được chép lại phép kiểm"*. Một file **không hề kiểm gì
cả** thoả mãn nó hoàn hảo. `allocator.py` nằm trong tầm ngắm và vẫn xanh, vì cổng đếm
sự CÓ MẶT của bản sao — vắng mặt là màu xanh.

**Cổng B** — sweep float+bool từng tham số trong `tests/domain/test_ledger.py`:

```
vũ trụ của nó = ledger.__all__ (9 tên)
'allocate' có trong ledger.__all__: False
```

Cổng B quét đúng thứ cần quét, nhưng vũ trụ là `__all__` của **một module khác**.
`allocate()` không bao giờ vào được danh sách.

Và **cổng A sẽ chống lại bản vá hiển nhiên nhất**:

```
vá nội tuyến -> cổng A bắt được: {'_validate_structure'}
```

Ai viết `isinstance(amount, bool) or not isinstance(amount, int)` thẳng vào
`allocator.py` sẽ làm cổng A **đỏ**. Bản vá hợp lệ phải gọi
`app.domain.money.vnd_violation`.

## Chốt chặn thật sự: hợp đồng đông lạnh không có từ để nói

`ERROR_PRECEDENCE` (`app/domain/contract.py:16`) có 19 mã. Mã nói về kiểu số nguyên:
**không có**. Và `AllocationError.__init__` từ chối mã lạ:

```
raise AllocationError('AMOUNT_NOT_INTEGER')
   -> ValueError: unknown allocation error code: 'AMOUNT_NOT_INTEGER'
```

Không phải `AllocationError`. `app/api/service.py` chỉ bắt `AllocationError`, nên bản
vá viết ẩu ở đây biến 422 thành **500**.

Ba đường đi, mỗi đường một cái giá. Đây là quyết định của người sở hữu domain
(Codex/backend) và của Lead, không phải của tôi:

1. **Thêm mã vào `ERROR_PRECEDENCE`** — sửa hợp đồng ADR-0004 đã đông lạnh. CLAUDE.md
   nói rõ: đổi luật tiền thì **mở ADR trước**. Còn phải chọn vị trí trong thứ tự ưu
   tiên, và 41 vector golden ghim thứ tự đó.
2. **Dùng lại mã có sẵn** (`NEGATIVE_AMOUNT`? `AMOUNT_TOO_LARGE`?) — mã sẽ nói sai
   chuyện gì đã xảy ra, và client branch theo mã.
3. **Chặn TRƯỚC allocator, ở service** — rẻ nhất, nhưng `allocate()` vẫn hở cho mọi
   người gọi sau này, kể cả test và script. Đúng cái hình dạng đã tạo ra bug này.

## Bằng chứng

Chạy từ `services/api`:

```
$ python tests/qa/qa2-082907-luat-1-o-allocator/probe_duong_di_cua_mot_so_tien.py
   exit 0 — 183 dòng, tự kiểm: "Mọi nền dương và đối chứng đều đúng như mong đợi"
```

Probe tự bỏ phiếu chống chính nó: nếu nền int không chạy, nếu nền dương HTTP không
201, nếu `require_vnd` không chặn, nếu đếm ra khác 41 vector — nó in
"PHÉP ĐO NÀY HỎNG" và thoát 1.

Cây xanh trong khi lỗ hổng vẫn còn nguyên:

```
$ python3 -m pytest services/api/tests tests -q
   2784 passed, 580 skipped, 5049 subtests passed in 341.23s
   (gồm cả cổng mới của #448 gác script dưới tests/qa/)

$ cd services/api && python3 -m pytest tests/domain/test_allocator_golden.py \
    tests/domain/test_allocator_properties.py tests/domain/test_ledger.py \
    tests/test_one_money_check.py tests/api/test_expenses.py -q
   65 passed, 3868 subtests passed in 2.46s

$ python3 -m pytest tests/test_qa_scripts_are_ruff_formatted.py -q
   4 passed

$ $(scripts/ruff_pinned.sh) check <file probe>   → All checks passed!
$ $(scripts/ruff_pinned.sh) format <file probe>  → 1 file left unchanged
```

3868 subtest về luật tiền xanh trong khi `allocate(total_vnd=True)` trả 1 đồng.

## Phân loại theo luật blocker của charter

Thuộc loại **sai tiền** — nhưng bán kính đo được là 0 đường HTTP. Tôi **không** đặt
blocker: chưa tái lập được từ ngoài, và tiêu chí gỡ chặn sẽ là một quyết định ADR chứ
không phải một dòng code.

Đề nghị xếp là **lỗ hổng ngủ ưu tiên cao**: chi phí vá sẽ chỉ tăng, và tiêu chí gỡ
chặn nên là — có một ca đỏ được ở bản hiện tại, gọi `allocate()` trực tiếp với
`total_vnd=True`, và xanh sau khi vá.

## Cái này KHÔNG chứng minh

- Không chứng minh không có đường HTTP nào khác lọt. Tôi đo `POST /expenses` và
  `BillCreateRequest`; 56 ô `*_vnd` chưa đo hết từng ô một qua route của nó.
- Không chứng minh Postgres thật cũng chặn. Cột `BigInteger` có hành vi ép kiểu
  riêng; tôi chạy trên fake repository (`tests/api/conftest.py`).
- Không chứng minh `crash` thành 500 **trên route thật** — tôi suy ra từ việc
  `service.py` chỉ bắt `AllocationError`. Chưa dựng được đường HTTP nào tới đó, đúng
  theo bảng bán kính ở trên.
- Không chứng minh backend sai ở "5 ca". Trục của họ khác trục của tôi; ba chỗ lệch ở
  trên là chỗ hai trục nhìn ra hai thứ, không phải chỗ ai đó đếm nhầm.
