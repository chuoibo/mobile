# 02.03 — Chi tiết địa điểm

**Feature chính:** Khám phá & gợi ý địa điểm  
**Asset:** `02_03_place_detail.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Hiển thị đầy đủ thông tin venue và giải thích vì sao AI đề xuất.

## 2. Cách đọc UI từ trên xuống dưới

1. Hero gallery + favorite.
2. Tên địa điểm, rating, review count, khoảng cách.
3. Địa chỉ, giờ mở cửa, price range.
4. Tag ambience/nhóm đông/outdoor.
5. Card “Vì sao AI gợi ý địa điểm này?”.
6. Map preview.
7. CTA Chỉ đường và Lưu địa điểm.

## 3. User flow từng bước

1. Mở từ Explore/AI Match.
2. Xem lý do match + thông tin thực tế.
3. Lưu hoặc mở chỉ đường.
4. Production nên thêm CTA Đề xuất cho nhóm / Thêm vào kèo.

## 4. Hành vi hệ thống / AI

- Opening-hours state phải đổi theo giờ hiện tại.
- Nếu venue đóng cửa, CTA cần cảnh báo.
- Nếu đã ở trong một outing context, ưu tiên CTA Add to Plan.

## 5. Các state cần design/dev hỗ trợ

- `Open`
- `Closed`
- `Saved`
- `Added-to-plan (recommended future state)`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_place_detail` — mở màn hình.
- `primary_action_place_detail` — hành động chính của màn.
- `error_place_detail` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Thiếu CTA trực tiếp “Thêm vào kèo” hoặc “Đề xuất cho nhóm”; hiện chỉ có Chỉ đường + Lưu địa điểm nên chưa khép core loop Discover → Plan.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
