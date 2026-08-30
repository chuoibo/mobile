# 06.01 — Tường nhóm riêng tư

**Feature chính:** Kỷ niệm của nhóm  
**Asset:** `06_01_group_wall.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Feed riêng của group để lưu ảnh, caption, reaction và comment sau chuyến đi.

## 2. Cách đọc UI từ trên xuống dưới

1. Header Team Đà Lạt + lock + 8 thành viên.
2. Tabs Tường nhóm/Album/Kế hoạch/Thành viên.
3. Post card với author, caption, photo grid.
4. Reaction count, comment count.
5. Actions Thích/Bình luận/Lưu kỷ niệm.

## 3. User flow từng bước

1. Member đăng post → group feed.
2. Tap image → viewer.
3. React/comment.
4. Lưu kỷ niệm → đánh dấu highlight/album tùy product rule.

## 4. Hành vi hệ thống / AI

- Privacy mặc định chỉ group members.
- Deleted member/content moderation cần policy.

## 5. Các state cần design/dev hỗ trợ

- `Loading`
- `Posting`
- `Posted`
- `Commenting`
- `Deleted`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_group_wall` — mở màn hình.
- `primary_action_group_wall` — hành động chính của màn.
- `error_group_wall` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
