# PASS — PR #493

**Lý do:** hai con số của PR tái lập được bằng phép đo độc lập (37/41 → 0/41), PR
không đụng code sản phẩm, và cả bốn cổng đều xanh trên đúng SHA của PR. Nhưng
phép đo đi tiếp một bậc thì lộ ra: cơ chế mà chính PR nêu tên — `information_schema.columns`
lọc theo quyền — trong PostgreSQL lọc ở mức **CỘT**, không phải mức bảng. Ở
`8094a09`, **283/287 cột** và **21/21 cột tên tiền** rời được phép đọc mà toàn bộ
cổng vẫn in `16 passed`. Đây là phát hiện cho lượt sau, **không phải blocker của
PR này**: PR này chỉ làm chặt lại, không làm hỏng gì.

---

## Đo trên cái gì

```
đo tại   8094a09   (nhánh backend/cong-486-phep-doc-phai-phu-du-bang-cua-models)
sha này  là nhánh CHƯA merge = origin/main@7fff89c ⊕ đúng 1 commit
đối chứng 7fff89c ĐÃ ở main
```

`git merge-base origin/main <nhánh>` = `7fff89c` = `origin/main`. Nhánh không tụt
lại sau main, nên bản TRƯỚC của mọi phép đo dưới đây chính là `main` đang chạy.

Postgres: container `postgres:16-alpine` dùng một lần, cổng loopback ngẫu nhiên,
mật khẩu sinh theo lượt, xoá khi xong. Không đụng `make up` của lane nào.

---

## 1. Bốn cổng trên đúng SHA của PR

