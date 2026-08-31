# FAIL — PR #488, cổng Luật 1 phía biểu thức SQL

**Lý do, viết trước phần chi tiết.** Bảy bản sửa mã sản phẩm trong PR này **đúng và
đã được đối chứng**: cổng mới ra đúng 7 finding trên mã `main@7fff89c` và 0 finding
sau bản sửa, và bảng đột biến cho thấy cổng bắt được **cả 7 cast bỏ từng cái một**.
Cái làm nó FAIL là một lớp đột biến khác: **bỏ MỘT dòng gọi khỏi
`_drive_money_query_surface` trong khi giữ tên trong `MONEY_QUERY_SURFACE` thì cổng
in xanh và không có gì kêu lên** — 4/4 điểm vào đều lọt, và 3/3 khi ghép thêm một
bản lùi cast THẬT thì **cả cây `tests/postgres` in `550 passed`** trong lúc
`load_confirmed_receipts` đã quay về trả `numeric`. Docstring của chính file khai
rằng số câu lệnh quan sát được "asserted below"; phép đo cho thấy nó chỉ được
`assert ... > 0`. Gỡ chặn rẻ: ràng đúng con số, hoặc sinh phần lái ra từ chính
`MONEY_QUERY_SURFACE` để tên và lời gọi không thể lệch nhau.

---

## Đo tại đâu

```
đo tại   b53321e571fcad540bda75ba3e58fd93f18a364b   (nhánh backend/cong-bieu-thuc-sql-tra-tien-phai-la-so-nguyen)
sha này  là nhánh CHƯA merge, dựng thẳng trên origin/main@7fff89c
         git merge-base --is-ancestor origin/main HEAD  ->  0 (main là tổ tiên)
đối chứng đo tại  7fff89c  (origin/main lúc bắt đầu lượt)
cây làm việc      sạch trước và sau mỗi đột biến (git status --porcelain rỗng)
```

Không có commit nào mới trên `origin/main` giữa lượt: `git log HEAD..origin/main` rỗng.

## Cái gì đã thật sự chạy

| Lệnh | Kết quả thật |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | `2883 passed, 606 skipped, 5272 subtests passed in 315.31s` |
| `make test-db` (Postgres dùng-một-lần, cả hai cây) | `tests/postgres` ĐẠT · `../../tests/qa` ĐẠT `89 passed` |
| `tests/postgres` đầy đủ, `MOBILE_REQUIRE_POSTGRES_TESTS=1` | `550 passed in 72.51s`, **0 skipped** |
| Riêng cổng mới | `11 passed in 1.08s` |
| `ruff check` file QA mới | `All checks passed!` |

## Đối chứng: cổng ĐỎ trước, XANH sau — trên chính file thật

Không dùng đột biến bịa. Lùi `services/api/app/api/repository.py` về đúng bản
`origin/main` rồi chạy cổng mới:

```
git checkout origin/main -- services/api/app/api/repository.py
MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres/test_money_expressions_are_integer_postgres.py -q
```

```
AssertionError: 7 result column(s) came back inexact out of 46 observed across 19 statements:
    'split_total_vnd' is numeric   <- group_recap
    'sum_1'           is numeric   <- load_confirmed_receipts
    'coalesce_1'      is numeric   x5  <- person_finance_summary
1 failed, 10 passed
```

Sau khi khôi phục: `11 passed`. **Đúng 7 finding, đúng những tên PR khai.** Con số
PR nộp tái lập được từng chữ.

## Bảng đột biến — 18 mutant, bỏ TỪNG thứ một

Chạy lại được bằng một lệnh; máy đột biến đã commit ở
`tests/qa/qa-tt-0002-488/dot_bien_cong_bieu_thuc_sql_488.py`. Nó **tự dò** 7 điểm
cast bằng AST, **tự nhập** `MONEY_QUERY_SURFACE` từ module cổng, và **tự tìm** dòng
gọi trong thân hàm lái — không mang danh sách viết tay nào, nên nó không thể im
lặng đo thiếu khi cây mọc thêm điểm thứ tám.

```
scripts/postgres_tier.sh --keep -k money_expressions     # in ra URL
MOBILE_TEST_DATABASE_URL='<URL đó>' \
  python3 tests/qa/qa-tt-0002-488/dot_bien_cong_bieu_thuc_sql_488.py
```

