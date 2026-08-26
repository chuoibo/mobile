# ADR-0001 — Quy trình team và phân công Giai đoạn 0

- **Trạng thái:** ĐÃ CHẤP NHẬN
- **Ngày:** 2026-08-26
- **Người quyết:** Claude + Codex hội tụ; leader có quyền lật
- **Căn cứ:** spec mục 13, 15, 16 · `docs/team/charter.md` · `docs/team/backlog.md`

## Bối cảnh
Sau khi spec sản phẩm hội tụ (19 vòng), leader yêu cầu hai engineer chia việc và làm việc như một team: nhánh riêng, review chéo, nhật ký theo ngày. Câu hỏi đầu tiên phải trả lời là **việc gì hợp lệ khi spec cấm viết product code trước cổng hành vi 13.3**.

## Quyết định
1. Backlog Giai đoạn 0 gồm W0, W1, W2, W3, W4a, W6, W7, W8, W9, W9a. W4b hoãn tới sau gate và chỉ làm nếu PASS. Phân công ở `docs/team/backlog.md`.
2. Quy trình nhánh / review / blocker / hai cổng / tài liệu ở `docs/team/charter.md`.
3. **Leader lane được ghi vào kế hoạch chính**, không phải phụ chú.

## Những phương án bị bác

**Codex sở hữu 4/6 việc ban đầu (W1, W2, W4, W6).**
Bác. Codex tự khai điểm yếu là "biến tool nghiên cứu thành kiến trúc đẹp để dùng lâu", và W1/W4/W6 chính là ba nơi rủi ro đó lớn nhất. Tập trung cả ba vào một người là khuếch đại rủi ro đã biết.

**Claude review mọi thứ Codex viết, Codex không review ngược.**
Bác. Tạo silo: Codex thành xưởng code, Claude thành cơ quan cấp phép. Claude không tích luỹ hiểu biết từ dữ liệu lỗi thật; Codex không được dùng thế mạnh formal reasoning. Review **hai chiều**.

**Phác schema sản phẩm ngay bây giờ.**
Bác — hoãn thành W4b. Mục 13 *cho phép* schema trên giấy, nhưng cả điểm của Giai đoạn 0 là mô hình dữ liệu có thể sai. Schema vẽ trước dữ liệu thực địa là công cụ cam kết: nó quyết định console log cái gì, rồi dữ liệu thu được sẽ "xác nhận" chính ontology đó. Vòng luẩn quẩn.
*Nhưng* **measurement contract KHÁC product schema và phải làm TRƯỚC W1** — study ID giả danh, cohort, `protocol_version`, lane, timestamp thao tác, nhãn operator, input modality, error severity, số lần sửa, thời gian chủ động của organizer, trạng thái consent, provenance và thời hạn giữ dữ liệu.

**Reviewer/implementer cho allocator tiền.**
Bác — thay bằng hai hiện thực độc lập + differential gate. Xem `docs/team/backlog.md`.

**W8 pricing chạy trên cùng nhóm concierge.**
Bác. Hỏi giá trong lúc concierge đang chạy đổi khung nhận thức của organizer từ "được giúp" sang "đang bị bán hàng", tác động thẳng vào chỉ số self-initiation theo hướng không đoán được dấu. Tệ hơn: đo WTP với Wizard-of-Oz là đo WTP cho **một dịch vụ có người thật làm**, mang cả thiên lệch cận trên (xử lý ngoại lệ) lẫn cận dưới (niềm tin, tốc độ) cùng lúc, không tách được.
Ba track: **H** hành vi (không thấy giá/paywall/fake door cho tới khi outcome đã khoá) · **M** market/pricing (mẫu tuyển riêng) · **P** sau prototype (revealed preference).
Fake door **không** tự động vô hại — chỉ chạy song song khi audience, tracking và recruitment path tách biệt. Participant đã thấy fake door không được âm thầm nhập Track H.

**Làm mục 14.3 trên giấy để lấp cửa sổ rỗng của engineer.**
Bác. "Giấy" vẫn là cửa sau cho product design.

## Hệ quả
- W0 chặn W1 và W3. Không ai được bắt đầu study instrument trước khi có giao thức đo.
- W9a chặn mọi tiếp xúc dữ liệu thật, nhưng **không** chặn khởi động W1 — W1 dựng bằng dữ liệu tổng hợp.
- Giảm allocation engineer trong 12–16 tuần field là kết quả **được chấp nhận trước**, không phải sự cố.
