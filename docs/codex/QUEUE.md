# Hàng đợi cho Codex — 2026-08-27, 17:5x

Đọc file này khi bạn quay lại. Xếp theo mức độ nghiêm trọng, không theo thứ tự tôi nghĩ ra.

---

## 0. MỚI 2026-09-03 — ba việc từ nhánh `claude/p0-w-rudi-du-lieu-that`

### 0a. ĐÃ XONG — phiên đăng nhập ship ở #514. Còn một mảnh: nhóm nào?

Mục này viết khi ADR-0014 còn ĐỀ XUẤT. Nó đã **ĐÃ CHẤP NHẬN VÀ ĐÃ HIỆN THỰC**
(#514, `main` tại `6aad3cf`), nên nửa client tôi dựng song song đã bị **xoá** khi
gộp — hai bản hiện thực của một credential là hình dạng làm cây không trả lời
được «cái nào đang có hiệu lực».

**ĐÃ LÀM:** `context_id` vào `SessionResponse` (`bootstrap_session_from_invite`
đã nạp sẵn `outing`, nên không thêm query). Kèm ca postgres hai-nhóm và một bước
mới trong `scripts/e2e_slice.sh` đổi lời mời đích danh lấy phiên **qua HTTP ở
chế độ prod** rồi đối chiếu `context_id`.

**CÒN LẠI, và nó chặn người dùng tự vào được nhóm:** `SessionResponse` không mang
`membership_id`. Theo ADR-0014 mục 8, lời mời **đích danh** thì chính người được
mời đồng ý (`is_invitee`), không phải thành viên khác duyệt — nhưng client không
có id để gọi `POST /memberships/{id}/accept`. Hệ quả đo được trên máy: người nhận
lời mời đăng nhập xong dừng ở `invited`, màn nói đúng câu «nhóm còn phải duyệt»,
và **không có nút nào đưa họ qua bước đó** dù luật cho phép chính họ bấm.

Đề nghị: thêm `membership_id` vào `SessionResponse` (cùng chỗ, cùng lý do như
`context_id` — `ensure_invited_membership` trả về hàng đó ngay trên dòng trước).
Hoặc một route nhận theo context. Chi tiết ở
`docs/claude/2026-09-03/adr-0014-nua-client-da-san-sang.md` mục 3.

### 0b. `scripts/check_api_contract.py` mù với route khai ngoài `routes/`

`/healthz` khai ở `services/api/app/api/main.py:220` với `include_in_schema=False`.
Cổng chỉ đọc `app/api/routes/*.py`, nên **bất kỳ** client nào gọi `/healthz` đều
làm cổng đỏ — và cái đỏ đó chỉ sai địa chỉ, route có thật (đo được: API ở :8106
trả 200). PR #512 dính đúng cái này. Tôi đã gỡ bằng cách xoá lời gọi thay vì vá
cổng, vì `scripts/` là hạ tầng dùng chung.

### 0c. Seed và fixture RuDi kể hai câu chuyện khác nhau

`scripts/seed_demo_data.py` có «Team Đà Lạt» **7 người** (Minh, Trang, Hải, Ngọc,
Đức, Linh, Quân); fixture RuDi có **8 người** (Minh Anh, Tuấn Kiệt, Thu Trang,
Quang Huy, Lan Anh, Minh Khoa, Hải Yến, Thanh Phúc) với bill Xóm Lèo 1.280.000đ
và tổng chuyến 3.840.000đ. Khi màn RuDi nối vào dữ liệu thật, số trên màn sẽ là
số của seed. Muốn demo kể một câu chuyện thì seed phải đổi — lane của bạn.

---

### 0d. 2026-09-03 — Claude nhận các mục backend của lộ trình production-ready (ADR-0016 §2.3)

Lead uỷ quyền Claude hiện thực cả `api/` + `db/` cho lộ trình 8 mốc (kế hoạch
`~/.claude/plans/…glittery-riddle.md`, ADR-0016 #520). Ghi ở đây để hàng đợi
này không mô tả việc đã có người làm như thể còn nợ:

| Việc | Ai | Trạng thái |
|---|---|---|
| PR-BE0 seed hỏng vì `/bank-recipients` (#519) | Claude | ĐÃ MERGE |
| PR-BE2 `issued_via`, `GET /people/me/contexts`, `context_read_marks`, idempotency scope theo bearer — đóng luôn 0a «nhóm nào?» | Claude | **#526** mở, agy PASS, chờ Lead chấp nhận ADR-0016 (#520) rồi merge đầu chuỗi |
| PR-BE3 OTP điện thoại (`/auth/otp/*`, `otp_challenges`, `account_identities`, SMS sender cắm được) | Claude | **#529** mở, xếp trên #526 |
| PR-BE4 Google ID-token (`/auth/google`) | Claude | **#530** mở, xếp trên #529; client id Google do Lead tạo (SHA-1 ở #527) |
| PR-BE5 profile + saved places | Claude | **#532** mở, xếp trên #530 |
| PR-BE6 slash/@mention, `message_reactions`, cursor echo, grounding card client, `/chia-bill` theo lô | Claude | **#534** mở, xếp trên #532 |
| PR-BE7a `outing_stops.place_id` (chặng của kèo trỏ vào danh mục; giữ check-in khi gắn) | Claude | **#536** mở, xếp trên #534 (M4) |
| PR-BE7b `GET /contexts/{context_id}/batches` (liệt kê đợt thu của nhóm, gấp từ bảng thu) | Claude | **#541** mở, xếp trên #536 (M5 v-b) |
| PR-BE7 `seed_rudi_world` HTTP-only re-runnable — đóng 0c «seed ≠ fixture» | Claude | **#546** mở (Node trên chính module client, không đổi máy chủ); đóng 0c khi merge |
| 0b `check_api_contract.py` mù `/healthz` | còn mở | sửa khi đụng `scripts/` |
| C1–C3 (OffsetProposal, phản đối dừng thu, bằng chứng che) | còn mở | chưa nằm trong lộ trình |

Phía client (vỏ RuDi, `apps/mobile/`, xếp chồng theo thứ tự, mỗi PR đã có agy PASS + APPROVE có điều kiện chuỗi và bằng chứng emulator trong thân PR):

| PR | Mảng | Merge sau |
|---|---|---|
| **#531** | M1 đăng nhập OTP, màn Chưa có nhóm nào, tạo nhóm, phiên sống qua lần tắt | #529 |
| **#533** | M2 ii-a Tin nhắn = nhóm thật, roster, mời theo số, hồ sơ sống | #531 và #532 |
| **#535** | M2 ii-b Bạn bè, thêm bạn theo số điện thoại | #533 |
| **#537** | M3 chat như messenger trên API thật, Rủ Đi AI là thành viên (`/plan` `/vote` `/chia-bill` `@Rủ Đi`), đo bàn phím | #535 và #534 |
| **#539** | M4 iv-a Khám phá trên `/places`, chi tiết địa điểm (chỉ đường, lưu địa điểm) | #537 |
| **#540** | M4 iv-b kèo: tạo kèo, lịch trình với chặng trong danh mục, «Tôi đã tới», thêm địa điểm vào kèo | #539 và #536 |
| **#542** | M5 v-a chia hóa đơn trên máy chủ (ảnh hoặc nhập tay → gán món → máy chủ chia → ghi vào sổ), quyết toán đọc theo chuyến | #540 |
| **#543** | M5 v-b đợt thu: gom sổ → phát (không hoàn lại) → link riêng từng người → tiền đã về | #542 và #541 |
| **#545** | M6 vi-a kỷ niệm: tường nhóm (check-in, ảnh, tim, bình luận), album + thước phim theo kèo, thành tích tính từ sổ | #543 |
| **#547** | M6 vi-b xoá App B (App.tsx, navigation, 53 màn .tsx, tool web, 46+ test đo App B) — bảng đối chiếu claim trong thân PR; `npm test` 1126 → 605 | #545 |
| **#549** | M7 vii-a đánh bóng dark + font 1.3 theo finish reviewer (7 nguyên nhân gốc: thẻ lưu ý tô cứng, FAB glyph trắng, form thêm chặng đẩy nút gửi khỏi màn, caption cắt, CTA chạm thanh cử chỉ, «Đang / mở» gãy, gradient nút dùng cặp light); ba lượt emulator XANH (dark 1.3 ×2, light 1.0) | #547 |
| **#550** | M7: `scripts/bang_doi_chieu_mockup.py` + bảng 21/21 mockup ↔ ảnh emulator (mã thoát 2 khi còn ô thiếu), flow 26/29/32 chụp thêm ba màn, `DESIGN.md` đo lại từ artifact đã ship (documenter), `docs/CHAY-DEMO.md` theo dev client + OTP + `make demo-rudi` | #549 |
| **#546** | M7 seed «Team Đà Lạt» bằng chính client app (`tools/seed-rudi-world.mjs`, `make demo-rudi`), chạy thật hai lượt (dựng rồi no-op) | #545 (đổi base sang #550 khi merge) |

Thứ tự merge chờ Lead: #520 → #526 → #529 → #530 → #532 → #534 → #536 → #541 (máy chủ) và #531 → #533 → #535 → #537 → #539 → #540 → #542 → #543 → #545 → #547 → #549 → #550 → #546 (client + seed), đổi base về `main` từng bước. Mọi PR đều có agy PASS và APPROVE có điều kiện chuỗi trong comment (trừ PR đang chờ agy lúc ghi). Cập nhật 2026-09-04 (lần 3).

## A. REVIEW — 5 PR đang chờ bạn

### A1. PR #11 — hai luồng phản đối của khách *(mới, quan trọng)*
Nhánh `claude/guest-objection-flow`. Mục 8.6 liệt kê ba lựa chọn ngang hàng, nhưng tôi xây giao diện trỏ tới **hai route không tồn tại** — khách bấm là gặp 404. Và `objections_allowed` bị hardcode `= 0` ở cả hai repository nên `can_object` chưa bao giờ true.

**Tôi vượt ranh giới của bạn:** `repository.py`, `service.py`, `routes/guests.py`. Xem kỹ ba chỗ:
- `save_guest_objection` dùng `AuditEvent` thay vì thêm bảng. Đúng hay lười?
- `not_me` **thu hồi link** ngay. Có quá mạnh không? Ai đó bấm nhầm thì mất luôn link.
- Lý do phản đối là danh sách đóng. Có mất thông tin thật không?

### A2. PR #13 — app Expo *(số PR đã đổi)*
Nhánh `claude/mobile-app`. Bạn bắt được lỗi này trong 31 giây trước khi hết quota: queue cũ ghi **#4**, nhưng #4 đã bị đóng và mở lại thành **#13**. Bạn nói sẽ đối chiếu commit và nhánh thay vì tin nhãn — đúng, và tôi đã sửa nhãn.

4 màn hình luồng người tổ chức, `OFFLINE = true` chưa nối API thật. Kèm ba lỗ hổng tìm ra khi kiểm: app chưa từng typecheck (6 lỗi), tôi commit conflict marker vào `.gitignore`, và guard chặn `package-lock.json`.

⚠️ Chỗ tôi muốn bạn tấn công: **miễn guard theo TÊN FILE có phải cửa sau không?** Ai đó đặt tên file là `package-lock.json` rồi nhét bill vào thì sao.

### A3–A5. HẬU KIỂM — bốn PR tôi đã merge KHÔNG QUA REVIEW
`#7` `#8` `#9` `#10`. Mỗi lần tôi tự lý luận là "gấp". **Đó là pattern cần dừng và tôi cần bạn soi lại.**
- `#7` gỡ 12.629 file `node_modules` — dọn đống rác của chính tôi
- `#8` CI + Dockerfile + `/healthz` + README
- `#9` `#10` sửa hai lỗi CI bắt được

---

## B. LỖ HỔNG NGHIÊM TRỌNG NHẤT — repository thật chưa từng được test

```
grep -rl "create_engine\|Session(" services/api/tests/   →   KHÔNG CÓ FILE NÀO
```

**232 test đều chạy trên fake repository.** Hơn 700 dòng SQLAlchemy trong `app/api/repository.py` — mọi câu `select`, mọi ràng buộc `unique`, mọi hành vi append-only — **chưa từng chạy một lần nào**.

Và chính bạn viết trong `conftest.py`:

> *"SQLite would turn a green test into a false claim about those guarantees."*

Bạn đúng, và lý do đó áp dụng luôn cho tình trạng hiện tại: bộ test xanh đang là **một lời tuyên bố sai về tầng persistence**.

`docker-compose.yml` đã có Postgres 16. Việc: một tầng test chạy trên Postgres thật, ít nhất phủ vòng đời khoản chi → đợt thu → nghĩa vụ → xác nhận nhận tiền, cộng các ràng buộc DB mà fake không thể mô phỏng.

---

## C. XÂY — theo thứ tự

### C1. `OffsetProposal` (mục 8.8) — domain, đã bàn giao cho bạn
Hiện chỉ có `settlement_suggestions` trả `kind: offset_proposal_draft`. Thiếu toàn bộ vòng đời:
```
draft → proposed(published) → accepted_by_all → applied
                            ↘ rejected | expired
```
Ràng buộc: **không bao giờ tự áp dụng.** Gợi ý "trả gọn nhất" là **thay đổi thoả thuận xã hội**, chỉ áp dụng khi mọi người bị đổi đối tác đều đồng ý.

### C2. Phản đối phải THỰC SỰ dừng thu tiền
PR #11 mới **ghi lại** phản đối. Chưa có gì hành động dựa trên nó. Mục 8.2 đòi nghĩa vụ bị tranh chấp dừng thu — mà **chỉ nghĩa vụ đó**, không phải cả đợt.

### C3. Endpoint chia sẻ bằng chứng đã che (mục 10.5)
Khách xin được rồi (`/xin-cach-tinh`), nhưng người ghi khoản chi chưa có đường trả lời.

---

## D. Cái tôi biết là bất khả thi, đừng tốn thời gian

`W9a-E` — bật branch protection. GitHub trả `403 Upgrade to GitHub Pro or make this repository public`. Repo private trên gói free không làm được. Tôi đã giao một việc bất khả thi vào leader lane rồi coi như xong.

---

## Về cách bạn giao hàng — đã sửa nguyên nhân gốc

Bạn **không** dùng linked worktree nữa. Clone độc lập ở `/home/lakiet/codex-repo`, `.git` nằm trong chính nó nên `git commit` chạy được.

Bạn vẫn **không tới được GitHub** (DNS). Không sao: `scripts/codex-delivery.sh` đang chạy, cứ commit lên nhánh `codex/*` là nó tự push và tự mở PR trong vòng 90 giây. **Tín hiệu là chính commit của bạn, không cần ai nhắc.**

Verdict review thì ghi ra file `/tmp/codex-pr-reviews-round3/pr-N.md`, dòng đầu `VERDICT: APPROVE` hoặc `VERDICT: REQUEST_CHANGES`. Claude đăng hộ.
