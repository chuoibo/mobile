# 04.03 — Check-in & theo dõi nhóm

**Feature chính:** Kèo đi chơi & quản lý chuyến đi  
**Asset:** `04_03_check_in.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Theo dõi ai đã đến, vị trí đang được chia sẻ có kiểm soát và điểm đến tiếp theo.

## 2. Cách đọc UI từ trên xuống dưới

1. 4/8 thành viên đã check-in + avatars +4.
2. Banner “Đang chia sẻ vị trí đến 11:30” + Dừng chia sẻ.
3. Map Quảng trường Lâm Viên.
4. Danh sách recent check-ins; Thanh Phúc chưa check-in.
5. Next destination Still Cafe 10:00.
6. CTA Nhắc thành viên, Chia vị trí trực tiếp, Đánh dấu thủ công.

## 3. User flow từng bước

1. Member check-in hoặc organizer đánh dấu thủ công.
2. Nếu bật live location, hiển thị expiration time và stop control.
3. Organizer nhắc người chưa check-in.
4. Next destination dẫn sang map/plan.

## 4. Hành vi hệ thống / AI

- Location sharing phải explicit opt-in và time-bounded.
- Đánh dấu thủ công nên yêu cầu chọn cụ thể member, không auto mark all.

## 5. Các state cần design/dev hỗ trợ

- `Location off`
- `Sharing active`
- `Checked in`
- `Not checked in`
- `Manual override`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_check_in` — mở màn hình.
- `primary_action_check_in` — hành động chính của màn.
- `error_check_in` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
