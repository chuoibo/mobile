# PASS cho PR #416 tại `691710b` — bản vá là thật; cổng thì tốt hơn hai đời trước và vẫn mù hai kiểu đo được

- task: `qa-tt-0055`
- protocol_version: v1
- verdict: **APPROVE**
- skill: `e2e-testing`, `bug-reproduction`

```
đo tại   671178f  = #416@691710b ⊕ main@f6c4518   (merge sạch, chiến lược ort)
691710b  là nhánh CHƯA merge
f6c4518  là main lúc đo; main đã nhích 12 commit kể từ lúc PR tự merge main@2fcd723
         — không commit nào trong 12 cái đó chạm ledger.py hay tests/domain/
```

## Lý do, viết trước chi tiết

**PASS.** Hai lỗi PR này nói nó sửa là **thật**, tôi tái lập độc lập trên chính
code của `main` (không đọc lời PR): `confirmed_total` trả `0.3000…04` (float 17 chữ
số của `0.1+0.2`) từ một hàm khai `-> int`, và `obligation_status(0.5, …)` trả
`'over_confirmed'`
— giá trị quyết định một người còn nợ hay đã trả. Sau bản vá cả năm phép thử đều
`AMOUNT_NOT_INTEGER`. Cổng mới **đỏ được** ở bản trước bản vá, đỏ đúng 3 slot,
34 subtest còn lại vẫn xanh — probe đúng hình dạng, không phải đỏ vì dựng sai.
Ba tầng đều xanh trên cây gộp.

**Nhưng cổng KHÔNG phải là thứ chống mục ruỗng mà docstring của nó nói.** Tôi đo
được hai lỗ, cả hai sống sót **2718 passed / 0 failed** trên toàn cây:

1. **Tham số tiền mới khai bằng `None`** → sinh **0 slot**, dân số slot đứng yên
   ở 11, và `confirmed_total(…, waived_vnd=0.5)` trả **99.5**. Đây đúng là lỗi
   PR này tồn tại để sửa, đi vào lại qua cánh cửa cổng hứa đang gác.
2. **Vai trò "người ứng tiền" vắng mặt trong golden call** → mọi thay đổi riêng
   nhánh đó không làm đỏ gì.

Tôi **không** chặn merge vì hai lỗ này: chúng là khoảng mù của cổng cho thay đổi
**tương lai**, không phải tiền đang chảy sai, và không thuộc năm loại blocker của
charter. Chặn PR này còn giữ **hai lỗi sống** đang nằm trên `main`. Nhưng câu
trong docstring — *"adding it to the golden call then hands it to the float and
bool sweeps automatically"* — **đo được là SAI**, và nó là loại câu làm người sau
thôi kiểm lại. Xin sửa câu đó ở một PR nhỏ tiếp theo.

## 1. Đối chứng: lỗi có thật ở bản TRƯỚC (bug-reproduction)

Nạp thẳng `ledger.py` của `origin/main@f6c4518` bằng `importlib`, không dùng test
của PR, không tin mô tả PR:

| gọi | `main` f6c4518 | cây gộp 671178f |
|---|---|---|
| `confirmed_total([{0.1},{0.2}])` | `0.3000…04` (float) | `RAISE(AMOUNT_NOT_INTEGER)` |
| `obligation_status(3, [0.1, 0.2])` | `'partially_confirmed'` | `RAISE(AMOUNT_NOT_INTEGER)` |
| `obligation_status(0.5, [3])` | `'over_confirmed'` | `RAISE(AMOUNT_NOT_INTEGER)` |
| `obligation_status(True, [3])` | `'over_confirmed'` | `RAISE(AMOUNT_NOT_INTEGER)` |
| `obligation_status(300000.7, [3])` | `'partially_confirmed'` | `RAISE(AMOUNT_NOT_INTEGER)` |

Hàng 1 là vi phạm luật tiền 1 nhìn thấy được: hàm khai `-> int` trả `float`.

**Cổng mới có đỏ được ở bản cũ không** — thay `ledger.py` bằng bản `main`, chạy
đúng file test của PR:

```
7 failed, 33 passed, 34 subtests passed
SUBFAILED confirmed_total   receipt_confirmations (0,'amount_vnd')  float
SUBFAILED obligation_status declared_amount_vnd   ()                float
SUBFAILED obligation_status receipt_confirmations (0,'amount_vnd')  float+bool
```

