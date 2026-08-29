# rd-qa-04 — Gác PR #83 (rd-be-03: món ăn, gán người, nối vào allocator)

**PASS.**

Đường tiền qua bốn route đi đúng trên Postgres thật: `Σ` phân bổ bằng đúng tổng kể cả
ca lẻ không chia hết, hai đường bịa nghĩa vụ đều bị từ chối bằng mã ổn định, và không
một hàng `bills` nào chạm vào sổ cái. CI đỏ ở job `mobile bundle and tests` **không
phải lỗi của #83** — đó là dấu vết của nền cũ, đã chứng minh bên dưới.

| | |
|---|---|
| PR | #83, head `14530f6` |
| Đo trên | merge của `14530f6` vào `origin/main` @ `dc9d68c` — sạch, không xung đột |
| protocol_version | v1 |
| verdict | `APPROVE` |
| blocker còn mở | không |

Đo lại lần hai sau khi #89 (`dc9d68c`) vào main giữa lúc đang gác. Số dưới đây là của
lần hai; lần đầu (nền `b872482`) cho cùng kết luận với 800 ca thay vì 829.

---

## 1. CI đỏ là di sản của nền cũ, không phải lỗi của #83

Job `mobile bundle and tests` đỏ ở đúng một ca:

```
not ok 147 - không thành phần nào đọc .confidence hay in ra một phần trăm
  expected: false     actual: true
```

#83 **không sửa một file frontend nào** (`git diff --name-only origin/main...14530f6`
lọc `apps/mobile|packages/` ra rỗng), nên nó không thể là nguyên nhân. Nguyên nhân thật:

```
$ git log --oneline -1 refs/pull/83/merge
0c536c2 Merge 14530f6 into 43ae65d          <- GitHub test bản HỢP NHẤT, không phải nhánh trần
$ git ls-tree -r --name-only origin/pr83merge -- apps/mobile/src | grep -i daiban
apps/mobile/src/screens/kham-pha/DaiBanDo.tsx        <- có mặt
$ git merge-base --is-ancestor b872482 origin/pr83merge
NO — thiếu b872482                                    <- cổng đã sửa thì KHÔNG có
```

Tức CI chạy trên `#83 + main@43ae65d`: có `DaiBanDo.tsx` của #81 (`left: ${x}%` là toạ
độ CSS) nhưng **chưa** có bản vá cổng ở #82. Đúng sự cố main đỏ hôm qua, lặp lại trên
một PR vô can. Đối chứng hai chiều:

| Cây | `npm test` |
|---|---|
| nhánh trần `14530f6` | 129/129 pass — cổng pill **xanh**, chạy riêng `receipt.test.mjs` ra 22/22 |
| `#83` ⊕ `main@dc9d68c` (cổng đã sửa) | **183/183 pass** |

Không cần tác giả làm gì. Merge lên main hiện tại là hết đỏ. Nếu muốn thấy CI xanh
trước khi bấm, đẩy một commit rỗng hoặc rebase để GitHub dựng lại `refs/pull/83/merge`.

## 2. Đường tiền thật, bốn route, Postgres thật

Script: `scripts/qc/probe_duong_tien_bill.py` (đi bằng HTTP thật; đọc sổ bằng
**connection khác**, không đọc lại qua API — một phản hồi viết ra trước khi commit vẫn
trông đúng nếu đọc lại bằng chính đường đó).

```
python3 scripts/qc/probe_duong_tien_bill.py --base-url http://127.0.0.1:8283 \
  --pg-container qa83-postgres-1 --context <ctx> --participant <a> --participant <b> --participant <c>
-> 10/10 PASS, exit 0
```

| Câu hỏi | Kết quả |
|---|---|
| Lẻ 100.001đ chia 3: `Σ` == tổng, 100% | PASS — `33334 + 33334 + 33333 = 100001` |
| Mỗi phần là số nguyên đồng (luật 1) | PASS — `int, int, int` |
| Món riêng: ai ăn gì trả đúng món đó | PASS — `219000 / 148000 / 30000`, `Σ = 397000` |
| **Món không ai nhận** | PASS — `422 ITEM_HAS_NO_ASSIGNEE`, **không** mặc định chia cho tất cả |
| **Bill không ra món** | PASS — `422 BILL_HAS_NO_ITEMS`, **không** lui về chia đều |
| Gợi ý AI chưa xác nhận vào sổ | PASS — `422 bill_assignments_not_confirmed` |
| **Sổ cái không đổi một hàng nào** | PASS — `drift = none` trên 10 bảng tiền |
| ...nhưng `bills/bill_items` **có** ghi | PASS — `15/18` hàng |

