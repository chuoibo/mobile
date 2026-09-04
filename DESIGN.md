# Design

<!-- impeccable:design-schema 1 -->

Hệ thiết kế của **Rủ Đi**. Token đo từ mockup 2026-08-29; luật thành phần và
luật native bên dưới **đo lại từ artifact đã ship** (commit `86a55fb`,
2026-09-04), không phải từ kế hoạch. Chỗ nào mockup và bản ship lệch nhau thì
bản ship thắng và được ghi rõ. Nguồn số duy nhất là
`packages/shared/tokens.json`; file này mô tả và giải thích nó.
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

## Đo lại từ artifact đã ship (2026-09-04, 86a55fb)

Nguồn: `apps/mobile/src/rudi/theme.ts`, `ui.tsx`, `app/(tabs)/_layout.tsx`,
`app/_layout.tsx`, và hai lượt chụp trên emulator Android (sáng + font 1.0
`da101c9 (chụp 2026-09-04 lúc 13:17:38)`, tối + font 1.3 `86a55fb (chụp 2026-09-04 lúc 13:33:58)`). Kit App B
cũ (`Kit.tsx`) đã bị xoá cùng App B ngày 2026-09-04; vỏ RuDi là kit duy nhất.

### Hợp đồng hướng đi (ghi trong `app/_layout.tsx`, nguyên văn)

> THESIS: A warm evening with friends, organised by a calm assistant: every
> screen tells one group what happens next and what it costs, nothing more.
> OWN-WORLD: Cream ground, white cards, one leading tone per screen (accent =
> brand action, split = money, ai = machine output); brand gradients only on
> hero and primary CTA, never under small text.
> STORY: Discover → plan together in chat → go → photograph the bill →
> everyone sees their own share; the screen never invents a number.
> FIRST VIEWPORT: The tab bar and one decision above it, on a 360x800 phone,
> with real data or an honest empty state; no fixture text in production.
> FORM: expo-router stack + 4 tabs + create sheet; 44pt targets, 12px floor,
> tabular-nums for money, motion ≤ 220ms. Seed: none rolled. Every screen
> here is an Extension of the world already committed in DESIGN.md.
> FINISH: the shipped screens are reviewed on the emulator, not on the web export.

Một chỗ bản ship vượt hợp đồng: FORM nói 44pt, code ship **48dp** (xem dưới).

### Tông dẫn theo họ màn hình (đo bằng `<RudiScreen tone=…>`)

| Họ màn | Tông dẫn | Bằng chứng |
|---|---|---|
| Đăng nhập, OTP, nhóm, bạn bè, kèo (`keo/*`), khám phá, kỷ niệm | `accent` (mặc định của `RudiScreen`) | 58 dùng `tone="split"` và 35 `tone="ai"` đều nằm trong thành phần con, không đổi tông màn |
| Chia bill (`ChiaBillLive`), đợt thu (`DotThuLive`), quyết toán (`batches/[id]`), `Bill` | `split` | mọi `RudiButton` trên các màn này mang `tone="split"`, kể cả outline/ghost |
| Thẻ AI trong chat, gợi ý hợp gu ở Khám phá | `ai` chỉ ở **thành phần** (`Card tone="ai"`, `AiNote`, `Chip tone="ai"`) | không màn live nào ship với `tone="ai"` ở `RudiScreen`; chỉ các màn fixture cũ (`Discovery`, `Group`, `Profile`) |

`RudiScreen` vẽ hai vệt sáng mờ (`AmbientBackdrop`): vệt trên lấy `<tone>Soft`
của tông dẫn, vệt dưới luôn `accentSoft`. Đó là cách một màn "nói" tông của nó
trước khi có chữ.

### Primitive và luật của từng cái (`ui.tsx`)