Đỏ đúng ba slot, không đỏ tràn. Test không đỏ được ở bản cũ thì không chứng minh
gì — cái này đỏ được.

## 2. Đột biến: cổng cắn được cái gì, và mù cái gì

Commit TRƯỚC khi đột biến; khôi phục bằng `git checkout HEAD --` + xoá
`__pycache__`; kiểm lại nền sạch `34 passed, 40 subtests` sau mỗi lượt.

| # | Đột biến | test_ledger.py | Toàn cây |
|---|---|---|---|
| **D-B1** | Khai tham số tiền thứ 10 (`waived_vnd`), **chưa** thêm vào `GOLDEN_CALLS` | **ĐỎ** 1 failed | — |
| **D-A** | Phần chia của **chính người ứng tiền** đổi kiểm KIỂU → kiểm DẤU | **XANH** | **2718 passed** |
| **D-B2** | Cùng tham số đó, khai `"waived_vnd": None` vào `GOLDEN_CALLS` đúng như thông báo lỗi bảo làm | **XANH** | **2718 passed** |

**D-B1 bị giết — đây là phần cổng này làm được thật.** `inspect.signature` bắt
một tham số tiền mới **ngay khi được khai**, kể cả khi có giá trị mặc định. Cổng
đếm-theo-tên-export của đời trước không thể là thứ đó. Ghi nhận.

**D-B2 là lỗ nghiêm trọng hơn, và nó nằm ngay sau D-B1.** Thông báo lỗi của D-B1
bảo: *"add it, then declare it in NOT_MONEY_SLOTS if it is not dong"*. Người sửa
làm đúng vế đầu, khai bằng giá trị mặc định tự nhiên của tham số là `None`:

```
dân số slot          : 11  ->  11        (KHÔNG đổi — tham số tiền mới sinh 0 slot)
slot của confirmed_total: chỉ receipt_confirmations, như cũ
confirmed_total([100], waived_vnd=0.5)  -> 99.5
confirmed_total([100], waived_vnd=True) -> 99
toàn cây                                -> 2718 passed, 0 failed
```

`_integer_slots` chỉ sinh slot từ **lá số nguyên**. `None` không có lá nào, nên
tham số qua được `test_every_parameter_of_every_export_is_named_in_its_golden_call`
(ca này chỉ đòi tham số **CÓ MẶT**, không đòi giá trị vàng **CHỨA số nguyên**) rồi
biến mất khỏi cả hai phép quét float/bool. Cùng lớp: `[]`, `{}`, `0.0`.

Và đây mới là chỗ đau: docstring của chính ca đó viết *"adding it to the golden
call then hands it to the float and bool sweeps automatically"*. Đo được là sai.
Cổng gác được cái tên và cái chữ ký; phần **người phải tự nhớ điền một giá trị
nguyên thật** thì không có gì gác.

**D-A** — golden call của `obligations_from_allocations` là `{"ha": 100}` với
`advancer_id="nam"`: người ứng tiền **không có entry trong `allocations`**, nên
phần chia của chính họ không sinh slot nào. Đổi nhánh đó sang chỉ kiểm dấu:

```
ofa({"nam":0.5,  "ha":100}, "nam") -> chạy, không báo lỗi
ofa({"nam":True, "ha":100}, "nam") -> chạy, không báo lỗi
ofa({"nam":"100","ha":100}, "nam") -> TypeError trần (không phải LedgerError)
ca legacy test_a_negative_advancer_allocation_is_caught -> vẫn XANH (nó chỉ probe -100)
```

**Hậu quả hôm nay có giới hạn, tôi nói rõ để không ai đọc quá lời:** phần chia của
người ứng tiền bị `continue` bỏ qua nên float đó không đi vào obligation nào. Đây
là lỗ **phủ của cổng**, không phải tiền sai. Giá trị của nó là chỉ ra: golden data
chỉ phủ **vai trò thường**, nên mọi hành vi riêng của vai trò đặc biệt là vùng
không ai gác.

## 3. Cổng đầy đủ trên cây gộp `671178f` — cây sạch, chạy tay

