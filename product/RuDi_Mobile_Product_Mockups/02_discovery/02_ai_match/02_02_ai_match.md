# 02.02 — AI Match / tìm kiếm tự nhiên

**Feature chính:** Khám phá & gợi ý địa điểm  
**Asset:** `02_02_ai_match.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Biến câu tìm kiếm tự nhiên thành ranking địa điểm phù hợp sở thích, budget, thời gian và nhóm.

## 2. Cách đọc UI từ trên xuống dưới

1. Natural-language query “quán chill view đẹp ở Đà Lạt budget 250k/người”.
2. Filter button.
3. Các result card với AI Match %, tags, giá, rating, distance và Save.
4. Dòng giải thích AI Match dựa trên sở thích nhóm, ngân sách, thời gian, địa điểm, thời tiết, đánh giá.

## 3. User flow từng bước

1. User nhập câu tự nhiên → parser trích intent/constraint.
2. Recommendation service rank địa điểm.
3. User mở card → Place Detail; hoặc Save.
4. User chỉnh filter → rerank.

## 4. Hành vi hệ thống / AI

- AI Match nên được hiểu là match score, không nên trình bày như xác suất nếu chưa calibration.
- Phải cho user biết recommendation đang dùng group nào.

## 5. Các state cần design/dev hỗ trợ

- `Parsing`
- `Searching`
- `Results`
- `No match`
- `Filter changed`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_ai_match` — mở màn hình.
- `primary_action_ai_match` — hành động chính của màn.
- `error_ai_match` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Ảnh ghi “kết quả … cho nhóm bạn (6 người)” trong khi canonical trip hiện dùng 8 người. Nếu đây là cùng journey nên đổi thành 8 hoặc cho phép chọn subgroup rõ ràng.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
