# 01.01 — Welcome / Màn hình chào

**Feature chính:** Bắt đầu cùng Rủ Đi  
**Asset:** `01_01_welcome.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Giới thiệu giá trị cốt lõi của Rủ Đi và tạo điểm bắt đầu rõ ràng trước khi người dùng đăng nhập.

## 2. Cách đọc UI từ trên xuống dưới

1. Hero hình nhóm bạn đi chơi tạo cảm xúc social/travel.
2. Logo Rủ Đi + tagline truyền tải định vị AI-first.
3. CTA chính “Rủ Đi thôi!” để bắt đầu onboarding.
4. CTA phụ “Tìm hiểu thêm” dành cho người chưa sẵn sàng đăng ký.
5. Page indicator thể hiện đây là bước đầu của onboarding.

## 3. User flow từng bước

1. Mở app lần đầu → xem Welcome.
2. Nhấn CTA chính → chuyển sang Đăng ký/Đăng nhập.
3. Nhấn CTA phụ → mở phần giải thích ngắn về giá trị ứng dụng.

## 4. Hành vi hệ thống / AI

- Không yêu cầu quyền hệ thống ở màn này.
- Không tự tạo tài khoản hoặc lưu thông tin nhạy cảm trước khi người dùng chủ động tiếp tục.

## 5. Các state cần design/dev hỗ trợ

- `First launch`
- `Returning logged-out user`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_welcome` — mở màn hình.
- `primary_action_welcome` — hành động chính của màn.
- `error_welcome` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
