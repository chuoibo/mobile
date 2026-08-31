# PASS #497 — cổng Luật 1 phía GHI

**Phán quyết: PASS.**

**Lý do, viết trước phần chi tiết:** mọi con số #497 khai đều tái lập được bằng
phép đo độc lập (551 passed · 12 passed · 7/7 đột biến bị bắt · bảng 8 ứng viên
giống từng dòng), và lỗ nó vá là lỗ THẬT — trên cây trước PR, một `float` ghi
thẳng vào sổ cái vẫn cho **539/539 xanh**. Nhưng cổng này với tới **biên
repository, không với tới trên đó**: bơm `float` ở `service.py` trên đường HTTP
thật thì **551/551 vẫn xanh**, trong khi chính máy quan sát của #497 — khi chĩa
vào đúng đường đó — đếm được **6 lần bind float** vào 6 cột nằm TRONG nhóm 11 cột
mà cổng in ra là "đã được lái chạm tới". Đó là câu trả lời cho câu hỏi Lead để
lại ở #460: **không**, #497 không gác 5 nguồn thượng nguồn.

- protocol_version: v1
- Đo tại `0feb017` (head PR lúc nhận việc)
- SHA này: **đã vào main** — squash `9ddd65a`, merged 2026-08-31T15:31:12Z, ngay
  giữa lượt đo của tôi. Cả **ba file** của PR **giống nhau từng byte** giữa
  `0feb017` và `9ddd65a`, nên mọi số dưới đây chuyển nguyên sang bản đang chạy.
  Đây là hậu kiểm sau merge, không phải cổng chặn merge.
- Kỹ năng: `e2e-testing`, `bug-reproduction`

---

## 1. Mọi con số của PR, đo lại độc lập

Cây sạch, database dùng-một-lần do `scripts/postgres_tier.sh --keep` dựng
(PostgreSQL 16.14, container riêng, không đụng lane nào).

| PR khai | Tôi đo được | Khớp |
|---|---|---|
| `tests/postgres` 551 passed | **551 passed in 76.16s**, 0 skipped | ✅ |
| riêng cổng mới 12 passed | **12 passed in 1.64s** | ✅ |
| vùng mù 24 cột / lái chạm 11 / chưa phủ 13 | **24 / 11 / 13**, đúng 13 tên đó | ✅ |
| bảng đột biến 7/7 bắt được, A1 xanh lại | **7/7 bắt được, A1 rc=0 12 passed** | ✅ |
| bảng đo 8 ứng viên: 1 từ chối · 3 đúng · 4 đổi số | **giống từng dòng** | ✅ |
| `repo_guard range` | **passed, 4049 file scan trong 3 commit** | ✅ |
| `ruff check` | **All checks passed!** (cả 3 file) | ✅ |
| cổng offline 2882 passed / 608 skipped | **2881 passed / 609 skipped / 5272 subtests** | ⚠️ lệch 1 |
| tầng postgres BỎ cổng, dưới M1/M2: 553 passed | **539 passed** trên cây trước PR | ⚠️ số khác |

Hai ô lệch, cả hai đều **không** đổi kết luận:

- **2881 vs 2882.** Chênh đúng một ca, và nó là ca skip
  `tests/test_phone_path.py:398: apps/mobile/node_modules chưa cài`. Khác biệt
  môi trường (tác giả đã cài node_modules, tôi chưa), không phải khác biệt code.
- **539 vs 553.** `tests/postgres` trên `7fff89c` collect đúng **539**, và trên
  cây PR đúng **551** — chênh 12 là 12 ca cổng mới, cộng trừ khớp. Con số 553 của
  PR tôi không dựng lại được từ cây nào. **Hướng thì y hệt**: xanh toàn phần,
  không một ca nào thấy gì.

## 2. Lỗ có thật — tái lập trên cây TRƯỚC PR, không suy luận

Kỷ luật `bug-reproduction`: phải chứng minh bản cũ hỏng ở đúng chỗ PR nói.

Cây `7fff89c` (main trước PR), đột biến một dòng — `save_receipt_confirmation`
ghi `float(amount_vnd)` vào sổ cái, dòng `repository.py:4178`:

```
539 passed in 76.47s   rc=0
```

**539/539 xanh** trong lúc một `float` đang được ghi vào chính bảng mà số dư được
tính lại từ đó. Không một tầng nào trong repo nhìn thấy. Lỗ này có thật, và trước
#497 không có gì gác.

Cùng đột biến ấy trên cây PR:

