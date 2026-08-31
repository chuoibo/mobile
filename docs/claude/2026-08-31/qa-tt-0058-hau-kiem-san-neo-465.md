# PASS #465 — hậu kiểm: lỗ hổng rộng gấp đôi mô tả, và bản vá đóng hết 13/13

**Phán quyết: PASS.**

**Lý do, trước phần chi tiết:** lỗ hổng #465 mô tả là có thật và tôi tái lập được
độc lập trên cây trước bản vá — nhưng nó **rộng hơn** con số PR đưa ra: **13/13**
tên, khi mất đúng MỘT tên, đều làm cổng trả lời như cây sạch, và **9/13** tên còn
không có bất kỳ phép kiểm nào bắt được (bộ test cũ xanh trơn). Bản vá đóng **13/13**
(exit 2, có câu giải thích). Gỡ chính bản vá ra thì bộ test mới đỏ 11/14, lắp lại thì
14/14 — đối chứng đi cả hai chiều. Không vượt ranh giới sở hữu, ruff sạch, repo guard
sạch. **Ba điều Lead cần biết:** (1) `hero-walk` đỏ **trên chính `main`**, không phải
do #465; (2) một câu trong mô tả PR nói quá phạm vi — cổng **vẫn mù** với một wrapper
HOÀN TOÀN MỚI trong `api.ts`, tôi đo có đối chứng dương; (3) **#465 đã được merge lúc
03:40:59Z, trong lúc tôi đang test nó** — nên đây là hậu kiểm, không phải cổng trước
merge.

```
đo tại    92fc72f (head #465) và fee2d73 (main TRƯỚC khi merge #465)
xác nhận  ec0c0fb (main SAU khi merge, = 06ae2d7 của #465)
sha này   #465 ĐÃ ở main (squash thành 06ae2d7); fee2d73 là main ngay trước đó
```

---

## 1. Lỗ hổng CÓ THẬT, và rộng hơn mô tả

PR đo hai tên (`doFetch`, `translatedAnonymous`) cho `check_api_contract` và một ca
rỗng cho `check_pin_drift`. Tôi quét **cả 13 tên**, mỗi lần bỏ đúng một tên, trên
worktree sạch cắt từ `fee2d73` (main ngay trước merge).

Bảng vẫn đầy, vẫn không rỗng, nên sàn "chỉ nổ khi RỖNG" của #430 im lặng đúng như PR nói.

### `check_api_contract.py` — bỏ 1 tên khỏi `REQUEST_FUNCTIONS`

| bỏ tên | CLI | đọc được | bộ test cũ trên main |
|---|---|---|---|
| `fetch` | **exit 0** | 60 đường / 66 gọi / 9 file | 3 failed, 24 passed |
| `doFetch` | **exit 0** | 63 đường / 75 gọi / 8 file | 2 failed, 25 passed |
| **`callAsActor`** | **exit 0** | **52 đường / 62 gọi** / 12 file | **27 passed — XANH TRƠN** |
| `callAnonymous` | **exit 0** | 67 đường / 77 gọi / 12 file | **27 passed — XANH TRƠN** |
| `translatedAsActor` | **exit 0** | 29 đường / 40 gọi / 9 file | 1 failed, 26 passed |
| `translatedAnonymous` | **exit 0** | 64 đường / 75 gọi / 12 file | **27 passed — XANH TRƠN** |

Nguyên vẹn: `67 đường dẫn qua 79 lần gọi trong 12 file, exit 0` — khớp con số PR.

Chỗ tệ nhất là `callAsActor`: **15 đường dẫn và 17 lần gọi biến mất**, cổng vẫn in
"Client và máy chủ khớp hợp đồng", **và cả 27 ca của bộ test cũ đều xanh**.

Ba tên (`callAsActor`, `callAnonymous`, `translatedAnonymous`) không có phép kiểm nào
bắt. Ba tên còn lại bị bắt **do may**, không do sàn: chúng có mặt trong fixture của
vài ca khác. `scripts/gate.sh contract` thì **ĐẠT** trên cả sáu.

### `check_pin_drift.py` — bỏ 1 tên khỏi `IMPORT_CRITICAL`

Trên máy này 5 pin lệch thật cùng lúc, nên tôi cô lập bằng `--requirements` ghim đúng
một tên ở `0.0.0.dev0`, để mã thoát chỉ phụ thuộc tên đang xét.

| bỏ tên | CLI | bộ test cũ trên main |
|---|---|---|
| `fastapi` | **exit 0** | 3 failed, 11 passed |
| `starlette` · `pydantic` · `sqlalchemy` · `alembic` · `pytest` | **exit 0** | **14 passed — XANH TRƠN** |
| `pytest-subtests` | **exit 0** | **13 passed, 1 skipped — XANH TRƠN** |

Chỗ này là kiểu im lặng khó chịu nhất, vì **bằng chứng nằm ngay trên màn hình mà mã
thoát nói ngược lại**:

