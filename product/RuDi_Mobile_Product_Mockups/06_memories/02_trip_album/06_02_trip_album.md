# 06.02 — Album chuyến đi

**Feature chính:** Kỷ niệm của nhóm  
**Asset:** `06_02_trip_album.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Gom ảnh/video/check-in theo ngày và highlight; số liệu đã được sửa để cộng đúng.

## 2. Cách đọc UI từ trên xuống dưới

1. Trip Đà Lạt 2026, 17–19/10/2026, 8 người.
2. Stats 256 ảnh, 18 video, 12 check-in.
3. Day 1: 96/6/5; Day 2: 84/6/4; Day 3: 76/6/3.
4. Khoảnh khắc nổi bật.
5. CTA Thêm ảnh/video.

## 3. User flow từng bước

1. Mở Album từ Group Wall/Trip.
2. Browse theo ngày hoặc highlight.
3. Tap thumbnail để mở media viewer.
4. Thêm ảnh/video → upload và gắn trip/day metadata.

## 4. Hành vi hệ thống / AI

- Counts phải được derive từ data thật.
- Duplicate media nên dedupe bằng file hash/perceptual match.

## 5. Các state cần design/dev hỗ trợ

- `Empty album`
- `Uploading`
- `Processing`
- `Ready`
- `Upload failed`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_trip_album` — mở màn hình.
- `primary_action_trip_album` — hành động chính của màn.
- `error_trip_album` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
