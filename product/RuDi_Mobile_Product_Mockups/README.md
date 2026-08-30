# Rủ Đi — Mobile Product Mockups

Package đã được chuẩn hóa từ ZIP nguồn: **23 ảnh → 21 ảnh canonical theo cấu trúc 7 × 3**. Hai ảnh cũ bị duplicate/conflict đã được loại khỏi package.

## Cấu trúc

```text
RuDi_Mobile_Product_Mockups/
├── 00_product_docs/
├── 01_onboarding/
├── 02_discovery/
├── 03_group_chat_ai/
├── 04_outing_management/
├── 05_smart_bill/
├── 06_memories/
└── 07_profile_finance/
```

## Danh sách 21 màn hình

| # | Màn hình | Audit | Image | Spec |
|---:|---|---|---|---|
| 01.01 | Welcome / Màn hình chào | ✅ READY | `01_onboarding/01_welcome/01_01_welcome.png` | `01_onboarding/01_welcome/01_01_welcome.md` |
| 01.02 | Đăng ký / Đăng nhập | ✅ READY | `01_onboarding/02_login/01_02_login.png` | `01_onboarding/02_login/01_02_login.md` |
| 01.03 | Cá nhân hóa sở thích | ✅ READY | `01_onboarding/03_personalization/01_03_personalization.png` | `01_onboarding/03_personalization/01_03_personalization.md` |
| 02.01 | Khám phá địa điểm | ✅ READY | `02_discovery/01_explore/02_01_explore.png` | `02_discovery/01_explore/02_01_explore.md` |
| 02.02 | AI Match / tìm kiếm tự nhiên | ⚠️ NEEDS UPDATE | `02_discovery/02_ai_match/02_02_ai_match.png` | `02_discovery/02_ai_match/02_02_ai_match.md` |
| 02.03 | Chi tiết địa điểm | ⚠️ NEEDS UPDATE | `02_discovery/03_place_detail/02_03_place_detail.png` | `02_discovery/03_place_detail/02_03_place_detail.md` |
| 03.01 | Nhóm chat | ⚠️ NEEDS UPDATE | `03_group_chat_ai/01_group_chat/03_01_group_chat.png` | `03_group_chat_ai/01_group_chat/03_01_group_chat.md` |
| 03.02 | AI tạo lịch trình | ⚠️ NEEDS UPDATE | `03_group_chat_ai/02_ai_itinerary/03_02_ai_itinerary.png` | `03_group_chat_ai/02_ai_itinerary/03_02_ai_itinerary.md` |
| 03.03 | Bình chọn & chốt plan | ⚠️ NEEDS UPDATE | `03_group_chat_ai/03_voting/03_03_voting.png` | `03_group_chat_ai/03_voting/03_03_voting.md` |
| 04.01 | Tạo kèo đi chơi | ✅ READY | `04_outing_management/01_create_outing/04_01_create_outing.png` | `04_outing_management/01_create_outing/04_01_create_outing.md` |
| 04.02 | Lịch trình chuyến đi | ⚠️ NEEDS UPDATE | `04_outing_management/02_trip_timeline/04_02_trip_timeline.png` | `04_outing_management/02_trip_timeline/04_02_trip_timeline.md` |
| 04.03 | Check-in & theo dõi nhóm | ✅ READY | `04_outing_management/03_check_in/04_03_check_in.png` | `04_outing_management/03_check_in/04_03_check_in.md` |
| 05.01 | Chụp bill / Xem lại hóa đơn | ✅ READY | `05_smart_bill/01_receipt_review/05_01_receipt_review.png` | `05_smart_bill/01_receipt_review/05_01_receipt_review.md` |
| 05.02 | AI nhận diện món & gán người | ⚠️ NEEDS UPDATE | `05_smart_bill/02_ocr_assignment/05_02_ocr_assignment.png` | `05_smart_bill/02_ocr_assignment/05_02_ocr_assignment.md` |
| 05.03 | Kết quả thanh toán / Settlement | ⚠️ NEEDS UPDATE | `05_smart_bill/03_settlement/05_03_settlement.png` | `05_smart_bill/03_settlement/05_03_settlement.md` |
| 06.01 | Tường nhóm riêng tư | ✅ READY | `06_memories/01_group_wall/06_01_group_wall.png` | `06_memories/01_group_wall/06_01_group_wall.md` |
| 06.02 | Album chuyến đi | ✅ READY | `06_memories/02_trip_album/06_02_trip_album.png` | `06_memories/02_trip_album/06_02_trip_album.md` |
| 06.03 | Thả khoảnh khắc | ✅ READY | `06_memories/03_share_moment/06_03_share_moment.png` | `06_memories/03_share_moment/06_03_share_moment.md` |
| 07.01 | Hồ sơ cá nhân | ⚠️ NEEDS UPDATE | `07_profile_finance/01_profile/07_01_profile.png` | `07_profile_finance/01_profile/07_01_profile.md` |
| 07.02 | Tài chính cá nhân | ✅ READY | `07_profile_finance/02_finance/07_02_finance.png` | `07_profile_finance/02_finance/07_02_finance.md` |
| 07.03 | Thành tích | ✅ READY | `07_profile_finance/03_achievements/07_03_achievements.png` | `07_profile_finance/03_achievements/07_03_achievements.md` |

## Cách dùng package

1. Đọc `00_product_docs/CANONICAL_DATA.md` trước để hiểu dữ liệu chuẩn xuyên suốt journey.
2. Đọc `00_product_docs/AUDIT_REPORT.md` để biết màn nào có thể handoff ngay và màn nào chỉ là concept cần update.
3. Với mỗi màn, mở file PNG cạnh file Markdown cùng tên. Markdown là behavioral spec; PNG là visual reference.
4. Team Design nên sửa các mục `NEEDS UPDATE` trước khi freeze Figma production.
5. Team Dev không nên lấy text/số liệu hardcode từ PNG; dùng spec/data source thật.