```
python3 -m pytest services/api/tests tests -q
  -> 2718 passed, 580 skipped, 4938 subtests passed in 325.68s

MOBILE_TEST_DATABASE_URL=… MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q
  -> 523 passed in 88.86s          (PostgreSQL 16 THẬT, 0 skipped)

cd apps/mobile && npm test
  -> tests 974 · suites 23 · pass 974 · fail 0 · skipped 0

python3 scripts/repo_guard.py tree HEAD
  -> Repo guard passed tracked tree: 1266 file scan(s)

$(scripts/ruff_pinned.sh) check   ledger.py test_ledger.py -> All checks passed!   (ruff 0.9.2 bản ghim)
$(scripts/ruff_pinned.sh) format --check  cùng 2 file      -> 2 files already formatted
```

580 skip ở tầng 1 **được đóng**, không phải được giải thích: đó chính là
`tests/postgres` + `tests/qa/rd-qa-40`, và chúng chạy `523 passed / 0 skipped` khi
có `MOBILE_REQUIRE_POSTGRES_TESTS=1`.

Con số `2718 passed` xuất hiện **ba lần** trong báo cáo này — nền sạch, D-A, và
D-B2. Đó không phải trùng lặp, đó là phát hiện: hai đột biến không dời được một
con số nào.

## 4. Ô CHƯA quét — phần quan trọng nhất

- **`app/domain/` ngoài `ledger.py`** (allocator, bill, budget): không quét lượt
  này. Kết quả âm của PR về allocator tôi **không** kiểm lại.
- **`settlement_plan` vẫn tự viết phép kiểm** (`isinstance` riêng) vì phải cho
  phép số dư âm — PR tự khai, tôi xác nhận là còn nguyên, và **không** đo nó.
- **`allocator.py` không có cổng kiểu riêng** — PR tự khai, ngoài phạm vi, tôi
  không kiểm lại lượt này.
- **Lỗ D-A/D-B2 qua HTTP**: không dựng được. 21/21 cột tiền là `BigInteger` nên
  đường từ DB không mang float vào — đúng như PR nói. Cả hai lỗ là **tiềm ẩn**.
- **Mã QR quét bằng app ngân hàng thật**: chưa ai làm, vẫn mở, cần leader và một
  điện thoại thật (ADR-0010 mục 8).
- Không đi bộ trang khách / lát cắt dọc lượt này: PR chạm đúng 2 file domain +
  test, không đổi schema, không đổi persistence, không đổi route.

## 5. Phân loại theo 5 loại blocker của charter

| Phát hiện | Loại | Chặn? |
|---|---|---|
| D-B2 — tham số tiền mới khai `None` lọt cả hai phép quét | không thuộc 5 loại: khoảng mù cho thay đổi tương lai, không phải tiền đang sai | **không** |
| Docstring hứa phủ tự động — đo được là sai | như trên; là câu chữ trong cổng, nhưng là câu chữ làm người sau thôi kiểm | **không** |
| D-A — vai trò người ứng tiền không có trong golden data | như trên, hậu quả còn hẹp hơn (giá trị bị bỏ đi) | **không** |

Tiêu chí gỡ (nếu Lead muốn siết thành blocker, tôi ghi sẵn): `_money_slots` đòi
mỗi tham số không nằm trong `NOT_MONEY_SLOTS` phải sinh **≥ 1 slot**, và
`GOLDEN_CALLS["obligations_from_allocations"]["allocations"]` có thêm entry cho
chính `advancer_id`. Cả hai là sửa trong file test, không chạm sản phẩm.

## Điều không được đọc lệch

Cổng này là đời **thứ ba** của cùng một họ lỗi trong `ledger.py`: đếm theo TÊN
EXPORT (7) → đếm theo THAM SỐ (9) → duyệt lá số nguyên sinh SLOT (11). Mỗi đời
đơn vị đếm mịn hơn, mỗi đời vẫn còn mù, và mỗi đời đều có một câu docstring nói
rằng lần này đã kín. Đời này bắt được nhiều hơn hẳn hai đời trước — D-B1 là bằng
chứng. Nó vẫn không phải là "đã kín".

Và câu không được bỏ: repo này **chưa có bằng chứng hành vi nào** (ADR-0006).
2718 dấu xanh nói code làm đúng điều tác giả nghĩ; nó không nói người thật hiểu
sản phẩm.