```
IMPORT_CRITICAL nguyên vẹn   KHỚP 0   LỆCH 1   THIẾU 0   ->  exit 1
bỏ đúng 1 tên "fastapi"      KHỚP 0   LỆCH 1   THIẾU 0   ->  exit 0
```

Cùng một dòng chữ `LỆCH 1`, hai mã thoát ngược nhau. Cổng vẫn đếm được cái lệch, chỉ
là không còn coi nó là quan trọng nữa.

**Tổng: 13/13 mù ở mức CLI/cổng; 9/13 không có phép kiểm nào bắt.**

## 2. Bản vá đóng 13/13

Cùng 13 đột biến, chạy trên head #465 (`92fc72f`) và xác nhận lại trên `main` sau
merge (`ec0c0fb`) — **13/13 exit 2**, kèm câu nói rõ tên nào mất:

```
cổng tự từ chối chạy: IMPORT_CRITICAL không còn liệt kê ['starlette']. ...
KHÔNG CHẠY ĐƯỢC: REQUEST_FUNCTIONS không còn tên ['callAsActor']. ...
```

Mã thoát 2 (không phải 1) là đúng: 1 ở `check_api_contract` nghĩa là "client sai hợp
đồng", tức đổ lỗi cho code người khác vì lỗi cấu hình của chính bộ đọc.

### Đối chứng hai chiều trên chính bộ test của PR

Gỡ **chính bản vá** ra (`git checkout origin/main -- scripts/check_api_contract.py
scripts/check_pin_drift.py`), giữ nguyên file test:

```
TRƯỚC (gỡ bản vá):  11 failed, 3 passed
SAU  (nguyên bản):  14 passed
```

Đúng con số PR khai. 3 ca xanh ở cả hai lần là đối chứng dương.

### Sàn có tự bảo vệ được không — tôi đánh vào chính nó

| tấn công | CLI | bộ test |
|---|---|---|
| bỏ tên ở **bảng** | exit 2 | đỏ |
| bỏ tên ở **bảng + neo** (2 sửa) | **exit 2** — `REQUIRED_* chỉ còn 6 tên, phải có ít nhất 7` | đỏ |
| bỏ **bảng + neo + hạ COUNT** (3 sửa phối hợp) | **exit 0 — lọt** | `test_anchor_table_floors.py` **2 failed** |

Ba sửa phối hợp qua được sàn lúc import, nhưng **bộ test mới của PR bắt được**. Tôi
kiểm bằng `starlette` — tên mà bộ test cũ hoàn toàn không gác (`test_pin_drift_gate.py`
vẫn **14 passed**) — nên ca đỏ đó đúng là công của #465, không phải phòng tuyến sẵn có.
Phòng thủ hai lớp đứng vững; `make gate` chạy cả `tests/` nên lớp này nằm trong cổng.

## 3. Chỗ VẪN HỞ — mô tả PR nói quá, cần sửa lại cho Lead

Mô tả PR viết: *"Cả hai phòng tuyến cũ đều hỏi 'tên tôi biết còn trong client không'.
Không cái nào hỏi được chiều ngược lại: 'tên client đang có, tôi còn biết không'. PR
này là chiều ngược lại."*

**Đo ra thì không phải.** Sàn ghim tên đã biết vào một literal thứ hai — nó gác *bảng
có còn nguyên không*, chứ không quét `api.ts` tìm wrapper lạ. Tôi thêm một wrapper mới
vào `api.ts` gọi tới một route **không tồn tại trên máy chủ**, kèm đối chứng dương là
cùng route đó qua một wrapper đã biết:

```
gọi /route-nay-khong-he-ton-tai qua callAsGuest (wrapper MỚI)   -> exit 0  "khớp hợp đồng"
gọi /route-nay-khong-he-ton-tai qua callAnonymous (đã biết)     -> exit 1  "mọi lần gọi sẽ là 404"
```

Cùng một route ma: **vô hình** qua tên lạ, **bị bắt** qua tên đã biết.

Đây **không phải lỗi của #465** — lỗ này có sẵn trên main và PR không làm nó tệ đi;
`test_every_wrapper_it_reads_is_still_declared_in_api_ts` của #430 vẫn gác được hướng
*đổi tên* (tên cũ biến mất khỏi `api.ts` thì đỏ). Hướng còn hở là **thêm tên hoàn toàn
mới** trong khi giữ nguyên các tên cũ. Hôm nay bảng đang đầy đủ thật: `send` và
`sendPublish` trong `api.ts` chỉ tới được qua `callAsActor`/`callAnonymous`/
`translatedAsActor`, không phải cửa vào riêng.

Tôi nêu ra vì Lead chỉ đọc mô tả PR: đọc câu đó sẽ tin cổng đã bắt được wrapper lạ, mà
nó chưa. Theo charter đây là **suggestion** (độ chính xác của mô tả), không phải blocker.

