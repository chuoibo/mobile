# Chất liệu của sổ (texture tiles)

Hai ô lặp 256×256, nền trong suốt, **sinh bằng script Pillow với seed cố định 20260905** (không chụp, không tải từ đâu; không chứa dữ liệu người hay ảnh thật). Đặt lên bề mặt bằng `ui/Grain.tsx` — một **lưới Image thường** (ô = PNG ở đúng pixel máy, tối đa 60 ô), không dùng `resizeMode="repeat"`: trên Android ảnh lặp được raster một lần theo cỡ view lúc yêu cầu, và trên bìa cao cả màn bitmap ra ngắn hơn view nên vân dừng ở một phần ba trên (bảng 2026-09-05). Opacity đo trên emulator ở 1x: **bìa 0.30, giấy 0.45 (đêm 0.30), trong con dấu 0.42** — 0.11/0.07 đọc như màu phẳng. Ô đen/trắng trung bình trung tính nên màu token bên dưới đo vẫn đúng trong một mức.

| File | Dùng cho | Cấu tạo |
|---|---|---|
| `vai-bia.png` | bìa indigo (`CoverBand`, Welcome) | dệt chéo sợi 2px sáng/tối + nhiễu ±18 alpha |
| `giay-trang.png` | trang giấy (`RudiScreen`) | 2600 đốm alpha 10–46 + 140 sợi giấy nâu mờ |

Provenance nhúng trong PNG (`imp embed-prompt`): câu mô tả + tên script sinh. Đổi seed hay tham số thì sinh lại, nhúng lại, ghim lại digest trong `.repo-guard-allowlist.json`.
