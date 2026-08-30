# FAIL cho PR #397 tại 9df1c82

Cổng đọc hợp đồng route mù đi 64 → 10 đường dẫn mà vẫn thoát 0, và cây gộp với
main không biên dịch được ở hai route tiền — không xung đột một dòng nào.

- protocol_version: v1
- đo tại: `9df1c82` (head của `frontend/api-actor-id-bat-buoc` lúc bắt đầu)
- sha này: **là nhánh chưa merge**, và **sau main 15 commit**
- merge-base: `33d16d8`
- main lúc đo: `5220ebd`
- verdict: **FAIL**

---

## Lý do, trước mọi chi tiết

Hai blocker, cả hai thuộc loại **vi phạm spec/cổng**:

1. **PR làm mù cổng `check_api_contract.py` mà cổng vẫn báo xanh.** Bộ đọc
   route nhận diện hàm bọc **bằng tên** (`WRAPPERS = {"call": ..., "translated": ...}`,
   `scripts/check_api_contract.py:427`). PR đổi tên cả hai, nên bộ đọc thôi
   không theo được nữa: **64 → 10** đường dẫn, riêng `api.ts` **39 → 2**. Cổng
   vẫn in `Client và máy chủ khớp hợp đồng` và **thoát 0**.
2. **Cây gộp `#397 ⊕ main` không biên dịch được**, ở hai route tiền, với
   **0 xung đột merge**.

Điều đáng ghi nhận: **PR sửa đúng một lỗ có thật**, tôi đã tự dựng đối chứng và
xác nhận (mục 3). Vấn đề không nằm ở ý tưởng, nằm ở hai chỗ nó va vào mà chưa ai đo.

---

## 1. Blocker A — cổng đọc route mù đi, và vẫn xanh

`scripts/check_api_contract.py` là cổng trả lời câu *"client có gọi route nào máy
chủ không có không"*. Nó tìm lời gọi bằng **tên hàm bọc**:

```python
# scripts/check_api_contract.py:427
WRAPPERS = {
    "call": (0, 1),
    "translated": (1, 2),
}
```

PR đổi `call` → `callAsActor` / `callAnonymous` và `translated` →
`translatedAsActor` / `translatedAnonymous`. Không tên nào trong bảng trên còn khớp.

Đo bằng chính bộ đọc của cổng, cùng một hợp đồng, chỉ khác SHA:

| cây | đường dẫn đọc được | riêng `src/api.ts` |
|---|---|---|
| merge-base `33d16d8` | **64** | **39** |
| PR head `9df1c82` | **10** | **2** |

Và cổng **không hề đỏ**:

```
$ python3 scripts/check_api_contract.py          # tại 9df1c82
Máy chủ có 77 route. Đọc được 10 đường dẫn qua 16 lần gọi trong 7 file,
6 chỗ không phân giải được.
GHIM CŨ: apps/mobile/src/api.ts :: path -- không còn khớp chỗ nào; ...
GHIM CŨ: apps/mobile/src/api.ts :: path: string -- không còn khớp chỗ nào; ...
GHIM CŨ: apps/mobile/src/api.ts :: string> -- không còn khớp chỗ nào; ...
Client và máy chủ khớp hợp đồng.
EXIT=0
```

`EXIT=0` trên một cây mà cổng chỉ còn nhìn thấy 16% số đường dẫn nó từng thấy.
Đây đúng hình dạng "cổng mặc định là đồ trang trí": không ai đọc số 10, người ta
đọc dòng cuối.

**Thứ đã cứu lượt này là canary chống mù có sẵn trong repo**, không phải tôi:

```
tests/test_api_contract.py::ReaderDoesNotGoBlind::test_the_real_client_still_has_routes_to_check
AssertionError: 10 not greater than 10
```

Đối chứng ba điểm, một biến, cùng một lệnh:

| cây | `ReaderDoesNotGoBlind` |
|---|---|
| merge-base `33d16d8` | 4 passed |
| PR head `9df1c82` | **1 failed**, 3 passed |
| main `5220ebd` | 4 passed |

