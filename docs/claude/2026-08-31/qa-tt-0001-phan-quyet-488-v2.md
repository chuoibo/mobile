# PASS #488 — cổng biểu thức SQL, phán quyết lượt hai

- **protocol_version**: v1
- **verdict**: `PASS`
- **PR**: #488 `backend/cong-bieu-thuc-sql-tra-tien-phai-la-so-nguyen`
- **đo tại**: `e03b56f206b14238abf1865579b3844197d644c3` ⊕ `origin/main@e41bcdc`
  (cây gộp `e7b1b0a38d90827e7f49acfc0956a474088708aa`, tree `51129f5`)
- **sha này**: nhánh **chưa merge**; cây đo là kết quả gộp, không phải HEAD của PR đơn thuần
- **blocker còn mở**: không
- **phán quyết trước**: `FAIL` tại `b53321e5` (#492, đã vào main ở `f8fbf49`)

`origin/main` nhích hai lần trong lúc tôi đo (`e41bcdc` → `f8fbf49`, do chính #489 và
#492 của tôi được merge). Cả hai commit đó **không đụng `services/api/`**
(`git diff --stat e41bcdc origin/main -- services/api/` ra rỗng), nên số đo dưới đây
vẫn đứng trên nền hiện tại.

## Lý do, viết trước mọi chi tiết

Tiêu chí gỡ chặn tôi ra ở #492 là một câu đo được: **4 mutant `D` và 3 mutant `P` phải
ĐỎ**. Tôi chạy lại **chính máy đột biến của #492, không sửa một dòng nào** (blob
`890aa908312be8b8d27886fa6a742bf598c2cf6f`) trên cây gộp: **18/18 mutant bị bắt, exit 0**.
Bảy cái sống sót ở lượt trước nay chết hết.

Và tôi không đọc "0 sống sót" thành "đã gác": cùng máy đo, cùng database, cùng cây, chỉ
lùi **riêng file cổng** về bản `b53321e` thì **7 mutant sống lại** đúng bảy cái cũ,
exit 1. Nên dấu xanh ở trên là do hai commit `f48a1a0` + `e03b56f` gây ra, không phải do
máy đo hỏng hay môi trường đổi.

Tôi có tìm thêm một hướng mù và **đo được kích thước của nó** (mục 4). Nó **không phải
blocker**: docstring của PR đã khai đúng rằng nhắc nhở coverage "được dựng trên tên và
thừa hưởng giới hạn của tên", và trên cây này **không có query tiền nào nằm ngoài vùng
nhắc nhở quét**, nên không có lỗi tiền nào đang sống. Đây là ghi chú cho lượt trôi dạt
sau, không phải điều kiện merge.

## 1. Tiêu chí gỡ chặn của #492 — đạt

Máy đo: `tests/qa/qa-tt-0002-488/dot_bien_cong_bieu_thuc_sql_488.py`, nguyên văn bản đã
merge. Nó tự dò điểm đột biến bằng AST và **từ chối chạy** khi nguồn nào ra rỗng hoặc
khi cây bẩn — cả hai cửa đó đều đã bật trong lượt này (nó chặn tôi một lần vì cây bẩn).

```
tim thay 7 diem cast(..., BigInteger) trong repository.py
MONEY_QUERY_SURFACE co 4 ten: group_recap, load_confirmed_receipts,
                              person_finance_summary, obligation_amounts_statement

M0 khong dot bien (phai XANH)                     rc=0  14 passed in 1.07s
C1..C7  lui TUNG cast mot cai mot                 -> BAT DUOC 7/7
N1..N4  bo TUNG ten khoi MONEY_QUERY_SURFACE      -> BAT DUOC 4/4
D1..D4  bo DONG GOI, GIU ten trong list           -> BAT DUOC 4/4   (lượt trước: LỌT 4/4)
P1..P3  bo dong goi VA lui 1 cast THAT cua no     -> BAT DUOC 3/3   (lượt trước: LỌT 3/3)

khong dot bien nao song sot        exit 0
```

## 2. Đối chứng: máy đo này ĐỎ được

Một bảng toàn "BAT DUOC" không phân biệt được "cổng gác tốt" với "máy đo hỏng". Nên tôi
lùi **đúng một file** — file cổng — về bản trước hai commit sửa, giữ nguyên mọi thứ khác
kể cả database đang chạy:

```
D1..D4  bo DONG GOI, GIU ten trong list           -> LOT 4/4   (11 passed)
P1..P3  bo dong goi VA lui 1 cast THAT cua no     -> LOT 3/3   (11 passed)
7 dot bien SONG SOT        exit 1
```

Biến duy nhất thay đổi giữa hai bảng là nội dung file cổng. `11 passed` → `14 passed`
là ba ca mới của hai commit sửa.

## 3. Mutant S — lý do tồn tại của `e03b56f`, kiểm riêng

`e03b56f` sinh ra để bắt hướng mà máy đo của tôi **không** dựng được: xoá *fixture* thay
vì xoá *dòng gọi*. Tôi đo trực tiếp, đổi mặc định `seed_trip=True` → `False`:

```
FAILED ...::test_every_surface_method_reaches_a_computed_expression
1 failed, 13 passed in 1.11s
```

Đỏ, và đỏ **đúng ở assert được thêm để bắt nó** (dòng 454), không phải đỏ vì một lý do
khác. Trước `e03b56f` cùng đột biến này ra `12 passed`. Lời khai của tác giả tái lập được.

## 4. Hướng mù còn lại, đã đo — GHI CHÚ, không phải blocker

`test_every_aggregating_method_is_driven` là câu trả lời của PR cho "danh sách viết tay
không tự biết mình thiếu": nó duyệt AST hai module repository, tìm hàm nào gọi
`func.{sum,avg,round}`, và đòi tên hàm đó phải có trên `MONEY_QUERY_SURFACE`.

Luật kiểu bên cạnh nó **mù với cách viết một cách có chủ ý** — nó đọc kiểu Postgres khai
cho từng cột kết quả. Nhắc nhở thì không: nó dựng trên tên. Tôi đo khoảng cách đó bằng
cách thêm **một query tiền mới không ai lái**, mỗi hàng một cách viết:

```
M0 khong dot bien                                       rc=0  14 passed
Y0 func.sum -- cach viet nhac nho CO biet                rc=1  1 failed  -> BAT DUOC (dung nhac nho)
Y1 chia doi bill bang toan tu / 2.0 (khong co Call nao)  rc=0  14 passed -> LOT
Y2 SQL viet tay qua text()                               rc=0  14 passed -> LOT
Y3 func.sum o module NGOAI hai module duoc quet           rc=0  14 passed -> LOT
```

Hàng `Y0` là đối chứng dương và nó **bắt buộc phải đỏ đúng ở
`test_every_aggregating_method_is_driven`** — máy đo đọc *lý do* đỏ chứ không đọc mã
thoát. Lần chạy đầu của tôi có `Y0/Y1/Y2` đều "đỏ" với `1 error in 0.16s`: đó là lỗi thu
thập của pytest do chính đột biến sai thụt lề, tức **đỏ sai lý do**, và nếu tôi đọc mã
thoát thì đã kết luận ngược hoàn toàn ("không cách viết nào lọt"). Máy đo hiện tại trả
`KHONG KIEM DUOC` + exit 2 cho tình huống đó thay vì in bảng sạch.

**Vì sao đây không phải blocker.** Trên cây này `func.sum|avg|round` xuất hiện đúng 8 lần,
7 ở `app/api/repository.py` và 1 ở `app/db/repository.py` — cả hai đều đã nằm trong
`REPOSITORY_MODULES`. Không có query tiền nào ở ngoài vùng quét, nên không có lỗi tiền
nào đang sống vì chuyện này. Và docstring của PR **đã** khai nhắc nhở này "được dựng trên
tên và thừa hưởng giới hạn của tên" — nó không bán thứ nó không làm được. Cái tôi thêm
vào là **con số**: 3 trên 4 cách viết. `Y1` đáng chú ý nhất vì nó là phép chia đôi bill,
thứ sản phẩm này làm thật.

## 5. Cổng đầy đủ trên cây gộp

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | `2889 passed, 627 skipped, 5272 subtests passed in 283.46s` |
| `tests/postgres` + `MOBILE_REQUIRE_POSTGRES_TESTS=1` | `571 passed in 67.29s`, **0 skipped** |
| riêng file cổng | `14 passed in 1.06s` |
| `ruff check` / `ruff format --check` trên file tôi thêm | `All checks passed!` / `1 file already formatted` |
| `repo_guard.py staged` | `Repo guard passed staged diff: 1 file scan(s)` |

## 6. Chạy lại — không có đường tuyệt đối nào trong máy đo

```bash
scripts/postgres_tier.sh --keep -k money_expressions      # in ra URL

MOBILE_TEST_DATABASE_URL='<URL nó in>' \
  python3 tests/qa/qa-tt-0002-488/dot_bien_cong_bieu_thuc_sql_488.py   # tiêu chí #492
MOBILE_TEST_DATABASE_URL='<URL nó in>' \
  python3 tests/qa/qa-tt-0001-488/do_nhac_nho_phu_gi.py                # mục 4
```

Cả hai script lấy gốc repo bằng `git rev-parse --show-toplevel`, không ghim đường máy tôi.

## 7. Ô CHƯA quét

- `apps/mobile && npm test` — **chưa chạy**. PR đụng đúng 2 file phía server.
- Lát cắt dọc `npm run test:e2e` — **chưa chạy**, không dựng uvicorn lượt này.
- Trang khách, ma trận trạng thái × chủ đề × khung nhìn — **chưa quét**.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Chỉ leader đóng được ô này.
- Số nằm **trong `jsonb`** — tác giả đã khai là ngoài tầm cổng; tôi **không** đo lại.
- Cổng này chứng minh **kiểu** và **độ với tới**, **không** chứng minh số tiền ra tới
  client là đúng. Đó là việc của 41 golden vector và của lát cắt dọc.
- Hướng trôi dạt liên-module (một query tiền mới ở module thứ ba) — đo ở mục 4 là mù,
  **chưa** có cổng nào phủ.
