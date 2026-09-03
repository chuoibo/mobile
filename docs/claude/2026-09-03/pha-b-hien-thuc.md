# Pha B — hiện thực: phiên đăng nhập thay `X-Actor-ID`

- **Ngày:** 2026-09-03
- **Nhánh:** `claude/p0-w-rudi-session-impl` (cắt từ `origin/main` `f63628d`)
- **Hợp đồng:** ADR-0014 (PR #513, docs, vẫn ĐỀ XUẤT)
- **Ranh giới sở hữu:** Lead cho phép vượt sang `api/` + `db/` trong lượt này. Codex đọc phần dưới trước khi đụng lại hai thư mục đó.

## Cái gì đổi

**Máy chủ**

| File | Việc |
|---|---|
| `app/api/auth_mode.py` | Cờ `MOBILE_AUTH_MODE`. **Vắng mặt = `prod`.** Giá trị lạ thì ném lúc khởi động, không đoán. |
| `app/db/models.py` | Bảng `account_sessions` (chỉ digest SHA-256, `person_id`, hạn, thu hồi, `issued_from_invite_id`). Nới `link_carries_digest` từ đẳng thức thành kéo theo. |
| `migrations/…c9f28a4d1b73` | Tạo bảng + nới constraint. `downgrade()` **từ chối chạy** nếu còn lời mời đích danh mang digest, thay vì xoá bí mật đang sống. |
| `app/api/deps.py` | `get_actor` đọc chế độ từ `app.state`; `prod` → Bearer, thiếu/hỏng → 401; `X-Actor-*` vẫn khai trong chữ ký nhưng bị bỏ qua. |
| `app/api/repository.py` | `create/get/revoke_account_session`, `actor_grants`, `consume_named_invite_secret`, `rotate_outing_invite_digest`; `ensure_invited_membership` nhận `origin`. |
| `app/api/routes/sessions.py` | `POST /sessions` (không đòi actor), `DELETE /sessions/current`. |
| `app/api/routes/outings.py` | `POST /outings/{id}/invites/{invite_id}/rotate`. |
| `app/api/cors.py` | `authorization` vào ALLOWED_HEADERS (cổng CORS bắt được chỗ này trước khi người thật bắt). |
| `scripts/genesis_session.py` | Phiên đầu tiên trên host sạch. |
| `docker-compose.yml` | Stack dev bật `MOBILE_AUTH_MODE: dev` **rõ ràng**. Host thật không có dòng đó nên chạy `prod`. |

**Client** — `apps/mobile/src/phien.ts` (mới), `api.ts` (giữ token, gắn `Authorization` trong `actorHeaders` nên cả bốn lời gọi multipart cũng có), `AppRoot.tsx` (khôi phục phiên lúc mở app), `NhanLoiMoi.tsx` (chưa có phiên → cửa `/sessions`; đã có phiên → cửa link cũ), `LenPlan/MoiVaoChuyen` (nút **Cấp lại mã**).

## Hợp đồng như đã dựng

Hai cửa, hai loại token, không giành nhau một digest:

| Cửa | Token | Kết quả |
|---|---|---|
| `POST /sessions` | digest lời mời **đích danh** (`group`/`friend`) | Bearer cho `invited_person_id`, membership `INVITED`, provenance `NAMED` |
| `POST /outing-invites/{token}/accept` | digest lời mời **link** | membership `INVITED`, **không** cấp phiên |

Thân request của `/sessions` chỉ có `invite_token`. Không có trường `person_id` nào được đọc — đó là toàn bộ lý do lỗ cũ đóng lại.

Tiêu tại chỗ: bootstrap **xoá** `token_digest` khỏi hàng. Mã cũ chết vĩnh viễn vì không còn cột nào để so. Xoay (`/rotate`) ghi digest mới lên chính hàng đó, **không** đụng `accepted_at`.

## Ba chỗ lệch với ADR như đã duyệt — đọc kỹ

1. **Bootstrap lần hai trả 404, không phải 409.** ADR viết 409. 409 nói cho kẻ đang thử token trộm biết token đó *từng* thật; 404 không nói gì. Hàng "409" trong bảng tiêu chí vẫn đúng cho **cửa link** (`accept_outing_invite` giữ nguyên 409 `invite_already_accepted`).
2. **`SessionResponse` có thêm `membership_state`.** Không có nó thì màn hình phải đoán giữa "đã đăng nhập, còn chờ duyệt" và "đã đăng nhập, bạn đã ở trong nhóm" — và sẽ nói sai với một nửa số người đọc.
3. **Genesis là script chạm DB, không phải route.** Đúng lỗ tôi nêu ở vòng review cuối: mọi cửa HTTP đóng đúng thì host sạch không ai vào được. Uỷ quyền của script là quyền truy cập DB, tức không mở thêm bề mặt nào so với `psql`.

## Roles: quyết định bằng cách đọc bảng quyền, không bằng khẩu vị

`ROLES` có 10 giá trị. Đếm trong `_TABLE` (74 mục):

- `advancer`, `recipient`, `sender`, `creditor` — **mọi** action cần chúng đều kèm predicate chứng minh từ resource (`is_named_advancer`, `is_recipient_of_this_obligation`, `is_creditor_of_this_obligation`, `is_own_capability`, `envelope_contains_own_account`). Nên cấp cho mọi phiên hợp lệ đáng giá đúng bằng "quyền được hỏi câu hỏi thật". Không cấp thì 403 mọi lần xác nhận đã nhận tiền.
- `member` — cấp cho mọi phiên, **kể cả khi chưa có membership nào**, vì `accept_context_membership` đòi đúng role đó cộng `is_invitee`. Không cấp thì người vừa bootstrap không tự đồng ý lời mời của chính mình được: khoá chết.
- `group_admin` — **không** cấp trên phiên. Suy theo từng nhóm đang bị tác động (`ApiService._group_admin_role`). Xem mục cập nhật cuối file: bản đầu cấp theo phiên và đó là một đường leo quyền thật.
- `former_member` — từ `state == left`.
- `platform_moderator` — **không cấp**. Ba action của nó không có predicate nào, và **không route nào gọi tới ba action đó**, nên từ chối tốn 0 tính năng.
- `guest` — không phải người; vẫn dựng ở `_guest_actor` từ digest `GuestLink`.

`context_ids` lấy từ membership ACTIVE. Ghi chú: `actor.context_ids` **chưa từng** được đọc để phân quyền (`service.py` nói thẳng ở hai chỗ), roles mới là phần thật.

## Đã đo được gì

- `tests/api/test_auth_mode.py` + `test_prod_session_auth.py`: 24 ca xanh. **Đột biến:** `trusts_actor_headers` luôn True → 9 đỏ; mặc định env vắng thành `dev` → 3 đỏ.
- `tests/postgres/test_session_bootstrap_postgres.py`: 12 ca trên PostgreSQL thật. **Đột biến:** không xoá digest khi tiêu → đỏ; provenance hardcode `LINK` → đỏ; cửa link nhận mã đích danh → đỏ.
- `tests/postgres/test_genesis_session_postgres.py`: 3 ca, chạy chính script trên schema cô lập.
- `apps/mobile/tests/phien.test.mjs`: 9 ca. **Đột biến:** bỏ header `Authorization` → 2 đỏ; nhét `person_id` vào thân `/sessions` → 1 đỏ.
- Cổng: `check_server_routes_called` (3 route mới đều có người gọi), `check_api_contract`, `check_cors_contract`, `check_actor_headers`, `check_alembic_heads`, `repo_guard tree` + `staged` — tất cả exit 0.

## Đã đo được là KHÔNG chứng minh gì

- **Một đột biến sống sót và tôi để nguyên:** bỏ dòng chặn lời mời `link` trong `bootstrap_session_from_invite` vẫn 12/12 xanh, vì `consume_named_invite_secret` chặn cùng luật ở tầng dưới. Bỏ **cả hai** thì đỏ, và lúc đó `acceptance_is_whole` của PostgreSQL mới là cái ném. Đó là ba lớp, nhưng bộ test chỉ đo được **cặp**, không đo được từng dòng. Đã ghi vào docstring của chính ca đó.
- **Chưa ai chạy trên máy thật.** Không có build EAS, không có thiết bị, không có SecureStore thật — đường native chỉ được suy từ kiểu và từ `expo export` web đi qua.
- **Cửa sổ đua lúc khởi động lạnh.** `khoiPhucPhien` là fire-and-forget: request bắn ra trong vài mili giây đầu có thể thiếu Bearer và ăn 401. Chặn render để đóng cửa sổ đó sẽ làm app **không render gì** dưới `renderToStaticMarkup`, tức mọi phép đo màn hình của repo này mù luôn. Đã chọn cửa sổ đua và ghi lại, không chọn cổng mù.
- **`check_actor_headers.py` giờ đo hợp đồng của chế độ `dev`.** Nó đọc OpenAPI tìm tham số `X-Actor-ID`, mà chữ ký vẫn khai header đó. Nó không biết `prod` tồn tại.
- **Không có TLS, không có domain public, không có quét VietQR bằng app ngân hàng.** Pha C và Pha E vẫn nguyên.
- Test xanh vẫn không phải bằng chứng hành vi người thật (ADR-0006).

## Vận hành

Host thật: **không đặt `MOBILE_AUTH_MODE`** là đúng — mặc định `prod`. Một dòng log lúc khởi động ghi chế độ đang chạy; đọc nó trước khi tin.

Phiên đầu tiên:

```bash
python3 scripts/genesis_session.py --display-name 'Tên bạn' --group 'Tên nhóm'
```

In ra `person_id`, `context_id` và Bearer token **một lần**. Từ đó dùng đường thường: đặt tên người mới (`PUT /people/{id}`), tạo chuyến, mời đích danh, người kia đổi mã lấy phiên.

Mất máy: người trong nhóm bấm **Cấp lại mã** trên lời mời đích danh của người đó. Mời lần hai là 409 — `uq_outing_invites_person` chỉ cho mỗi người một hàng cho mỗi chuyến, và đó là lý do nút xoay tồn tại.

---

# Cập nhật cùng ngày — sau khi CI chạy lại và sau e2e prod

Repo đã thành public nên GitHub Actions chạy trở lại (B0 gỡ). **Ba thứ CI bắt được mà chạy local không thấy**, và một thứ chỉ e2e prod mới thấy.

## CI bắt được, local mù

1. **`repo_guard tree HEAD` đỏ.** `apps/mobile/package-lock.json` ghim theo sha256; thêm `expo-secure-store` làm đổi digest nên ghim hết khớp và file bị quét thô (10 finding). Local `tree HEAD` xanh vì tôi chạy nó **trước** khi commit; `staged` xanh vì chế độ đó quét diff còn luật aggregate-base64 tính theo cả file. Đã cập nhật ghim.
2. **`scripts/postgres_tier.sh` đỏ.** Nó chạy **hai** tiến trình pytest, và tiến trình `../../tests/qa` không thu thập gì dưới `services/api/tests` nên conftest đặt `MOBILE_AUTH_MODE=dev` ở đó không import: 22 ca QA sống ăn 401. Thêm `tests/conftest.py` cho gốc repo. Cơ chế này hỏng theo hướng **đỏ ồn ào**, không phải xanh im lặng — ghi thẳng vào docstring.
3. **`ruff format --check` đỏ** trên 8 file (bản ghim 0.9.2, khác bản trên PATH).

## E2e prod bắt được, 2915 ca unit mù

`scripts/e2e_slice.sh` giờ chạy uvicorn ở **prod** và mint phiên thật cho ba người demo bằng `genesis_session.py`. Lần chạy đầu: **0/7**. Sau khi nối phiên: 7/9, và hai ca đỏ còn lại là hai lỗi thật.

**Lỗi thật số một — publish đợt thu 403.** `publish_batch` chứng minh `owns_batch` từ resource nhưng **để role `batch_owner` tới từ `X-Actor-Roles`**. Ở `prod` không ai khai role, nên người **sở hữu** đợt thu bị từ chối chính đợt thu của mình. Đường hero chết. Không một ca nào trong `tests/api` hay `tests/postgres` thấy được, vì tất cả đều gửi header. Sửa: suy `batch_owner` từ resource đúng khuôn `freeze_batch` ngay bên trên nó.

**Cổng cấu trúc để lần sau không phải chờ e2e:** `tests/api/test_roles_have_a_server_side_source.py` đọc bảng quyền cùng `service.py` và từ chối call site nào phụ thuộc một role mà phiên không cấp và cũng không tự suy. Canary: bỏ bản sửa `publish_batch` → cổng đỏ trong 0.06 giây, thay vì một chặng e2e mười phút.

## Một lỗ tôi tự tạo, và tự đóng trước khi e2e che mất

Bản đầu cấp `group_admin` **theo phiên** khi người đó là admin của bất kỳ nhóm nào. `invite_context_member` đòi `group_admin` + `is_group_member` — **không** đòi `is_group_admin` — nên role trên phiên là toàn bộ phép kiểm: admin nhóm A thêm được người vào nhóm B nơi họ chỉ là thành viên thường. Giờ `actor_grants` **không** cấp `group_admin`; `ApiService._group_admin_role` suy theo đúng nhóm đang bị tác động, cùng khuôn `batch_owner`. Ca đối chứng chạy trên Postgres thật: admin nhóm A → 403 khi thêm người vào nhóm B, **và** 201 vào nhóm của chính mình (không có vế sau thì ca kia xanh cho một máy chủ từ chối tất cả). Đột biến trả `group_admin` về phiên → 2 ca đỏ.

## Số đo cuối

| Tầng | Kết quả |
|---|---|
| `pytest services/api/tests tests` | 2915 passed |
| `scripts/postgres_tier.sh` | ĐẠT cả `tests/postgres` lẫn `../../tests/qa` |
| `npm test` (mobile) | 1048 passed |
| **`scripts/e2e_slice.sh` (uvicorn **prod** + phiên thật)** | **9/9** |
| 5 cổng hợp đồng + repo guard | exit 0 |

Trong 9 ca e2e có hai ca về chính hợp đồng auth: client **tự** gắn Bearer cho người đang đăng nhập (harness không phải vá lần nào — nếu `api.ts` thôi gắn thì harness sẽ vá và ca này đỏ), và máy chủ prod **từ chối** `X-Actor-ID` giả không kèm phiên (gửi bằng `fetch` thô, không qua wrapper, nếu không request đó đã bị sửa thành hợp lệ và chứng minh điều ngược lại).

## Vẫn KHÔNG chứng minh gì

Mọi mục ở phần trên còn nguyên. Thêm hai mục:

- **E2e chạy `fetch` của node, không phải trình duyệt.** Không có CORS thật ở đó — một cấu hình CORS hỏng vẫn qua được chặng này, đúng như header của `e2e_slice.sh` đã tự khai.
- **Ba người demo lấy phiên bằng genesis, không bằng đường đổi lời mời.** Đường đổi lời mời được chứng minh riêng ở `tests/postgres/test_session_bootstrap_postgres.py` (13 ca, HTTP thật trên Postgres thật). E2e chứng minh **80 route còn chạy khi actor tới từ phiên**; nó không chạy lại đường cấp phiên.