| Primitive | Luật đo được |
|---|---|
| `RudiScreen` | `SafeAreaView` cạnh top/left/right; lề ngang `space.md` (16), `space.lg` (24) khi ≥ 700dp; `gap` 18 giữa khối; `bottomInset` mặc định 32, màn có tab bar dùng **112** để nội dung không chui dưới thanh tab + FAB; `footer` ghim dưới, `footerInset` do màn truyền `insets.bottom` |
| `TopBar` | cao tối thiểu 52, hai bên rộng 52; tiêu đề `title` 1 dòng, phụ đề `caption` 1 dòng; không có back thì hiện `Logo compact` |
| `Heading` | `display`/`h1`/`h2` màu `ink`, phụ đề `body` màu `inkSoft`, rộng tối đa 620/560 |
| `SectionHeader` | `h2` + hành động chữ màu `accent`, hộp bấm cao **48** dù chữ chỉ 14 |
| `Card` | bo `radius.base` (20), đệm 16, viền 1px `line` **và** `cardShadow`; `tone` đổi nền sang `<tone>Soft` và viền cùng màu nền (viền biến mất). Có `onPress` thì là `button`, nhấn co 0.992 và mờ 0.94 |
| `RudiButton` | cao tối thiểu **52** (48 khi `compact`), bo `radius.control` (14), nhãn `label` 14/600 một dòng, icon 20 (18 compact). `solid` = gradient `[colors.accent, colors.accentEnd]` theo **scheme**, nhãn `accentInk`; tông khác `solid` là màu phẳng của tông. `soft` = nền `<tone>Soft`, chữ màu tông. `outline` = nền `card`, viền `lineStrong`, chữ màu tông. `ghost` = trong suốt. Nhấn: mờ 0.82, co 0.98. `disabled` mờ 0.45 |
| `IconButton` | **48 × 48**, bo 16; `quiet` không viền không nền; `solid` = nền tông, glyph `<tone>Ink` |
| `Field` | cao tối thiểu 52 (108 nếu `multiline`), nền `card`, viền `lineStrong`, bo 14, chữ `body`, placeholder `inkFaint`; nhãn `label` màu `ink` phía trên |
| `OtpBoxes` | 6 ô 44 × 54, một `TextInput` thật phủ lên (chữ trong suốt, không dùng opacity 0); ô đang nhập viền `accent`, ô khác `lineStrong` |
| `Chip` có `onPress` | cao tối thiểu **48**, bo `pill`; chưa chọn: nền `card`, viền `lineStrong`, chữ `inkSoft`; đã chọn: nền `<tone>Soft`, viền màu tông, chữ màu tông **và** dấu check, để trạng thái không dựa vào màu đơn thuần |
| `Chip` không `onPress` | là **sự thật, không phải control**: không role, cao 30, bo `radius.small` (10). Đây là cách ship trạng thái («Đã trả bill», «Đang mở», «Quản trị») |
| `Stat` | số bằng `typography.money`, nhãn `caption` `inkFaint`, icon 38 trong nền `<tone>Soft` |
| `AiNote` | nền `aiSoft`, thanh trái 3px `ai`, icon `sparkles` trên nền `ai`, tiêu đề cố định «Rủ Đi AI gợi ý» |
| `ListRow` | cao tối thiểu 58, icon 40 trong `<tone>Soft`, chevron `inkFaint` khi bấm được |
| `Segmented` | `role="tab"`, mỗi đoạn cao 48, đoạn chọn nền `<tone>Soft` bo 10 trong khung bo 14 |
| `Divider` | `StyleSheet.hairlineWidth`, màu `line` |
| `Avatar` | vòng tròn chữ cái đầu, viền 2px `card` (hoặc `accent` khi `ring`); không bao giờ là ảnh người thật |
| `DemoBadge` | viền `line`, chữ 10/700 `inkFaint`, icon `flask-outline`; **render rỗng ở chế độ live**. Nhãn demo trên tiền thật là lời nói dối ngược chiều |
| Thanh tab + FAB | tab bar cao `62 + insets.bottom`, nhãn 10/700, active `accent`, inactive `inkFaint`; iOS mờ kính `BlurView` 78. FAB 58 × 58 bo 21, nền `brand.coral`, glyph `accentInk`, **vòng 4px màu `ground`** tách nó khỏi thanh tab; ≥ 700dp đổi thành rail trái 104 |

Có trong `ui.tsx` nhưng **không màn nào ship dùng**: `Eyebrow`, `SurfaceLabel`
(nhãn in hoa giãn chữ), `FloatingGlass`. Chúng không phải hệ; đừng lấy làm mẫu.

### Luật native đã ship

