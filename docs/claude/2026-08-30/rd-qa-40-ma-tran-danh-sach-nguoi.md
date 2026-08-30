# rd-qa-40 · Ma trận: mọi đường ghi nhận định danh người từ phía người gọi

- commit đo: `dbc1e35` (main lúc nhận việc, không đổi trong suốt lượt đo)
- nhánh: `qa3/rd-qa-40-quet-khuon-danh-sach-nguoi`
- protocol_version: v1
- verdict: **không có** — đây là báo cáo QA, không phải review một PR
- kỹ năng đã dùng: `e2e-testing`, `bug-reproduction`

## Câu hỏi

Khuôn đã nổ hai lần: chỗ nào nhận định danh người từ thân request rồi ghi mà
chỉ kiểm **người gọi**, không kiểm **những người bị gọi tên**.

- #235 `confirm_expense` — `participants` lấy thẳng từ thân request.
- #247 `PUT /bills/{id}/assignments` — cùng lỗ, đúng đường bản demo đi qua.

Cả hai lần đều tìm ra bằng cách grep chữ `participants`. Nên lượt này **không
grep**. Danh sách suy ra từ `app/api/schemas.py`: mọi trường khai `UUID` hoặc
`list[UUID]` chỉ một người, cộng mọi path param `person_id`, rồi khớp ngược về
method trong `service.py` ghi nó.

## Bảng

Ba loại ô, và đọc code không phân biệt được — nên mỗi ô có màu đột biến kèm theo.

