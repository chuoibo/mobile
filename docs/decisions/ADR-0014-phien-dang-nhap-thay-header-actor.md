# ADR-0014 — Phiên đăng nhập thay header `X-Actor-ID` khi chạy production

- **Trạng thái:** 🟡 **ĐỀ XUẤT** 2026-09-02 — **Lead chấp nhận rồi Codex mới viết `api/` / `db/`**
- **Sửa:** 2026-09-03 — cấp phiên bằng lời mời đích danh, không đổi person-id; re-login xoay digest
- **DRI đề xuất:** Claude (lane `apps/mobile/`) · **Hiện thực server:** Codex · **Cổng ADR:** Lead
- **Review chính thức (ADR-0007):** Codex hoặc Lead trên GitHub PR — **không** phải Claude cùng lane với tác giả. Đầu vào cùng lane là comment, không phải `APPROVE` / `REQUEST_CHANGES` / `REJECT`.
- **Nguồn:** QA native 2026-09-02 · `app/api/deps.py` · `OutingInvite` · `GuestLink` · `ROLES` trong `permissions.py`
- **Chặn:** một người lạ gửi header giả và được đối xử như thành viên nhóm

> **Không viết bảng session, không đổi `get_actor`, không gắn OAuth trước khi ADR này đóng băng.** Hợp đồng sai ở đây không làm lệch allocator, nhưng làm rò dữ liệu nhóm khác.