Xanh ở merge-base, đỏ ở PR head, xanh ở main → **PR gây ra**, không phải nợ cũ.

Hệ quả là PR **đỏ ở cổng mặc định của repo**:

```
$ python3 -m pytest services/api/tests tests -q     # tại 9df1c82
1 failed, 2637 passed, 574 skipped, 4888 subtests passed in 240.52s
```

## 2. Blocker B — cây gộp không biên dịch, và merge không xung đột

PR đứng **sau main 15 commit**. Trong khoảng đó main thêm 141 dòng vào chính
`api.ts`, trong đó có hai lời gọi qua `call` — hàm mà PR **xoá đi**.

```
$ git merge origin/main            # vào 9df1c82
CONFLICTS: (rỗng — không một file nào)

$ npx tsc --noEmit                 # cây gộp
src/api.ts(1013,20): error TS2304: Cannot find name 'call'.
src/api.ts(2386,24): error TS2304: Cannot find name 'call'.
```

Hai chỗ đó là route tiền, không phải chỗ rìa:

- dòng 1013 — `GET /bank-recipients/{recipientId}` (đọc lại tài khoản nhận tiền)
- dòng 2386 — `POST /bills/{billId}/split` (**chia bill — đúng đường hero**)

Mỗi nửa tự nó đều sạch:

| cây | `npx tsc --noEmit` |
|---|---|
| PR head `9df1c82` một mình | sạch, 0 lỗi |
| main `5220ebd` một mình | sạch, 0 lỗi |
| **gộp hai cái** | **2 lỗi TS2304** |

Hai nhánh xanh, không xung đột, gộp lại đỏ. Git im lặng vì hai bản sửa nằm ở hai
vùng khác nhau của cùng một file — nó nối văn bản, nó không biết `call` đã mất tên.

## 3. Đối chứng — lỗ hổng PR khai là CÓ THẬT

Tôi không nhận lời khai của PR. Tôi dựng lại lỗi ở bản **trước** PR: cùng một sai
lầm (gọi route được `X-Actor-ID` gác, không nói ai gọi), viết theo API tại
merge-base, biên dịch bằng chính `tsconfig` của cây đó.

```ts
// tests/canary-qa/quen-actor-id-cu.ts  @ 33d16d8
import { translated } from "../../src/api";
export async function quenActorId(billId: string) {
  return translated<{ id: string }>({}, `/bills/${billId}`, { method: "GET" });
}
```

```
$ npx tsc -p tsconfig.canary-qa.json     # tại 33d16d8
TSC_EXIT=0        ← biên dịch SẠCH: lỗ hổng có thật
```

Ở PR head, canary tương đương của chính tác giả **không** biên dịch được, và ca
hồi quy đòi nó đỏ vì đúng lý do:

```
$ node --test tests/actor-id-bat-buoc.test.mjs   # tại 9df1c82
# pass 2   # fail 0
```

**Đột biến** — nới `actorId: string` về `actorId?: string` ở `ActorCallOptions`,
giữ nguyên mọi thứ khác:

```
# pass 0   # fail 2     ← cả hai ca đều giết được
```

Nên phần lõi của PR là thật và có gác. Đó là lý do đây là FAIL "sửa hai chỗ va",
không phải REJECT.

## 4. Cái đã xanh, ghi cho đủ

| phép đo tại `9df1c82` | kết quả |
|---|---|
| `npm test` (apps/mobile) | **890 pass / 0 fail**, 15 suites |
| `scripts/check_actor_headers.py` | ĐẠT — 118 file, **133 lời gọi**, exit 0 |
| `npx tsc --noEmit` trong cây PR | sạch |

Con số 133 khớp lời khai của PR: cổng header actor đọc được đúng bằng trước khi
sửa. Cổng *đó* không mù. Cổng anh em của nó thì mù, và PR không đo cổng anh em.

---

## DA CHAY