| Cổng | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2882 passed, 602 skipped**, 5272 subtests, 311.64s |
| `tests/postgres` trên PostgreSQL thật, `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **545 passed, 0 skipped**, 73.88s |
| `tests/qa` trên cùng database | **89 passed**, 11.88s |
| `cd apps/mobile && npm test` | **1032 pass, 0 fail, 0 skipped**, 24 suites |

602 skipped ở dòng đầu là các ca đòi PostgreSQL; chúng được chạy thật ở hai dòng
sau với `MOBILE_REQUIRE_POSTGRES_TESTS=1` và `0 skipped`. Không có ô nào của cổng
này bị đọc từ một lượt bỏ qua.

`npm test` không thể bị PR này ảnh hưởng — PR đụng đúng một file Python. Chạy để
khỏi phải suy, không phải vì nghi ngờ.

---

## 2. Đối chứng: lỗi cũ CÓ THẬT ở bản TRƯỚC

PR nói "37/41 bảng đi lọt" ở `7fff89c`. Tôi không dùng lại máy đột biến của PR —
một máy tự chứng nhận chính nó là thứ cần nghi ngờ đầu tiên. Phép đo của tôi khác
ở **cơ chế**: PR mô phỏng mất bảng bằng cách lọc danh sách đã đọc trong Python;
tôi đột biến ngay **mệnh đề `where` của chính câu SQL**, nên đường đo chạy từ
database ra tới assertion.

Đủ 41 bảng, không lấy mẫu, xoá bytecode mỗi lượt, hai canary mỗi lượt chạy:

| | TRƯỚC `7fff89c` | SAU `8094a09` |
|---|---|---|
| canary NỀN (pristine) | 10 passed | 16 passed |
| canary CUỐI (đã khôi phục) | 10 passed | 16 passed |
| **bảng đi lọt (không ca nào đỏ)** | **37 / 41** | **0 / 41** |
| bảng bị bắt | 4 / 41 | 41 / 41 |

Bốn bảng bị bắt ở bản TRƯỚC đúng như PR khai, và bắt vì lý do PR khai:

- `expense_versions` → `test_schema_enumeration_is_not_empty` (sáu cột tiền, đủ kéo
  24 xuống dưới sàn 20)
- `audit_events`, `memories`, `messages` → `test_reviewed_entries_still_describe_the_schema`,
  tức trượt sàn allowlist-freshness vì tình cờ có tên trong allowlist. Không phải
  luật tiền nào bắt chúng.

Suy ra con số thứ hai của PR cũng đúng: **40/41 bảng vô hình với riêng hai cái sàn**
(chỉ `expense_versions` trượt sàn).

Ở bản SAU, cả 41 dòng đều đỏ ở `test_schema_read_covers_every_model_table` — tức
đúng luật mới, không phải đỏ nhầm lý do.

Bảng từng-bảng-một sinh lại bằng `tests/qa/qa-tt-0004/do_phep_doc_mat_gi.sh bang`
trên mỗi rev. Bản dump thô không nằm trong repo: repo guard từ chối chúng theo
luật `controlled-artifact`, và một phép đo sinh lại được thì tốt hơn một phép đo
dán vào.

---

## 3. Cổng mới có rỗng không — đột biến chính bộ dò

Bốn luật "không dòng nào khớp" thì một hàm hỏng cũng thoả mãn y như một schema
sạch. Nên tôi đột biến chính bộ dò, ở `8094a09`:

| Đột biến | Kết quả | |
|---|---|---|
| nền pristine | 16 passed | |
| `_looks_like_money` → luôn `False` | **5 failed** | ✅ |
| `INEXACT_SQL_TYPES` → `frozenset()` | **5 failed** | ✅ |
| `_tables_missing_from_read` → luôn `[]` | **1 failed** | ✅ luật MỚI được gác |
| `_model_tables` → `frozenset()` | **1 failed** | ✅ nguồn RỖNG không tự tháo cổng |
| khôi phục | 16 passed | |

Dòng thứ tư là dòng đáng giá nhất: một danh sách nguồn rỗng làm vòng lặp không
chạy và cổng in xanh trong im lặng là kiểu hỏng đã xảy ra ở repo này. #493 tự
chặn nó bằng `assert checked == sorted(model_tables)` và `assert len(checked) > 0`,
và đột biến xác nhận hai dòng đó thật sự cắn.

---

## 4. Phát hiện — độ mịn thật của cơ chế là CỘT, không phải BẢNG

PR đặt tên nguyên nhân đúng, rồi phủ mất một bậc:

> "A missing role grant is a measured cause; restore the grant before trusting
> this gate."

Trong PostgreSQL, `information_schema.columns` chỉ hiện những cột mà
`current_user` có quyền — phép lọc ở **mức cột**. Đo trên chính container
postgres:16 mà cổng đang chạy:

```sql
create table qa0004_grant.hoa_don (id int, amount_vnd bigint, ghi_chu text);
grant usage on schema qa0004_grant to qa0004_reader;
grant select (id, ghi_chu) on qa0004_grant.hoa_don to qa0004_reader;  -- cố tình bỏ amount_vnd
```

| đọc `information_schema.columns` với tư cách | thấy |
|---|---|
| `mobile` (chủ sở hữu) | `amount_vnd`, `ghi_chu`, `id` |
| `qa0004_reader` (thiếu quyền 1 cột) | `ghi_chu`, `id` — **mất `amount_vnd`** |
| `qa0004_reader`, đếm dòng của cả schema | **2** — **bảng vẫn còn trong phép đọc** |

Nên hình dạng thật của "một grant thiếu" là: **một cột biến mất, bảng ở lại**.
`test_schema_read_covers_every_model_table` so tập *tên bảng*, nên nó mù với đúng
hình dạng đó theo cấu tạo.

### Đo, không suy: bỏ từng cột một, đủ 287 cột của model, ở `8094a09`

```
LỌT (mã 0, không ca nào đỏ): 283 / 287
BỊ BẮT                     :   4 / 287
cột TÊN TIỀN (_vnd / *amount*): tổng 21 — lọt 21
```

Bốn cột bị bắt là `audit_events.event_data`, `memories.lat`, `memories.lng`,
`messages.card` — cả bốn bị bắt bởi `test_reviewed_entries_still_describe_the_schema`,
tức lại là allowlist-freshness, không phải luật tiền. **Không một cột tiền nào bị bắt.**

`payment_reports.amount_vnd` và `receipt_confirmations.amount_vnd` — hai cột trên
đường tiền thật — rời phép đọc, cổng vẫn `16 passed`.

Sàn `len(money_named) >= 20` trên 24 cột tiền cho một **hạn mức im lặng là 4 cột**:
mất tới bốn cột tiền vẫn không ai thấy; cột thứ năm mới nổ.

Bảng từng-cột-một sinh lại bằng `tests/qa/qa-tt-0004/do_phep_doc_mat_gi.sh cot`.

### Vì sao đây không phải blocker của #493

Ba lý do, và tôi muốn nói rõ vì "tìm ra cái gì đó" không đồng nghĩa với "chặn":

1. #493 không tạo ra lỗ này. Nó có sẵn ở `7fff89c` và ở mọi bản trước đó.
2. #493 làm hẹp lỗ lại, đo được: 37/41 → 0/41 ở mức bảng.
3. #493 không đụng code sản phẩm — một file test, không có đường nào để nó làm
   sai tiền.

Chặn nó sẽ là giữ lại bản `main` **kém hơn**. Đây là việc cho lượt sau, và nó là
bước thứ ba của đúng chuỗi Lead đã ghi lúc 11:18 (#430 rỗng → #465 mất một tên →
#471 bản đồ): **chặn một trạng thái cực đoan rồi tưởng đã chặn cả vùng.** Ở đây
trạng thái cực đoan là "mất cả bảng"; vùng là "mất bất kỳ phần nào của phép đọc".

Tiêu chí gỡ ở lượt sau: so tập `(bảng, cột)` của phép đọc với
`Base.metadata`, chứ không so tập tên bảng. Cùng một `Base.metadata` đã import
sẵn trong file, nên chi phí gần bằng không.

---

## 5. Quan sát phụ — một bất biến bị gỡ, không phải lỗi

#493 xoá dòng cuối của bộ canary có tham số:

```python
assert caught_by_type_rule or caught_by_name_rule, (
    "this row claims neither rule catches the column, which would make "
    "it a documented hole rather than a control"
)
```

và thêm bốn dòng `(False, False)` làm lỗ có tài liệu. Việc này hợp lý và PR có
ghi rõ trong docstring. Cái mất đi là: từ nay một canary DƯƠNG có thể lặng lẽ
thoái hoá thành một lỗ có tài liệu — nếu bộ dò hỏng, sửa kỳ vọng thành
`False, False` là bảng xanh trở lại, không có gì phản đối.

Tôi **không** đột biến để đo kịch bản này, nên đừng đọc nó như một con số. Nêu ra
để người sửa lượt sau biết cái rào đó đã không còn.

---

## 6. Ô CHƯA quét

- **Kịch bản grant thật trên cây test.** Cổng chạy với tư cách `mobile`, chủ sở
  hữu schema, nên phép lọc theo quyền **không thể** cắn ở cấu hình hiện tại. Số
  283/287 đo bằng cách mô phỏng hậu quả (bỏ cột khỏi câu SQL), không phải bằng
  cách thu hồi grant thật trên schema đã migrate. Cơ chế thì tôi đã đo thật (mục 4,
  bảng ba dòng); hậu quả trên cây test là mô phỏng.
- **Cột không thuộc model.** Tôi đếm trên 287 cột suy từ `Base.metadata`. Phép đọc
  thật trả 293 cột; 6 cột chênh (gồm `alembic_version` và cột của view) không nằm
  trong mẫu số của tôi.
- **JSONB.** Tiền nằm trong tài liệu JSON vẫn ngoài mọi luật — #486 và #493 đều
  đã ghi, tôi không đo thêm.
- **Ba loại đầu vào #460 nêu** (4 nguồn đọc thẳng từ dataclass + phép cộng ở
  `bill.py:104`): cổng này ở phía lưu trữ, không chạm tới chúng. Không đo trong
  lượt này.
- **Mã QR quét bằng app ngân hàng thật.** Vẫn chưa ai làm. Không agent nào làm được.
- **GitHub Actions.** Không đo — đỏ vì billing từ 2026-08-29, `steps: []`.

---

## 7. Chạy lại

```bash
git fetch && git checkout 8094a09

# cổng
python3 -m pytest services/api/tests tests -q
scripts/postgres_tier.sh
cd apps/mobile && npm test

# phép đo của báo cáo này — tự dựng Postgres dùng một lần rồi tự xoá
tests/qa/qa-tt-0004/do_phep_doc_mat_gi.sh bang   # 0/41 lọt ở 8094a09; 37/41 ở 7fff89c
tests/qa/qa-tt-0004/do_phep_doc_mat_gi.sh cot    # 283/287 lọt, 21/21 cột tiền lọt
```

Script tự chạy hai canary (nền pristine phải xanh, và phải xanh lại sau khi khôi
phục), tự đối chứng rằng đột biến thật sự vào được file, và tự dừng mã 2 nếu vòng
lặp chạy thiếu nạn nhân. Nó tự từ chối in bảng khi những điều đó không đúng.
