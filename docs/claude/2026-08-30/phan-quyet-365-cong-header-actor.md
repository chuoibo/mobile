# FAIL

**Gộp #365 vào `main` làm cổng `tests/test_actor_header_contract.py` đỏ, tức là làm
`python3 -m pytest services/api/tests tests -q` đỏ trên `main`.** Nhưng sản phẩm
KHÔNG sai: client có gửi `X-Actor-ID`, tiền chia đúng. Cổng báo nhầm, vì regex đọc
generic của nó không đi qua được `<>` lồng. Gỡ chặn tốn khoảng hai phút, và có hai
chỗ sửa được — chọn một.

---

## Đo tại đâu

```
PR #365 head   34d867f  (qa3/man-chi-tiet-5-route)
main           98b7b1b  (sau khi #371 merge, giữa lượt đo này)
đo tại         e2e6e11 = 34d867f ⊕ main@98b7b1b   — nhánh CHƯA merge
```

Tôi đo **kết quả gộp**, không đo head trần của PR: PR đứng sau `main` 5 commit, và
thứ Lead thực sự bấm merge là cây gộp. Gộp sạch, 0 xung đột.

`main` nhích một lần giữa lượt (`b56a772` → `98b7b1b`, #371 vào). Tôi gộp lại lên
nền mới và chạy lại; kết luận không đổi.

---

## Cổng nào đỏ, và nó nói gì

```
$ python3 -m pytest services/api/tests tests -q          # tại e2e6e11
1 failed, 2613 passed, 551 skipped, 4899 subtests passed in 233.15s

FAILED tests/test_actor_header_contract.py::TheTreeItselfPasses::
       test_every_actor_route_the_app_calls_sends_the_header
```

Nguyên văn cổng:

```
Cổng header actor — 106 file client, 100 lời gọi tới route đòi X-Actor-ID.

HỎNG — 1 chỗ gọi route đòi X-Actor-ID mà không gửi:
  POST /bills/{}/split
      apps/mobile/src/api.ts:2282 docChiaBill()
```

## Đối chứng: `main` một mình thì xanh

```
$ git checkout --detach origin/main && git log --oneline -1
98b7b1b Container không có khoá là HỎNG, không phải "chưa kết luận được" (#371)

$ python3 -m pytest tests/test_actor_header_contract.py -q
12 passed in 2.31s
```

Xanh ở `main`, đỏ ở cây gộp. Nên cái đỏ này là do #365 mang vào, không phải nợ cũ.

## Đối chứng: cổng có trung thực không

Cổng này có canary sẵn trong người. Chạy trước khi tin nó:

```
$ python3 scripts/check_actor_headers.py --selftest
  ĐẠT    canary xấu: có vi phạm (mong đợi có)
  ĐẠT    canary sạch: không có vi phạm (mong đợi không có)
  ĐẠT    canary mù: có vi phạm (mong đợi có)
  ĐẠT    canary mù/sạch: không có vi phạm (mong đợi không có)
exit=0
```

4/4. Cổng đỏ được khi thật sự thiếu header và xanh được khi không thiếu — nên con
số của nó có nghĩa, và cái đỏ trên kia đáng đi tìm nguyên nhân chứ không đáng bỏ qua.

---

## Nhưng sản phẩm gửi header. Đo trên dây, không đọc chữ

Cổng đọc văn bản TypeScript. Tôi đo cái client biên dịch xong đưa cho `fetch`:

```
$ node docs/claude/2026-08-30/qa-tt-0042/do-header-tren-day.mjs
URL     : http://localhost:8099/bills/bill-xyz/split
METHOD  : POST
HEADERS : {
  "Content-Type": "application/json",
  "X-Actor-ID": "ACTOR-UUID-1234",
  "X-Actor-Roles": "member,advancer,recipient,batch_owner",
  "X-Actor-Contexts": "ctx-9",
  "Idempotency-Key": "k1"
}
X-Actor-ID CO tren day: ACTOR-UUID-1234
exit=0
```

Chỉ `fetch` bị thay. Không vá gì bên trong client, nên header trên kia đúng là
header máy chủ sẽ nhận.

Đọc mã nguồn cũng khớp: `docChiaBill(billId, actorId, contextId, attempt)` có
`actorId` là tham số **bắt buộc**, và nó truyền thẳng `actorId` xuống `call()`;
`call()` dựng header bằng `actorHeaders(actorId, roles, contexts)` khi `actorId`
có giá trị (`api.ts:307`).

---

## Vì sao cổng báo nhầm

`scripts/check_actor_headers.py:398`:

```python
pattern = re.compile(rf"\b{re.escape(name)}\s*(?:<[^<>()]*>)?\s*\(")
```

Nhóm generic tùy chọn là `<[^<>()]*>` — nó **cấm `<` và `>` bên trong**. Lời gọi ở
`docChiaBill` là:

```ts
const result = await call<{
    allocation: {
      allocations: Record<string, number>;      // <-- <> lồng ở đây
      exact_shares: Record<string, string>;
      ...
  }>(`/bills/${billId}/split`, { method: "POST", body: {}, actorId, attempt, contexts: contextId });
```

`Record<string, number>` làm nhóm generic trượt, rồi `\s*\(` cũng trượt, nên
**pattern không khớp một lần nào**. `call_args()` trả `[]`. `passes_an_actor()` gặp
danh sách rỗng thì trả `False`, và `False` được đọc là "hàm này không đưa actor cho
`call`" → báo vi phạm.

Chạy lại được, bằng chính các hàm của cổng:

```
$ python3 docs/claude/2026-08-30/qa-tt-0042/tai-lap-cong-do.py
1. Regex `<[^<>()]*>` gap ba hinh dang generic:
   KHOP  | generic la mot ten                 call<SoDuWire>(...)
   KHOP  | inline, khong long <>              call<{ a: string }>(...)
   TRUOT | inline, CO long <>                 call<{ a: Record<string, number> }>(...)

2. Tren file that — apps/mobile/src/api.ts:2282 docChiaBill():
   than ham chua 'actorId,' : True
   call_args(...,'call')    : []
   passes_an_actor          : False

3. Cung than ham, chi bo <> long trong generic:
   so blob doc duoc         : 1
   blob co chua actorId     : True
exit=0
```

Và trên chính file thật, đổi **hình dạng** chứ không đổi một dòng logic nào — nhấc
kiểu inline lên thành `type ChiaBillWire = {...}` rồi gọi `call<ChiaBillWire>(...)`:

```
truoc:  1 failed, 11 passed
sau  :  12 passed in 2.27s
hoan nguyen (git checkout -- apps/mobile/src/api.ts):
        1 failed, 11 passed
```

Đỏ → xanh → đỏ lại, do đúng một thay đổi hình dạng. Chẩn đoán đóng.

---

## Hai chỗ sửa được — chọn một

1. **Phía #365** (`apps/mobile/src/api.ts`, chủ sở hữu: qa3/frontend): nhấc kiểu
   inline của `docChiaBill` lên thành một `type` có tên. Không đổi hành vi, không
   đổi kiểu. Đây là bản tôi đã đo và nó làm cổng xanh.

2. **Phía cổng** (`scripts/check_actor_headers.py:398`): cho nhóm generic đi qua
   được `<>` lồng — ví dụ đếm ngoặc nhọn giống cách `call_args` đã đếm ngoặc tròn,
   thay vì `[^<>()]*`. Sửa chỗ này thì mọi hàm tương lai dùng `Record<K,V>` trong
   generic inline khỏi vấp.

Tôi nghiêng về **(2)**, vì `Record<...>` trong generic inline là cách viết bình
thường và cái bẫy này sẽ quay lại. Nhưng (1) rẻ hơn và gỡ chặn được ngay đêm nay;
(2) có thể đi PR riêng. Quyền chọn thuộc chủ sở hữu file, không thuộc tôi.

**Hướng lệch của lỗ hổng này là an toàn**: khi không đọc được lời gọi, cổng báo vi
phạm chứ không bỏ qua. Ồn, không mù. Đó là hướng đúng cho một cổng.

---

## Phần còn lại của #365 tôi đã đo được

**`npm test` trong `apps/mobile`, tại cây gộp — XANH:**

```
# tests 797
# suites 11
# pass 797
# fail 0
# skipped 0
```

Gồm cả `tests/nam-man-chi-tiet.test.mjs` (251 dòng) mà PR thêm vào.

**Route `POST /bills/{bill_id}/split` trên API sống 8099** (máy demo, đang chạy
`main`; Lead dựng lại lúc 23:24). Hoá đơn thật trong dữ liệu demo, 4 người chia:

```
KHONG header : HTTP 401  {"code":"authentication_required","detail":"Missing X-Actor-ID"}
CO header    : HTTP 200
  so nguoi         : 4
  Σ phan bo        : 745000
  total_amount_vnd : 745000
  LUAT 2 (Σ == tong)   : DAT
  LUAT 1 (nguyen dong) : DAT
  assignment_state     : confirmed
```

Hai điều: 401 khi thiếu header là **thật** — nên nỗi lo mà cổng canh là có cơ sở,
chỉ là nó chỉ nhầm người; và con số của route này thoả luật tiền 1 và 2. Σ 745.000
khớp đúng con số PR tự dán trong phần bằng chứng.

**Cổng route-không-ai-gọi, tại cây gộp — XANH:**

```
$ python3 scripts/check_server_routes_called.py
Máy chủ khai 77 route. 52 có người gọi, 5 miễn, 20 đang nợ, 0 không ai gọi và chưa ghi nhận.
Không có route mới nào bị bỏ rơi.
exit=0
```

Cổng này **tự suy lại** người gọi chứ không đọc phán quyết ghi sẵn — nó có nhánh
báo "ghim cũ" khi một route đã có người gọi mà vẫn còn nằm trong
`.server-routes-uncalled.json`. Nên việc PR gỡ ghim là được máy xác nhận, không
phải lời khai.

### Một chỗ lệch giữa mô tả PR và cây, không phải blocker

Bảng trong mô tả PR nói **5** route có màn gọi. Cây thì gỡ **3** ghim:
`/bank-recipients/{recipient_id}` · `/bills/{bill_id}/split` · `/places/{place_id}`.

Hai route còn lại:

- `/contexts/{id}/widget` — đã có người gọi từ #348, không còn trong danh sách nợ
  từ trước. PR thêm **cửa vào** màn đó, đúng như mô tả. Không có ghim để gỡ.
- `/contexts/{cid}/photos/{pid}` — **vẫn nằm trong danh sách nợ** sau khi gộp. Đây
  không phải thiếu sót: ảnh đi qua `taiAnhCoQuyen` trong `Anh.tsx`, tức là `fetch`
  bằng một URI **động** máy chủ trả về, rồi vẽ bằng `blob:`. Cổng đọc tĩnh không
  quy được URI động về route nào, nên route ở lại danh sách nợ dù runtime có gọi.
  Cơ chế này là đúng và cố ý — `<img>` không gửi được header, mà route ảnh là
  members-only (401 nếu thiếu header).

Nói ra vì người đọc mô tả PR sẽ đếm 5 rồi đi tìm 5 dòng bị gỡ và chỉ thấy 3.

---

## Ô CHƯA QUÉT — đọc phần này trước khi coi #365 là đã được kiểm

- **Đi bộ bằng trình duyệt qua 5 cửa vào giao diện.** Tôi **không** dựng bundle từ
  `e2e6e11` và **không** bấm thử. Câu "mỗi route có một chỗ bấm tới được" hiện chỉ
  được bảo lãnh bởi test của chính tác giả, không bởi phép đo độc lập của tôi. Đây
  là ô trống lớn nhất còn lại.
- **Ảnh chụp / tương phản / bàn phím** trên `ChiTietDiaDiem`, `AnhToanMan`, thẻ
  "Máy chủ chia thử", thẻ "Đã có tài khoản trên máy chủ": chưa quét.
- **`tests/postgres` tầng sống**: chưa chạy trong lượt này (`551 skipped` ở lệnh
  pytest gồm cả tầng đó). #365 không chạm `app/db/`, nhưng tôi vẫn ghi ra vì một
  dấu xanh không nói giúp phần bị bỏ qua.
- **Che số tài khoản**: PR nói `docTaiKhoanNhan` mask tại chỗ và có assert cấm số
  đầy đủ lọt. Tôi **chưa** tự đâm vào chỗ đó bằng dữ liệu thật; mới thấy nó nằm
  trong 797 ca xanh của tác giả.
- **Mã QR quét bằng app ngân hàng thật**: vẫn chưa ai làm, và không agent nào làm
  được. Câu này chỉ đóng bằng một điện thoại thật trong tay leader.

## Tiêu chí gỡ chặn

`python3 -m pytest services/api/tests tests -q` xanh trên cây gộp
(#365 ⊕ `main` tại thời điểm merge). Chỉ vậy. Không đòi thêm gì, vì phần còn lại
của PR tôi đo được đều xanh và tiền thì đúng.

Đẩy commit mới thì phán quyết này hết hiệu lực và tôi đo lại từ SHA mới.

## Phân loại blocker

**Loại 1 — vi phạm cổng.** Có dẫn chứng (đỏ/xanh hai chiều, đối chứng trên `main`),
có hậu quả (`main` đỏ ngay sau merge, và cổng này chính là cổng đã được dựng lên vì
bug-191433 từng làm màn Khám phá hỏng hai tiếng trên `main`), có tiêu chí gỡ chặn ở
trên.

Không phải loại 2: **không có sai tiền nào.** Σ phân bổ = tổng, số nguyên đồng, một
allocator duy nhất.
