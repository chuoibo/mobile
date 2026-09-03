# Design

<!-- impeccable:design-schema 1 -->

Hệ thiết kế của **Rủ Đi**, rút từ mockup đã chốt chứ không tự chế. Nguồn số
duy nhất là `packages/shared/tokens.json`; file này mô tả và giải thích nó.
`.impeccable/design.json` là bản máy đọc, sinh ra từ chính tokens.json nên
mọi con số dưới đây là **tính ra**, không phải gõ tay.

> **Cách đo.** Màu lấy bằng script lấy mẫu điểm ảnh trên `mockup.png` và 5 tờ
> trong `features/`, lọc theo độ bão hoà và vùng màu, rồi lấy các màu xuất hiện
> nhiều nhất trong từng vùng. Không ước lượng bằng mắt. Màu đo được mà không
> đạt WCAG AA thì bị làm tối lại, giữ nguyên sắc và độ bão hoà, và **cả hai số
> đều ghi lại** ở mục "Sai lệch có chủ ý" bên dưới.

## Nền tảng

| | |
|---|---|
| Bề mặt | App Expo (`apps/mobile/`) và trang khách web (`services/api/app/web/`) |
| Nguồn token | `packages/shared/tokens.json`, một file, hai bề mặt đọc lại |
| Cổng giữ đồng bộ | `services/api/tests/web/test_shared_tokens.py` so từng token với `guest.css` |
| Chữ | System stack, không webfont |
| Chế độ | Sáng và tối, cả hai đều đo đủ |

## Ba tông mang nghĩa

Đây là quy ước có nghĩa, không phải bảng màu trang trí. Nhìn thấy màu là biết
đang ở phần nào:

| Tông | Token | Nghĩa |
|---|---|---|
| Cam | `accent` | Thương hiệu và hành động chính trong app |
| Teal | `split` | Chia bill, tiền, quyết toán |
| Tím | `ai` | Thứ do máy sinh ra, người còn sửa được |

**Một màn hình chỉ có MỘT tông dẫn.** Hai tông dẫn cùng lúc là lỗi, không phải
lựa chọn. Trang khách là mặt quyết toán, nên tông dẫn của nó là teal, không phải
cam, dù cam mới là màu thương hiệu.

## Màu, kèm số đo tương phản

46 cặp chữ trên nền mà hệ này thật sự dùng đều được đo. Thấp nhất **4.52:1**,
cao nhất **16.33:1**, không cặp nào dưới ngưỡng AA 4.5:1.

Bảng này chỉ đo **chữ**. Ranh giới của thành phần giao diện đi theo ngưỡng khác
và nằm ở mục "Sàn phi-chữ 3:1" bên dưới. Đọc thiếu mục đó là cách lỗi viền nút
1.21:1 đã lọt qua một lần.

### Chế độ sáng

