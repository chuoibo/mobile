# Có đường nào máy chủ đặt id ngoài participants vào trường người-được-chia không?

task_id: qa2-115432 · lane qa2 · 2026-08-31
nền đo: `6f4c499` (origin/main lúc đo) · nhánh `qa2/hai-cho-de-xuat-in-id`
skill: `security-testing` (khung A01 — broken access control / IDOR: id ở trường
tiền có được **buộc** vào tập nguồn không, hay chỉ **tình cờ** thuộc nó)

## Câu hỏi

> Có đường nào trong mã máy chủ đặt một id vào trường người-được-chia mà id ấy
> KHÔNG bắt buộc lấy từ tập participants của chính khoản chi đó không?

Đọc mã máy chủ, không gọi API. Câu này phải trả lời bằng **cấu trúc**, vì
`5/5 ca` của frontend là danh sách viết tay và danh sách viết tay không tự biết
mình thiếu gì.

## Trả lời

**CÓ — đúng một đường: `POST /bills/{id}/split`.** Nó có chủ ý, có ghi chú dài
trong mã, và có test bảo vệ. Hai đường còn lại thì **KHÔNG**, và cái "không" đó
đúng mãi mãi vì nó là *by construction*, không phải một phép kiểm.

Kèm một mệnh đề thứ hai, vì thiếu nó thì câu trên dễ bị đọc thành báo động:
**màn duy nhất đọc `/split` hôm nay đã dựng đúng hình dạng** (duyệt khoá của máy
chủ, không duyệt roster của bill). Nên đây là *cửa mở, chỗ nó dẫn tới đã được
gác* — không phải một lỗ đang chảy. Xem mục cuối; tôi đã tự bác một kết luận sai
ở đúng chỗ này.

## Mẫu số 3 là suy ra, không phải tôi liệt kê

Trường "người được chia" trên dây là `AllocationProposal.allocations` và
`.rounding_gainers` (`app/api/schemas.py:87-90`).

```
AllocationProposal(  dựng ở ĐÚNG MỘT chỗ   -> app/api/service.py:521  _wire_allocation
_wire_allocation     có ĐÚNG BA nơi gọi    -> service.py:3628, 3650, 3757
allocations=         chỗ khác              -> 3771, 3786, đều là request.expected_allocations
```

Hai chỗ `expected_allocations` không phải lỗ: `service.py:3758` so nó với
`wire.allocations` và ném 409 `proposal_changed` nếu lệch, nên nó không mang
được tập khoá khác vào.

Vậy mẫu số là **3**, và 3 này rơi ra từ "ai dựng được cái struct đó", không phải
từ việc tôi đi tìm các route mình nghĩ ra.

## Bất biến: allocator không thể SINH RA một id

Đây là phần trả lời "đúng mãi mãi" và nó nằm trong `app/domain/allocator.py`:

- `_exact_shares` khoá dict theo `participants` ở **cả hai** nhánh:
  nhánh chia đều `return {p: total / count for p in participants}`;
  nhánh chung `base = {p: Fraction(0) for p in participants}` và
  `extra = {p: Fraction(0) for p in participants}`.
- `_validate_references` ném `UNKNOWN_PARTICIPANT` nếu bất kỳ id nào trong
  `item["shared_by"]` không thuộc `participants`. Nên vòng
  `base[participant] += share` **không thể tạo khoá mới** — nó đã bị chặn ở trên.
- `_apportion`: `ranked = sorted(exact, key=rank)` · `gainers = ranked[:deficit]`
  · `allocations = {p: ... for p in exact}`.

Suy ra `allocations.keys() == exact.keys() == set(participants)` và
`rounding_gainers ⊆ participants`. Đây là **hình dạng của mã**, không phải một
validator ai đó nhớ gọi — nên không cần đếm ca cho phần này.

`advancer_id` là ngoại lệ được khai rõ: `allocate()` chỉ thêm warning
`advancer_not_participant` chứ không từ chối. Nhưng advancer **không vào** trường
người-được-chia; ở `_apportion` nó chỉ là khoá phụ của `rank()` để phá hoà, nên
nó không bơm được id nào vào `gainers`.

## Ba đường, và tập participants của mỗi đường đến từ đâu

| # | service.py | route | `participants` lấy từ | buộc vào khoản chi? |
|---|---|---|---|---|
| 1 | 3628 | `POST /bills/{id}/split` | `repository.list_members(context_id)`, lọc `state == "active"` | **KHÔNG** |
| 2 | 3650 | `POST /expenses` (propose) | `proposal.participants` (thân request) | CÓ |
| 3 | 3757 | confirm | `request.proposal.participants` + `_require_participants_are_members` | CÓ, và còn soát roster |

Đường 1 là câu trả lời. `service.py:3558`:

```python
participant_ids = {
    membership.person_id
    for membership in self.repository.list_members(record.context_id)
    if membership.state == "active"
}
```

Và `BillSplitRequest` (`schemas.py`) chỉ có `for_ledger` và `paid_by_id` —
**không có trường participants nào cả**. Nên id trong `allocations` /
`rounding_gainers` của phản hồi này là id máy chủ tự chọn từ roster NHÓM; client
chưa từng gửi chúng, và chúng không buộc phải có mặt trên bill đang được gõ.

