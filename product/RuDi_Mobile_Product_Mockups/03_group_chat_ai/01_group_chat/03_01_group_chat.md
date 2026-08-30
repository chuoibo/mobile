# 03.01 — Nhóm chat

**Feature chính:** Nhóm chat & lên kế hoạch cùng AI  
**Asset:** `03_01_group_chat.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Không gian giao tiếp realtime của nhóm; AI xuất hiện như một thành viên hỗ trợ.

## 2. Cách đọc UI từ trên xuống dưới

1. Header Team Đà Lạt + member count.
2. Chat bubbles, reaction chips, timestamps.
3. Rủ Đi AI bubble.
4. Message composer + emoji/attachment.

## 3. User flow từng bước

1. Thành viên chat bình thường.
2. AI đọc context nhóm khi được gọi hoặc khi hệ thống phát hiện intent phù hợp.
3. Khi AI tạo object như itinerary/poll/expense, nên render card có CTA.

## 4. Hành vi hệ thống / AI

- AI phải tôn trọng privacy scope của group.
- Không tự thay đổi kế hoạch/chi phí khi chưa có confirm.
- Support optimistic send, retry, unread state.

## 5. Các state cần design/dev hỗ trợ

- `Sending`
- `Sent`
- `Failed`
- `AI typing`
- `AI result card`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_group_chat` — mở màn hình.
- `primary_action_group_chat` — hành động chính của màn.
- `error_group_chat` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Header đang ghi Team Đà Lạt 7 thành viên, lệch canonical 8 người.
- AI nói đã tạo lịch trình nhưng không render plan card/CTA “Xem kế hoạch”; production nên trả về interactive object thay vì chỉ text.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
