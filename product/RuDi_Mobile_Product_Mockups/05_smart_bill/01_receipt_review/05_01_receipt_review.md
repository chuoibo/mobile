# 05.01 — Chụp bill / Xem lại hóa đơn

**Feature chính:** Chia bill thông minh  
**Asset:** `05_01_receipt_review.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Xác nhận ảnh hóa đơn trước khi OCR; tách rõ captured-preview state khỏi camera state.

## 2. Cách đọc UI từ trên xuống dưới

1. Title Xem lại hóa đơn.
2. Receipt preview trên nền gỗ + crop corners.
3. Ngày 17/10/2026 19:45.
4. 6 dòng item + tổng 1.280.000đ.
5. CTA Chụp lại / Dùng ảnh này.
6. Hint ảnh rõ nét, đủ sáng, không cắt góc.

## 3. User flow từng bước

1. User chụp ảnh ở camera screen trước đó → đến preview này.
2. Chụp lại → quay camera.
3. Dùng ảnh này → upload/process OCR.

## 4. Hành vi hệ thống / AI

- Không hiển thị shutter/flash ở preview state.
- Nên deskew/crop tự động nhưng cho user adjust nếu detect kém.

## 5. Các state cần design/dev hỗ trợ

- `Preview good`
- `Blur warning`
- `Corner missing`
- `Upload/OCR processing`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_receipt_review` — mở màn hình.
- `primary_action_receipt_review` — hành động chính của màn.
- `error_receipt_review` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