Đây không phải sơ suất. Ghi chú ngay trên đoạn đó nói rõ đó là chủ đích, và
`tests/api/test_split_does_not_invent_participants.py` giữ nó:

> The participants of a split are the group's roster, never the bill's own
> shares. […] An empty roster means there is nobody to split between, which is
> a refusal, not a licence to trust the request body.

Fallback "roster rỗng thì lấy shares làm roster" đã bị bỏ đúng vì nó đưa cho
allocator chính cái danh sách mà `UNKNOWN_PARTICIPANT` sinh ra để phán xét — một
phép kiểm chỉ có thể trả lời "có".

## Hệ quả cho cạnh 320k-vs-480k mà tôi đang giữ

Phải tách làm hai, vì hai màn đọc hai route khác nhau:

**Trên đường `DeXuat` đọc (`POST /expenses` propose): KHÔNG có đường.**
`propose_expense` chạy trên `_allocator_input(proposal)`, participants là của
client, nên theo bất biến ở trên `allocations.keys()` **luôn** bằng đúng tập
client vừa gửi. `DeXuat.tsx:35` đặt `const people = proposal.participants` và
`:59` `people.map(...)`, nên hai bên không thể lệch qua route này.

Nghĩa là cái stub nói dối trong phép đo trước của tôi **là bắt buộc**, không phải
đường tắt — và tôi giữ nguyên cách xếp loại cũ: cạnh đó là **hình dạng**, chưa
phải lỗ đang chảy. Điểm mới là giờ tôi nói được *tại sao* nó không chảy, bằng cấu
trúc chứ không bằng "5 ca tôi thử đều sạch".

**Trên `/bills/{id}/split`: CÓ ở máy chủ — nhưng màn duy nhất đọc nó đã dựng
đúng hình dạng.** Route này không đổ vào `DeXuat` mà vào `GoiYChia.tsx`
(`docChiaBill`, `api.ts:2423`), và trong `GoiYChia` nó chỉ tới đúng một thẻ:

- `GoiYChia.tsx:1026` `KetQuaChiaThu` — `Object.entries(ketQua.allocations).map(...)`
  + `labelInGroup`, tức duyệt **khoá của máy chủ**. Không ai rơi. Đây là hình
  dạng đúng, và ghi chú `:997-1012` nói rõ nó được tách ra khỏi `MayChuChiaThu`
  chính vì lý do này.

**Tôi đã suýt kết luận sai ở đây và tự bác lại.** Thẻ `GoiYChia.tsx:217` cũng
duyệt `people` (`= roster.participants`, `:99`) và cũng đọc
`split.allocations[person.id]`, nhìn y hệt một đường rơi thứ hai. Nhưng `:107`:

```ts
const split = preview !== null && preview.signature === live ? preview.split : null;
```

`split` ở thẻ đó là `SplitPreview` từ `previewSplit` — tức `POST /expenses`, chứ
**không phải** `/bills/{id}/split`. Nên khoá của nó vẫn ≡ tập participants client
vừa gửi, và thẻ đó không rơi được ai. Ghi chú `:902` đã nói sẵn điều này ("Every
dong above this card came from `previewSplit`"); tôi đọc `split.allocations` rồi
suy ra nguồn thay vì đi tìm nguồn.

Vậy kết luận đúng là: **cửa mở ở máy chủ, và chỗ nó dẫn tới đã được gác.** Không
có màn nào hôm nay rơi người từ một phản hồi `/split`.

Client đã biết chuyện này: `participants.ts:174-200` giải thích rằng `/split` và
`/balances` "routinely name people who are legitimately absent from the bill", và
`labelInGroup` được thêm sau bug-050923. Nhưng đó là bản vá cho **cái NHÃN** (in
UUID cạnh tên thật), không phải cho **cái DÒNG**. Chỗ nào duyệt `people` mà lại
đọc một `allocations` **không** bảo đảm cùng tập khoá thì người đó biến mất hẳn —
nhãn đẹp không cứu được. Hôm nay không có chỗ nào như thế; nó phụ thuộc vào việc
mỗi thẻ tiếp tục lấy đúng nguồn của mình, và **không có phép kiểm nào giữ điều đó**.

## Cái này KHÔNG chứng minh

- Không chạy API, không dựng máy chủ. Đây là lập luận trên mã nguồn. Nó nói về
  **hình dạng của mã** — đúng cho tới khi mã đổi, và không ai được báo khi nó đổi.
- Không có phép kiểm nào cưỡng chế "thẻ duyệt `people` chỉ được đọc `allocations`
  cùng tập khoá". Hôm nay bốn chỗ đều đúng nguồn; đó là kỷ luật, không phải cổng.
  Một lần đổi `preview.split` thành `docChiaBill` ở `GoiYChia:107` là đủ mở lại,
  và bộ test sẽ không đỏ (`KetQuaChiaThu` từng bị revert về `labelFor` mà 999/999
  vẫn xanh — ghi chú `:1006-1010`).
- `list_members` có thể trả roster ⊋ người trên bill tới mức nào là chuyện dữ
  liệu, tôi không đo phân bố đó.
- Không xét các trường tiền khác ngoài `allocations`/`rounding_gainers`
  (nghĩa vụ, đợt thu, envelope khách) — câu hỏi giới hạn ở trường người-được-chia.