```
3 failed, 9 passed   rc=1
  test_no_money_column_is_ever_written_a_non_integer
  test_recorder_passes_a_value_known_to_be_lawful
  test_the_column_itself_refuses_almost_nothing
```

Đỏ trước / xanh sau, đúng chiều, và trùng khít dòng M1 trong bảng của PR.

## 3. Phát hiện — vùng mù thứ tư, không có trong mục "does NOT prove"

Docstring của #497 khai ba giới hạn: cột đặt tên ngoài quy ước · money trong
`jsonb` · xoá hẳn một entry khỏi `MONEY_WRITE_SURFACE`. Có một giới hạn thứ tư,
lớn hơn cả ba, và nó không được nói ra.

### 3.1 Bề mặt được lái dừng ở biên repository

`Slice` (mượn từ `test_person_finance_postgres.py`) dựng
`SqlAlchemyApiRepository(session)` rồi gọi **thẳng** các method của repository,
với `rollups` và `allocations` là **số nguyên viết tay trong chính fixture**.
`app/api/service.py` **không bao giờ được chạy** bởi cổng này.

Nên cổng đo được: "repository có làm hỏng một `int` nó được đưa không".
Cổng **không** đo được: "cái đưa cho repository có phải `int` không".

### 3.2 Đo, không suy: bơm float ở thượng nguồn

Đột biến một dòng ở `services/api/app/api/service.py:3789`, ngay trước lời gọi
`save_expense_confirmation` — đúng đường HTTP thật:

```python
rollups={k: float(v) for k, v in component_rollups(domain_expense).items()},
```

Cả tầng postgres trên cây PR:

```
551 passed in 74.53s   rc=0
```

### 3.3 Kiểm tương đương trước khi tin con số xanh đó

Một đột biến xanh có thể chỉ là no-op. Đổi đúng dòng ấy thành `1 / 0`:

```
28 failed, 523 passed   rc=1
  13× test_group_recap_postgres.py
  11× test_suggestion_postgres.py
   2× test_idempotency_postgres.py
   1× test_group_budget_postgres.py
   1× test_expense_participant_membership_postgres.py
```

Dòng đó **có chạy**, 28 ca đi qua nó. Nên `551 passed` ở trên là mù thật, không
phải mù vì không ai chạm.

### 3.4 Chính máy quan sát của #497 bắt được — khi được chĩa đúng chỗ

Probe QA dùng lại `recording()` của #497 nguyên vẹn, nhưng lái qua `live_client`
(ASGI thật, HTTP thật) thay vì gọi thẳng repository:

```
confirm status = 201
tổng số bind tiền quan sát được = 8
    expense_versions.subtotal_amount_vnd <- 82000.0 (float)
    expense_versions.fee_amount_vnd      <- 0.0     (float)
    expense_versions.vat_amount_vnd      <- 0.0     (float)
    expense_versions.shipping_amount_vnd <- 0.0     (float)
    expense_versions.discount_amount_vnd <- 0.0     (float)
    expense_versions.total_amount_vnd    <- 82000.0 (float)
    confirmed_allocations.amount_vnd     <- 41000   (int)
    confirmed_allocations.amount_vnd     <- 41000   (int)
VI PHẠM (không phải int) = 6
```

**Máy đo đúng và đủ. Cái mù là bề mặt được lái.**

Đối chứng hai đầu của chính probe này, chạy trên `9ddd65a` (bản ĐANG CHẠY):

| | probe báo | cổng #497 báo |
|---|---|---|
| main sạch | 8 bind, **0 vi phạm** | 12 passed |
| + đột biến `service.py:3789` | 8 bind, **6 vi phạm** | **12 passed** |

Dòng cuối là toàn bộ phát hiện: sáu `float` đang đi vào cột tiền trên đường HTTP
thật, và cổng vẫn in **12 passed** trên chính SHA đã ship.

### 3.5 Vì sao điều này quan trọng hơn con số 13 cột chưa phủ

Sáu cột bị bind float ở trên — `expense_versions.{subtotal,fee,vat,shipping,
discount,total}_amount_vnd` — **nằm trong nhóm 11 cột** mà
`test_money_columns_never_written_by_the_driver` in ra là "được lái chạm tới".

Nên bản đồ vùng mù mà #497 in ra mỗi lượt **hẹp hơn vùng mù thật**. Người đọc
dòng `24 | 11 | 13` sẽ hiểu 11 cột kia đã được gác. Đo được: 6 trong 11 cột đó
không được gác trước float đến từ thượng nguồn. Câu chữ trong file thì đúng
("được lái chạm tới" ≠ "đã được gác"), nhưng con số sẽ bị trích dẫn như một tỉ lệ
phủ, và ở dạng đó nó nói quá.

