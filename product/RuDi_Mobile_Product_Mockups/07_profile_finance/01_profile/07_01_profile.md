# 07.01 — Hồ sơ cá nhân

**Feature chính:** Hồ sơ & tài chính cá nhân  
**Asset:** `07_01_profile.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Hồ sơ social cá nhân tổng hợp identity, sở thích, nhóm, địa điểm yêu thích và badge.

## 2. Cách đọc UI từ trên xuống dưới

1. Cover + avatar + edit.
2. Tên Tuấn Kiệt, username, bio.
3. Stats bạn bè/nhóm/chuyến đi/kỷ niệm.
4. Sở thích chips.
5. Nhóm nổi bật.
6. Địa điểm yêu thích.
7. Huy hiệu.

## 3. User flow từng bước

1. User mở profile → xem stats.
2. Edit → sửa avatar/bio/preferences.
3. Tap group/place/badge → detail tương ứng.

## 4. Hành vi hệ thống / AI

- Privacy setting cần kiểm soát phần nào public/friends/groups-only.
- Không expose finance ở public profile.

## 5. Các state cần design/dev hỗ trợ

- `Self profile`
- `Friend profile`
- `Private fields hidden`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_profile` — mở màn hình.
- `primary_action_profile` — hành động chính của màn.
- `error_profile` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Mục “Nhóm nổi bật” có group 128/96/76 thành viên, khiến scope giống public community. Với MVP nhóm bạn thân, nên dùng group nhỏ (5–10 người) hoặc ghi rõ đây là community feature P3.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
