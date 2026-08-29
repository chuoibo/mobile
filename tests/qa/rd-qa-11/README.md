# rd-qa-11 — quét #116 (buổi đi chơi), một lỗ rò quyền và một khe đua

**Phán quyết: FAIL.** #116 đã ở trên `main` và mở một đường cho người ngoài đọc
tin nhắn, tường kỷ niệm và số dư của một nhóm chưa từng mời họ.

Commit đã kiểm: `061f979` (main tại 2026-08-29T13:5x+07).
Nền: PostgreSQL 16 thật + uvicorn thật, stack riêng `qa11` (API `:8811`, PG `:5811`).

---

## Vì sao lượt quét này tồn tại

#116 (rd-be-08) vào `main` lúc 06:46Z mà **chưa có phán quyết QA nào**. Nó thêm
một bề mặt API mới (F13 tạo buổi đi · F14 mời · F15 dòng thời gian), và mô tả
commit của nó tự nêu năm lời tuyên bố kiểm được. Bốn cái đúng. Cái thứ năm —
đúng cái bản lề quyền riêng tư — sai, và sai theo cách bộ test của chính tác giả
không thể thấy.

Tác giả viết 18 ca live cho tính năng này. Chúng tốt. Chỗ hỏng nằm **một lời gọi
HTTP sau** chỗ ca kiểm cuối cùng dừng lại.

---

## Phát hiện 1 — RÒ DỮ LIỆU NGƯỜI KHÁC (chặn, loại 3)

### Lời tuyên bố

`service.py::accept_outing_invite` viết trong docstring của chính nó:

> A link can be forwarded to anybody, so INVITED is the ceiling created here.
> Because `is_member` requires ACTIVE, the holder cannot read group messages,
> memories, or balances **until a human accepts them through the existing
> `/memberships/{id}/accept` route**.

Hai vế đầu đúng. `is_member` thật sự đòi `ACTIVE`
(`repository.py:1118`), và đổi link thật sự chỉ sinh ra `INVITED`.

Câu vẫn sai, vì **"a human" đó là ai**.

### Cái thực sự xảy ra

`accept_context_membership` chứng minh đúng một vị từ — `is_invitee`, tính bằng
`membership.person_id == actor.id` (`service.py:558`). Người được mời **chính là**
người bấm đồng ý. Không ai trong nhóm được hỏi.

Và `POST /outing-invites/{token}/accept` trả về luôn `membership_id` trong phản
hồi — tức là bước 1 đưa sẵn cho người cầm link cái id mà bước 2 cần.

Nên trần không phải INVITED. Trần là ACTIVE, cách đó **hai lời gọi HTTP**.

### Tái lập

```
cd tests/qa/rd-qa-11
MOBILE_API=http://localhost:8811 python3 forward_link_to_active.py
```

Kết quả thật, chạy trên `061f979`:

```
== truoc khi doi link ==
  GET /contexts/../memories  -> 403
  GET /contexts/../messages  -> 403
  GET /contexts/../balances  -> 403

== buoc 1: doi link -> state=invited ==
  phan hoi tra ve luon membership_id = d2c30579-7e70-4379-b860-e5720fbb2a9e

== buoc 2: tu bam accept -> HTTP 200 ==
  state=active

== sau khi tu accept ==
  GET /contexts/../memories  -> 200
  GET /contexts/../messages  -> 200
  GET /contexts/../balances  -> 200

KET LUAN: nguoi ngoai doc duoc memories, messages, balances.
  Doc duoc ca noi dung that: caption tuong ky niem, noi dung tin nhan nhom.
  Khong mot thanh vien nao trong nhom bam dong y cho nguoi nay.
```

Không phải suy luận từ mã trạng thái: probe khẳng định **cái có trước** — nó tìm
thấy đúng chuỗi caption và đúng chuỗi tin nhắn mà nhóm đã đăng, trong thân phản
hồi trả về cho người ngoài. Trang trắng không làm dòng này pass được.

### Quy trách nhiệm cho đúng chỗ