| Cặp | Vai trò | Tỉ lệ | Ngưỡng |
|---|---|---|---|
| `ink` #1f2230 trên `ground` #feeee0 | Chữ thân trên nền trang | **13.93:1** | AAA |
| `ink` #1f2230 trên `card` #ffffff | Chữ thân trên thẻ | **15.79:1** | AAA |
| `inkSoft` #4e5563 trên `card` #ffffff | Chữ phụ trên thẻ | **7.49:1** | AAA |
| `inkSoft` #4e5563 trên `ground` #feeee0 | Chữ phụ trên nền | **6.61:1** | AA |
| `inkFaint` #676e7b trên `card` #ffffff | Chú thích trên thẻ | **5.13:1** | AA |
| `inkFaint` #676e7b trên `ground` #feeee0 | Chú thích trên nền | **4.52:1** | AA |
| `accent` #c93900 trên `card` #ffffff | Cam trên thẻ | **5.16:1** | AA |
| `accent` #c93900 trên `ground` #feeee0 | Cam trên nền | **4.55:1** | AA |
| `accentInk` #ffffff trên `accent` #c93900 | Nhãn trên nút cam | **5.16:1** | AA |
| `accent` #c93900 trên `accentSoft` #fff0ea | Cam trên chip cam nhạt | **4.65:1** | AA |
| `split` #00756b trên `card` #ffffff | Teal trên thẻ | **5.59:1** | AA |
| `split` #00756b trên `ground` #feeee0 | Teal trên nền | **4.93:1** | AA |
| `splitInk` #ffffff trên `split` #00756b | Nhãn trên nút teal | **5.59:1** | AA |
| `split` #00756b trên `splitSoft` #d5f5f0 | Teal trên chip teal nhạt | **4.83:1** | AA |
| `ai` #7d49ef trên `card` #ffffff | Tím trên thẻ | **5.16:1** | AA |
| `ai` #7d49ef trên `ground` #feeee0 | Tím trên nền | **4.55:1** | AA |
| `aiInk` #ffffff trên `ai` #7d49ef | Nhãn trên nút tím | **5.16:1** | AA |
| `ai` #7d49ef trên `aiSoft` #f5f1ff | Tím trên chip tím nhạt | **4.64:1** | AA |
| `warn` #c2410c trên `card` #ffffff | Cảnh báo trên thẻ | **5.18:1** | AA |
| `warn` #c2410c trên `ground` #feeee0 | Cảnh báo trên nền | **4.57:1** | AA |
| `ink` #1f2230 trên `accentSoft` #fff0ea | Chữ thân trên chip cam | **14.22:1** | AAA |
| `ink` #1f2230 trên `splitSoft` #d5f5f0 | Chữ thân trên chip teal | **13.65:1** | AAA |
| `ink` #1f2230 trên `aiSoft` #f5f1ff | Chữ thân trên chip tím | **14.22:1** | AAA |
### Chế độ tối

| Cặp | Vai trò | Tỉ lệ | Ngưỡng |
|---|---|---|---|
| `ink` #f7efe7 trên `ground` #17120f | Chữ thân trên nền trang | **16.33:1** | AAA |
| `ink` #f7efe7 trên `card` #221c18 | Chữ thân trên thẻ | **14.8:1** | AAA |
| `inkSoft` #c3b7ad trên `card` #221c18 | Chữ phụ trên thẻ | **8.58:1** | AAA |
| `inkSoft` #c3b7ad trên `ground` #17120f | Chữ phụ trên nền | **9.47:1** | AAA |
| `inkFaint` #8b8290 trên `card` #221c18 | Chú thích trên thẻ | **4.56:1** | AA |
| `inkFaint` #8b8290 trên `ground` #17120f | Chú thích trên nền | **5.04:1** | AA |
| `accent` #fb693e trên `card` #221c18 | Cam trên thẻ | **5.77:1** | AA |
| `accent` #fb693e trên `ground` #17120f | Cam trên nền | **6.37:1** | AA |
| `accentInk` #1c0d06 trên `accent` #fb693e | Nhãn trên nút cam | **6.48:1** | AA |
| `accent` #fb693e trên `accentSoft` #3a0b00 | Cam trên chip cam nhạt | **5.86:1** | AA |
| `split` #02a498 trên `card` #221c18 | Teal trên thẻ | **5.42:1** | AA |
| `split` #02a498 trên `ground` #17120f | Teal trên nền | **5.99:1** | AA |
| `splitInk` #04201d trên `split` #02a498 | Nhãn trên nút teal | **5.5:1** | AA |
| `split` #02a498 trên `splitSoft` #002320 | Teal trên chip teal nhạt | **5.36:1** | AA |
| `ai` #9667ff trên `card` #221c18 | Tím trên thẻ | **4.55:1** | AA |
| `ai` #9667ff trên `ground` #17120f | Tím trên nền | **5.03:1** | AA |
| `aiInk` #150a30 trên `ai` #9667ff | Nhãn trên nút tím | **5.08:1** | AA |
| `ai` #9667ff trên `aiSoft` #221046 | Tím trên chip tím nhạt | **4.62:1** | AA |
| `warn` #df5c2f trên `card` #221c18 | Cảnh báo trên thẻ | **4.58:1** | AA |
| `warn` #df5c2f trên `ground` #17120f | Cảnh báo trên nền | **5.05:1** | AA |
| `ink` #f7efe7 trên `accentSoft` #3a0b00 | Chữ thân trên chip cam | **15.03:1** | AAA |
| `ink` #f7efe7 trên `splitSoft` #002320 | Chữ thân trên chip teal | **14.63:1** | AAA |
| `ink` #f7efe7 trên `aiSoft` #221046 | Chữ thân trên chip tím | **15.0:1** | AAA |
## Sàn phi-chữ 3:1 (WCAG 1.4.11)