- `python3 -m pytest services/api/tests tests -q` @ `9df1c82` → 1 failed, 2637 passed, 574 skipped, 4888 subtests
- `python3 -m pytest tests/test_api_contract.py::ReaderDoesNotGoBlind` @ `33d16d8` / `9df1c82` / `5220ebd` → 4 passed / **1 failed** / 4 passed
- `python3 scripts/check_api_contract.py` @ `9df1c82` → exit 0, chỉ 10 đường dẫn, 3 GHIM CŨ
- đếm đường dẫn bằng bộ đọc của cổng @ `33d16d8` / `9df1c82` → 64 / 10
- `python3 scripts/check_actor_headers.py` @ `9df1c82` → ĐẠT, 133 lời gọi, exit 0
- `npx tsc --noEmit` @ `9df1c82` / `5220ebd` / cây gộp → sạch / sạch / **2 lỗi**
- `git merge origin/main` vào `9df1c82` → 0 xung đột
- `npm test` @ `9df1c82` → 890 pass, 0 fail
- `node --test tests/actor-id-bat-buoc.test.mjs` @ `9df1c82` → 2 pass; sau đột biến → 2 fail
- đối chứng canary API cũ @ `33d16d8` → `tsc` exit 0

## KHONG CHAY — phần này quan trọng hơn phần trên

- **`tests/postgres`** — không chạy (không dựng Postgres). 574 skipped ở lệnh
  pytest gồm tầng này. Lý do: PR không chạm `app/db`, và blocker đã đủ để FAIL.
  **`skipped` không phải xanh.**
- **`npm run test:e2e` (lát cắt dọc thật)** — không chạy, cần uvicorn + Postgres
  sống. Đây là **ô trống đáng tiếc nhất**: PR đổi đúng lớp client mà lát cắt dọc
  đi qua, nên nó là chỗ duy nhất chứng minh được "không đổi hành vi runtime"
  trên dây thật. Tôi mới chứng minh điều đó ở tầng kiểu + cổng header + 890 ca,
  **không** phải bằng header thật trên một request thật.
- **`make gate` / `make gate-merge` đầy đủ** — không chạy.
- **Trang khách, ma trận ảnh, tương phản, a11y** — không chạm, PR không đụng `app/web/`.
- **Mã QR quét bằng app ngân hàng thật** — vẫn **chưa quét**, như mọi lượt trước.
- **Từng header trên dây của 133 lời gọi** — không kiểm từng cái.

---

## Tiêu chí gỡ chặn

1. Dạy `WRAPPERS` trong `scripts/check_api_contract.py` bốn tên mới
   (`callAsActor`, `callAnonymous`, `translatedAsActor`, `translatedAnonymous`),
   rồi chứng minh bộ đọc quay lại **~64** đường dẫn, không phải chỉ vượt mốc 10.
   Dọn luôn 3 `GHIM CŨ` trong `.api-contract-unresolved.json` mà cổng đang kêu.
2. Rebase lên `main`, đổi hai lời gọi `call(` còn lại ở `api.ts`
   (`/bank-recipients/{id}`, `/bills/{id}/split`) sang `callAsActor`, và chứng
   minh `npx tsc --noEmit` sạch **trên cây gộp**, không chỉ trên nhánh.
3. Chạy lại `python3 -m pytest services/api/tests tests -q` cho tới khi
   `ReaderDoesNotGoBlind` xanh.

## Một ghi chú về hình dạng, không phải về PR này

Cổng thứ hai vừa bị bắt vì nhận diện **bằng tên hàm**. Cổng CORS ở #379 mù đúng
kiểu đó (`function ...[Hh]eaders(` không khớp `tieuDe`), và #410 đang mở để sửa
phần *câu chữ* của chính chuyện đó. Ở đây thì tên đổi bên client, cổng ở lại.
Ba cổng đang đọc client bằng tên hàm — đáng để Lead cân nhắc một vòng riêng, vì
đổi tên là thao tác refactor bình thường và không ai coi nó là việc chạm cổng.