Nhánh GitHub hiện tại (`claude/p0-w-rudi-session-adr`, PR #513) thiếu số Work ID `p0-w<N>`. **Không đổi tên remote** — gãy PR. Work ID do Lead đặt khi mở nhánh hiện thực.

## Bối cảnh

`get_actor` đọc `X-Actor-ID` / `X-Actor-Roles` / `X-Actor-Contexts` và tin chúng. Comment trong `deps.py` nói rõ: *gateway tin cậy phải ghi đè, đây không phải auth production.* Gateway đó không tồn tại. Client Expo gửi header thẳng. RuDi login trên PR #512 là skip có ghi nhãn «bản trải nghiệm».

`PUT /people/{id}` và route identity mint person-id từ số điện thoại: **không** cấp phiên. `derive_person_id` cố ý: cùng số + cùng key → cùng UUID («typing my number twice logs me back in») — đó là ổn định **id**, không phải Bearer.

Đây **không** phải ADR-0011 (nhận diện khuôn mặt). Google / Apple là Pha D: để **bỏ bước nhờ người mời**, không phải để mở đường đăng nhập lại đầu tiên. OTP SMS nhà cung cấp **cấm** trong PR hiện thực ADR này.

`accept_outing_invite` (`routes/outings.py`) đòi `get_actor`. `GuestLink` là capability trang khách, không đổi lấy phiên người (spec 8.6).

## Quyết định

### 1. Hai chế độ, một cờ — mặc định prod

Tên cờ do Codex chọn khi hiện thực. **Giá trị mặc định khi env vắng mặt là prod** (fail-closed). Dev/demo phải **bật rõ** (ví dụ `=dev`). Quên set env trên host production = prod, không phải header giả vẫn ăn.

Lúc khởi động API: **in một dòng log** ghi chế độ đang chạy (`prod` hay `dev`). Không log secret.

- *dev/demo:* giữ `X-Actor-ID` như hiện tại, để `tests/api` và `tests/postgres` còn chạy.
- *prod:* `get_actor` **không** tin `X-Actor-ID` / `X-Actor-Roles` / `X-Actor-Contexts` do client gửi. Thiếu phiên hợp lệ → **401**. Gửi header giả khi prod → **401**, không 200 với actor giả.

### 2. Phiên là hàng server; chỉ persist SHA-256 digest

Codex thêm persistence (bảng / event — schema thuộc Codex) cho: **digest SHA-256 của token**, `person_id`, hạn, thu hồi. **Cấm lưu token thô.** Chữ «token mờ» ở bản đề xuất trước **không** đủ: quy ước repo đã có ở `GuestLink` (`models.py`, docstring *only a SHA-256 token digest is persisted*) và `OutingInvite` (*never persists a bearer secret* / link chỉ digest). Cùng khuôn đó cho session token.

Token không phải UUID người; không nhét `person_id` vào chỗ client sửa rồi được tin.

### 3. Cấp phiên = đổi lời mời đích danh, không đổi person-id

Giữ mint person-id không auth. **Cấm** đổi person-id đã mint lấy Bearer. **Cấm** cấp phiên vì biết số.

Bootstrap prod (không đòi `X-Actor-ID`):

- Chỉ đổi lời mời `OutingInvite` có `source ∈ {group, friend}` và `invited_person_id IS NOT NULL`.
- Phiên gắn **đúng** `invited_person_id`. Caller **không** khai `person_id` — không đọc trường `person_id` nào trên body.
- `source=link` **không** đổi được phiên. Link chỉ đi cửa `POST /outing-invites/{token}/accept` cũ (đã có phiên, cap membership `INVITED`, người ACTIVE khác duyệt trước khi dữ liệu nhóm hiện — docstring `service.py` *Redeem a bearer link into a request capped at INVITED*).

`OutingInviteSource` là `group` | `friend` | `link`. Constraint `link_names_nobody` / `link_carries_digest` hôm nay là đẳng thức: `(source = 'link') = (token_digest IS NOT NULL)` và `= (invited_person_id IS NULL)`. Group/friend **chưa** được mang digest. Codex **nới** constraint để lời mời đích danh mang secret một lần (raw trao đúng một lần, chỉ persist digest). **Cấm** dùng `invite.id` làm secret: `invite_id` đã trả ra trong `OutingInviteAcceptResponse` — dữ liệu công khai.

Người mới vào đúng `register_person`: thành viên ACTIVE mint `person_id` từ số bạn đưa, đặt tên (*nobody signs up before a friend adds them to a dinner*), mời đích danh `friend`.

### 4. Mỗi cửa một loại token

| Cửa | Token | Việc |
|---|---|---|
| Bootstrap (không actor) | digest lời mời **đích danh** | cấp phiên = `invited_person_id` |
| `accept_outing_invite` | digest lời mời **link** | membership `INVITED`, không cấp phiên |

Không hai route giành một digest.

### 5. Re-login = xoay digest trên hàng sẵn có

Partial unique index `uq_outing_invites_person` (`outing_id`, `invited_person_id`) where `invited_person_id IS NOT NULL` **không** lọc `accepted_at` / `revoked_at`. `create_outing_invite` precheck `find_outing_invite_for_person`; comment: *the partial unique index is the real duplicate guarantee*. INSERT hàng đích danh thứ hai cho cùng người + outing → **409**. «Mời đích danh lại» không phải đường re-login.

**Chốt:** lần đầu (chưa có hàng) INSERT một lời mời đích danh kèm digest. Mất phiên (cài lại app, đổi máy): thành viên ACTIVE **xoay bí mật trên hàng đã có**, không INSERT hàng thứ hai. Tiền lệ: `GuestLink` *Rotatable bearer capability*. Unique ở đây cấm hàng mới → xoay **tại chỗ**.

Google/Apple (Pha D) bỏ bước nhờ người mời. Gõ số hai lần không cấp Bearer.

### 6. 409 neo vào digest, không neo `accepted_at`

Cùng một digest đổi lần hai → **409**. Xoay **cấp digest mới**; digest cũ **chết vĩnh viễn**.

**Cấm** hiện thực xoay bằng xoá `accepted_at`. Làm vậy thì `accept_outing_invite` chạy được hai lần trên cùng secret.

### 7. Roles và context_ids suy từ DB — từng role một nguồn

`ROLES` trong `app/domain/permissions.py` có **đúng 10** giá trị (không có `editor`). `MembershipRole` trên DB chỉ `member` | `admin`. Hôm nay hầu hết role sống nhờ `X-Actor-Roles`. Prod **không** fail-open: không copy role từ header/body; không «grant all roles».

| Role trong `ROLES` | Nguồn server-side bắt buộc | Có nguồn hôm nay? |
|---|---|---|
| `member` | hàng `memberships` trạng thái ACTIVE, `role=member` (hoặc tương đương) | Có |
| `group_admin` | `memberships.role == admin` — map tên DB `admin` → role domain `group_admin` | Có (cần map; literal `admin` không nằm trong `ROLES`) |
| `former_member` | `memberships.state == left` | Có |
| `batch_owner` | `extra_roles` **tại action**, suy từ resource (pattern `service.py` lúc tạo batch: *resource-derived, never read from a request body*). **Không** sticky trên Bearer | Có, một call site |
| `guest` | digest `GuestLink` → `Actor(roles={guest})` như `_guest_actor`. **Không** phải phiên người | Có |
| `advancer` | sự kiện sổ / nghĩa vụ tại action + predicate `requires` trong `_TABLE` | **Chưa** trên phiên; không copy header |
| `recipient` | như trên | **Chưa** trên phiên |
| `sender` | như trên | **Chưa** trên phiên |
| `creditor` | như trên | **Chưa** trên phiên |
| `platform_moderator` | bảng/grant riêng khi có. Chưa có thì prod **không** cấp role này | **Chưa có bảng** |

`context_ids` trên Actor prod: các context mà người phiên có membership (predicate tương đương `is_group_member` / hàng membership), **không** copy `X-Actor-Contexts`.

Role **chưa có nguồn trên phiên** (nêu tên): `advancer`, `recipient`, `sender`, `creditor`, `platform_moderator`. Với mỗi role đó Codex viết **một ca prod**: cấp đúng từ nguồn tại action, hoặc **403** nếu chưa có nguồn — không 200 với role đó từ header. `batch_owner` có nguồn resource: ca prod chứng minh lấy từ resource, không từ header, không gắn sẵn lên session.

**Ca âm bắt buộc:** phiên `member` gửi header hoặc body tự xưng `creditor` hoặc `platform_moderator` → Actor **không** mang role đó.

Ca `tests/api` chế độ dev gửi `X-Actor-Roles` **không** được tính là chứng minh prod.

### 8. Provenance membership (bắt buộc ghi đúng, không nới luật duyệt)

`ensure_invited_membership` hôm nay hardcode `origin=MembershipOrigin.LINK`. Bootstrap đi lời mời đích danh mà ghi `LINK` là sai đúng field `MembershipOrigin` sinh ra để phân biệt tin cậy (docstring: named = thành viên chọn người; link = chỉ sở hữu bearer).

Membership **tạo mới** qua bootstrap đích danh ghi `NAMED`. Hệ quả đã có sẵn, **không** nới: `accept_context_membership` — origin named thì chính invitee đồng ý (`is_invitee`); origin link thì thành viên ACTIVE **khác** duyệt. Một thành viên đủ để thêm người theo lời mời đích danh. ADR này **không** đòi thành viên thứ hai duyệt cho named.

`ensure_invited_membership` khi đã có hàng `left_at IS NULL` trả **nguyên trạng**: người ACTIVE nhận phiên mới **không** tụt `INVITED`, không phải xin duyệt lại.

### 9. Client (Claude, sau khi route sống)

`Authorization: Bearer …`, token trong SecureStore, không ghi person-id vào header. RuDi 21 màn tiếp tục bản trải nghiệm khi chưa có token — copy nói vậy. Không Zustand/MMKV làm nguồn sự thật phiên.

### 10. Không đụng allocator, không đụng sổ

Auth không được thành đường ghi tiền thứ hai.

## Tiêu chí ra (Pha B xong)

| Phép đo | Kết quả bắt buộc |
|---|---|
| Cờ **mặc định** (không set env) trên binary giống production | hành vi **prod**, không phải header giả 200 |
| Cờ prod + request không token, có `X-Actor-ID` hợp lệ hình thức | 401 |
| Cờ prod + token đã thu hồi hoặc hết hạn | 401 |
| Cờ prod + token còn hạn | actor đúng `person_id` của phiên; roles/context từ nguồn mục 7, không từ header |
| Cờ dev (bật rõ) | hành vi cũ; `tests/api` + `tests/postgres` hiện tại vẫn chạy (Codex thêm case prod, không phá case dev) |
| Log khởi động | một dòng ghi `prod` hoặc `dev` |
| Bootstrap với `source=link` | không cấp phiên |
| Bootstrap với lời mời đích danh còn hạn | phiên đúng `invited_person_id`; body không có trường `person_id` nào được đọc |
| Cùng một digest đổi lần hai | 409; invite **chưa** tiêu thì `accept_outing_invite` cũ vẫn chạy (cửa link) |
| Xoay bí mật trên hàng đích danh đã có | digest cũ chết vĩnh viễn; digest mới cấp phiên đúng `invited_person_id` |
| Người đã ACTIVE nhận phiên mới | vẫn ACTIVE, không tụt `INVITED`, không phải xin duyệt lại |
| Membership **tạo** qua bootstrap đích danh | `origin=NAMED` (không hardcode `LINK`) |
| Biết số, không có lời mời đích danh còn hạn / digest còn sống | không cấp phiên |
| Mỗi role chưa có nguồn trên phiên (`advancer`, `recipient`, `sender`, `creditor`, `platform_moderator`) | một ca **prod**: đúng nguồn tại action hoặc 403 |
| `batch_owner` | một ca **prod**: `extra_roles` từ resource, không từ header, không sticky trên Bearer |
| Ca âm: phiên `member` tự xưng `creditor` / `platform_moderator` | không được role đó |
| Golden allocator | không đổi |

## Những phương án bị bác

**Tin `X-Actor-ID` mãi, «gateway sẽ tới».** Không có gateway.

**Đổi person-id đã mint lấy token.** Cùng lỗ impersonation với header giả: identity là oracle; `derive_person_id` định sẵn.

**Cấp phiên vì biết số / OTP SMS bắt buộc ở Pha B.** Không nhà cung cấp, không creds native. Google/Apple là Pha D.

**Bootstrap từ `source=link`.** Link không ràng người (`invited_person_id IS NULL`); caller sẽ tự khai `person_id`.

**Đọc `person_id` từ body lúc bootstrap.**

**INSERT hàng đích danh thứ hai** cho cùng `(outing_id, invited_person_id)` để re-login. Unique index giết. Xoay digest trên hàng sẵn có.

**Xoay bằng xoá `accepted_at`.** 409 phải neo digest.

**Dùng `invite.id` làm secret.** Đã public trên accept response.

**OAuth Google/Apple trong cùng PR với bảng session.** Pha D.

**Zustand/MMKV làm nguồn sự thật phiên.**

**Claude sửa `deps.py` «cho lẹ».** Ranh giới 2026-08-27: Codex giữ `api/` và `db/`.

**Rule «đã ACTIVE thì không bootstrap».** Khoá re-login tới hết Pha D. Người ACTIVE mất máy phải xoay digest, không bị từ chối vì đang ACTIVE.

**Mặc định cờ = dev.** Deploy quên env thì fail-open im lặng — đúng sự cố ADR này sinh ra để chặn.

**Fail-open role chưa có nguồn** («grant all», copy `X-Actor-Roles` khi prod).

## Hệ quả

- Lead chấp nhận → Codex mở nhánh hiện thực (Work ID Lead đặt), PR riêng. Verdict ADR-0007 sống trên GitHub PR; **không** tự review. Claude không đụng `api/` / `db/`.
- Claude không gắn SecureStore / Bearer trước khi route cấp token có trên nhánh Codex đã merge hoặc đang review với contract đóng băng.
- Pha C (API public TLS + EAS preview) phụ thuộc Pha B **đã có đổi-invite-đích-danh**, danh sách mời đóng. Không đẩy C xuống sau OAuth. Public + header giả vẫn ăn thì mở lỗ ra internet.
- ADR-0006 không đổi: test xanh không phải bằng chứng hành vi người thật.

## Đường lùi

Tắt chế độ prod → `get_actor` trở lại header. Bảng session **để nguyên**, không xoá lịch sử.

**Ai được tắt:** chỉ **Lead**, trên host đang phục vụ người thật (hoặc staging được Lead chỉ định). Không phải «ai SSH / sửa `.env` trên máy mình cũng được».

**Ghi lại ở đâu:** mỗi lần tắt (và mỗi lần bật lại prod trên host đó) = một PR hoặc issue Lead đóng, ghi **ngày**, **host**, **lý do**. Không tắt bằng biến env không có dấu vết review.