Bảng 46 cặp bên trên chỉ đo **chữ trên nền**. Nó không đo một dòng nào cho
token `line`, và đó là một lỗ thật chứ không phải thiếu sót hình thức: nút
`quiet` không có nền (`backgroundColor: "transparent"`), nên **viền là thứ duy
nhất cho biết nó là nút**. Viền đó vẽ bằng `line`, đo được **1.21:1** trên nền
trang. Một cổng chỉ đo chữ báo xanh hoàn hảo trong khi cái nút gần như vô hình.

WCAG 1.4.11 đòi **3:1** cho ranh giới của **thành phần giao diện**, tức thứ
người ta bấm được. Nó **không** đòi gì ở cạnh trang trí của một container. Hai
ngưỡng khác nhau thì cần hai token, nên `line` tách làm hai:

| Token | Việc của nó | Sàn |
|---|---|---|
| `line` | Cạnh thẻ, đường kẻ chia, rãnh trích dẫn. Container, không phải control | không có sàn, cố ý giữ mềm theo mockup |
| `lineStrong` | Ranh giới của thứ bấm được: nút quiet, ô nhập, chip chưa chọn, con trượt thanh cuộn | **3:1 trên mọi nền nó nằm lên** |

### Chế độ sáng

| Cặp | Vai trò | Tỉ lệ | Ngưỡng |
|---|---|---|---|
| `lineStrong` #ac7f56 trên `ground` #feeee0 | Viền control trên nền trang | **3.13:1** | 1.4.11 |
| `lineStrong` #ac7f56 trên `card` #ffffff | Viền control trên thẻ | **3.54:1** | 1.4.11 |
| `line` #e7dace trên `ground` #feeee0 | Cạnh thẻ trên nền trang | **1.21:1** | trang trí |
| `line` #e7dace trên `card` #ffffff | Đường kẻ trong thẻ | **1.37:1** | trang trí |

### Chế độ tối

| Cặp | Vai trò | Tỉ lệ | Ngưỡng |
|---|---|---|---|
| `lineStrong` #716962 trên `ground` #17120f | Viền control trên nền trang | **3.45:1** | 1.4.11 |
| `lineStrong` #716962 trên `card` #221c18 | Viền control trên thẻ | **3.13:1** | 1.4.11 |
| `line` #413c38 trên `ground` #17120f | Cạnh thẻ trên nền trang | **1.71:1** | trang trí |
| `line` #413c38 trên `card` #221c18 | Đường kẻ trong thẻ | **1.55:1** | trang trí |

Số của `line` ghi ra ở đây **chính vì nó không đạt 3:1**. Người sau đọc bảng
này phải thấy ngay nó đứng ở đâu, thay vì thấy một token không có số rồi dùng
nó cho một cái nút.

`lineStrong` được chọn bằng cách hạ lightness của `line` và **giữ nguyên sắc và
độ bão hoà**, đúng cách `accent` và `split` đã làm, nên nó vẫn là đường ấm cùng
họ với nền kem chứ không phải một đường xám lạc lõng.

**Cổng giữ nó**: `services/api/tests/web/test_contrast_floor.py` không kiểm token
trong bảng, nó **đọc token ra từ `Kit.tsx` và `guest.css` rồi mới đo**. Thêm một
token đạt chuẩn mà không component nào dùng thì test vẫn đỏ, và một control lặng
lẽ quay về `line` cũng đỏ. Chiều ngược lại cũng có cổng: đẩy cạnh thẻ lên
`lineStrong` để cho dễ pass thì test cũng đỏ.

