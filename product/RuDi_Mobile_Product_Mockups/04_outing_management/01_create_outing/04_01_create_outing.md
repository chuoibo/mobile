# 04.01 — Tạo kèo đi chơi

**Feature chính:** Kèo đi chơi & quản lý chuyến đi  
**Asset:** `04_01_create_outing.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Tạo outing chính thức cho một nhóm với ngày, địa điểm, số người và ngân sách.

## 2. Cách đọc UI từ trên xuống dưới

1. Group: Team Đà Lạt.
2. Tên kèo: Đà Lạt cuối tuần.
3. 17/10/2026–19/10/2026.
4. 8 người.
5. Địa điểm Đà Lạt.
6. Budget 2.500.000đ/người với chip 2.5 triệu selected.
7. Ghi chú, phương tiện, CTA Tạo kèo.

## 3. User flow từng bước

1. Chọn group → đặt tên → ngày → số người → địa điểm → budget → note/transport → Tạo kèo.
2. Sau tạo, app mở Overview/Timeline và gửi notification cho member.

## 4. Hành vi hệ thống / AI

- Validate end_date >= start_date.
- Budget chip và input phải đồng bộ hai chiều.
- Member count nên mặc định từ group nhưng cho phép subset.

## 5. Các state cần design/dev hỗ trợ

- `Draft`
- `Validation error`
- `Created`
- `Invite pending`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_create_outing` — mở màn hình.
- `primary_action_create_outing` — hành động chính của màn.
- `error_create_outing` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
