# Claude — nhật ký 2026-08-26

**Phase:** Giai đoạn 0, chuẩn bị · **Việc:** thiết lập team · **Nhánh:** `main`

## Làm gì hôm nay

Chạy 4 vòng debate với Codex về phân chia công việc. Sản phẩm:
- `docs/team/charter.md` — điều lệ làm việc
- `docs/team/backlog.md` — W0–W9, phân công, thứ tự phụ thuộc
- `docs/decisions/ADR-0001` — quy trình + phân công (đã chấp nhận)
- `docs/decisions/ADR-0002` — chọn biến thể Giai đoạn 0 (**chờ leader**)

Nhận **W0** làm việc đầu tiên. Nhánh `claude/p0-w0-field-protocol`.

## Tôi sai chỗ nào trong 4 vòng

Ghi lại để không lặp.

1. **Ranh giới ownership tôi vẽ cho W2 là giả.** Gate A có 5 chỉ số; 2 trong đó cần người dùng thật nên thuộc W3. Không thể giao "toàn bộ Gate A" cho một người.
2. **Bỏ sót W0.** Đề xuất vòng 1 để W1 (study instrument) đi trước protocol. Console khi đó sẽ *phát minh* protocol thay vì *hiện thực* nó.
3. **Hoãn quá rộng.** Tôi hoãn "schema", nhưng measurement contract khác product schema và phải làm trước W1. Nếu không, field data không phân tích được.
4. **Overclaim differential test.** Tôi viết "mọi bất đồng giữa hai bản là chỗ mơ hồ trong spec". Sai — còn 4 nguyên nhân khác. Và hai bản đồng ý *không* chứng minh đúng: cả hai có thể cùng hiểu sai một câu spec. Golden vector tính tay là bắt buộc.
5. **Nói fake door vô hại.** Sai — nó bẩn nếu chung funnel/audience/tracking.
6. **Viết sai bất biến tiền:** đúng là `Σ allocated_vnd == expense_total_vnd`, không phải "tổng = 100%".
7. **Định giá sai Giai đoạn 0 cho leader** — trộn sàn pilot 30/cohort (mục 15, sau prototype) với cổng 13.3 (`/10`, trong Giai đoạn 0). Làm leader hiểu Phase 0 đắt gấp đôi thực tế. Đã đính chính ở ADR-0002. **Đây là lỗi nặng nhất** vì nó là con số leader dùng để quyết có làm hay không.
8. **Viết "6–12 nhóm"** cho P0-Gọn — ngụ ý 6 là đủ. Sai: 6 chỉ sinh STOP hoặc chẩn đoán.
9. **Ngụ ý consent tự soạn thay được counsel.** Trái mục 16.1.

## Tôi đóng góp gì được Codex nhận

- **W4a/W4b tách đôi + hoãn W4b.** Schema vẽ trước fieldwork là công cụ cam kết: nó quyết định console log gì, rồi dữ liệu "xác nhận" chính ontology đó.
- **W8 không được chạy trên nhóm concierge.** Đo WTP với Wizard-of-Oz là đo WTP cho một dịch vụ có người thật làm.
- **Hai hiện thực độc lập cho allocator** thay vì reviewer/implementer.
- **Leader lane.** Cả hai chúng tôi đang viết kế hoạch cho một tổ chức chưa được xác nhận là tồn tại.
- **Nhịp docs theo phase.** Nhật ký hằng ngày trong 12 tuần field là nghi lễ rỗng.
- **W0 thuộc Claude** vì Codex sở hữu W1/W2/W4a/W9a — người viết giao thức đo không nên là người xây công cụ hiện thực nó.

## Review việc của Codex

**Không có.** Codex chưa tạo artifact nào — 4 vòng đều read-only, không sửa file. Việc đầu tiên của Codex là W9a trên nhánh `codex/p0-w9a-repo-guard`; review sẽ nằm ở `docs/claude/<ngày>/review-p0-w9a-repo-guard.md`.

## Chặn / rủi ro

- 🔴 **ADR-0002 chặn toàn bộ field work.** Không biết biến thể nào thì W0 không thể chốt cohort, cỡ mẫu, hay vai operator.
- 🟡 W0 sẽ được viết **tham số hoá theo biến thể**, phần chung chốt trước, phần phụ thuộc để trống chờ leader.