Đây đúng hình dạng Lead ghi lúc 11:18 — chặn một trạng thái cực đoan rồi tưởng đã
chặn cả vùng.

### 3.6 Trả lời thẳng câu Lead để lại ở #460

Lead hỏi: #497 có gác được 5 nguồn không qua rào pydantic không, đặc biệt phép
cộng ở `bill.py:104`?

**Không.** Phép cộng đó (`domain/bill.py:103-107`,
`sum(item["amount_vnd"] …) + sum(surcharge…) - sum(discount…)`) nằm ở tầng
domain, thượng nguồn của repository, và `bills.*` / `bill_items.*` là 4 trong 13
cột **chưa** được lái chạm. Cả hai lớp đều không với tới nó. Cộng `int` với
`float` ra `float`, và không rào nào trên đường đó nhìn thấy.

## 4. Cách chạy lại

```bash
scripts/postgres_tier.sh --keep                # in ra URL database dùng-một-lần
export URL='<URL nó in ra>'

cd services/api && MOBILE_TEST_DATABASE_URL="$URL" MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest tests/postgres/test_money_writes_are_integer_postgres.py -q -s
MOBILE_TEST_DATABASE_URL="$URL" python3 tests/qa/backend-tt-0004-ghi-tien/probe_ghi_tien_khong_nguyen.py
MOBILE_TEST_DATABASE_URL="$URL" python3 tests/qa/backend-tt-0004-ghi-tien/dot_bien_cong_ghi_tien.py

# vùng mù thượng nguồn — đột biến ở services/api/app/api/service.py:3789
#   rollups={k: float(v) for k, v in component_rollups(domain_expense).items()},
cd services/api && MOBILE_TEST_DATABASE_URL="$URL" MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest tests/postgres -q          # 551 passed — mù
# kiểm tương đương: đổi float(v) thành 1 / 0  -> 28 failed, dòng đó CÓ chạy
```

## 5. Ô CHƯA quét — phần quan trọng nhất

- **`apps/mobile && npm test` không chạy.** PR không đụng client. Ca
  `tests/test_phone_path.py:398` skip vì `apps/mobile/node_modules` chưa cài
  trong cây tôi đo.
- **`npm run test:e2e` (lát cắt dọc) không chạy.** Không có bằng chứng **hành
  vi** nào ở lượt này; chỉ có bằng chứng kiểu và bằng chứng bind.
- **13 cột tiền chưa được lái chạm** — nguyên danh sách in ra ở §1, gồm cả
  `bill_items.*`, `bills.*`, `collection_obligation_progress.*`.
- **Money trong `jsonb`** — ngoài mọi luật ở đây, và tôi cũng không đo.
- **Cột tiền đặt tên ngoài quy ước `_vnd` / `amount`** — cả #486 lẫn #497 đều
  không với tới; tôi không quét xem có cột nào như vậy không.
- **Số có ĐÚNG không** — cổng này chỉ nói về kiểu. Một `int` sai vẫn qua sạch.
  41 golden vector là chỗ khác.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Không agent nào quét được;
  chỉ leader đóng được câu này.
- **Đường thượng nguồn (service, HTTP, allocator marshalling)** — tôi mới đo
  ĐÚNG MỘT điểm bơm (`service.py:3789`). Còn 8 nguồn khác trong bản đồ #460 tôi
  **chưa** đo từng cái.

## 6. Phân loại theo 5 loại blocker

Không có blocker. Phát hiện ở §3 là **suggestion có dẫn chứng**, không phải
blocker: #497 không làm sai tiền, không làm hỏng gì đang chạy, và câu chữ trong
docstring của nó đúng theo nghĩa đen. Nó chỉ để lại một vùng mù lớn hơn bản đồ mà
chính nó in ra.

Đề xuất việc tiếp (backend, không gấp):

1. Thêm một entry vào `MONEY_WRITE_SURFACE` lái qua **service/HTTP** thay vì
   repository, để 11 cột đang "được lái chạm" thực sự được gác cả từ thượng
   nguồn. Probe ở §3.4 là bản mẫu chạy được.
2. Bổ sung giới hạn thứ tư vào mục "does NOT prove", và làm rõ trong dòng in
   rằng `11` là "được lái chạm ở tầng repository", không phải "đã được gác".