Hai hàng cuối phải đọc cùng nhau. "Sổ không đổi" một mình sẽ pass y hệt trên một phép
đo chết; hàng dưới chứng minh phép đo còn sống — draft **có** được ghi, sổ **vẫn**
đứng yên. Đó là bất biến 3, đo được chứ không phải hứa.

## 3. Cổng có thật sự đỏ được không — đối chứng bằng đột biến

Lead đã đột biến "giấy thắng" và AST-không-có-phép-chia, nên tôi đột biến hai đường
**bịa nghĩa vụ tiền** mà chưa ai đâm vào. Cả hai lần đều trả lại nguyên trạng
(`git diff --quiet` sạch).

**Đột biến A** — món không ai nhận, thay `raise` bằng "chia cho tất cả":

```
1 failed, 799 passed
FAILED tests/domain/test_bill_projection.py::ThingsTheProjectionRefusesToGuess::
       test_an_item_nobody_is_assigned_to_is_refused_not_shared_by_everyone
```

**Đột biến B** — bill rỗng, bỏ `raise` để rơi xuống chia đều:

```
2 failed, 798 passed
FAILED tests/api/test_bills.py::TestSplitReusesTheAllocator::
       test_a_bill_with_no_lines_is_not_quietly_split_evenly
FAILED tests/domain/test_bill_projection.py::ThingsTheProjectionRefusesToGuess::
       test_a_bill_with_no_items_is_refused_rather_than_split_evenly
```

Đỏ đúng tên, đỏ ở cả tầng domain lẫn tầng API. Hai cổng này là cổng thật, không phải
assert trang trí.

## 4. Cổng đã chạy, số thật

Toàn bộ trên cây merge sạch (`git status` trống), commit `dc9d68c` ⊕ `14530f6`:

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **829 passed**, 137 skipped, 4434 subtests |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **122 passed, 0 skipped** |
| `cd apps/mobile && npm test` | **183 passed, 0 fail** |
| `npm run test:e2e` (ghim `EXPO_PUBLIC_API_URL=:8283`) | **2 passed** — chạy thật, không in "khong co server" |
| `alembic upgrade head --sql` (offline) | ok |
| `alembic heads` | `['b2d9f4c781a0']` — **một head** sau khi merge với main hiện tại |
| `make up` trên bộ riêng `qa83` | migration chạy được trên DB trắng, API healthy |

Migration là chỗ tác giả nêu rủi ro (hai `down_revision` cùng cha). Đã kiểm lại **sau**
khi hợp nhất với main mới: vẫn một head, và vẫn migrate được từ DB trắng.

Bẫy đã tránh: `npm run test:e2e` mặc định bắn vào `:8099` (container của lane khác) và
`seed_bank_recipient.py` mặc định ghi vào `:5432`. Không ghim cả hai thì phép đo này đo
nhầm máy người khác. Lần chạy đầu đỏ đúng ở `UNREADY_RECIPIENT_CHOICE_REQUIRED` vì
seed rơi vào DB khác — ghim rồi mới xanh.

## 5. Giao diện có ngụ ý con số đã được kiểm chứng không

Câu Lead hỏi ở #55 và #76, hỏi tiếp cho lần này. Quét bằng Playwright + axe-core trên
bundle web dựng từ chính cây merge (390×844, `vi-VN`):

- Màn **Chụp bill** (cửa vào hero): **0 vi phạm axe**, và câu chữ nói thẳng giới hạn —
  *"Trình duyệt không mở được camera trong app này"*, *"Bản demo: chưa nối đăng nhập thật"*.
  Không có câu nào khẳng định con số đã đúng.
- `POST /bills` **không** trả `confidence` ra wire (kiểm bằng khoá của response thật,
  không bằng đọc code) — đúng ADR-0009 quyết định 4.

Nên ở phần #83 chạm tới, giao diện **không** ngụ ý con số đã được kiểm chứng. Nhưng
xem ô chưa quét: tôi **chưa** đi được tới `KetQuaNhanDien`/`GoiYChia` với dữ liệu thật.

## 6. Hai phát hiện a11y — KHÔNG chặn #83

Cả hai nằm sẵn trên main, #83 không đụng file frontend nào nên không thể là nguyên
nhân. Ghi ở đây vì tìm ra trong cùng lượt đo; đã báo sang lane sở hữu.

