# 06.03 — Thả khoảnh khắc

**Feature chính:** Kỷ niệm của nhóm  
**Asset:** `06_03_share_moment.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Quick composer kiểu Locket/polaroid để chia sẻ một khoảnh khắc trực tiếp vào group.

## 2. Cách đọc UI từ trên xuống dưới

1. Title Thả khoảnh khắc.
2. Polaroid photo preview + caption “Đà Lạt về đêm ✨”.
3. Text box 0/300.
4. Target Team Đà Lạt · 8 thành viên · Nhóm riêng tư.
5. Toggle hiển thị ngay trên tường nhóm.
6. CTA Chia sẻ ngay vào nhóm.

## 3. User flow từng bước

1. Chụp/chọn ảnh → preview → caption → chọn group → toggle wall → Share.
2. Sau upload thành công, item xuất hiện trong Moments và tùy toggle có mặt trên wall.

## 4. Hành vi hệ thống / AI

- Nếu upload fail giữ draft local.
- Group picker chỉ hiện group user có quyền post.

## 5. Các state cần design/dev hỗ trợ

- `Draft`
- `Uploading`
- `Shared`
- `Failed`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_share_moment` — mở màn hình.
- `primary_action_share_moment` — hành động chính của màn.
- `error_share_moment` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