`is_invitee` **có trước** #116 (`e271ebb`) và lúc đó nó đúng: đường duy nhất tới
`INVITED` là `invite_context_member`, đòi `group_admin` **chỉ đích danh một
người**. Nhóm đã chọn bạn rồi, nên bạn tự xác nhận là hợp lý.

`ensure_invited_membership` sinh ra đúng ở `54152df` (#116) —
`git log -S` xác nhận. Nó là đường đầu tiên cho phép một **bearer token chuyển
tiếp được**, không đích danh ai, tự tạo hàng `INVITED` cho chính mình.

Lỗ nằm ở chỗ **ghép hai cái lại**. #116 là commit mở nó ra; bản sửa có thể nằm ở
một trong hai chỗ. Đề xuất (không phải việc của QA): người bấm đồng ý phải là
người **đã ở trong nhóm**, hoặc `INVITED` sinh từ link cần một vị từ khác
`is_invitee`.

### Ca kiểm hồi quy, đã đỏ trước

`regression_outing_invite_escalation.py` — cố ý **không** đặt tên `test_*.py` để
cổng của repo không nhặt, `main` không đỏ vì một lỗi QA mới chỉ báo.

Chạy tại đúng chỗ nó sẽ sống, hôm nay:

```
E  AssertionError: Người cầm link chuyển tiếp tự nâng mình lên ACTIVE được:
   HTTP 200 {... "state":"active" ...}
E  assert 200 == 403
1 failed in 1.41s
```

Đỏ ở **assertion**, không phải ở import hay fixture — nó thật sự chạm vào lỗi.
Khi sửa xong thì:

```
git mv tests/qa/rd-qa-11/regression_outing_invite_escalation.py \
       services/api/tests/postgres/test_outing_invite_escalation_postgres.py
```

### Vì sao 18 ca của tác giả không thấy

`test_redeeming_an_invite_link_grants_an_invited_membership_not_an_active_one`
làm đúng việc nó định làm: đổi link, rồi gõ cửa tường kỷ niệm và danh sách buổi
đi — cả hai trả 403. Ca kiểm dừng ngay đó.

Nó kiểm rằng **cánh cửa đang đóng**. Nó không thử **vặn tay nắm**.

---

## Phát hiện 2 — một link dùng một lần nhận hai người (chặn, loại 5)

`accept_outing_invite` đọc lời mời **không khoá**
(`get_outing_invite_by_digest` là một SELECT trần), quyết định trong Python rằng
`accepted_at is None`, rồi mới lấy `FOR UPDATE` — và ở trong khoá nó **đóng dấu
`accepted_at` vô điều kiện, không đọc lại cái điều kiện vừa đi qua**. TOCTOU
kinh điển trên một bearer token.

```
cd tests/qa/rd-qa-11
MOBILE_API=http://localhost:8811 MOBILE_DB='postgresql://mobile:mobile-dev-only@localhost:5811/mobile' \
  python3 race_invite_link.py 10
```

```
[ 1] statuses=[200, 409] 200s=1 invited_rows=1 ok
[ 2] statuses=[200, 200] 200s=2 invited_rows=2 VI PHAM
...
[10] statuses=[200, 200] 200s=2 invited_rows=2 VI PHAM

rounds=10 vi_pham=9
KET LUAN: mot link dung mot lan da nhan HAI nguoi vao nhom.
```

9/10 vòng. Hai người **khác nhau** cùng vào, nên partial unique index (một hàng
mở mỗi người mỗi nhóm) không đỡ được — nó chặn một người đổi hai lần, không chặn
hai người đổi một lần.

Kèm theo: `accepted_by_id` bị ghi đè, nên sổ chỉ nhớ **một** trong hai người đã
dùng link. Ai đổi link trước biến mất khỏi bản ghi.

Đọc lại bằng `psycopg` trên **connection khác** với connection của API — session
của chính API sẽ nói dối về chuyện này.

Ghép với phát hiện 1: mỗi người trong số đó tự lên ACTIVE được.

Chỉ quan sát được với server thật + PostgreSQL thật. Route là `def` đồng bộ nên
FastAPI đẩy sang threadpool, mỗi request một session một connection. Một
`TestClient` dùng chung session không thấy khe này.

---

## Cái đã kiểm và ĐÚNG

Bốn lời tuyên bố còn lại của #116 đứng vững — kiểm bằng 171 ca live, `TZ=UTC`:

- Ngân sách là **số nguyên đồng**; `2500000.0` và `"2500000"` đều 422. Không ép kiểu.
- Ngân sách **không chặn** gì: 0đ và 900 tỷ đều tạo được.
- Timeline giữ **thứ tự người dựng**, không sắp lại theo giờ.
- Token thô trả về **đúng một lần**; database chỉ giữ digest SHA-256.
- Người lạ không tạo/đọc/sửa được buổi đi của nhóm khác (403).
- Người đã rời nhóm thôi thấy buổi đi của nhóm.

Đây là phần khó và tác giả làm đúng. Lỗ duy nhất là chỗ ghép với route cũ.

---

## Một bẫy chưa nổ, ghi lại cho rd-fe-12

`GET /contexts/{id}/members` lọc theo `left_at IS NULL`, **không** lọc theo
`state` (`repository.py:1107`) — nên nó trả về cả người `INVITED`.

Hôm nay chưa hại ai: màn chia tiền (`GoiYChia`, `NhapKhoanChi`) lấy roster từ
`navigation/nhom-demo.ts`, tức nhóm demo seed sẵn, **không** gọi route này. Tôi
đã kiểm và **rút** phán quyết ban đầu của mình về chuyện này — nó không tái lập
được trên bản đang chạy.

Nhưng rd-fe-12 sẽ nối màn tạo buổi đi vào roster thật. Lúc đó, nếu
`availableMembers` (`src/participants.ts:88`) vẫn chỉ lọc "đã có trên bill chưa",
một người `INVITED` sẽ đứng trong ma trận chia tiền và **nhận được một phần của
hoá đơn**. Ba luật tiền vẫn xanh: Σ vẫn đúng tổng, vẫn số nguyên đồng. Tiền chỉ
rơi vào người chưa ai đồng ý cho vào nhóm.

Không phải blocker hôm nay. Là thứ cần lọc `state == 'active'` trước khi màn đó
lên.

---

## Quét a11y màn vào cửa (#115) — nơi luồng mời của #116 sẽ đổ bộ

#116 chưa có giao diện (rd-fe-12 chưa vào main), nên chỗ quét được là màn vào cửa
của #115 và sheet `[+]` — đường **duy nhất** tới màn nhóm F03/F04 từ một lần mở
app lạnh, tức đường luồng mời sẽ đi qua.

Bundle riêng `dist-qa11`, ghim `EXPO_PUBLIC_API_URL=http://localhost:8811`, phục
vụ ở `:8911`. Đã đối chiếu hash bundle trong `index.html` khớp bản mình vừa dựng
trước khi tin bất kỳ con số nào — cổng bị chiếm là bẫy đã nổ một lần ở lane khác.

### axe WCAG 2.2 AA: 0 vi phạm / 6 ô

`mở đầu` · `#vao=dang-ky` · `#vao=nhom`, mỗi màn ở 390px và 320px.

**Một số 0 chỉ đáng tin sau hai phép đối chứng**, cả hai đều đã chạy
(`a11y_doi_chung.mjs`):

1. **axe có thật sự chạy không?** Cấy hai lỗi vào DOM sống rồi quét lại:
   `0 vi phạm -> 1 vi phạm (image-alt)`. Máy quét có chạy và có bắt được. Không
   cấy thì `[] + exit 0` trông y hệt "sạch" — đúng cái bẫy đã nổ với `imp detect`
   khi thiếu trình duyệt.
2. **Mỗi nhãn có đúng màn đã render không?** `AppRoot` đọc fragment **một lần**
   lúc mount, nên mọi lần chuyển màn đều đi qua `about:blank`. Đã in vân tay chữ
   + danh sách nút của từng màn: cả bốn fragment ra **bốn màn khác nhau**, không
   màn nào trùng mở đầu. Nhãn đúng.

### Phát hiện a11y — Escape không đóng sheet `[+]` (KHÔNG chặn merge)

axe cho 0 vi phạm và hoàn toàn không thấy cái này.

ARIA của sheet **đúng**: `role="dialog"`, `aria-modal="true"`,
`aria-label="Tạo gì đây?"`. Mở được bằng bàn phím (`Enter` trên "Tạo mới").
Nền bị `inert` đúng như `VoTab.tsx` mô tả.

Cái sai: **`Escape` không đóng sheet.** Mẫu dialog của ARIA APG đòi Escape đóng.

Tôi định gọi đây là bẫy bàn phím WCAG 2.1.2 mức A và **đã đo lại trước khi
báo** — không phải. Focus bị nhốt trong sheet (đúng, đó là hành vi modal đúng),
nhưng **chặng Tab đầu tiên là "Đóng menu tạo mới"**, một nút bấm được. Người dùng
bàn phím ra được, chỉ là không ra bằng phím họ mong đợi.

Nên: khó chịu thật, tái lập 100%, **không** phải blocker. Ghi vào báo cáo đúng như
Lead dặn — leader đang cần độ phủ tính năng, không cần một cổng nữa.

Tái lập: `MOBILE_WEB=http://localhost:8911 node a11y_sheet_ban_phim.mjs`

### Xác nhận thêm cho bản đồ chặng của Lead

`#tab=len-plan` tự khai bằng chữ trên màn: *"vỏ — Màn này chưa dựng, mới có chỗ
trong menu."* L4 (Khám phá không dẫn đi đâu) **vẫn cụt** — đúng như Lead dự đoán,
rd-fe-12 chưa vào main. Vỏ có tự nhận là vỏ, đó là cách làm đúng.

### Ô a11y chưa quét

- **Trình đọc màn hình thật** (VoiceOver / NVDA / TalkBack). Không agent nào chạy
  được, và đây là 60–70% số lỗi mà máy quét không thấy.
- **2.4.11** (focus bị che) và **2.5.7** (kéo thả) — axe không có rule.
- **2.5.8** vùng bấm — axe chỉ phủ một phần; script có tự đo `< 24x24` và không
  thấy nút nào vi phạm ở các màn đã đi.
- Màn của chính #116 — chưa tồn tại.

## Ô CHƯA QUÉT

Phần quan trọng nhất của báo cáo này.

- **Mã VietQR chưa từng được quét bằng app ngân hàng thật.** Không agent nào làm
  được. Cần leader, một điện thoại, 15 phút (ADR-0010 mục 8).
- **Chưa đi bằng tay nửa sau của luồng** ở lượt này: form → chia tiền → đợt thu →
  publish → trang khách. Ô này Lead đã hỏi từ 09:05 và vẫn mở. Script dở dang của
  lượt rd-qa-09 bị cắt ngang còn trong worktree (`tests/qa/rd-qa-09/`, chưa
  commit) — xem ghi chú cuối.
- **Chưa quét giao diện** của #116: chưa có màn hình nào cho buổi đi chơi
  (rd-fe-12 chưa vào main), nên không có gì để chụp.
- **Chưa đâm** vào `PUT /outings/{id}/timeline` ở mức đồng thời (hai người sửa
  lịch trình cùng lúc — PUT thay nguyên danh sách, ai thắng?).
- **Chưa kiểm** buổi đi chơi khi người tạo rời nhóm giữa chừng.
- **Chưa đo** hành vi thật của người dùng — ADR-0006 vẫn gác Giai đoạn 0. Bộ test
  xanh nói code làm đúng điều tác giả nghĩ; nó không nói người thật hiểu sản phẩm.

## Cổng đã chạy thật (cây sạch, `061f979`)

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **951 passed**, 194 skipped (tầng postgres), 4580 subtests |
| `tests/postgres` + `MOBILE_REQUIRE_POSTGRES_TESTS=1`, `TZ=UTC` | **171 passed, 0 skipped** |
| `forward_link_to_active.py` | **rò rỉ tái lập được**, 403→200 |
| `race_invite_link.py 10` | **9/10 vòng vi phạm** |
| `regression_outing_invite_escalation.py` tại đích | **đỏ ở assertion**, `assert 200 == 403` |

194 skipped ở dòng đầu **không phải** xanh — đó là tầng postgres chưa chạy, và
dòng thứ hai là chỗ nó thật sự chạy.
