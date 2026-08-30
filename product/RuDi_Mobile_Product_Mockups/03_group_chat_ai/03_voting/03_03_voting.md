# 03.03 — Bình chọn & chốt plan

**Feature chính:** Nhóm chat & lên kế hoạch cùng AI  
**Asset:** `03_03_voting.png`  
**Trạng thái audit:** ⚠️ NEEDS UPDATE

## 1. Mục tiêu của màn hình

Giúp nhóm ra quyết định về địa điểm/hoạt động mà không phải tranh luận dài trong chat.

## 2. Cách đọc UI từ trên xuống dưới

1. Tabs Bình chọn / Tổng kết.
2. Poll card theo câu hỏi.
3. Các option + progress bar + vote count.
4. Countdown.
5. Crown cho option dẫn đầu.
6. CTA Chốt kế hoạch.

## 3. User flow từng bước

1. Member chọn option → submit vote.
2. Sau vote hiển thị lựa chọn của chính user.
3. Khi poll đóng hoặc organizer chốt sớm theo rule → winner được đưa vào plan.

## 4. Hành vi hệ thống / AI

- Before vote phải dùng radio/selection state.
- After vote mới show result hoặc show cả hai nhưng cần “Bạn đã chọn…”.
- Chỉ organizer/admin có CTA chốt nếu sản phẩm dùng quyền vai trò.

## 5. Các state cần design/dev hỗ trợ

- `Open-not-voted`
- `Open-voted`
- `Closed`
- `Tie`
- `Organizer-finalized`

## 6. Quy tắc UX / dữ liệu

- Mọi CTA phải có loading/disabled state khi request đang chạy.
- Không thay đổi dữ liệu nhóm, kế hoạch hoặc tiền bạc từ AI mà không có confirm khi hành động có hậu quả.
- Text, số tiền, số người và ngày tháng phải lấy từ một source of truth; không hardcode rời rạc giữa các màn.
- Accessibility: touch target tối thiểu ~44pt, contrast đủ, trạng thái không chỉ phân biệt bằng màu.

## 7. Analytics gợi ý

- `screen_view_voting` — mở màn hình.
- `primary_action_voting` — hành động chính của màn.
- `error_voting` — lỗi thao tác/network/validation nếu có.

## 8. Audit / conflict hiện tại

- Ảnh vừa ghi “Chọn 1 lựa chọn” vừa hiển thị kết quả vote nhưng không cho biết user đã vote hay chưa.
- CTA “Chốt kế hoạch” xuất hiện khi countdown vẫn đang chạy; cần rule rõ organizer có được chốt sớm hay không.

## 9. Acceptance criteria tối thiểu

- [ ] User hiểu được mục tiêu chính của màn trong vài giây.
- [ ] CTA chính dẫn đúng bước tiếp theo trong product loop.
- [ ] Data hiển thị nhất quán với entity nguồn.
- [ ] Có loading / empty / error / retry khi màn phụ thuộc network.
- [ ] Nếu có AI suggestion, user biết đó là gợi ý và có quyền chỉnh/confirm.
- [ ] Nếu có location/payment/privacy, quyền và trạng thái được thể hiện rõ.
