# ADR-0014 — Phiên đăng nhập thay header `X-Actor-ID` khi chạy production

- **Trạng thái:** 🟢 **ĐÃ CHẤP NHẬN VÀ ĐÃ HIỆN THỰC** 2026-09-03 — Lead chấp nhận, và cho phép Claude vượt ranh giới sở hữu sang `api/` + `db/` cho lượt này thay vì chờ Codex.
- **Hiện thực:** PR #514, merge vào `main` tại `6aad3cf`. Đọc `docs/claude/2026-09-03/pha-b-hien-thuc.md` trước khi đụng lại `api/` / `db/`: ở đó có bảng đột biến, các chỗ hợp đồng đổi, và **một đột biến còn sống**.
- **Sửa:** 2026-09-02 cấp phiên bằng lời mời đích danh, không đổi person-id; re-login xoay digest. 2026-09-03 ghi lại bốn chỗ hợp đồng đổi khi hiện thực (mục "Đã hiện thực" ở cuối).
- **DRI:** Claude (lane `apps/mobile/`) · **Hiện thực server:** Claude, được Lead uỷ quyền · **Cổng ADR:** Lead
- **Review chính thức (ADR-0007):** Lead uỷ quyền merge #514 cho Claude **với điều kiện có e2e thật ở chế độ production**, không phải smoke test. Điều kiện đó được đáp bằng `scripts/e2e_slice.sh` chạy uvicorn ở `prod` với phiên thật (9/9, chạy trong CI). Ghi lại vì đây là ngoại lệ có điều kiện, không phải luật mới.
- **Nguồn:** QA native 2026-09-02 · `app/api/deps.py` · `OutingInvite` · `GuestLink` · `ROLES` trong `permissions.py`
- **Chặn:** một người lạ gửi header giả và được đối xử như thành viên nhóm

> **Không viết bảng session, không đổi `get_actor`, không gắn OAuth trước khi ADR này đóng băng.** Hợp đồng sai ở đây không làm lệch allocator, nhưng làm rò dữ liệu nhóm khác.

