# 02.01 — Khám phá địa điểm

**Feature chính:** Khám phá & gợi ý địa điểm  
**Asset:** `02_01_explore.png`  
**Trạng thái audit:** ✅ READY

## 1. Mục tiêu của màn hình

Trang khám phá địa điểm local theo category, khoảng cách và hành vi lưu địa điểm.

## 2. Cách đọc UI từ trên xuống dưới

1. Search bar tìm địa điểm/món ăn/hoạt động.
2. Filter icon.
3. Category cards: Quán ăn local, Cafe, Playground, Đi chơi đêm.
4. Danh sách gợi ý với ảnh, rating, review count, distance và nút Save.
5. Bottom navigation với tab Khám phá đang active.

## 3. User flow từng bước

1. Nhập query hoặc chọn category.
2. Scroll danh sách → chạm card để mở Chi tiết địa điểm.
3. Heart → lưu vào Saved Places.
4. Filter → giới hạn khoảng cách, giá, giờ mở cửa, loại địa điểm.

## 4. Hành vi hệ thống / AI

- Kết quả cần location permission hoặc vị trí người dùng chọn thủ công.
- Rating/distance phải có nguồn dữ liệu rõ ràng.
- Bottom navigation phải được thống nhất ở design system toàn app.

## 5. Các state cần design/dev hỗ trợ

- `Loading`
- `Location denied`
- `Empty result`
- `Network error`
- `Saved/unsaved`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_explore` — mở màn hình.
- `primary_action_explore` — hành động chính của màn.
- `error_explore` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Không phát hiện conflict logic quan trọng trong phiên bản ảnh hiện tại.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
