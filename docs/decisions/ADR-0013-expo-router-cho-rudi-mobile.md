# ADR-0013 - Expo Router cho RuDi Mobile

- **Trạng thái:** ĐÃ CHẤP NHẬN 2026-09-01, Lead duyệt trong kế hoạch UI RuDi
- **Ngày:** 2026-09-01
- **DRI:** Codex theo uỷ quyền trực tiếp của Lead cho `apps/mobile/`
- **Phạm vi:** chỉ app Expo; không đổi API, database, allocator hay guest web

## Bối cảnh

App hiện dùng `AppRoot.tsx` và `VoTab.tsx` như một state machine điều hướng. Cách
này đủ cho PoC ban đầu nhưng không còn phù hợp khi cùng một hành trình có 21 màn,
deep link, back stack, modal tạo mới và bằng chứng native trên Android/iOS. Nhiều
màn chỉ có thể mở qua fragment QA riêng; system Back và cold start không có một
hợp đồng route thống nhất.

Expo SDK 57 và React Native 0.86 đã luôn chạy New Architecture. Quyết định này
không thêm cờ `newArchEnabled` và không dùng việc đổi kiến trúc runtime làm lý do
viết lại nghiệp vụ.

## Quyết định

1. Entry point chuyển sang `expo-router/entry`; route file là hợp đồng điều hướng.
2. Dùng `Stack` và `Tabs` ổn định. Không đưa `ExperimentalStack` hay
   `unstable-native-tabs` vào đường quan trọng.
3. Bốn destination cấp cao là Khám phá, Lên plan, Tin nhắn và Cá nhân. Nút tạo là
   một action nổi mở modal, không phải destination thứ năm.
4. Fragment QA cũ được đọc đúng một lần và ánh xạ sang route mới. Link mới dùng
   scheme `rudi://` và pathname có type.
5. Screen mới chỉ thay view và orchestration. Domain, API client, allocator và các
   test hành vi cũ không bị xoá để làm cho migration dễ hơn.

## Hệ quả và đường lùi

- Back stack, cold start và modal có một nguồn sự thật; từng mockup có thể mở trực
  tiếp để chụp native.
- Thêm dependency Router và React Navigation do Router quản lý; package được ghim
  theo bundled versions của SDK 57.
- Tab bar được cô lập trong một layout. Sau này có thể chuyển sang NativeTabs mà
  không đổi route hoặc screen nếu API đó ổn định.
- Đường lùi là trả `main` về `index.ts`; `App.tsx`, `AppRoot` và `VoTab` vẫn còn
  nguyên trong migration này.

## Cái ADR này không chứng minh

- Có Router không chứng minh UI đẹp hay deep link production an toàn.
- EAS export xanh không chứng minh app đã chạy trên iPhone/iPad.
- Fixture canonical chỉ là dữ liệu demo, không phải bằng chứng backend hay người
  dùng thật.