Hai nhánh đều thiếu số Work ID `p0-w<N>` (`claude/p0-w-rudi-session-adr` → #513, `claude/p0-w-rudi-session-impl` → #514). Không đổi tên vì đổi là gãy PR; ghi lại để lần sau đặt đúng ngay từ đầu.

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
| `member` | cấp cho **mọi phiên hợp lệ**, kể cả người chưa có membership nào | Đã dựng |
| `former_member` | `memberships.state == left` | Đã dựng |
| `advancer` · `recipient` · `sender` · `creditor` | cấp cho mọi phiên hợp lệ, vì **mọi** action cần chúng đều kèm predicate chứng minh từ resource | Đã dựng |
| `group_admin` | **`extra_roles` tại action**, suy từ `memberships.role` của **đúng nhóm đang bị tác động** (`ApiService._group_admin_role`). **Không** cấp trên phiên | Đã dựng, hai call site |
| `batch_owner` | `extra_roles` tại action, suy từ resource. **Không** sticky trên Bearer | Đã dựng, hai call site |
| `guest` | digest `GuestLink` → `Actor(roles={guest})` như `_guest_actor`. **Không** phải phiên người | Đã có sẵn |
| `platform_moderator` | bảng/grant riêng khi có. Chưa có thì prod **không** cấp | **Chưa có bảng**, và không route nào gọi ba action của nó |

`context_ids` trên Actor prod: các context mà người phiên có membership (predicate tương đương `is_group_member` / hàng membership), **không** copy `X-Actor-Contexts`.

**Vì sao bốn role `advancer` / `recipient` / `sender` / `creditor` được cấp thẳng trên phiên** — quyết định bằng cách đọc `_TABLE`, không bằng khẩu vị: cả năm mục cần chúng đều có predicate server chứng minh (`is_named_advancer`, `is_recipient_of_this_obligation`, `is_creditor_of_this_obligation`, `is_own_capability`, `envelope_contains_own_account`), nên mang role chỉ đáng giá bằng "quyền được hỏi câu hỏi thật". Không cấp thì 403 mọi lần xác nhận đã nhận tiền. `member` cấp cả khi chưa có membership vì `accept_context_membership` đòi đúng role đó cộng `is_invitee` — không cấp thì người vừa bootstrap không tự đồng ý nổi lời mời của chính mình.

**Cổng cấu trúc thay cho việc nhớ:** `services/api/tests/api/test_roles_have_a_server_side_source.py` đọc `_TABLE` cùng `service.py` và từ chối call site nào phụ thuộc một role phiên không cấp mà cũng không tự suy; action chưa có route phải khai trong `UNREACHABLE` kèm lý do, và một action mọc route sau này không được nấp ở đó.

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

> **Trạng thái 2026-09-03: đã đạt hết.** Ca tương ứng nằm ở `tests/api/test_auth_mode.py`, `tests/api/test_prod_session_auth.py`, `tests/postgres/test_session_bootstrap_postgres.py` (13 ca, HTTP thật trên PostgreSQL thật) và `tests/postgres/test_genesis_session_postgres.py`. Hai hàng đọc khác bản viết ban đầu — xem mục "Bốn chỗ hợp đồng đổi" ở cuối file.

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

- ~~Lead chấp nhận → Codex mở nhánh hiện thực~~ — Lead uỷ quyền cho Claude làm cả server lẫn client trong một PR (#514), có điều kiện e2e prod. Ranh giới sở hữu 2026-08-27 **không đổi**: đây là một ngoại lệ được ghi, không phải luật mới.
- ~~Claude không gắn SecureStore / Bearer trước khi route cấp token đã merge~~ — cùng PR, nên contract không kịp trôi giữa hai bên.
- Pha C (API public TLS + EAS preview) phụ thuộc Pha B **đã có đổi-invite-đích-danh**, danh sách mời đóng. Không đẩy C xuống sau OAuth. Public + header giả vẫn ăn thì mở lỗ ra internet.
- ADR-0006 không đổi: test xanh không phải bằng chứng hành vi người thật.

## Đường lùi

Tắt chế độ prod → `get_actor` trở lại header. Bảng session **để nguyên**, không xoá lịch sử.

**Ai được tắt:** chỉ **Lead**, trên host đang phục vụ người thật (hoặc staging được Lead chỉ định). Không phải «ai SSH / sửa `.env` trên máy mình cũng được».

**Ghi lại ở đâu:** mỗi lần tắt (và mỗi lần bật lại prod trên host đó) = một PR hoặc issue Lead đóng, ghi **ngày**, **host**, **lý do**. Không tắt bằng biến env không có dấu vết review.

---

## Đã hiện thực (2026-09-03, PR #514 → `main` `6aad3cf`)

### Mục 11 — Genesis: phiên đầu tiên trên một host sạch

Thiếu ở bản đề xuất, và nếu thiếu thật thì sản phẩm không vào được. Vòng lặp tự đóng: phiên đến từ lời mời, lời mời do người **có phiên** phát, host sạch không ai có phiên. Mọi cửa HTTP đóng đúng, và không ai đăng nhập được lần đầu.

`scripts/genesis_session.py` là cửa duy nhất ngoài HTTP: tạo người + nhóm + membership ACTIVE `admin`, mint một phiên, in token **đúng một lần**. Uỷ quyền của nó là quyền truy cập database — mạnh sẵn rồi, nên không mở thêm bề mặt nào so với `psql`. Nó **không** tắt chế độ prod: host cần phiên thì được cấp phiên, không được cấp một cửa sổ tin header.

```bash
python3 scripts/genesis_session.py --display-name 'Tên' --group 'Tên nhóm'   # --json cho harness
```

### Bốn chỗ hợp đồng đổi so với bản đã duyệt

1. **Bootstrap lần hai trả 404, không 409.** ADR viết 409. 409 nói cho kẻ đang thử token trộm biết token đó *từng* thật; 404 không nói gì. Hàng «409» ở bảng tiêu chí vẫn đúng cho **cửa link** (`accept_outing_invite` giữ nguyên `invite_already_accepted`).
2. **`SessionResponse` có thêm `membership_state`.** Không có nó thì màn hình phải đoán giữa «đã đăng nhập, còn chờ duyệt» và «đã đăng nhập, đã ở trong nhóm», và sẽ nói sai với một nửa người đọc.
3. **Genesis là script chạm DB, không phải route** (mục 11 trên).
4. **`group_admin` không cấp trên phiên.** Bản đầu cấp nó khi người đó là admin của **bất kỳ** nhóm nào — và `invite_context_member` đòi `group_admin` + `is_group_member`, **không** đòi `is_group_admin`, nên role trên phiên là toàn bộ phép kiểm: admin nhóm A thêm được người vào nhóm B nơi họ chỉ là thành viên. Giờ suy theo đúng nhóm đang bị tác động. Bảng ở mục 7 đã sửa theo.

### Lỗ mà chỉ e2e chế độ prod mới thấy

`publish_batch` chứng minh `owns_batch` từ resource nhưng **để role `batch_owner` tới từ `X-Actor-Roles`**. Ở prod không ai khai role, nên người **sở hữu** đợt thu bị 403 chính đợt thu của mình — đường hero chết. 2915 ca unit đều xanh, vì tất cả đều gửi header. Chỉ `scripts/e2e_slice.sh` chạy ở `prod` mới thấy.

Rút ra, và đã dựng thành cổng: một bộ test mà **mọi** ca đều gửi header thì không nói được gì về chế độ không đọc header. Đó là lý do `e2e_slice.sh` giờ dựng uvicorn ở `prod` và mint phiên thật, và lý do có `test_roles_have_a_server_side_source.py`.

### Bằng chứng lúc merge

2915 ca python · `postgres_tier.sh` ĐẠT cả `tests/postgres` lẫn `tests/qa` · 1048 ca mobile · **`e2e_slice.sh` 9/9 trên uvicorn chế độ prod với phiên thật** · ba workflow CI xanh trên `main`.

**Vẫn không chứng minh:** chưa ai chạy trên máy thật, chưa có build EAS, e2e chạy `fetch` của node nên không có CORS thật, và một đột biến còn sống (bỏ dòng chặn lời mời link ở tầng service vẫn xanh vì repository chặn cùng luật — chi tiết ở `docs/claude/2026-09-03/pha-b-hien-thuc.md`).

