# Audit report — Rủ Đi mockup package

## 1. Kết quả tổng

- ZIP nguồn: **23 PNG**.
- Bộ mục tiêu: **21 màn hình = 7 feature × 3 sub-feature**.
- Đã giữ: **21 PNG**.
- Đã loại: **2 PNG cũ duplicate/conflict**.
- Không thiếu sub-feature nào trong bộ 21 màn đã thống nhất.

## 2. Ảnh bị loại

| Source file | Lý do |
|---|---|
| `ChatGPT Image Aug 30, 2026, 03_56_12 PM.png` | Old check-in: 4/6, year 2025, unsafe “Xác nhận có mặt đầy đủ”; replaced by corrected screen index 04. |
| `ChatGPT Image Aug 30, 2026, 03_56_44 PM.png` | Old album: day counts sum incorrectly (288 photos / 15 check-ins vs header 256 / 12); replaced by corrected album index 02. |

## 3. Các màn còn cần update logic nhưng được giữ

| Screen | Vấn đề |
|---|---|
| 02.02 AI Match / tìm kiếm tự nhiên | Ảnh ghi “kết quả … cho nhóm bạn (6 người)” trong khi canonical trip hiện dùng 8 người. Nếu đây là cùng journey nên đổi thành 8 hoặc cho phép chọn subgroup rõ ràng. |
| 02.03 Chi tiết địa điểm | Thiếu CTA trực tiếp “Thêm vào kèo” hoặc “Đề xuất cho nhóm”; hiện chỉ có Chỉ đường + Lưu địa điểm nên chưa khép core loop Discover → Plan. |
| 03.01 Nhóm chat | Header đang ghi Team Đà Lạt 7 thành viên, lệch canonical 8 người. |
| 03.01 Nhóm chat | AI nói đã tạo lịch trình nhưng không render plan card/CTA “Xem kế hoạch”; production nên trả về interactive object thay vì chỉ text. |
| 03.02 AI tạo lịch trình | Ảnh dùng 24–25/05/2025 và 7 thành viên; không khớp canonical trip 17–19/10/2026, 8 người. |
| 03.02 AI tạo lịch trình | Nếu đây là cùng end-to-end journey, cần regenerate/cập nhật data. |
| 03.03 Bình chọn & chốt plan | Ảnh vừa ghi “Chọn 1 lựa chọn” vừa hiển thị kết quả vote nhưng không cho biết user đã vote hay chưa. |
| 03.03 Bình chọn & chốt plan | CTA “Chốt kế hoạch” xuất hiện khi countdown vẫn đang chạy; cần rule rõ organizer có được chốt sớm hay không. |
| 04.02 Lịch trình chuyến đi | Ảnh dùng 17–19/10/2025, trong khi canonical hiện là 17–19/10/2026. Nội dung 8 người đúng nhưng năm cần cập nhật nếu cùng journey. |
| 05.02 AI nhận diện món & gán người | Header gọi “6 món” nhưng Phí phục vụ không phải món; nên dùng “6 khoản” hoặc “5 mục + 1 phí”. |
| 05.02 AI nhận diện món & gán người | Khăn lạnh x4 nhưng ghi chia đều 6 người là không tự nhiên; nên assign 4 người hoặc coi là phí chung không quantity. |
| 05.02 AI nhận diện món & gán người | Nhiều món chính đang assign cả 6 người, làm yếu killer feature “ai ăn gì”; production nên thể hiện phân bổ người khác nhau và confidence/confirm. |
| 05.03 Kết quả thanh toán / Settlement | Ảnh là bản stale: trạng thái ghi “4 / 4 giao dịch” nhưng bên dưới lại “2 đã thanh toán, 2 chờ thanh toán”. Đúng phải là “2 / 4 đã thanh toán”. |
| 05.03 Kết quả thanh toán / Settlement | CTA “Tạo VietQR” quá generic dù có nhiều receiver; phải contextual theo current user/receiver. |
| 05.03 Kết quả thanh toán / Settlement | Ảnh chưa giải thích rõ 3.840.000đ là tổng chuyến đi và 1.280.000đ chỉ là một bill. |
| 07.01 Hồ sơ cá nhân | Mục “Nhóm nổi bật” có group 128/96/76 thành viên, khiến scope giống public community. Với MVP nhóm bạn thân, nên dùng group nhỏ (5–10 người) hoặc ghi rõ đây là community feature P3. |

## 4. Missing so với bộ 21 mockup

**Không thiếu màn nào** so với scope 7 feature × 3 sub-feature đã thống nhất.

## 5. Missing so với full product backlog lớn hơn

Các feature dưới đây đã xuất hiện trong product feature list trước đó nhưng **chưa có mockup riêng trong bộ 21 màn**:
- Add Friend / Friend Request / QR Add Friend.
- Invite members / invite link flow riêng.
- Notifications center.
- Social Map / places friends visited.
- Meet-in-the-middle location optimizer.
- Automatic place detection / explicit check-in confirmation flow riêng.
- Bank/VietQR payment detail screen riêng cho từng payer/receiver.
- AI face/person enrollment và consent flow.
- Visual food/person attribution review chuyên sâu.
- Public social feed / public community (P3).
- AI trip summary / highlight reel.
- Group achievements riêng (khác personal achievements).

## 6. Product-loop coverage hiện tại

`Onboarding → Discover → AI Match → Place Detail → Group Chat → AI Plan → Vote → Create Outing → Timeline → Check-in → Receipt → OCR Assignment → Settlement → Group Wall → Album → Share Moment → Profile/Finance/Achievements`

Core loop được cover khá đầy đủ; các gap lớn nhất hiện tại nằm ở **friend graph**, **notification/payment detail**, và một số **AI vision consent/review flow**.
