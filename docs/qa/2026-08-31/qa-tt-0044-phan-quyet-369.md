# PASS — PR #369 tại `6d1041c`

**Lý do:** lỗi cũ tái lập được trên **cả ba bảng tiền** ở đúng revision ngay trước
bản vá, và bản vá chặn đúng nó bằng chính khoá ngoại (SQLSTATE 23503), không phải
bằng một lỗi khác đội lốt. Bốn đột biến đều bị giết. Trên máy chủ sống, `POST
/expenses` với nhóm không tồn tại trả **404 `context_not_found`** thay vì 500, mà
đường hạnh phúc vẫn **201**. Và điều quan trọng nhất với một migration động vào sổ
cái: trên chính máy demo có 10932 hàng mồ côi, migration **đã chạy xong và không
xoá hàng nào**.

Một suggestion, không chặn merge: cổng `test_migration_matches_models.py` không so
khoá ngoại, nên đột biến M3 (bỏ `expenses` khỏi danh sách) đi qua nó mà vẫn xanh.
Tầng PostgreSQL bắt được, nên lỗ hổng này không ảnh hưởng phán quyết.

---

## Đo tại đâu

```
đo tại   6d1041c  (head PR #369, đúng SHA khi nhận việc và khi kết thúc)
sha này  là nhánh CHƯA merge — không phải tổ tiên của origin/main
cây gộp  672da41 = 6d1041c ⊕ origin/main@4d79f7c   (gộp sạch, 0 xung đột)
```