| # | Đường ghi | Trường | Có kiểm người **bị gọi tên** không | Cổng nào giữ | Hậu quả nếu không |
|---|---|---|---|---|---|
| 1 | `POST /expenses/{id}/confirm` | `proposal.participants` | **Có** | `_require_participants_are_members` (#235) · đột biến **ĐỎ** | — |
| 2 | `POST /expenses/{id}/confirm` | `proposal.paid_by_id` | **KHÔNG** | **không có cổng nào** | tiền — xem A |
| 3 | `POST /expenses/{id}/confirm` | `proposal.recorded_by_id` | **KHÔNG** | **không có cổng nào** | riêng tư — xem B |
| 4 | `POST /expenses` · `confirm` | `items[].shared_by` | Không, **ở tầng này** | `allocator._validate_shape` → `UNKNOWN_PARTICIPANT` · đột biến **ĐỎ** | ô trống **tương đương**, không phải lỗ |
| 5 | `POST /expenses/{id}/confirm` | `expected_allocations` (khoá dict) | Không, **ở tầng này** | so lại với bản allocator vừa tính → 409 `proposal_changed` · đột biến **ĐỎ** | ô trống **tương đương** |
| 6 | `POST /bills` | `items[].suggested_participant_ids` | **KHÔNG** | **không có cổng nào** | chết đường demo — xem C |
| 7 | `PUT /bills/{id}/assignments` | `assignments[].participant_ids` | **Có** | `_require_participants_are_members` (#247) · đột biến **ĐỎ** | — |
| 8 | `POST /bills/{id}/split` | `paid_by_id` → `advancer_id` | Không | đường **đọc**, không ghi; kết quả chỉ vào `confirm_expense`, nơi ô 2 mới là chỗ hở | không phải đường ghi |
| 9 | `POST /bank-recipients` | `recipient_id` | **Có** (chính chủ, không phải thành viên) | `is_own_account` · đột biến **ĐỎ** | — |
| 10 | `PUT /people/{id}/bank-recipient` | `person_id` (path) | **Có** | cùng vị ngữ, chủ thể nằm trên đường dẫn nên không nới rộng được | — |
| 11 | `POST /contexts/{id}/members` | `person_id` | **Có** (đã đăng ký — đúng câu hỏi cho một lời mời) | `_require_registered_person` · đột biến **ĐỎ** | — |
| 12 | `PUT /contexts/{id}/members/{person_id}/role` | `person_id` (path) | Không, **ở tầng này** | `WHERE state=ACTIVE AND left_at IS NULL` trong `set_membership_role` · đột biến **ĐỎ** | ô trống **tương đương** |
| 13 | `DELETE /contexts/{id}/members/{person_id}` | `person_id` (path) | **Có** | vị ngữ `is_self` | — |
| 14 | `POST /friends/requests` | `addressee_id` | **Có** (tồn tại — kết bạn vốn xuyên nhóm) | `get_person` → 404 · đột biến **ĐỎ** | — |
| 15 | `POST /outings/{id}/invites` | `person_id` | **KHÔNG** | chỉ khoá ngoại, và nó ném 500 | lỗ **đang ngủ** — xem D |
| 16 | `POST /batches` · `publish` | `expense_version_ids` | không có định danh người trong thân | mọi người đều suy từ sổ (`load_batch_inputs`) | — |
| 17 | `POST /obligations/{id}/confirm-receipt` | — | **Có** | `is_recipient_of_this_obligation`, đọc từ nghĩa vụ đã lưu | — |

Ô 4, 5, 12 là **ô trống vì tầng khác đỡ**, không phải lỗ. Chúng có màu đột biến
riêng chính vì #129 suýt ghi nhầm một đột biến tương đương thành lỗ: mỗi ô đó
được chứng minh bằng cách xoá check **ở tầng thật sự giữ nó** và xem thư mục
test đỏ.

## Ba lỗ, kèm hậu quả đo được

### A. `paid_by_id` — cả đợt thu chuyển hướng về người ngoài nhóm

`paid_by_id` trở thành `advancer_id` cho allocator, được lưu là
`ExpenseVersion.paid_by_id`, rồi `create_batch` đưa nó vào
`obligations_from_allocations` làm **`recipient_id` của MỌI nghĩa vụ** sinh ra
từ khoản chi đó.

Đo trên PostgreSQL thật, `dbc1e35` sạch. Nhóm hai người (Nam, Bình), bữa ăn
80.000 ₫, `paid_by_id` trỏ tới một người **ở nhóm khác** đã tự đăng ký tài khoản
ngân hàng của chính họ (việc hoàn toàn hợp lệ, và là thứ làm đợt thu đóng băng
được thay vì dừng ở `recipient_setup_incomplete`):

```
confirm  -> 201
batch    -> frozen
obligation sender=<Nam>  recipient=<người ngoài> amount=40000
obligation sender=<Bình> recipient=<người ngoài> amount=40000
```

Ba luật tiền **xanh suốt**: 40.000 + 40.000 = 80.000 đúng bằng hoá đơn, số
nguyên đồng, sổ replay được. Số học không nhìn thấy được chuyện này — đúng chữ
ký của #235.

Người thật sự trả tiền xuất hiện ở cột **sender**: Nam bỏ ra 80.000 ₫ rồi bị ghi
là còn nợ 40.000 ₫, và không ai nợ Nam.

`acknowledge_as_advancer` trông như đã che chỗ này nhưng không: mặc định nó là
`False`, và vị ngữ nó chứng minh (`actor.id == paid_by_id`) chỉ được đánh giá
khi cờ được bật — tức là check do chính người muốn né nó bật lên.

Chặn ở đâu: `publish` đòi mọi khoản chi trong đợt được advancer xác nhận, nên
phong bì và VietQR **không** tới được nếu kẻ đặt tên không điều khiển được phiên
của người ngoài đó. Nói rõ ra để không thổi phồng. Nhưng đợt thu đã **đóng
băng**: nghĩa vụ đã nằm trên bảng thu, đã vào màn tài chính cá nhân của từng
người, và các phiên bản khoản chi đã bị tiêu.

Phân loại blocker: **loại 2 (sai tiền)**.

### B. `recorded_by_id` — tên người ngoài in lên trang khách

`ExpenseVersion.recorded_by_id` được `guest_envelope` đọc lại và join với
`people` để điền `recorded_by_display_name`.

Đo trên PostgreSQL thật, `dbc1e35` sạch:

```
PROBE-LIVE guest recorded_by_display_name = 'TEN BI MAT CUA NHOM KHAC'
```

Trang khách là **capability dạng bearer** nằm trong tay người đang bị hỏi tiền —
thường là người ngoài nhóm, có khi ngoài cả sản phẩm. Nên đây là tên của một
người bất kỳ trong hệ thống, do người gọi chọn, hiện ra cho một người đọc chưa
bao giờ ở trong nhóm đó.

Phân loại blocker: **loại 3 (quyền riêng tư)**.

### C. `suggested_participant_ids` — cùng lỗ #247, trên route anh em

#247 gác `PUT /bills/{id}/assignments`. **Không ai gác `POST /bills`**, dù nó
nhận đúng một danh sách người và ghi thẳng vào `bill_item_shares` với
`source="ai_suggested"`.

Đo trên PostgreSQL thật, `dbc1e35` sạch:

```
bill written with shares: [('i1', ['<người ngoài>']), ('i2', ['<Nam>'])]
split BEFORE confirm:          422 UNKNOWN_PARTICIPANT
split AFTER confirming i2:     422 UNKNOWN_PARTICIPANT
```

`split_bill` dựng danh sách participant từ **roster đang active** rồi bắt
allocator tôn trọng share đã lưu, nên một share mang tên người ngoài là
`UNKNOWN_PARTICIPANT` và hoá đơn **không chia được nữa**.

Xác nhận gán món không gỡ được: `confirm_bill_assignments` chỉ xoá share của
đúng những `item_key` mà request nêu tên, nên món nào không được gán lại thì giữ
nguyên share bẩn. Màn hình không có lý do gì để gán lại một món trông đã gán
xong. Từ phía nhóm, hoá đơn chỉ đơn giản là kẹt: **chụp bill → gán món → chia**,
đúng đường bản demo đi, chết và không có lối ra bên trong sản phẩm.

Phân loại blocker: **loại 1 (vi phạm spec/cổng)** — và nó nằm trên hero path.

### D. `OutingInviteCreateRequest.person_id` — lỗ đang ngủ

`source` khai xuất xứ (`group` / `friend` / `link`). `source="group"` nghĩa là
"người này ở trong nhóm". Service đọc trường đó, ghi `invited_person_id`, và
**không bao giờ hỏi lại**. Đo được: mời một người thuộc nhóm khác với
`source="group"` → chấp nhận, ghi hàng.

Chưa route nào đọc một lời mời đích danh thành quyền, nên hôm nay đây là lỗ
**đang ngủ** chứ không phải lỗ đang chảy. Ghi vào bảng để không phải phát hiện
lại vào đúng ngày một màn hình bắt đầu đọc `outing_invites`.

Ca bên cạnh — `person_id` là UUID không ứng với ai — do
`fk_outing_invites_person` chặn, nhưng chặn bằng `IntegrityError`, nên người gọi
nhận **HTTP 500** thay vì một lời từ chối họ xử lý được.

Phân loại blocker: **suggestion** cho phần membership (chưa có hậu quả sống),
**loại 1 nhẹ** cho cái 500.

## Bằng chứng

Cây sạch, `dbc1e35` + nhánh này. Lệnh và số thật:

```
python3 -m pytest services/api/tests tests -q
  -> 1557 passed, 339 skipped, 4736 subtests passed        (main dbc1e35, trước khi thêm gì)

MOBILE_TEST_DATABASE_URL=…/rdqa40 MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest tests/postgres -q
  -> 301 passed, 0 skipped                                  (tầng live thật sự chạy)

MOBILE_TEST_DATABASE_URL=…/rdqa40 MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest tests/qa/rd-qa-40 -q
  -> 12 passed, 6 xfailed
```

`339 skipped` ở lệnh đầu là tầng postgres tự bỏ qua khi thiếu URL — đó là lý do
lệnh thứ hai tồn tại, và nó chạy với `MOBILE_REQUIRE_POSTGRES_TESTS=1` để một
lượt bỏ qua thành một lượt đỏ.

### Ba lỗ: đỏ-trước / xanh-sau

Sáu ca (ba lỗ × hai tầng) mang `xfail(strict=True)`. Chúng không có hàng trong
`mutants.sh` vì **không có check nào để xoá** — đột biến sẽ đo một chỗ trống.
Thay vào đó, phép kiểm là chiều ngược lại: dán một guard ứng viên vào
`service.py` (mở rộng `_require_participants_are_members` sang `paid_by_id` và
`recorded_by_id`, và gọi nó trong `create_bill`) rồi chạy lại.

```
6 failed, 10 passed
  [XPASS(strict)] test_paid_by_id_from_the_body_must_be_a_member
  [XPASS(strict)] test_recorded_by_id_from_the_body_must_be_a_member
  [XPASS(strict)] test_suggested_participant_ids_must_be_members
  [XPASS(strict)] test_live_paid_by_outsider_must_not_reach_the_ledger
  [XPASS(strict)] test_live_recorded_by_outsider_must_not_reach_the_guest_page
  [XPASS(strict)] test_live_bill_suggestion_of_a_non_member_is_refused
```

Cả sáu lật. Đó là điều phân biệt "cổng đo đúng tính chất" với "ca đỏ vì lý do
khác" — cái bẫy đã ghi trong `docs/`: đỏ nhầm lý do đọc y hệt đã gác.

Cổng toàn repo với guard ứng viên đó: **1564 passed**, không ca cũ nào đỏ. Tức
là hướng sửa này không đụng gì khác — thông tin cho lane sẽ vá, không phải bản
vá (`api/` thuộc Codex). Đã hoàn nguyên `service.py` ngay sau khi đo; cây sạch.

### `mutants.sh` — 11 hàng, tất cả đúng dự đoán

```
# baseline -- unmutated tree
    rc=0  12 passed, 6 xfailed

[GATED]     confirm_expense: participants guard removed (#235)          ĐỎ  OK
[GATED]     confirm_bill_assignments: guard removed (#247)              ĐỎ  OK
[GATED]     set_bank_recipient: is_own_account dropped                  ĐỎ  OK
[GATED]     invite_context_member: registration check removed           ĐỎ  OK
[GATED]     send_friend_request: addressee existence check removed      ĐỎ  OK
[ELSEWHERE] allocator: shared_by subset-of-participants check removed   ĐỎ  OK
[ELSEWHERE] confirm_expense: recomputed-proposal comparison removed     ĐỎ  OK
[ELSEWHERE] repository: set_membership_role stops filtering on ACTIVE   ĐỎ  OK
[UNCHANGED] confirm_expense: participants sorted before the check      XANH OK
[UNCHANGED] participant guard: refusal wording changed, code kept      XANH OK
[UNCHANGED] participant guard: roster built by loop instead of set-comp XANH OK

ALL ROWS AS EXPECTED
```

Ba hàng `UNCHANGED` là phần làm cho tám hàng đỏ có nghĩa. Một bảng toàn đỏ không
phân biệt được "cổng chạy" với "test bị hàn vào một chi tiết ngẫu nhiên" — thứ
tự client gửi, hay câu chữ của thông báo từ chối.

Một hàng đã tự bắt lỗi của chính nó: hàng `set_membership_role` **XANH** ở lượt
chạy đầu. Ca live lúc đó chỉ thử "người không có hàng membership nào", mà người
như thế bị mệnh đề `person_id` loại ra bất kể `WHERE` còn lại nói gì. Bản test
đó sẽ ghi "tầng dưới đỡ" mà không chứng minh được tầng nào đỡ. Thêm hai standing
`INVITED` và `LEFT` thì hàng đó mới đỏ — `INVITED` ghim `state`, `LEFT` ghim
`left_at`.

## Ô chưa quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Không agent nào quét được mã
  QR; `test_vietqr.py` chỉ kiểm chuỗi EMVCo và CRC. Câu này còn nguyên cho tới
  khi leader cầm điện thoại thật.
- **Đường ghi qua repository trực tiếp, ngoài `service.py`.** Việc này quét
  `service.py`. `app/db/repository.py` và các route tự gọi repository chưa được
  soi cùng một khuôn.
- **Đường vào từ client.** Bảng này nói server nhận gì. Màn nào của
  `apps/mobile/` đang gửi `paid_by_id` từ đâu thì chưa đo — nghĩa là chưa biết
  ba lỗ trên đang bị **chạm vào** hay mới chỉ đang **mở**.
- **Trang khách theo ma trận trạng thái × chủ đề × khung nhìn.** Không nằm trong
  phạm vi việc này; ô B chỉ chạm đúng một trường trên trang đó.
- **`X-Actor-*`.** Vẫn là chỗ tạm của gateway tin cậy, đã ghi trong `CLAUDE.md`.
  Mọi kết luận ở trên **không** dựa vào việc giả header: các đường đo được đều
  đi bằng một thành viên hợp lệ của nhóm.

## Việc còn nợ, cho lane khác

Ba lỗ A/B/C nằm trong `services/api/app/api/service.py` — **Codex sở hữu**. Lane
này không sửa. `xfail(strict=True)` là bản giao: gỡ marker là nửa sau của bản
vá, và một bản vá quên gỡ sẽ tự làm đỏ cổng và tự nói tên mình.
