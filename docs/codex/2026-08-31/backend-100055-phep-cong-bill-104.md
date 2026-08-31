# Phép cộng ở `bill.py:104`, và mọi phép tính khác trên tiền

<!-- repo-guard: allow=long-number reason=harness-task-id-not-an-account-number -->
- **task_id**: `backend-100055-72219001`
- **protocol_version**: v1
- **Đo tại**: `f9a3b68` (nhánh `backend/phep-cong-bill-104-va-quet-chia-tien`, dựng
  thẳng từ `origin/main` `f9a3b68`, không có commit nào của riêng mình trong
  `app/`)
- **SHA này**: `f9a3b68` **ĐÃ ở main** — nó là commit merge của #450.
- **Nền đối chứng**: `b632d53` (main trước #450, tree `7ff65dd6`), chạy trong một
  worktree riêng ở `/tmp`.
- **Không sửa một dòng nào trong `services/api/app/`.** Chỉ thêm một máy quét, ba
  probe và tài liệu này.

> Lưu ý về thời điểm: lúc nhận việc `origin/main` ở `3912e7e`. Trong lượt này main
> nhích **hai lần** — `b632d53` (#460), rồi `f9a3b68` (#450 được merge). Nghĩa là
> hàng rào `AMOUNT_NOT_INTEGER` mà mọi kết luận dưới đây dựa vào **vừa mới vào main
> trong lúc đang đo**. Blob `allocator.py` của main `f9a3b68` và của nhánh #450
> giống hệt nhau (`bc5aceb9`), nên cái tôi đo đúng là cái đã ship.

---

## Trả lời ngắn, theo đúng ba câu anh hỏi

**Câu 3 trước, vì anh dặn báo NGAY nếu có: KHÔNG có chỗ nào dùng `/` trên tiền.**
27 nút `ast.Div` trong toàn bộ `app/`, 5 nút chạm tiền, cả 5 nằm trong pipeline
`Fraction` của `allocator.py` — nơi `/` là phép chia hữu tỉ chính xác, không phải
float. Không có gì để leo thang.

**Câu 1: `bill.py:104` cộng ba tổng, mọi toán hạng đến từ database.** Phép cộng
đúng là có TẠO RA giá trị mới như anh nói, và trong `bill.py` không có gì kiểm
giá trị đó. Nhưng nó không đi đâu xa: nó rơi thẳng vào `expense["total_vnd"]`
và `allocate()` kiểm nó bằng đúng `vnd_violation` mà #450 vừa thêm. Đo được ở
cả hai nền, bảng ở dưới.

**Câu 2: có một phép tính khác đang vi phạm Luật 1 — nhưng không phải phép chia,
mà là `SUM()` của PostgreSQL.** `app/db/repository.py:31` trả `Decimal` chứ không
trả `int`. Đo trên PostgreSQL 16 thật. Chi tiết ở mục 4. **Hôm nay chưa ai gọi
hàm đó**, nên nó không phải lỗ đang mở — nhưng `CLAUDE.md` chỉ đúng file này ra
làm *mẫu để chép*, nên nó là một cái khuôn sai chứ không phải một chỗ sót lẻ.

---

## 1. `bill.py:104` cộng những gì, toán hạng đến từ đâu

```python
total_vnd = (
    sum(item["amount_vnd"] for item in items)              # bill.py:104
    + sum(surcharge["amount_vnd"] for surcharge in surcharges)
    - sum(discount["amount_vnd"] for discount in discounts)
)
```

Chỉ có **một** người gọi trong `app/`: `service.py:3565`, trong `split_bill`.
Ba toán hạng đến từ đây:

| toán hạng | dựng ở | giá trị lấy từ | cột DB | rào khi ĐỌC |
|---|---|---|---|---|
| `item["amount_vnd"]` | `service.py:3577` | `item.line_total_vnd` của `BillItemRecord` | `bill_items.line_total_vnd` `BigInteger`, CHECK `> 0` | không |
| `surcharge["amount_vnd"]` | `service.py:3592` | `surcharge.amount_vnd` của `BillSurchargeRecord` | `BigInteger` | không |
| `discount["amount_vnd"]` | `service.py:3600` | `discount.amount_vnd` của `BillDiscountRecord` | `BigInteger` | không |

Không có toán hạng nào đến từ thân request: `BillSplitRequest` chỉ có `for_ledger`
và `paid_by_id`, **không một trường tiền nào** (đây là chỗ #460 đã chỉ ra). Toàn bộ
tiền của phép cộng này đến từ database, và rào duy nhất che nó là
`BillCreateRequest` (`PositiveMoneyVnd`, strict) ở một endpoint khác, sớm hơn.

**Có trường optional nào mặc định `0.0` không, hay tỷ lệ nào không?** Không. Không
có trường tiền nào trong `app/api/schemas.py` mang default float; cả bốn alias tiền
(`MoneyVnd`, `PositiveMoneyVnd`, `NonNegativeMoneyVnd`, và các `Annotated[int,
Field(strict=True, ...)]` viết tay) đều `strict=True`. Không có tỷ lệ/hệ số nào nhân
vào tiền ở đây — `bill.py` docstring tự nói nó *sắp xếp*, không *tính*, và có một
test parse AST giữ điều đó.

### Cái mà phép cộng thật sự tạo ra, và ai bắt nó

`tests/qa/backend-100055-phep-cong-bill-104/probe_phep_cong.py`, chạy hai nền.

> **Phần 1 dưới đây đã bị qa-tt-0057 làm trước, và làm kỹ hơn.** #466 lên main lúc
> 10:40, tức là *sau* khi tôi đo nhưng *trước* khi tôi mở PR này. Họ chạy ma trận
> 5 slot × 4 hình dạng = 21 ô đi đúng đường tiền thật, ra `0 BLOCKED` ở nền
> `b632d53` và `21 BLOCKED` ở sau #450, và họ đặt tên cho hiện tượng chính xác hơn
> tôi: ở ca `bool` phép cộng **giặt sạch bằng chứng** (`True + 70_000 = 70001`,
> int, không còn vết), trong khi ở ca float nó giữ vết. Phần 1 của tôi vì thế chỉ
> còn giá trị là một phép đo độc lập trùng kết quả — **đừng đọc nó như phát hiện
> mới**. Cái mới của tài liệu này là Phần 2, mục 2 và mục 3.

**Phần 1 — một toán hạng xấu đi vào phép cộng**

| ca | `total_vnd` phép cộng đẻ ra | kiểu | main **trước** #450 (`b632d53`) | main **hôm nay** (`f9a3b68`) |
|---|---|---|---|---|
| mọi toán hạng int | `135000` | int | ACCEPTED | ACCEPTED |
| item `65000.0` | `135000.0` | **float** | `TypeError: slice indices...` | `AllocationError(AMOUNT_NOT_INTEGER)` |
| item `65000.5` | `135000.5` | **float** | `TypeError` | `AMOUNT_NOT_INTEGER` |
| item `True` | `70001` | int | **ACCEPTED — `{'an': 1, 'binh': 70000}`** | `AMOUNT_NOT_INTEGER` |
| surcharge `5000.0` | `140000.0` | **float** | `TypeError` | `AMOUNT_NOT_INTEGER` |
| discount `5000.0` | `130000.0` | **float** | `TypeError` | `AMOUNT_NOT_INTEGER` |

Hàng `True` là hàng đáng đọc. Phép cộng nuốt một `bool` và đẻ ra một số **int
trông hoàn toàn bình thường** (`70001`), rồi trước #450 nó được chia luôn: món
giá `True` bị tính **1 đồng**. Đây chính là ca "tiền SAI im lặng" của #452, lần
này đo được là nó đi qua đúng `bill.py:104`. Năm hàng float thì ồn ào (`TypeError`
= 500), một hàng bool thì im — và im là hàng nguy hiểm.

**Phần 2 — cái mà CHỈ phép cộng mới tạo ra được**

Đây mới là phần riêng của một phép cộng, vì mọi toán hạng dưới đây **đều hợp lệ
từng cái một**: số nguyên dương, không vượt trần. Không một phép kiểm theo-từng-
toán-hạng nào có thể từ chối chúng; chỉ kết quả mới sai.

| ca | `total_vnd` | kết cục (cả hai nền giống nhau) |
|---|---|---|
| `Σdiscounts > Σlines` | `-65000` | `AllocationError(NEGATIVE_AMOUNT)` |
| `Σdiscounts == Σlines` | `0` | ACCEPTED, `{'an': 0, 'binh': 0}` — đúng: bill 0 đồng chia thành 0 |
| mỗi item `= MAX`, `Σ = 2×MAX` | `2_000_000_000_000` | `AllocationError(AMOUNT_TOO_LARGE)` |

Cả ba đều được bắt (hoặc vô hại). Nên câu trả lời đầy đủ cho nỗi lo của anh là:
**phép cộng đúng là tạo ra một giá trị không model nào validate, nhưng giá trị đó
rơi vào `expense["total_vnd"]` và `allocate()` kiểm `total_vnd` bằng đúng một
predicate với mọi toán hạng khác.** Nó không được bảo vệ bởi kiểu của mình — nó
được bảo vệ bởi chặng kế tiếp.

Điều đó có nghĩa hàng rào ở `allocate()` **là hàng rào duy nhất** trên đường này.
Gỡ nó ra, và `bill.py:104` không còn gì phía sau. Đó là lý do probe này có một
`assert` thật (chứ không chỉ in bảng) đúng ở hàng `bool`, và tôi đã đo nó **đỏ**
trên nền `b632d53` (`EXIT=1`) và **xanh** trên `f9a3b68` (`EXIT=0`) — nền thật,
không phải đột biến tự chế.

---

## 2. Census toàn bộ phép tính trên tiền

`tests/qa/backend-100055-phep-cong-bill-104/quet_phep_tinh_tien.py`.

**Đơn vị đếm: nút `ast.Div` / `ast.BinOp`, không phải hit của grep.** Đây là bài
học của chính lane này ở #437 và #450: một con số chỉ đáng tin bằng cái đơn vị nó
được đếm bằng, và người đi chép có thể đổi tên biến, đổi lời comment, đổi mã lỗi.
Họ không đổi được việc một `/` là `ast.Div`. Pass A vì thế **không lọc tiền gì cả** —
liệt kê hết 27 nút rồi để người đọc tự loại.

### Pass A — 27 `ast.Div` trong toàn `app/`

| chạm tiền | nơi | ghi chú |
|---|---|---|
| **có** | `allocator.py:191` `total / count` | `Fraction / int` — chính xác |
| **có** | `allocator.py:197` `net[...] / len(shared_by)` | `Fraction / int` |
| **có** | `allocator.py:214` `(total_base - global_discount) / total_base` | `Fraction / Fraction` |
| **có** | `allocator.py:240` `amount / count` | `Fraction / int` |
| **có** | `allocator.py:243` `amount * base[p] / basis` | `Fraction / Fraction` |
| không | `faces.py:127-130` | toạ độ khuôn mặt chuẩn hoá 0..1 |
| không | `preferences.py:167` `((count*200+top)//(2*top)) / 100` | **điểm sở thích**, không phải tiền. Comment tại chỗ nói rõ họ làm tròn nửa-lên bằng số nguyên TRƯỚC rồi mới chia 100 để ra 0.00–1.00 |
| không | `identity.py:86` | cửa sổ rate-limit |
| không | `areas.py:141-142` | haversine, km |
| không | `scoring.py:89` | khoảng cách, và cũng đã dùng `Fraction` |
| không | 12 nút còn lại | `pathlib.Path / "..."` — nối đường dẫn |

**Chỉ có `Fraction` được chia.** `allocator.py` `_item_net` bọc mọi `amount_vnd`
vào `Fraction(...)` trước, và điểm làm tròn duy nhất là `_apportion` (largest
remainder) dùng `value.numerator // value.denominator`. Đúng như ADR-0004 và đúng
như `CLAUDE.md` mô tả.

Một chi tiết đáng nói ra vì nó cho thấy giới hạn của chính máy quét: cờ "money-shaped"
của pass A **bỏ sót `allocator.py:197`**, một phép chia tiền thật, vì biểu thức đó
chỉ chứa `item_id` và `shared_by` — không token nào giống tiền. Nếu tôi lọc theo tên,
tôi đã đếm 4 thay vì 5. Pass A không lọc chính là vì thế.

### Pass B/C — `+ - * // % sum() round()` trên tiền: 63 + 26 nút

Không có nút nào tạo ra float. Các điểm đáng nêu:

- **`//` trên tiền: 16 nút, không nút nào là phân bổ.** Chia làm ba nhóm:
  *bình quân đầu người để hiển thị* — `budget.py:121,135`, `preferences.py:187`,
  `suggestion.py:189`; *đổi sang "k" để in ra chữ* — `places.py:407,408`,
  `suggestion_gemini.py:77`, `places/reasons.py:93`, `places/search.py:155`,
  `places/scoring.py:127,128`; *điểm giữa khoảng giá để chấm điểm gợi ý* —
  `places/reasons.py:206,207`, `places/scoring.py:60`. Không nút nào ghi vào sổ,
  nên phần dư bị mất không đụng Luật 2. Phép chia tiền thật vẫn chỉ có một, ở
  allocator. (Nút thứ 16, `social_map.py:157`, là phần trăm của `visit_count` —
  không phải tiền; nó lọt vào danh sách vì chữ `total` trong tên biến, một minh
  hoạ nữa cho việc lọc theo tên thì yếu.)
- `receipt.py:330` `line_total_vnd // quantity` được gác bằng `% quantity == 0`
  ngay trên nó, nên nó chia hết — không mất đồng nào.
- `money_skill.py:91` và `receipt.py:156` đều có dạng `10 ** (n - len(x))`. Số mũ
  âm sẽ ra float. Cả hai đều **không** âm được: ở `money_skill` `len(x)` bị regex
  `(\d{1,3})?` chặn ở 3 còn `n = 6`; ở `receipt` thì `x = fraction[:scale_digits]`
  nên `len(x) <= scale_digits` theo định nghĩa. Đã kiểm từng cái, không phải đoán.
- `preferences.py:179` xác thực một giá trị **tiền** (`split_total_vnd`) bằng
  `_integer_count` — helper dành cho *số đếm*. Về hình dạng thì tương đương
  (`money.py` chia chung `_not_an_integer`), nên **không phải lỗi**. Nhưng docstring
  của `money.py` nói thẳng "một số người không phải một số tiền, nên helper tên
  `vnd_` không được validate nó" — chiều ngược lại cũng đúng, và ở đây nó bị vi
  phạm. Đây là *suggestion*, không phải blocker.

---

## 3. Chỗ Luật 1 thực sự đang bị vi phạm: `SUM()` của PostgreSQL

PostgreSQL cộng một cột `bigint` ra `numeric`, và psycopg trả `numeric` thành
`decimal.Decimal`. `CLAUDE.md` nói "Không `float`, không `Decimal`, **kể cả ở giá
trị trung gian**".

Đếm bằng AST: **8 chỗ `func.sum()` trên cột tiền trong `app/`.**

| chỗ | có `int()` không |
|---|---|
| `api/repository.py:4306, 4345, 4356, 4406, 4416` | có, bọc trực tiếp — 5 chỗ, kèm comment giải thích đúng lý do Decimal |
| `api/repository.py:1895` | có, ép ở chỗ tiêu thụ: `int(row.split_total_vnd or 0)` (dòng 1896) |
| `api/repository.py:3320` | có, ép ở chỗ tiêu thụ: `int(confirmed_amount_vnd)` (dòng 3348) |
| **`db/repository.py:31`** | **KHÔNG** |

Hai chỗ giữa cho thấy vì sao đơn vị đếm quan trọng: luật "có `int()` bọc ngoài
trong cùng biểu thức" đếm ra **3 chỗ hở**, nhưng hai trong ba được ép ở một biểu
thức khác cách đó vài dòng. Con số đúng là **1**, và tôi chỉ biết thế sau khi đọc
từng chỗ chứ không sau khi chạy máy quét. Máy quét ra lead, không ra phán quyết.

### Đo thật, không đọc

`tests/qa/backend-100055-phep-cong-bill-104/probe_sum_ra_decimal.py` — migrate một
schema riêng bằng Alembic tới head trên **PostgreSQL 16.14 / psycopg** thật, seed
chuỗi thật (person → context → batch → version → bank_recipient → snapshot →
obligation → 2 receipt confirmation), rồi gọi **chính hàm** `get_obligation_amounts`:

```
receipts seeded: 120,000 + 80,000

app/db/repository.py :: get_obligation_amounts() returned
  obligation_amount_vnd    = 200000                 int
  confirmed_amount_vnd     = Decimal('200000')      Decimal
  remaining_amount_vnd     = Decimal('0')           Decimal
```

`@dataclass(frozen=True, slots=True)` khai cả ba là `int`. Dataclass không kiểm gì
khi dựng, nên annotation đó là một lời comment. `remaining_amount_vnd` là
`max(int - Decimal, 0)` nên nó thừa hưởng `Decimal` — đúng cái cơ chế anh mô tả
cho phép cộng, chỉ khác là ở đây phép trừ.

### Vì sao tôi vẫn báo, dù nó chưa hỏng gì

`get_obligation_amounts` **không có người gọi nào** trong `app/` hay `tests/` —
grep toàn cây chỉ ra đúng định nghĩa của chính nó. Nên đây **không phải lỗ đang
mở**, không có người dùng nào đang thấy `520000.0`.

Nó đáng báo vì `CLAUDE.md` viết: *"Trạng thái nghĩa vụ suy ra từ event […]; xem
`app/db/repository.py` cho dạng aggregate đúng."* File được chỉ ra làm **mẫu để
chép** lại là file duy nhất thiếu đúng cái `int()` mà cả năm anh em của nó đều có
kèm comment cảnh báo. Người viết chỗ thứ hai sẽ chép cái khuôn này.

**Tôi không sửa** — anh dặn không sửa gì lượt này, và nó nằm ngoài phạm vi
`bill.py:104`. Đề nghị: một việc riêng, nhỏ, kèm một ca `tests/postgres/` (SQLite
bị từ chối có chủ ý, và fake repository sẽ trả `int` nên nó **không** bắt được lỗi
này — đây đúng là loại hành vi persistence mà `CLAUDE.md` bắt phải có ca live).

---

## 4. Cái này KHÔNG chứng minh

- **Không** chứng minh một `float` có thể *tới được* `bill.py:104` trong sản xuất.
  Probe gọi thẳng hàm domain, cố ý đi vòng qua HTTP. Đường ghi đã được #460 đo
  trên Postgres thật (cột `BigInteger`; Postgres **làm tròn** `1500.5 → 1500` chứ
  không từ chối; `bool` thì bị từ chối) và #452 đo 5/5 đường HTTP không lọt.
- **Không** chứng minh `allocate()` là chặng duy nhất phía sau `bill.py:104` cho
  *mọi* đường tương lai — chỉ cho đường `split_bill` hôm nay.
- Máy quét đọc **hình dạng**, không đọc **hành vi**: pass A đầy đủ với `/` viết
  bằng `/`, nhưng mù với `operator.truediv`, `__truediv__`, hay một phép chia nằm
  trong thư viện. Pass B/C lọc theo **tên**, mà tên thì người chép đổi được.
- **Trục đếm thứ hai chưa có.** Tôi có giao cho Codex một phép đếm độc lập (trục
  của nó, không cho nó biết số của tôi) đúng theo cách anh dặn lúc 06:22. Nó chạy
  hết 210k token, đọc `service.py` từng dòng, rồi **hết quota** trước khi trả lời
  (`You've hit your usage limit`, reset 2:24 PM). Nên **census ở mục 2 đứng trên
  một trục duy nhất**. Tôi nói ra chỗ này thay vì để con số 27 trông như đã được
  đối chứng.

---

## Đề nghị

1. **`bill.py:104`: không cần sửa.** Nhưng ghi nhận rằng nó được bảo vệ bởi
   `allocate()` chứ không bởi chính nó — nếu có ai thêm một người gọi
   `allocator_input_from_bill` mà không đi tiếp vào `allocate()`, hàng rào biến mất
   im lặng. Probe trong PR này là chỗ để cắm một ca gác nếu anh muốn.
2. **`app/db/repository.py:31`: một việc riêng.** Thêm `int()` + một ca
   `tests/postgres/`. Nhỏ, nhưng chạm tiền, nên theo luật của anh nó phải chờ
   phán quyết QA chứ không merge theo dấu xanh.
3. `preferences.py:179` dùng `_integer_count` cho một giá trị tiền — suggestion,
   không phải blocker.
