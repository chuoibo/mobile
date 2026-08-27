# Claude — W0, nháp đầu

**Nhánh:** `claude/p0-w0-field-protocol` · **protocol_version:** `v1` (DRAFT) · **Reviewer:** Codex

## Giao gì

`docs/protocol/v1/` — 5 file:

| File | Nội dung |
|---|---|
| `00-tong-quan-va-dinh-nghia.md` | 7 định nghĩa hoạt động + danh sách tham số bị ADR-0002 chặn |
| `01-giao-thuc-thuc-dia.md` | Baseline · tương đương · concierge · cấm-list operator · cây quyết định nhãn · wave/block/stopping · guardrail người gửi · an toàn tiền · đạo đức |
| `02-measurement-contract.md` | Ranh giới sự kiện quan sát vs trạng thái sản phẩm · trường bắt buộc/bị cấm · danh mục sự kiện · append-only · mẫu số · dữ liệu thiếu · khoá cohort |
| `03-preregistration.md` | Kết quả chính/phụ/guardrail · kế hoạch phân tích · lịch interim · ma trận chẩn đoán · **điều gì sẽ bác bỏ luận đề** |
| `04-ban-khai-thien-lech.md` | 10 thiên lệch đã biết, khai trước khi thu dữ liệu |

## Quyết định thiết kế đáng tranh luận — Codex xem kỹ mấy chỗ này

**1. `valid_cost_opportunity` neo vào baseline của chính nhóm, không dùng ngưỡng tiền tuyệt đối.**
35k đáng chia với nhóm này, không đáng với nhóm khác. Ngưỡng tuyệt đối sẽ sai ở cả hai đầu. Đánh đổi: mẫu số khác nhau giữa các nhóm, khó gộp. Tôi chấp nhận vì mẫu số sai nguy hiểm hơn mẫu số không đồng nhất.

**2. Hai đường xác định cơ hội, ưu tiên A (đăng ký trước lúc intake).**
Đường B (check-in trung lập sau cửa sổ) có recall bias — tôi khai thẳng. Lý do vẫn giữ B: nếu không có cách xác định cơ hội độc lập với việc dùng dịch vụ thì "không có cơ hội" thành lời bào chữa cho mọi lần không quay lại, và mẫu số sập.
*Chỗ tôi không chắc:* liệu check-in trung lập có prime người ta nghĩ tới chia tiền không. Tôi đã bỏ mọi từ khoá, gửi sau khi cửa sổ đóng, câu chữ giống hệt cho mọi nhóm. Vẫn có thể chưa đủ. **Đây là điểm tôi muốn bạn tấn công nhất.**

**3. Q1 (ngoài hợp đồng) và Q2 (dùng hiểu biết cá nhân) đứng TRƯỚC Q3 (tất định) trong cây quyết định nhãn.**
Q1 trước vì một hành động có thể vừa tất định vừa ngoài hợp đồng — tự nhắc khách vô danh là tất định nhưng sản phẩm không có quyền đó.
Q2 thứ hai vì đó là chế độ hỏng chính khi founder tự làm operator. Không hỏi sớm thì mọi thao tác sẽ rơi vào `model_plausible` và kết luận "AI làm được phần lớn" là giả.

**4. `kappa < 0.6` → nhãn không dùng để mở cổng.**
Ngưỡng này tôi lấy theo quy ước phổ biến, **không phải từ spec**. Nếu bạn thấy nên khác, đây là chỗ cần cãi trước khi đóng băng.

**5. Ngưỡng thu tiền đổi từ "sàn 50%" thành "≥ baseline của chính nhóm".**
Spec mục 15 ghi sàn thử nghiệm 50%, nhưng cũng ghi 50% là vô nghĩa nếu nhóm đó dùng Zalo đang đạt 70%. Tôi cho hai câu đó xung đột và chọn câu sau. **Đây là chỗ tôi cố ý lệch khỏi câu chữ của spec — cần verdict của bạn.**

**6. `indeterminate` là trạng thái bắt buộc của `opportunity_resolved`.**
Ép nhị phân sẽ đẩy mọi ca mơ hồ về phía có lợi cho sản phẩm.

**7. Mục 8 của `03-` ràng buộc lên chính leader.**
Leader không được đổi ngưỡng sau khi thấy kết quả. Cố ý viết vào một artifact leader phải ký.

## Chưa xong / bị chặn

- 🔴 **ADR-0002 chặn 5 tham số** đã liệt kê ở `00-` — số cohort, operator, audit độc lập, phạm vi counsel, có giữ ảnh bill không. Không chốt được `v1` nếu leader chưa chọn.
- 🟡 Script cụ thể cho từng phản hồi chuẩn của operator: chưa viết. Phụ thuộc W1 biết instrument trông thế nào. Sẽ vào `v1` trước khi đóng băng.
- 🟡 `failure-mode register` mới định nghĩa cấu trúc, chưa tạo file. Tạo khi Wave A bắt đầu.
- 🟡 Bộ câu hỏi khảo sát người gửi: chưa soạn. Thuộc W0 nhưng cần phối hợp W9 về consent.

## Review việc của Codex

W9a đang chạy trên `codex/p0-w9a-repo-guard` (worktree `/home/lakiet/mobile-codex`). Chưa có commit để review tại thời điểm viết. Review sẽ nằm ở `docs/claude/<ngày>/review-p0-w9a-repo-guard.md`.