Máy quét được chứng minh còn sống **trước** khi tin bất kỳ kết quả rỗng nào — cắm một
`<img>` không alt và một `<button>` không tên vào trang, axe bắt đúng `image-alt` +
`button-name`. Không có bước này thì `0 violations` và "máy quét không chạy" trông y hệt.

1. **`aria-required-children` (critical)** — `role="tablist"` của thanh tab có con thứ ba
   là `<div>` trần, `role=null`, không nhãn (chỗ nút `[+]`). Bên trong có 4 `role="tab"`
   hợp lệ, nhưng phần tử lạ nằm giữa làm cả tablist sai. Trình đọc màn hình đi vào thanh
   điều hướng chính sẽ gặp một phần tử không vai trò, không tên.
2. **`aria-prohibited-attr` × 12 (serious)** — 12 chấm bản đồ ở `DaiBanDo.tsx:50` là
   `<div>` trần mang `accessibilityLabel`. `aria-label` trên div không role bị trình đọc
   màn hình **bỏ qua**, và `tabindex` là `null` nên bàn phím cũng không tới được. Tên 12
   địa điểm trên bản đồ vô hình với AT. Đây đúng là "phần chấm bản đồ" Lead đã ghi là
   còn nợ — giờ có tên rule và số node.

## 7. Ô CHƯA QUÉT — đọc phần này trước khi tin phần trên

- **`KetQuaNhanDien` và `GoiYChia` với dữ liệu thật**: chưa. Đi tay tới được màn *Chụp
  bill* rồi dừng, vì đi tiếp cần ảnh bill thật qua Gemini. Câu hỏi "màn kết quả có ngụ ý
  con số đã được kiểm chứng không" vẫn **mở** cho hai màn đó.
- **Mã QR quét bằng app ngân hàng thật**: chưa, và không agent nào làm được (ADR-0010
  mục 8). Cần leader, một điện thoại, 15 phút.
- **Nửa sau của luồng bằng tay** (form → chia tiền → đợt thu → publish → trang khách):
  mới có e2e ở tầng HTTP (2 ca xanh), **chưa ai bấm bằng tay**. Ô này Lead đã nêu và vẫn
  còn nguyên.
- **Trang khách**: không quét trong lượt này. #83 không chạm `app/web/`.
- **Đua/idempotency trên bốn route bill**: chưa đâm. Gọi `split` hai lần đồng thời, hay
  `PUT assignments` chồng nhau, chưa ai đo.
- **`ruff`** trên file mới của #83: chưa chạy lại (tác giả khai đã sạch).

## 8. Ghi chú, không phải blocker

`POST /bills` nhận `context_id` **không tồn tại** (`00000000-...`) và trả 201, ghi 5
hàng draft mồ côi. Không phải lỗi của #83 và không phải blocker:

- `bills` **không** có khoá ngoại tới `contexts` — nhưng `expenses` (bảng sổ, có trước
  #83) cũng **không** có. #83 đi theo đúng quy ước sẵn có, không lệch khỏi nó.
- Hàng mồ côi là **draft**, đã chứng minh không chạm sổ (mục 2).
- Header `X-Actor-Contexts` do gateway tin cậy ghi đè là chỗ tạm đã ghi trong `CLAUDE.md`.

Ghi lại để lúc bỏ header tạm thì nhớ có chỗ này, không phải để chặn ai.

---

## Tái lập

```bash
git checkout -B kiem-83 origin/main && git merge 14530f6

MOBILE_PROJECT=qa83 MOBILE_API_PORT=8283 MOBILE_POSTGRES_PORT=5483 make up

python3 -m pytest services/api/tests tests -q
cd services/api && MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5483/mobile' \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest tests/postgres -q
cd apps/mobile && npm test
cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8283 \
  MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5483/mobile' \
  MOBILE_REQUIRE_E2E=1 npm run test:e2e

python3 scripts/qc/probe_duong_tien_bill.py --base-url http://127.0.0.1:8283 \
  --pg-container qa83-postgres-1 --context <ctx> \
  --participant <a> --participant <b> --participant <c>

MOBILE_PROJECT=qa83 make clean CONFIRM=qa83
```

Ảnh chụp màn hình để ngoài repo (`/tmp/qa83-shots/`, repo guard fail closed với binary).
Không có dữ liệu thật trong bất kỳ dòng nào ở trên: nhóm, người và số tiền đều là dữ
liệu seed tổng hợp.