```
tim thay 7 diem cast(..., BigInteger) trong repository.py
MONEY_QUERY_SURFACE co 4 ten: group_recap, load_confirmed_receipts,
                              person_finance_summary, obligation_amounts_statement

M0  không đột biến                                        rc=0  11 passed
C1..C7  lùi TỪNG cast một cái một                         rc=1  1 failed, 10 passed   -> BẮT ĐƯỢC 7/7
N1..N4  bỏ TỪNG tên khỏi MONEY_QUERY_SURFACE              rc=1  1 failed, 10 passed   -> BẮT ĐƯỢC 4/4
D1..D4  bỏ DÒNG GỌI, GIỮ tên trong list                   rc=0  11 passed             -> LỌT 4/4
P1..P3  bỏ dòng gọi VÀ lùi 1 cast THẬT của chính nó        rc=0  11 passed             -> LỌT 3/3

7 đột biến SỐNG SÓT
```

Canary của chính máy đột biến, chạy cùng lượt — số 0 của nó có nghĩa:

```
thiếu MOBILE_TEST_DATABASE_URL   -> exit 2 "KHONG KIEM DUOC"   (không phải exit 0 im lặng)
cây có thay đổi chưa commit      -> exit 2 "KHONG KIEM DUOC"
nền đã đỏ sẵn                    -> exit 2 (bảng trên cây đỏ không phân biệt được gì)
không tìm thấy điểm cast nào     -> exit 2 (danh sách nguồn rỗng không được đọc thành "đã phủ")
```

## Blocker (loại 1: vi phạm spec/cổng)

**Dẫn chứng.** Ba lớp `C`, `N`, `D` phủ ba hướng trôi dạt. Hai hướng đầu được gác.
Hướng thứ ba — dòng gọi biến mất khỏi `_drive_money_query_surface` — không có gì gác.
Đo thật, mutant P2 (bỏ `repository.load_confirmed_receipts(context_id)` **và** lùi
`cast(func.sum(ReceiptConfirmation.amount_vnd), BigInteger)`):

```
MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q
550 passed in 72.51s
```

Cả tầng duy nhất chạm SQL thật, 550 ca, xanh hết — trong khi
`load_confirmed_receipts` đã quay về khai `numeric`, đúng cái lớp lỗi PR này tồn tại
để chặn.

Vì sao hướng này không được gác: `test_recorder_is_actually_watching` là sàn
**chống-rỗng**, không phải phép đếm.

```python
assert recorder.statements_seen > 0, "recorder saw no statements at all"
assert recorder.result_columns_seen > 0, "recorder saw no result columns at all"
```

Bỏ 1 trong 4 điểm vào thì `statements_seen` tụt từ 19 xuống còn ~14 — vẫn `> 0`, vẫn
xanh. Đây đúng chuỗi mà Lead đã chốt lúc 11:18 qua #430 → #465 → #471: *chặn trạng
thái CỰC ĐOAN (rỗng) rồi tưởng đã chặn cả vùng.* Một bảng **mất một tên** vẫn không
rỗng, vẫn chạy, vẫn in xanh — và nó là trạng thái dễ xảy ra hơn hẳn bảng rỗng.

**Và docstring khai một phép ràng không tồn tại.** Dòng 63–66 của file cổng bảo vệ
đúng chỗ yếu nhất của nó bằng câu này:

> The difference from the name list is that it is *visible and countable* — **the
> number of statements observed is asserted below** and printed on failure —
> whereas "we forgot `func.avg`" was invisible by construction.

Grep toàn file: `statements_seen` chỉ xuất hiện ở `+= 1`, ở một `assert ... > 0`, và
ở chuỗi thông điệp lỗi của một test KHÁC. **Số được in, không được ràng.** Chỗ này
nặng hơn một comment lệch: nó là lời biện hộ duy nhất cho phần viết tay của cổng,
nên người đọc tin nó rồi NGỪNG kiểm — đúng kiểu hỏng "comment giải thích SAI giữ lỗi
sống thêm một ngày".

