# Cổng #486 gác được KIỂU nhưng không gác được PHÉP ĐỌC của chính nó

    đo tại   7fff89c0edaab2f18c2ba5c133aa3e2820c78a5b
    sha này  ĐÃ ở main (merge bằng #486)
    lượt     qa-tt-0001
    kỹ năng  e2e-testing · bug-reproduction

## PASS — cổng đầy đủ trên main xanh

| Cổng | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2882 passed, 596 skipped**, 5272 subtest, 299s |
| `make test-db` (PostgreSQL thật, DB dùng-một-lần) | `tests/postgres` **ĐẠT** · `tests/qa` **ĐẠT** (89 passed) |
| `cd apps/mobile && npm test` | **1032 pass / 0 fail**, 24 suite, 21.2s |
| migration render ra DDL (từ `services/api`) | exit 0 |
| `python3 scripts/repo_guard.py tree HEAD` | passed, 1348 file |
| 10 ca của #486 trên PostgreSQL live | **10 passed** |

596 skipped ở lệnh đầu là tầng Postgres khi chưa có URL — chúng đã chạy thật ở
`make test-db`, không phải ô trống.

## Phát hiện 1 — sàn chống-rỗng của #486 chỉ gác 4/41 bảng

#486 tự đặt ra một sàn và tự nói vì sao nó cần:

> "A gate whose input list is empty passes by saying nothing. Both rules below
> are 'no row satisfies X'. An empty enumeration satisfies them for free, so the
> schema read has to be shown non-empty first or the green means nothing."

```python
assert len(columns) > 200          # thực đo: 293  -> biên độ 92 cột
assert len(money_named) >= 20      # thực đo:  24  -> biên độ  4 cột
```

Sàn trả lời câu **"phép đọc có RỖNG không"**. Nó không trả lời câu
**"phép đọc có MẤT một bảng không"** — và đó mới là chuyện xảy ra được.

### Đo: bỏ MỘT bảng khỏi phép đọc, đủ 41 bảng

`dot_bien_bo_mot_bang.py` sửa chính câu SQL trong `_columns()` để loại đúng một
bảng, xoá bytecode cache, chạy lại **10 ca thật** trên PostgreSQL thật đã migrate,
rồi khôi phục. Một bảng một lượt, đủ 41 bảng — không phải chọn một bảng để thử.

```
canary baseline   : GREEN  10 passed
canary empty-read : RED    2 failed, 8 passed     <- sàn CÓ nổ khi rỗng hẳn
canary blind-name : RED    4 failed, 6 passed     <- sàn tiền CÓ nối dây

37/41 bảng biến mất khỏi phép đọc mà KHÔNG ca nào trong 10 ca đỏ
bảng TIỀN đi lọt: 13/14
```

Bốn bảng bị bắt: `expense_versions` (6 cột tiền, đủ để 24→18 phá sàn), và
`memories` · `audit_events` · `messages` — ba bảng này bị bắt vì có **tên trong
allowlist viết tay**, không phải vì luật tiền.

Nói cách khác: cổng chỉ nhận ra một bảng biến mất khi bảng đó tình cờ được gọi
tên sẵn trong file, hoặc tình cờ mang ≥5 cột tiền. Mười ba bảng tiền còn lại —
`bills`, `bill_items`, `confirmed_allocations`, `collection_obligations`,
`receipt_confirmations`, … — rời khỏi phép đọc trong im lặng hoàn toàn.

### Đây không phải giả thuyết: đường tới được, đo được

`information_schema.columns` **lọc theo quyền**: nó chỉ hiện cột của bảng mà
role hiện tại có quyền. Thiếu đúng một dòng `grant` là mất nguyên một bảng.

```
chủ sở hữu (mobile)        cột=293 (>200 ĐẠT)  tiền=24 (>=20 ĐẠT)  confirmed_allocations: CÓ
qa_reader thiếu 1 quyền    cột=287 (>200 ĐẠT)  tiền=23 (>=20 ĐẠT)  confirmed_allocations: KHÔNG
```

Cả hai sàn vẫn ĐẠT, và `confirmed_allocations` — sổ phân bổ đã chốt — **không
có mặt trong phép đọc**. Cổng in xanh trên một schema nó chưa từng nhìn.

**Nói rõ mức độ:** hôm nay tier chạy bằng role sở hữu (`postgres_tier.sh` dựng
container riêng), nên đường này đang **NGỦ**, chưa sống. Nó tỉnh dậy vào ngày ai
đó chạy tier bằng role hạn quyền, hoặc CI chuyển sang DB dùng chung có phân
quyền. Câu thứ hai — `where table_schema = current_schema()` — hở theo cùng một
kiểu nếu có bảng nào rơi sang schema khác.

Sàn `>200` / `>=20` không phụ thuộc đường nào tới được: nó **không đo được điều
nó được viết ra để đo**, dù nguyên nhân mất bảng là gì.

### Tiêu chí gỡ chặn

So số bảng/cột đọc được với một con số **suy ra từ chính models** thay vì một
hằng viết tay — ví dụ `set(Base.metadata.tables) - set(bảng đọc được) == set()`.
Sàn khi đó nổ vì *mất một bảng*, không phải vì *rỗng*.

## Phát hiện 2 — cột tiền tên lạ, kiểu ngoài họ số, đi lọt CẢ HAI luật

Docstring của file khai:

> "A money column added tomorrow is caught whatever it is called, because the
> rule is stated over the column's *type*, not over its *name*."

Câu đó chỉ đúng **trong họ numeric**. Ngoài họ đó, luật kiểu không thấy, và luật
tên chỉ bắt khi tên khớp `endswith("_vnd") or "amount" in name`:

```
gia_tri    text          luật KIỂU: KHÔNG   luật TÊN: KHÔNG   -> ĐI LỌT CẢ HAI LUẬT
so_tien    varchar(32)   luật KIỂU: KHÔNG   luật TÊN: KHÔNG   -> ĐI LỌT CẢ HAI LUẬT
tong_cong  jsonb         luật KIỂU: KHÔNG   luật TÊN: KHÔNG   -> ĐI LỌT CẢ HAI LUẬT
```

Tên tiếng Anh cũng lọt như thế: `total`, `price`, `fee`, `subtotal`, `balance`,
`cost` đều không khớp heuristic.

Bảng đối chứng dương của #486 **không thể** thấy ô này, vì nó tự loại ô đó ra:

```python
assert caught_by_type_rule or caught_by_name_rule, (
    "this row claims neither rule catches the column, which would make "
    "it a documented hole rather than a control")
```

Dòng đó biến "chưa ai phủ" thành "không được phép khai" — mục "does NOT prove"
ở đầu file liệt kê jsonb, biểu thức SQL và làm-tròn-float, nhưng **không** liệt
kê ô này.

## Ô CHƯA quét lượt này

- `npm run test:e2e` (lát cắt dọc thật qua uvicorn + Postgres) — **chưa chạy**.
- Ma trận ảnh trang khách (trạng thái × sáng/tối × 320/390/1440) — **chưa quét**.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Chỉ leader đóng được câu này.
- Phát hiện 1 mới đo trên `information_schema`; chưa đo đường schema-thứ-hai.

## Phân loại theo 5 loại blocker của charter

Cả hai phát hiện thuộc loại **1 — vi phạm spec/cổng**, ở mức **không chặn
merge**: #486 là cải thiện ròng (trước nó không có cổng nào ở tầng này) và không
làm gì tệ đi. Chúng là nợ cần trả ở lượt sau, không phải lý do lùi #486.

**Không** có phát hiện loại 2 (sai tiền): không cột tiền nào trên main hiện sai
kiểu — 10 ca của #486 xanh thật trên schema thật.
