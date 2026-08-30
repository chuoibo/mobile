# 04.02 — Lịch trình chuyến đi

**Feature chính:** Kèo đi chơi & quản lý chuyến đi  
**Asset:** `04_02_trip_timeline.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Hiển thị kế hoạch chuyến đi theo timeline ngày/giờ và cho phép chỉnh sửa/chia sẻ.

## 2. Cách đọc UI từ trên xuống dưới

1. Trip title + date + 8 người.
2. Tabs Tổng quan/Lịch trình/Chi phí/Thành viên.
3. Day sections.
4. Activity rows theo thời gian với icon.
5. Floating + để thêm activity.
6. CTA Chỉnh sửa và Chia sẻ lịch trình.

## 3. User flow từng bước

1. Mở outing → Lịch trình.
2. Tap activity để xem/edit details.
3. Tap + để thêm stop.
4. Reorder/time edit → save → notify group nếu thay đổi quan trọng.

## 4. Hành vi hệ thống / AI

- Time conflicts nên được cảnh báo.
- Place activities nên link place detail.
- Nếu offline, cache itinerary read-only.

## 5. Các state cần design/dev hỗ trợ

- `View`
- `Editing`
- `Unsaved changes`
- `Conflict warning`
- `Shared`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_trip_timeline` — mở màn hình.
- `primary_action_trip_timeline` — hành động chính của màn.
- `error_trip_timeline` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Ảnh dùng 17–19/10/2025, trong khi canonical hiện là 17–19/10/2026. Nội dung 8 người đúng nhưng năm cần cập nhật nếu cùng journey.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