## 4. Cổng đầy đủ

```
python3 -m pytest services/api/tests tests -q
  -> 2847 passed, 580 skipped, 5272 subtests passed in 351.60s      (khớp PR)

+ Postgres thật (MOBILE_REQUIRE_POSTGRES_TESTS=1)
  -> 3387 passed, 40 skipped, 5272 subtests passed in 443.77s
     đóng 540/580 skip; 40 còn lại là tầng Gemini live, cần MOBILE_REQUIRE_GEMINI_TESTS=1

ruff check / format (bản ghim, 3 file của PR)  -> All checks passed / 3 files already formatted
python3 scripts/repo_guard.py tree HEAD        -> passed, 1312 file scan(s)
ranh giới: chỉ scripts/ + 1 file test. KHÔNG chạm app/, apps/mobile/, phase0/, docs/protocol/v1/
```

### `make gate` — 2 chặng đỏ, **cả hai đều không phải do #465**

```
trên nhánh #465:  ĐẠT 16  HỎNG 2   hỏng: hero-walk, mobile
trên main ec0c0fb: mobile ĐẠT;  hero-walk VẪN HỎNG
```

- **`mobile`** đỏ vì `stacked-branch.test.mjs`: `3/3 file trong diff có nội dung y hệt
  origin/main`. Đây là cổng chạy **đúng** — #465 đã được merge giữa lúc tôi đo, nên
  nhánh không còn gì mới so với main. Trên `main` chặng `mobile` **ĐẠT**.
- Trong lượt đó có thêm `not ok 277 - đường vào Món của tôi, trên trang render thật`.
  Chạy lại riêng file đó: **7 pass 0 fail**; chạy cả chặng `mobile` trên main: **ĐẠT**.
  **Không tái lập được** — tôi ghi lại như một ca có thể chập chờn, không kết luận là lỗi.
- **`hero-walk`** đỏ **trên chính `main`**: phán quyết trong thư mục dùng chung neo vào
  client `8581c11`, không phải tổ tiên của `ec0c0fb`. PR đoán đúng cơ chế nhưng sha đã
  đổi (`9e13f9f` → `8581c11`) vì lane khác đã đi bộ từ lúc đó. **Đỏ với mọi người, kể cả
  trên main.** Không sửa từ đây được: `scripts/gate.sh` ghi rõ một thư mục phán quyết
  phục vụ mọi worktree, ghi đè là xoá bằng chứng lane khác.

## 5. Probe để đo lại

`services/api/tests/qa/qa-tt-0058-gac-465/probe_san_neo_mat_mot_ten.py` — đột biến một
bản sao của hai script rồi đọc **mã thoát của CLI thật**, không viết lại logic chấm điểm.
Mỗi đột biến tự `assert` phép thay chuỗi đã ăn trước khi tin kết quả, và trả cây về
nguyên trạng.

**Hai canary, cả hai đã chạy** — con số 13/13 chỉ có nghĩa khi bản trước vá đỏ được:

```
--tree <cây fee2d73, TRƯỚC #465>  ->  0/13 TỪ CHỐI CHẠY, 13 chỗ MÙ   (canary xấu ĐỎ)
--tree <cây ec0c0fb, main hôm nay> -> 13/13 TỪ CHỐI CHẠY             (canary sạch XANH)
```

## 6. Ô CHƯA quét

- **Mã VietQR chưa được quét bằng app ngân hàng thật.** Còn nguyên, chỉ leader đóng được.
- Tầng **Gemini live** (40 skip) — cần `MOBILE_REQUIRE_GEMINI_TESTS=1`, ngoài phạm vi #465.
- **Tấn công 4 sửa phối hợp** (bảng + neo + COUNT + sửa luôn file test) — không đo.
- Wrapper lạ trong `api.ts`: đo **một** hình dạng (hàm mới gọi `send`). Không quét các
  hình dạng khác (ví dụ gọi `fetch` thẳng trong một module ngoài `api.ts`).
- Không đo chi phí import trên máy khác; PR khai 9.3 ms, tôi không kiểm lại.

## 7. Ghi chú quy trình

**#465 merge lúc 03:40:59Z, khi tôi đang test nó** (PR của chính tôi, #466, cũng vậy).
Tôi phát hiện ra không phải từ GitHub mà từ chính cổng `stacked-branch` đỏ lên giữa
lượt đo. Mọi số liệu ở trên vẫn dùng được vì cây "TRƯỚC" của tôi ghim ở `fee2d73` và
nội dung ba file ở `92fc72f` giống hệt bản đã lên main — nhưng nếu bản vá có vấn đề
thì lúc tôi báo, nó đã ở trên `main` rồi. Nêu ra để Lead cân nhắc nhịp merge, không
phải để phàn nàn: kết luận vẫn là PASS.