- **Đích bấm 48dp.** Nút 52, nút compact 48, icon 48, chip bấm 48, đoạn segmented
  48, hành động chữ trong `SectionHeader` 48. Nhỏ hơn là lỗi.
- **Cỡ chữ theo sp**, đã chạy đủ lượt chụp ở font 1.3: không cắt, không đè.
  Chữ nào có `numberOfLines={1}` (14 chỗ) đều là tiêu đề/nhãn nút/chip; chú
  thích dài dùng `numberOfLines={2}` (5 chỗ), không bao giờ 1.
- **Hàng chip cuộn ngang, không lưới gập dòng, trong form.** Ở font 1.3 danh
  mục địa điểm gập thành tám hàng và đẩy nút gửi khỏi màn; `OutingLive` đổi
  sang `ScrollView horizontal`. Lưới gập chỉ dùng khi không có CTA bên dưới.
- **Safe area cho thứ ghim đáy.** Composer chat: `marginBottom =
  max(insets.bottom, 8)` (6 khi bàn phím mở, vì IME đã che thanh điều hướng).
  Màn chia bill: `bottomInset = max(insets.bottom, 16) + 40` để CTA cuối không
  nằm dưới thanh gesture. Tab bar: `paddingBottom = max(insets.bottom, 10)`.
- **Trạng thái là `Chip`, không phải chữ inline.** «Đã trả bill», «+lẻ đồng»,
  «Đã tới», «Đang mở/Đã đóng» đều là chip tĩnh; màu tông nói phần nào của
  sản phẩm đang nói.
- **Tiền luôn qua `typography.money`** (21/800, `tabular-nums`, 33 chỗ). Số
  tiền màu `ink`; chỉ số tiền trong **khoản chuyển** đề xuất mới lên `split`.
- **Gradient theo scheme, không theo brand.** Nút chính lấy `[accent, accentEnd]`
  của bảng màu hiện hành: sáng `#c93900 → #c9344a` nhãn trắng, tối
  `#fb693e → #e75262` nhãn `#1c0d06`. Ở tối, nút chính phải là thứ sáng nhất
  có thể bấm trên màn. Gradient brand (`logoGradient`, `heroGradient`) chỉ ở
  logo.
- **Đường kẻ là hairline** (`StyleSheet.hairlineWidth`, màu `line`): divider
  trong thẻ, cạnh trên tab bar, cạnh phải rail.
- **Bóng thẻ trên native**: iOS `#5A3014` 0/8 mờ 18 độ đục 0.1, Android
  `elevation: 3`. Ám ấm như web, nhưng nhẹ hơn.
- **Thẻ có tông** (`Card tone`) là cách ship khối tóm tắt của một phần: tổng
  chi chuyến (`split`), thẻ AI trong chat (`ai`). Một thẻ tông mỗi màn.
- **Rỗng / đang tải / lỗi**: rỗng là `Heading size="h2"` + một câu `caption`
  nói việc tiếp theo («Chưa có kèo nào… tạo một kèo ở Lên plan»); đang tải
  là `RudiButton loading` ngay tại nút vừa bấm (spinner thay icon, nút khoá);
  lỗi là chữ `warn` dưới form hoặc `RudiButton variant="outline"` «Thử lại».
  Không toast, không modal lỗi.
- **`DemoBadge`** đặt ở màn còn đọc fixture (9 file), tự ẩn khi phiên live.

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
trong bảng, nó **đọc token ra từ `src/rudi/ui.tsx` và `guest.css` rồi mới đo**
(`Kit.tsx` của App B đã đi cùng App B, 2026-09-04). Thêm một
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

Bảng trên là `tokens.json.type`, thang của **trang khách web**. App ship thang
riêng trong `theme.ts` (`typography`), đo lại từ artifact, nặng tay hơn một
bậc và có `lineHeight` tường minh vì RN không tự tính:

