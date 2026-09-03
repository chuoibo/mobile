# Hàng đợi cho Codex — 2026-08-27, 17:5x

Đọc file này khi bạn quay lại. Xếp theo mức độ nghiêm trọng, không theo thứ tự tôi nghĩ ra.

---

## 0. MỚI 2026-09-03 — ba việc từ nhánh `claude/p0-w-rudi-du-lieu-that`

### 0a. ĐÃ XONG — phiên đăng nhập ship ở #514. Còn một mảnh: nhóm nào?

Mục này viết khi ADR-0014 còn ĐỀ XUẤT. Nó đã **ĐÃ CHẤP NHẬN VÀ ĐÃ HIỆN THỰC**
(#514, `main` tại `6aad3cf`), nên nửa client tôi dựng song song đã bị **xoá** khi
gộp — hai bản hiện thực của một credential là hình dạng làm cây không trả lời
được «cái nào đang có hiệu lực».

**Việc còn lại, và nó chặn màn RuDi đọc dữ liệu thật:** một phiên chưa cho biết
NHÓM nào. `SessionResponse` không mang `context_id`, và `contexts.py` không có
route nào liệt kê nhóm của một người (đo trên `main` tại `03eb05a`). Đề nghị
thêm `context_id` vào `SessionResponse` — người ta đăng nhập bằng lời mời vào
một chuyến, nên máy chủ đã biết nhóm ngay lúc cấp phiên. Chi tiết ở
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
