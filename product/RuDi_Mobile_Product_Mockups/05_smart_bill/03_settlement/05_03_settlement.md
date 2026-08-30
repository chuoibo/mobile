# 05.03 — Kết quả thanh toán / Settlement

**Feature chính:** Chia bill thông minh  
**Asset:** `05_03_settlement.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Tối ưu net settlement để giảm số lần chuyển khoản và theo dõi paid/pending.

## 2. Cách đọc UI từ trên xuống dưới

1. Trip total 3.840.000đ, 8 người.
2. 4 optimized transfer rows với receiver/payer/amount/status.
3. Paid vs pending chips.
4. Progress card.
5. VietQR + reminder actions.

## 3. User flow từng bước

1. Engine aggregate mọi expense đã confirm → net balances → minimize transfers.
2. Mỗi user chỉ thấy CTA phù hợp: trả tiền cho receiver hoặc tạo QR nhận tiền.
3. Khi payment confirmed → cập nhật progress và ledger.

## 4. Hành vi hệ thống / AI

- Settlement phải derive từ ledger đã confirm.
- QR/payment CTA phải theo current user và một receiver cụ thể; không dùng một QR chung cho nhiều tài khoản.
- Khi expense bị sửa sau settlement, hệ thống cần recompute balances và lưu audit trail.

## 5. Các state cần design/dev hỗ trợ

- `Pending`
- `Paid`
- `Partially settled`
- `All settled`
- `Disputed/corrected expense`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_settlement` — mở màn hình.
- `primary_action_settlement` — hành động chính của màn.
- `error_settlement` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Ảnh là bản stale: trạng thái ghi “4 / 4 giao dịch” nhưng bên dưới lại “2 đã thanh toán, 2 chờ thanh toán”. Đúng phải là “2 / 4 đã thanh toán”.
- CTA “Tạo VietQR” quá generic dù có nhiều receiver; phải contextual theo current user/receiver.
- Ảnh chưa giải thích rõ 3.840.000đ là tổng chuyến đi và 1.280.000đ chỉ là một bill.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
