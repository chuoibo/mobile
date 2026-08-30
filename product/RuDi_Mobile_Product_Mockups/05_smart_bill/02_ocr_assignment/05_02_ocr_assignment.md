# 05.02 — AI nhận diện món & gán người

**Feature chính:** Chia bill thông minh  
**Asset:** `05_02_ocr_assignment.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

OCR hóa đơn, chuẩn hóa line item và gợi ý người tham gia từng khoản trước khi tính tiền.

## 2. Cách đọc UI từ trên xuống dưới

1. Summary 6 khoản / 6 người / 1.280.000đ.
2. Exact prices khớp receipt: 450k, 560k, 75k, 45k, 20k, 130k.
3. Avatar participant chips trên từng item.
4. AI confidence badges.
5. CTA Chỉnh sửa tay / Xác nhận chia bill.

## 3. User flow từng bước

1. OCR parse → normalize quantity/price → AI propose participant assignment.
2. User review từng item → sửa nếu cần → Confirm.
3. Confirmed payload mới được ghi thành expense.

## 4. Hành vi hệ thống / AI

- Confidence thấp phải highlight và yêu cầu confirm.
- Phí dịch vụ nên chia theo rule explicit (equally/pro-rata).
- Không auto-charge chỉ dựa trên face recognition; luôn có confirm.

## 5. Các state cần design/dev hỗ trợ

- `OCR processing`
- `High-confidence`
- `Needs confirmation`
- `Manually edited`
- `Confirmed`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_ocr_assignment` — mở màn hình.
- `primary_action_ocr_assignment` — hành động chính của màn.
- `error_ocr_assignment` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Header gọi “6 món” nhưng Phí phục vụ không phải món; nên dùng “6 khoản” hoặc “5 mục + 1 phí”.
- Khăn lạnh x4 nhưng ghi chia đều 6 người là không tự nhiên; nên assign 4 người hoặc coi là phí chung không quantity.
- Nhiều món chính đang assign cả 6 người, làm yếu killer feature “ai ăn gì”; production nên thể hiện phân bổ người khác nhau và confidence/confirm.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
