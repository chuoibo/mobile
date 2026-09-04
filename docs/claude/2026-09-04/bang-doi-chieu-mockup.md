# Bảng đối chiếu mockup ↔ emulator (2026-09-04)

21/21 mockup có ảnh emulator. Mockup là *decision comp*, không phải comp đã duyệt; ô ĐÃ CHỤP nghĩa là màn tồn tại trên máy và được một flow Maestro chụp, không nghĩa là khớp từng pixel.

- Máy: AVD rudi / Android 15 / 1080x2400@420, dev client com.lakiet.rudi 1.0.0
- Chế độ: L1 lượt M3 có khoá Gemini (chỉ dùng cho thẻ AI 03.02); L2 dark + font 1.3; L3 light + font 1.0 (bảng --otp); L4 bảng mặc định fixture (chỉ 01.03); L5 mini 22+26 light (26-tim-cau)
- Lượt (thư mục `<ngày><giờ>-<sha>` trong `.impeccable/review/native/`; lượt sau thắng khi trùng tên ảnh):
  - L1 = `d18d93c`, chụp 2026-09-04 lúc 05:28:33
  - L2 = `86a55fb`, chụp 2026-09-04 lúc 13:33:58
  - L3 = `c18cbe1`, chụp 2026-09-04 lúc 13:50:38
  - L4 = `b016ba1`, chụp 2026-09-04 lúc 14:06:52
  - L5 = `c6ff45c`, chụp 2026-09-04 lúc 14:19:25

| # | Màn hình | Audit mockup | Mockup | Ảnh emulator | Lượt | Trạng thái |
|---|---|---|---|---|---|---|
| 01.01 | Welcome / Màn hình chào | READY | `01_onboarding/01_welcome/01_01_welcome.png` | `2026-09-04_140705/00-smoke-deeplink/takeScreenshot/00-welcome.png` | L4 | ĐÃ CHỤP |
| 01.02 | Đăng ký / Đăng nhập | READY | `01_onboarding/02_login/01_02_login.png` | `2026-09-04_141933/22-dang-nhap-otp/takeScreenshot/22-man-dang-nhap.png` | L5 | ĐÃ CHỤP |
| 01.03 | Cá nhân hóa sở thích | READY | `01_onboarding/03_personalization/01_03_personalization.png` | `2026-09-04_140723/01-welcome-auth/takeScreenshot/01-personalization.png` | L4 | ĐÃ CHỤP |
| 02.01 | Khám phá địa điểm | READY | `02_discovery/01_explore/02_01_explore.png` | `2026-09-04_142030/26-kham-pha-that/takeScreenshot/26-danh-muc-that.png` | L5 | ĐÃ CHỤP |
| 02.02 | AI Match / tìm kiếm tự nhiên | NEEDS UPDATE | `02_discovery/02_ai_match/02_02_ai_match.png` | `2026-09-04_142030/26-kham-pha-that/takeScreenshot/26-tim-cau.png` | L5 | ĐÃ CHỤP |
| 02.03 | Chi tiết địa điểm | NEEDS UPDATE | `02_discovery/03_place_detail/02_03_place_detail.png` | `2026-09-04_142030/26-kham-pha-that/takeScreenshot/26-chi-tiet.png` | L5 | ĐÃ CHỤP |
| 03.01 | Nhóm chat | NEEDS UPDATE | `03_group_chat_ai/01_group_chat/03_01_group_chat.png` | `2026-09-04_140046/30-chat-that/takeScreenshot/30-phan-ung.png` | L3 | ĐÃ CHỤP |
| 03.02 | AI tạo lịch trình | NEEDS UPDATE | `03_group_chat_ai/02_ai_itinerary/03_02_ai_itinerary.png` | `2026-09-04_053713/40-ai-plan/takeScreenshot/40-ai-tra-loi.png` | L1 | ĐÃ CHỤP |
| 03.03 | Bình chọn & chốt plan | NEEDS UPDATE | `03_group_chat_ai/03_voting/03_03_voting.png` | `2026-09-04_140046/30-chat-that/takeScreenshot/30-binh-chon.png` | L3 | ĐÃ CHỤP |
| 04.01 | Tạo kèo đi chơi | READY | `04_outing_management/01_create_outing/04_01_create_outing.png` | `2026-09-04_135738/27-keo-that/takeScreenshot/27-tao-keo.png` | L3 | ĐÃ CHỤP |
| 04.02 | Lịch trình chuyến đi | NEEDS UPDATE | `04_outing_management/02_trip_timeline/04_02_trip_timeline.png` | `2026-09-04_135738/27-keo-that/takeScreenshot/27-hai-chang.png` | L3 | ĐÃ CHỤP |
| 04.03 | Check-in & theo dõi nhóm | READY | `04_outing_management/03_check_in/04_03_check_in.png` | `2026-09-04_135738/27-keo-that/takeScreenshot/27-da-toi.png` | L3 | ĐÃ CHỤP |
| 05.01 | Chụp bill / Xem lại hóa đơn | READY | `05_smart_bill/01_receipt_review/05_01_receipt_review.png` | `2026-09-04_135851/28-chia-bill-that/takeScreenshot/28-xem-lai.png` | L3 | ĐÃ CHỤP |
| 05.02 | AI nhận diện món & gán người | NEEDS UPDATE | `05_smart_bill/02_ocr_assignment/05_02_ocr_assignment.png` | `2026-09-04_135851/28-chia-bill-that/takeScreenshot/28-gan-mon.png` | L3 | ĐÃ CHỤP |
| 05.03 | Kết quả thanh toán / Settlement | NEEDS UPDATE | `05_smart_bill/03_settlement/05_03_settlement.png` | `2026-09-04_140005/29-dot-thu-that/takeScreenshot/29-quyet-toan-co-dot.png` | L3 | ĐÃ CHỤP |
| 06.01 | Tường nhóm riêng tư | READY | `06_memories/01_group_wall/06_01_group_wall.png` | `2026-09-04_140311/32-ky-niem-that/takeScreenshot/32-tim-binh-luan.png` | L3 | ĐÃ CHỤP |
| 06.02 | Album chuyến đi | READY | `06_memories/02_trip_album/06_02_trip_album.png` | `2026-09-04_140311/32-ky-niem-that/takeScreenshot/32-album-keo.png` | L3 | ĐÃ CHỤP |
| 06.03 | Thả khoảnh khắc | READY | `06_memories/03_share_moment/06_03_share_moment.png` | `2026-09-04_140311/32-ky-niem-that/takeScreenshot/32-tha-khoanh-khac.png` | L3 | ĐÃ CHỤP |
| 07.01 | Hồ sơ cá nhân | NEEDS UPDATE | `07_profile_finance/01_profile/07_01_profile.png` | `2026-09-04_135250/24-nhom-thanh-vien-va-ho-so/takeScreenshot/24-ho-so-da-sua.png` | L3 | ĐÃ CHỤP |
| 07.02 | Tài chính cá nhân | READY | `07_profile_finance/02_finance/07_02_finance.png` | `2026-09-04_140005/29-dot-thu-that/takeScreenshot/29-tai-chinh.png` | L3 | ĐÃ CHỤP |
| 07.03 | Thành tích | READY | `07_profile_finance/03_achievements/07_03_achievements.png` | `2026-09-04_140311/32-ky-niem-that/takeScreenshot/32-thanh-tich-cuoi.png` | L3 | ĐÃ CHỤP |

Không còn ô CHƯA CHỤP.
