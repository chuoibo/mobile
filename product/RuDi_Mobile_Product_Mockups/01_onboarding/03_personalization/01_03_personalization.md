# 01.03 — Cá nhân hóa sở thích

**Feature chính:** Bắt đầu cùng Rủ Đi  
**Asset:** `01_03_personalization.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Thu thập tín hiệu ban đầu để AI hiểu gu đi chơi, ngân sách và khả năng kết nối bạn bè.

## 2. Cách đọc UI từ trên xuống dưới

1. Các chip sở thích: ăn uống, cafe, nightlife, outdoor…
2. Budget preset theo đầu người.
3. Toggle đồng bộ danh bạ.
4. CTA Hoàn tất.

## 3. User flow từng bước

1. Chọn nhiều sở thích → chọn budget → tùy chọn sync contacts → Hoàn tất.
2. Nếu bật sync contacts, giải thích lợi ích trước rồi mới mở permission dialog của OS.

## 4. Hành vi hệ thống / AI

- Preferences là editable sau onboarding.
- Không bắt buộc sync contacts để hoàn tất.
- Nếu user bỏ qua budget, recommendation engine dùng default/unknown thay vì đoán cứng.

## 5. Các state cần design/dev hỗ trợ

- `Default`
- `Selected chips`
- `Permission pre-prompt`
- `Permission granted/denied`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_personalization` — mở màn hình.
- `primary_action_personalization` — hành động chính của màn.
- `error_personalization` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