| Bậc | Cỡ / dòng | Đậm | Giãn chữ | Dùng ở đâu |
|---|---|---|---|---|
| `display` | 34 / 39 | 800 | -1.1 | Số tiền tổng trên thẻ tông, một màn một lần |
| `h1` | 28 / 34 | 800 | -0.65 | Tiêu đề màn (`Heading` mặc định) |
| `h2` | 21 / 27 | 700 | -0.3 | `SectionHeader`, tiêu đề trạng thái rỗng |
| `title` | 17 / 23 | 700 | -0.15 | Tiêu đề `TopBar`, tiêu đề thẻ, chữ số OTP |
| `body` | 16 / 23 | 400 | 0 | Chữ thân, ô nhập |
| `label` | 14 / 19 | 600 | 0 | Nhãn nút, nhãn ô nhập, dòng chính `ListRow` |
| `caption` | 12 / 16 | 600 | 0 | Chip, phụ đề, chú thích. Sàn 12 giữ nguyên |
| `money` | 21 / 27 | 800 | 0, `tabular-nums` | Mọi số tiền |

Hai thang cùng sàn 12 và cùng system stack; số trong `tokens.json` không đổi
vì `guest.css` còn đọc nó.

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

Luật "một trong hai" ở trên là của **trang khách web**. `Card` native ship
**cả** viền 1px `line` lẫn `cardShadow` (Android `elevation: 3`, iOS đục 0.1):
bóng elevation 3 gần như không thấy trên nền kem, và ở chế độ tối bóng đen
trên nền `#17120f` không tách được gì, nên viền `line` là thứ giữ cạnh thẻ ở
cả hai scheme. Ghi lại để không ai "sửa" thẻ native theo luật web rồi mất
cạnh ở dark.

## Chuyển động

Bấm phải phản hồi trong một khung hình: `press` 100ms · `fade` 160ms ·
`settle` 220ms. Mọi thứ dài hơn 200ms trên màn tiền là bắt người ta chờ.

## Những chỗ cố ý khác mockup

| Mockup | Hệ này | Vì sao |
|---|---|---|
| Số tiền mỗi người tô màu theo từng người (đỏ, tím, teal) | Toàn bộ dùng teal | Màu ở đây phải mang nghĩa "tiền", không phải mã định danh người. Bốn màu trong một cột tiền làm người đọc đi tìm nghĩa không tồn tại |
| Avatar là ảnh người thật | Vòng tròn chữ cái đầu | Không đưa ảnh và tên người tham gia thật vào Git |
| Bất kỳ ô nào trông như mã chuyển khoản, nút VietQR, số tài khoản | Không vẽ | ADR-0015 gỡ đường thanh toán: sản phẩm nói phần của mỗi người rồi dừng. Quyết toán kết thúc ở «khoản chuyển đề xuất» và «Tạo đợt thu từ sổ» |
| Ảnh địa điểm làm hero | Dải typographic: khối `accentSoft` bo 20, icon trên nền `card`, `Heading` tên quán | Danh mục thật không có ảnh; một ảnh stock ở đó là bịa. `Photo`/`PhotoShade` chỉ còn ở màn fixture |
| Thẻ AI ở mọi màn | `AiNote`/`Card tone="ai"` chỉ khi có nguồn thật (`hop.real`, `match.source === "ai"`) | Màu tím hứa «máy sinh ra, người sửa được»; không có đầu ra thật thì không có thẻ |
| Nút phẳng một màu | Nút chính là gradient `[accent, accentEnd]` theo scheme | Đo từ mockup 2026-08-29 và giữ ở bản ship; hai đầu dải đều qua sàn chữ ở cả hai scheme (bảng trên) |
| Chip viền `line` mỏng | Chip bấm được viền `lineStrong`, có check khi chọn | Sàn 1.4.11 ở trên; chip là control |
| Mockup còn 9 tờ «NEEDS UPDATE» | Mockup là comp để quyết định, không phải comp đã duyệt | Bản ship là ground truth của file này, không phải mockup |

## Cổng phải xanh trước khi đổi hệ này

```bash
python3 -m pytest services/api/tests/web -q          # token trong guest.css khớp tokens.json; đọc ui.tsx và DESIGN.md
cd apps/mobile && node --test tests/rudi-khong-hex.test.mjs   # không file nào trong vỏ RuDi tự gõ mã màu
python3 -m app.web.design_preview 8010               # xem hệ, không cần DB
imp detect --json http://localhost:8010/             # 59 rule, contrast tính thật
```

Màn native thì cổng là **emulator**, không phải web export (dòng FINISH của hợp
đồng): chạy lượt Maestro ở cả sáng/font 1.0 và tối/font 1.3 rồi đọc ảnh.

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
