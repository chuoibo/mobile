# 03.02 — AI tạo lịch trình

**Feature chính:** Nhóm chat & lên kế hoạch cùng AI  
**Asset:** `03_02_ai_itinerary.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Biến context nhóm thành itinerary có thời gian, hoạt động, ngân sách và khả năng chỉnh sửa.

## 2. Cách đọc UI từ trên xuống dưới

1. Title “Kế hoạch được AI tạo”.
2. Trip card Đà Lạt 2N1Đ — Chill & Foodie.
3. Ngày, số thành viên, budget/người.
4. Tabs Ngày 1 / Ngày 2.
5. Timeline theo giờ.
6. CTA Chỉnh sửa và Gửi nhóm.

## 3. User flow từng bước

1. AI generate draft → user review.
2. Chỉnh sửa nếu cần.
3. Gửi nhóm → tạo plan object trong group chat.
4. Group có thể chuyển tiếp sang Poll để quyết định các điểm chưa chốt.

## 4. Hành vi hệ thống / AI

- AI output luôn là draft cho đến khi organizer/group confirm.
- Mỗi activity nên chứa place_id để liên kết Discovery/Map.

## 5. Các state cần design/dev hỗ trợ

- `Generating`
- `Draft`
- `Edited`
- `Shared`
- `Generation failed`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_ai_itinerary` — mở màn hình.
- `primary_action_ai_itinerary` — hành động chính của màn.
- `error_ai_itinerary` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Ảnh dùng 24–25/05/2025 và 7 thành viên; không khớp canonical trip 17–19/10/2026, 8 người.
- Nếu đây là cùng end-to-end journey, cần regenerate/cập nhật data.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