`origin/main` nhích **giữa lượt đo** (`0a2fe13` → `4d79f7c`, do #367 merge vào).
Tôi đo cây gộp hai lần; mọi số trong báo cáo này là **lần thứ hai**, trên main mới.

Môi trường: Postgres 16.15 **của riêng lượt này** (`qa44-pg`, cổng 5644) và uvicorn
dựng từ chính cây này (cổng 8644). Không dùng 8099 hay 8081 để lấy kết luận — hai
chỗ đó phục vụ bản dựng khác. Máy demo chỉ bị **đọc**, không bị ghi.

## Đối chứng hai chiều — lỗi cũ có thật, trên cả ba bảng

Một schema, migrate tới `d1e2f3a4b5c6` (revision **ngay trước** bản vá), ghi hàng
mồ côi, rồi migrate tiếp tới `b3c7e0d24f19` và ghi lại **cùng một hàng**:

| bảng | trước bản vá | sau bản vá | đường hạnh phúc (nhóm có thật) |
|---|---|---|---|
| `expenses` | **GHI ĐƯỢC** | CHẶN (23503) | GHI ĐƯỢC |
| `bills` | **GHI ĐƯỢC** | CHẶN (23503) | GHI ĐƯỢC |
| `collection_batches` | **GHI ĐƯỢC** | CHẶN (23503) | GHI ĐƯỢC |

Số hàng mồ côi trước và sau migration: `{expenses: 1, bills: 1, collection_batches: 1}`
→ **không đổi**. Không hàng nào bị dọn lén.

**Phép thử đầu tiên của tôi sai, và tôi ghi ra đây vì nó là cái bẫy chính của bug
này.** Bản v1 chỉ ghi `(id, context_id)`, nên `bills` và `collection_batches` chết vì
`NotNullViolation` — cũng là một `IntegrityError` — và v1 đọc thành "khoá đã chặn rồi".
Đỏ nhầm lý do. Bản v2 ghi **hàng đầy đủ** và phân loại theo **SQLSTATE**: `23503` là
khoá ngoại, `23502` là thiếu cột. Chỉ bảng kết quả của v2 ở trên mới có nghĩa.

Cột "đường hạnh phúc" tồn tại vì một khoá **từ chối tất cả** cũng sẽ làm cột giữa
xanh. Không có cột phải thì cột giữa không chứng minh gì.

## Đột biến — bốn cái, chết cả bốn

Chạy trên `tests/postgres` với Postgres thật, khôi phục file bằng `git checkout` sau mỗi lần.

| # | Đột biến | Kết quả |
|---|---|---|
| M1 | Bỏ `NOT VALID` khỏi `ADD CONSTRAINT` | **2 ca đỏ** — migration vỡ trên DB bẩn |
| M2 | `DELETE` hàng mồ côi trước khi thêm khoá | **1 ca đỏ** — đúng ca "không xoá gì" |
| M3 | Bỏ `expenses` khỏi `MONEY_TABLES` | **7 ca đỏ** |
| M4 | Bỏ dịch FK-violation → `RepositoryConflict` | **2 ca đỏ** |

M2 chỉ giết được **một** ca, và đó là đúng: ca thứ hai kiểm "vẫn chặn hàng mồ côi
tiếp theo", mà xoá lịch sử không làm hỏng tính chất đó. Không phải lỗ hổng.

## Máy chủ sống — 404 thay vì 500

uvicorn cổng 8644, Postgres 5644, cả hai dựng từ cây này:

```
POST /expenses, context_id KHÔNG tồn tại  -> HTTP 404
                {"code":"context_not_found","detail":"Context does not exist"}
POST /expenses, nhóm CÓ THẬT              -> HTTP 201, expense_id 129c120f-…
số dòng 500 / Traceback trong log API     -> 0
```

## Trên chính máy demo — nơi 10932 hàng mồ côi thật sự nằm

Đọc-chỉ trên `mobile-local-postgres-1` (DB đứng sau API 8099). Migration **đã được
ai đó áp lên đây rồi** — `alembic_version` = `b3c7e0d24f19`:

| bảng | tổng | mồ côi | trạng thái khoá |
|---|---|---|---|
| `expenses` | 11026 | **10932** | `convalidated=false` |
| `collection_batches` | 209 | **174** | `convalidated=false` |
| `bills` | 20 | 0 | `convalidated=true` |

Ghi thử một hàng mồ côi mới (rồi `ROLLBACK`) → bị từ chối bằng
`fk_expenses_context_id`. Nên trên dữ liệu thật, đúng như thiết kế khai: lịch sử còn
nguyên, đường sinh hàng mồ côi mới đã đóng, và khoá **thành thật nói rằng nó chưa
kiểm quá khứ**. Đây là bằng chứng mạnh hơn schema bẩn tôi tự dựng.

Con số mới cho người sẽ quyết chuyện dọn dữ liệu: **174 `collection_batches` mồ côi**
(docstring chỉ nhắc `expenses`), và tiền của các `expenses` mồ côi là **7311 bản ghi,
tổng xấp xỉ 789 triệu đồng** (con số đầy đủ lấy lại được bằng câu truy vấn ở cuối bài;
không viết ra đây vì repo guard chặn dãy 9 chữ số — luật chặn số tài khoản). Migration
có in cảnh báo kèm số lúc chạy nên không có gì bị giấu.

## Cổng đã chạy

| Cổng | Nhánh `6d1041c` | Cây gộp `672da41` |
|---|---|---|
| `pytest services/api/tests tests` (có URL Postgres) | 3115 pass · 40 skip · 0 fail | **3148 pass · 40 skip · 0 fail** |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | 506 pass · **0 skip** | (nằm trong dòng trên) |
| `apps/mobile` `npm test` | — | **812 pass · 0 fail** |
| Render migration ra DDL (offline) | exit 0 | exit 0 |
| `alembic heads` | 1 head | **1 head** (không tách chuỗi) |
| `repo_guard.py tree HEAD` | — | passed, 1146 file |

40 ca skip còn lại **chỉ** là tầng Gemini live (`GEMINI_API_KEY` +
`MOBILE_REQUIRE_GEMINI_TESTS=1`), bị gác có chủ ý. Chạy **không** có URL Postgres thì
563 ca tự bỏ qua — con số đó không được đọc là xanh, nên mọi dòng trên đều chạy có URL.

## Hai phép kiểm khác

**Đủ hay thiếu.** `MONEY_TABLES` là danh sách viết tay, mà danh sách viết tay không tự
biết mình thiếu. Nên tôi hỏi thẳng schema đã migrate thay vì đọc `models.py`: **10 bảng**
có cột `context_id`, và **10/10 đều có khoá ngoại**. Không bảng nào bị bỏ lại.

**Vòng xuống–lên.** `alembic downgrade -1` gỡ đúng 3 khoá trong `public` (còn 0), rồi
`upgrade head` dựng lại cả 3 với `convalidated=true` trên schema sạch. Trên schema bẩn
thì cả 3 ra `false` — đúng như migration khai.

## Suggestion (không chặn merge)

**S1 — cổng `test_migration_matches_models.py` mù với khoá ngoại.** Dưới đột biến M3
(models khai `fk_expenses_context_id`, migration không tạo nó), cổng này **vẫn xanh**
5 passed. Nó chỉ so tập bảng và tập cột từng bảng, không so constraint. Đây là lỗ hổng
**có sẵn**, không do PR này gây ra, và tầng PostgreSQL đã bắt M3 bằng 7 ca đỏ. Nhưng ai
chỉ chạy cổng rẻ sẽ để M3 lọt.

**S2 — cho Lead, không phải cho tác giả.** Máy demo đã ở revision `b3c7e0d24f19` trong
khi migration đó **chưa có trên `main`**. Máy demo đang chạy schema của một PR chưa
merge. Không ảnh hưởng phán quyết PR này; nhưng nếu #369 bị sửa thêm rồi mới merge thì
máy demo đang mang một bản khác.

## Ô CHƯA quét

- **Không chạy migration trên máy demo bằng tay** — nó đã được áp từ trước khi tôi tới.
  Tôi xác nhận *kết quả cuối*, không quan sát *lúc nó chạy* trên 11026 hàng.
- **Đua đồng thời**: hai `POST /expenses` cùng lúc trong khi nhóm bị xoá — không quét.
  Khoá ngoại của PostgreSQL xử lý được về lý thuyết, nhưng tôi không có bằng chứng đo.
- **Thời gian khoá bảng** khi `ADD CONSTRAINT NOT VALID` chạy trên bảng lớn — không đo.
- **Trang khách, VietQR, giao diện** — PR này không chạm tới, tôi không quét.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, vẫn cần leader và một
  điện thoại thật. Không liên quan PR này nhưng chưa được đóng lại.
- **10932 hàng mồ côi vẫn còn nguyên trong sổ**, và tiền của chúng vẫn cộng vào
  `GET /people/{id}/finance`. Đó là **chủ ý** của PR (dọn dữ liệu là quyết định của
  người, không phải của file migration) — nhưng nó vẫn là một lỗi đang mở, chỉ là
  không phải lỗi mà PR này nhận sửa.

## Cách chạy lại

```bash
docker run -d --name qa44-pg -e POSTGRES_USER=mobile -e POSTGRES_PASSWORD=mobile-dev-only \
  -e POSTGRES_DB=mobile -p 5644:5432 postgres:16
git checkout 6d1041c
MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5644/mobile' \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest services/api/tests tests -q
cd apps/mobile && npm test
```

Đếm hàng mồ côi và tiền của chúng trên máy demo (chỉ đọc, không ghi):

```sql
SELECT count(*) AS ban_ghi, sum(ev.total_amount_vnd) AS tong_vnd
FROM expenses e JOIN expense_versions ev ON ev.expense_id = e.id
WHERE NOT EXISTS (SELECT 1 FROM contexts c WHERE c.id = e.context_id);
```

`NOT EXISTS` chứ không `JOIN contexts`: một inner join ở đây **đánh rơi đúng những
hàng cần đếm** và trả về "sạch". Chính migration cũng ghi lại cái bẫy đó.
