# Chất liệu của sổ (texture tiles)

Hai ô lặp 256×256, nền trong suốt, **sinh bằng script Pillow với seed cố định 20260905** (không chụp, không tải từ đâu; không chứa dữ liệu người hay ảnh thật). Đặt lên bề mặt bằng `Image resizeMode="repeat"` với opacity thấp (bìa ~0.10, giấy ~0.07); chúng là lớp «vật liệu» đọc được ở 1x mà không đổi số đo màu token bên dưới.

| File | Dùng cho | Cấu tạo |
|---|---|---|
| `vai-bia.png` | bìa indigo (`CoverBand`, Welcome) | dệt chéo sợi 2px sáng/tối + nhiễu ±18 alpha |
| `giay-trang.png` | trang giấy (`RudiScreen`) | 2600 đốm alpha 10–46 + 140 sợi giấy nâu mờ |

Provenance nhúng trong PNG (`imp embed-prompt`): câu mô tả + tên script sinh. Đổi seed hay tham số thì sinh lại, nhúng lại, ghim lại digest trong `.repo-guard-allowlist.json`.