**Hậu quả.** Cổng có thể bị giải giáp cho một điểm vào bằng **một dòng bị xoá**, và
sau đó mọi hồi quy kiểu-biểu-thức ở điểm vào đó đi qua trong im lặng. Khác hẳn xoá
hẳn test (số ca tụt, nhìn thấy): ở đây `11 passed` không đổi, `550 passed` không đổi.

**Tiêu chí gỡ chặn — chọn một, cái nào cũng rẻ:**

1. Ràng đúng con số thay cho sàn `> 0`: `assert recorder.statements_seen == N` (hoặc
   `>= N` kèm hằng số nhìn thấy trong diff), để mất một điểm vào là đỏ; **hoặc**
2. Sinh phần lái ra từ chính `MONEY_QUERY_SURFACE` — ví dụ một `dict[str, Callable]`
   rồi lặp qua nó — để tên và lời gọi **không thể** lệch nhau, và
3. Sửa hoặc bỏ câu "the number of statements observed is asserted below" trong
   docstring cho khớp cái file thật làm.

Điều kiện nghiệm thu: chạy lại
`tests/qa/qa-tt-0002-488/dot_bien_cong_bieu_thuc_sql_488.py`, cả bốn mutant `D` và
ba mutant `P` phải ĐỎ. Không cần đổi một dòng nào trong 7 bản sửa `cast(...)` —
chúng đúng.

## Không phải blocker, ghi để tác giả biết

- Bảy `int(...)` phía caller **vẫn còn** (kiểm tại `repository.py:1887` và ở cả 5
  chỗ trong `person_finance_summary`). Nên hôm nay giá trị giao ra vẫn là `int` kể
  cả khi lùi cast, và không có bug tiền đang sống trên `main` vì chuyện này. Bản
  sửa của PR là lớp cho **kiểu của biểu thức**, không phải lớp duy nhất cho giá trị
  — đúng như PR tự khai. Điều đó làm hậu quả của blocker trên nhẹ hơn, nhưng không
  làm nó biến mất: thứ cổng này tồn tại để gác chính là lời khai của biểu thức.
- `test_money_values_reaching_python_are_int` không đi qua hàm lái, nên nó **không**
  bị mutant D làm mù — nhưng nó chỉ phủ `person_finance_summary` và `group_recap`.
  `load_confirmed_receipts` và `obligation_amounts_statement` không có lớp thứ hai
  nào ở tầng này.
- Kiểm `bool` bằng `type(value) is not int` ở dòng 307 là đúng cách: `bool` là lớp
  con của `int` và sẽ lọt `isinstance`.
- Đối chứng dương cho `round -> float8` (không phải `numeric`) là một chi tiết
  thật, đã tự chạy lại và đúng: một cổng đoán "nới kiểu nghĩa là numeric" sẽ mù với
  nó.

## Ô CHƯA quét

- **Mã VietQR chưa được quét bằng app ngân hàng thật.** Không agent nào làm được;
  chỉ leader, bằng một điện thoại thật.
- **Trang khách**: không quét lượt này. PR không đụng `app/web/`, nhưng
  `person_finance_summary` và `group_recap` có phục vụ màn Cá nhân — chưa đi bộ qua
  giao diện để xem con số hiện ra thế nào.
- **`apps/mobile && npm test`**: KHÔNG chạy lượt này. PR không đụng `apps/mobile/`
  và diff chỉ có 2 file phía server. Đây là ô trống thật, không phải ô đã phủ.
- **`npm run test:e2e` / lát cắt dọc**: chưa chạy. Nghĩa là chưa có bằng chứng hành
  vi nào rằng số tiền do 7 query đã sửa đi ra tới client vẫn đúng — chỉ có bằng
  chứng KIỂU.
- **Trôi dạt liên-module**: máy đột biến chỉ mutate 2 file. Một query tiền mới ở
  module thứ ba nằm ngoài mọi phép đo trong lượt này.
- **jsonb**: PR tự khai là ngoài phạm vi; tôi không kiểm, và đồng ý là ngoài phạm vi.

## Và một câu không được bỏ

Repo này **chưa có bằng chứng hành vi nào** (ADR-0006, Giai đoạn 0 bị gác theo quyết
định của chủ sản phẩm). `550 passed` nói rằng SQL khai đúng kiểu; nó không nói người
thật thấy đúng số.