### Tầng thương hiệu, đo riêng và giới hạn riêng

Bốn màu này giữ **nguyên số đo từ logo**, không chỉnh theo tương phản, vì chỉnh
là mất nhận diện. Đổi lại chúng bị giới hạn công dụng:

| Màu | Mã | Với chữ trắng | Với `ink` #1f2230 | Được phép dùng |
|---|---|---|---|---|
| `glow` | #fc7b37 | 2.62:1 | 6.04:1 | mảng lớn, logo, hero. Cấm chữ nhỏ |
| `coral` | #fb693e | 2.92:1 | 5.41:1 | mảng lớn, logo, hero. Cấm chữ nhỏ |
| `rose` | #e75262 | 3.63:1 | 4.35:1 | mảng lớn, logo, hero. Cấm chữ nhỏ |
| `violet` | #8350f6 | 4.73:1 | 3.34:1 | mảng lớn, logo, hero. Cấm chữ nhỏ |
| `actionGradient` | #c93900 → #c9344a | 5.16:1 / 5.16:1 | | nút chính, nhãn trắng an toàn cả dải |
Cam `coral` với chữ trắng chỉ đạt 2.92:1, dưới cả ngưỡng 3:1 của thành phần
giao diện. Nên **cấm đặt chữ nhỏ hoặc icon lên màu thương hiệu**. Cần chữ trên
nền cam thì dùng `actionGradient`, hai đầu đều 5.16:1 với nhãn trắng.

## Sai lệch có chủ ý so với màu đo được

Ghi lại để người sau kiểm được, không phải để biện minh:

| Token | Màu đo từ ảnh | Màu đang dùng | Lý do |
|---|---|---|---|
| `accent` (sáng) | `#fb693e` | `#c93900` | Màu đo được với chữ trắng chỉ 2.92:1. Làm tối tới khi đạt 5.16:1 |
| `split` (sáng) | `#04a89d` | `#00756b` | Đo được quá nhạt cho chữ trên thẻ trắng; và ở `#007b71` vẫn chỉ 4.46:1 trên chip teal nhạt |
| `ai` (sáng) | `#8350f6` | `#7d49ef` | Màu đo được đã đạt AA sẵn (4.73:1). Làm tối nhẹ để đứng cùng mức 5.16:1 với cam và teal, cho ba tông cân nhau |

Màu đo được vẫn còn nguyên trong `brand.*` cho mảng lớn, nên nhận diện không mất.

## Chữ

System stack là **quyết định có chủ ý**, không phải đi tắt: iOS ship SF Pro,
Android ship Roboto, cả hai render dấu tiếng Việt (ế ự ỡ ạ) đúng ở giá 0 byte.
Một webfont ở đây tốn LCP trên mạng di động và có rủi ro vỡ dấu, đổi lại không
được gì.

| Bậc | Cỡ | Đậm | Giãn chữ | Dùng ở đâu |
|---|---|---|---|---|
| `display` | 34 | 700 | -1 | Số tiền lớn, một màn một lần |
| `h1` | 28 | 700 | -0.6 | Tiêu đề màn |
| `title` | 20 | 600 | -0.3 | Tiêu đề thẻ |
| `body` | 16 | 400 | 0 | Chữ thân |
| `label` | 13 | 400 | 0 | Nhãn phụ |
| `micro` | 12 | 600 | 0.3 | Chip, badge. **Không nhỏ hơn 12** |

`micro` từng là 11px. Detector bắt 8 chỗ "tiny body text" nên nâng lên 12px,
đó là sàn của hệ này.

Số tiền luôn dùng `font-variant-numeric: tabular-nums`. Một cột tiền đọc dọc mà
chữ số nhảy bề ngang là đọc sai.

## Khoảng cách

Thang 4pt. Sáu bước, không thêm bước thứ bảy:

`xs` 6 · `sm` 10 · `md` 16 · `lg` 24 · `xl` 36 · `xxl` 48

## Bo góc

