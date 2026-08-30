# 07.02 — Tài chính cá nhân

**Feature chính:** Hồ sơ & tài chính cá nhân  
**Asset:** `07_02_finance.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Dashboard tổng hợp tiền đã trả, còn nhận, còn phải trả và lịch sử giao dịch theo chuyến đi.

## 2. Cách đọc UI từ trên xuống dưới

1. Cards Đã trả 2.100.000đ / Còn nhận 530.000đ / Còn phải trả 120.000đ.
2. Breakdown tháng theo Ăn uống, Di chuyển, Cafe, Vui chơi.
3. Recent transactions.
4. Quick actions Tạo VietQR, Nhắc thanh toán, Xem lịch sử.

## 3. User flow từng bước

1. Mở Finance → xem outstanding.
2. Tap transaction → expense/settlement detail.
3. QR action phải contextual theo khoản nhận cụ thể.
4. Reminder chỉ gửi cho pending debt hợp lệ.

## 4. Hành vi hệ thống / AI

- Màu semantic nên cố định toàn app: settled/positive, incoming, outgoing, overdue.
- Amounts derive từ ledger, không hardcode.

## 5. Các state cần design/dev hỗ trợ

- `No debt`
- `Receivable`
- `Payable`
- `Mixed`
- `Settled`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_finance` — mở màn hình.
- `primary_action_finance` — hành động chính của màn.
- `error_finance` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
