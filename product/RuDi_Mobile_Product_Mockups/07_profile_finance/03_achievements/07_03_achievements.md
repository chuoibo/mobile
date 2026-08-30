# 07.03 — Thành tích

**Feature chính:** Hồ sơ & tài chính cá nhân  
**Asset:** `07_03_achievements.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Gamification cho hoạt động đi chơi, check-in, bill splitting và khám phá.

## 2. Cách đọc UI từ trên xuống dưới

1. Profile Tuấn Kiệt + Level 7.
2. Stats 12 chuyến đi, 34 check-in, 18 bill đã chia.
3. Progress 780/1000 tới Level 8.
4. Badge grid: Food Hunter, Trip Planner, Bill Hero, Photographer, Night Owl, Explorer + locked badges.
5. Weekly challenges 2/3, 1/1 complete, 1/2.
6. CTA Xem tất cả thành tích.

## 3. User flow từng bước

1. Hoạt động hợp lệ → award points/progress.
2. Challenge đạt threshold → completed state + reward/XP.
3. Tap badge → criteria/detail.

## 4. Hành vi hệ thống / AI

- Cần anti-gaming rule cho check-in/bill spam.
- Achievement criteria phải deterministic và explainable.

## 5. Các state cần design/dev hỗ trợ

- `Locked`
- `In progress`
- `Unlocked`
- `Completed challenge`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_achievements` — mở màn hình.
- `primary_action_achievements` — hành động chính của màn.
- `error_achievements` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
