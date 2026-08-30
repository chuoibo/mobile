# 01.02 — Đăng ký / Đăng nhập

**Feature chính:** Bắt đầu cùng Rủ Đi  
**Asset:** `01_02_login.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Cho phép người dùng xác thực bằng Google, Apple hoặc số điện thoại với hierarchy tập trung hoàn toàn vào authentication.

## 2. Cách đọc UI từ trên xuống dưới

1. Greeting “Chào bạn 👋”.
2. Ba phương thức đăng nhập: Google, Apple, Số điện thoại.
3. Link “Tạo ngay” cho người chưa có tài khoản.
4. Điều khoản sử dụng và Chính sách bảo mật ở cuối màn.

## 3. User flow từng bước

1. Chọn provider → thực hiện OAuth/OTP.
2. Thành công → nếu user mới chuyển Personalization; nếu user cũ vào Home.
3. Thất bại → hiển thị lỗi tại chỗ và cho retry.

## 4. Hành vi hệ thống / AI

- Không trộn feature marketing với phương thức đăng nhập.
- Apple Sign In nên xuất hiện trên iOS; Android có thể giữ nếu sản phẩm hỗ trợ.
- Phone flow cần OTP, rate limit và resend timer.

## 5. Các state cần design/dev hỗ trợ

- `Loading provider`
- `OAuth canceled`
- `OTP requested`
- `OTP invalid/expired`
- `Success`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_login` — mở màn hình.
- `primary_action_login` — hành động chính của màn.
- `error_login` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