Đo từ mockup: nút bo 8px trên chiều cao 38px, thẻ bo ~16px trên bề ngang 212px,
cùng một tờ và cùng tỉ lệ render. Tỉ lệ thẻ:nút là 2:1 và giữ nguyên tỉ lệ đó:

| Token | Giá trị | Dùng cho |
|---|---|---|
| `base` | 20 | Thẻ, số tiền, toast |
| `control` | 14 | Nút |
| `small` | 10 | Chip và ảnh nằm trong thẻ |
| `pill` | 999 | Chip tròn hoàn toàn |

Chip cùng bo với thẻ chứa nó thì đọc thành đường nối, nên ba bậc là cần thiết.

## Bóng và cạnh thẻ

Mockup dùng thẻ trắng trên nền kem với bóng **rất mềm và ám ấm** (không phải xám
trung tính). Bóng ở đây để tách thẻ khỏi nền, không để giả độ cao.

**Luật: tách bằng bóng HOẶC bằng viền, không bao giờ cả hai.** Một đường 1px nằm
dưới bóng nhoè 30px là đường nối mà bóng đã làm thừa. Detector gọi đây là
`gpt-thin-border-wide-shadow` và nó bắt đúng: bỏ viền ở thẻ có bóng làm 17
finding còn 4, rồi còn 0. Thẻ `--quiet` không có bóng, nên ở đó viền là thứ duy
nhất giữ cạnh và viền được giữ lại.

## Chuyển động

Bấm phải phản hồi trong một khung hình: `press` 100ms · `fade` 160ms ·
`settle` 220ms. Mọi thứ dài hơn 200ms trên màn tiền là bắt người ta chờ.

## Những chỗ cố ý khác mockup

| Mockup | Hệ này | Vì sao |
|---|---|---|
| Số tiền mỗi người tô màu theo từng người (đỏ, tím, teal) | Toàn bộ dùng teal | Màu ở đây phải mang nghĩa "tiền", không phải mã định danh người. Bốn màu trong một cột tiền làm người đọc đi tìm nghĩa không tồn tại |
| Avatar là ảnh người thật | Vòng tròn chữ cái đầu | Không đưa ảnh và tên người tham gia thật vào Git |
| Bất kỳ ô nào trông như mã chuyển khoản | Không vẽ | Sản phẩm không có đường thanh toán: nói phần của mỗi người rồi dừng |

## Cổng phải xanh trước khi đổi hệ này

```bash
python3 -m pytest services/api/tests/web -q          # token trong guest.css khớp tokens.json
python3 -m app.web.design_preview 8010               # xem hệ, không cần DB
imp detect --json http://localhost:8010/             # 59 rule, contrast tính thật
```

Thêm một cặp màu tông-trên-tông mới thì **phải đo lại**, đừng nhìn bằng mắt.
Cặp `split` trên `splitSoft` trượt ở 4.46:1 đúng vì cả hai đều teal và không ai
nghĩ tới việc kiểm nó.

Thêm một **control mới** thì viền của nó phải dùng `lineStrong` và phải có một
dòng trong `interactive_boundaries()` của `test_contrast_floor.py`. Một control
không có dòng ở đó là một control không ai đo.

## Hai finding còn đứng, và vì sao không tắt

Detector còn báo 2 warning trên màn mẫu. Cả hai đều được giữ nguyên chứ không
thêm ignore, để con số không bị làm đẹp:

- **`overused-font`: "roboto 100% of text".** Đúng là một họ chữ cho toàn trang,
  và đó là quyết định đã ghi ở trên. Thêm nữa Roboto chỉ là thứ `system-ui` phân
  giải ra trên máy Linux chạy detector; trên iOS chính nó là SF Pro. Phân cấp ở
  đây do cỡ và độ đậm gánh, không do đổi họ chữ.
- **`cream-palette`: nền kem `rgb(254,238,224)`.** Luật này tồn tại để bắt "nền
  kem + điểm nhấn ấm" mặc định của UI do AI sinh. Ở đây nền kem là **đo từ
  `mockup.png`**, không phải thẩm mỹ mặc định. Giữ nguyên finding để người review
  tự phán, thay vì tắt nó đi rồi báo sạch.
