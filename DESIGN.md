---
name: Rủ Đi
description: Cuốn sổ chuyến đi của cả hội, bìa vải indigo và trang giấy sáng, ba cuộn washi mang nghĩa, trạng thái là con dấu
colors:
  ground: "#f7f3ec"
  card: "#ffffff"
  line: "#e6dfd3"
  line-strong: "#a7825d"
  ink: "#1f2230"
  ink-soft: "#4e5563"
  ink-faint: "#676e7b"
  accent: "#c93900"
  accent-end: "#c9344a"
  accent-ink: "#ffffff"
  accent-soft: "#fff0ea"
  split: "#00756b"
  split-ink: "#ffffff"
  split-soft: "#d5f5f0"
  ai: "#7d49ef"
  ai-ink: "#ffffff"
  ai-soft: "#f5f1ff"
  warn: "#c2410c"
  cover: "#1d2140"
  cover-ink: "#f7f3ec"
  cover-ink-soft: "#c9c6d6"
  cover-line: "#3a3f63"
  cover-line-strong: "#8d92bd"
  ground-dark: "#151830"
  card-dark: "#1f2340"
  line-dark: "#363b5e"
  line-strong-dark: "#7d82a9"
  ink-dark: "#f4f1ea"
  ink-soft-dark: "#c4c2cf"
  ink-faint-dark: "#9b9aae"
  accent-dark: "#fb693e"
  accent-end-dark: "#e75262"
  accent-ink-dark: "#1c0d06"
  accent-soft-dark: "#3d1a10"
  split-dark: "#02a498"
  split-ink-dark: "#04201d"
  split-soft-dark: "#0d2f30"
  ai-dark: "#a27dff"
  ai-ink-dark: "#150a30"
  ai-soft-dark: "#251b4a"
  warn-dark: "#e8734b"
  cover-dark: "#0f1126"
  cover-ink-dark: "#f4f1ea"
  cover-ink-soft-dark: "#c4c2cf"
  cover-line-dark: "#2e3255"
  cover-line-strong-dark: "#9095c0"
  brand-glow: "#fc7b37"
  brand-coral: "#fb693e"
  brand-rose: "#e75262"
  brand-violet: "#8350f6"
  brand-teal: "#04a89d"
typography:
  hero:
    fontFamily: "BricolageGrotesque-ExtraBold"
    fontSize: "40sp"
    fontWeight: 800
    lineHeight: "44sp"
    letterSpacing: "-1.2"
  display:
    fontFamily: "BricolageGrotesque-ExtraBold"
    fontSize: "34sp"
    fontWeight: 800
    lineHeight: "39sp"
    letterSpacing: "-1.1"
  h1:
    fontFamily: "BricolageGrotesque-ExtraBold"
    fontSize: "28sp"
    fontWeight: 800
    lineHeight: "34sp"
    letterSpacing: "-0.65"
  h2:
    fontFamily: "BricolageGrotesque-Bold"
    fontSize: "21sp"
    fontWeight: 700
    lineHeight: "27sp"
    letterSpacing: "-0.3"
  title:
    fontFamily: "system (Roboto / SF)"
    fontSize: "17sp"
    fontWeight: 700
    lineHeight: "23sp"
    letterSpacing: "-0.15"
  body:
    fontFamily: "system (Roboto / SF)"
    fontSize: "16sp"
    fontWeight: 400
    lineHeight: "23sp"
  label:
    fontFamily: "system (Roboto / SF)"
    fontSize: "14sp"
    fontWeight: 600
    lineHeight: "19sp"
  caption:
    fontFamily: "system (Roboto / SF)"
    fontSize: "12sp"
    fontWeight: 600
    lineHeight: "16sp"
  stamp:
    fontFamily: "BricolageGrotesque-CondensedBold"
    fontSize: "12sp"
    fontWeight: 700
    lineHeight: "14sp"
    letterSpacing: "0.8"
    textTransform: "uppercase"
  money:
    fontFamily: "BricolageGrotesque-ExtraBold"
    fontSize: "21sp"
    fontWeight: 800
    lineHeight: "27sp"
    fontFeature: "tnum"
rounded:
  base: "20dp"
  control: "14dp"
  small: "10dp"
  stamp: "6dp"
  cover-band: "28dp"
  pill: "999dp"
spacing:
  xs: "6dp"
  sm: "10dp"
  md: "16dp"
  lg: "24dp"
  xl: "36dp"
  xxl: "48dp"
components:
  stamp-button:
    backgroundColor: "{colors.brand-coral}"
    textColor: "{colors.ink}"
    typography: "BricolageGrotesque-Bold 18/22"
    rounded: "{rounded.control}"
    padding: "0 22dp"
    height: "56dp"
  cover-button:
    backgroundColor: "transparent"
    textColor: "{colors.cover-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 18dp"
    height: "50dp"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 18dp"
    height: "52dp"
  button-outline:
    backgroundColor: "{colors.card}"
    textColor: "{colors.accent}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 18dp"
    height: "52dp"
  field:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 14dp"
    height: "52dp"
  chip:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: "10dp 12dp"
    height: "48dp"
  chip-static:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent}"
    typography: "{typography.caption}"
    rounded: "{rounded.small}"
    padding: "5dp 9dp"
    height: "30dp"
  stamp:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "4dp 8dp"
    height: "26dp"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "16dp"
  cover-band:
    backgroundColor: "{colors.cover}"
    textColor: "{colors.cover-ink}"
    rounded: "{rounded.cover-band}"
    padding: "16dp 16dp 24dp"
  tab-bar:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink-faint}"
    typography: "{typography.caption}"
    height: "64dp"
  tab-bar-active:
    textColor: "{colors.accent}"
  fab:
    backgroundColor: "{colors.brand-coral}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.pill}"
    size: "56dp"
---

# Design System: Rủ Đi

<!-- impeccable:design-schema 2 -->

Hệ thiết kế v2 của **Rủ Đi**, **đo lại từ artifact đã ship** ở head
`d168b63` (nhánh `claude/p0-w-ui0-nen-tang-design-system`, 2026-09-05), lát
UI-0 (nền tảng) + UI-1 (vào cửa: Welcome, Login, OTP, thanh tab). Finish
reviewer trả `ship` trên head này cho phạm vi đã chấm: tám mục vật chất và hai
hồi quy, trên phone sáng font 1.0, phone tối font 1.3, tablet sáng. Chỗ nào
hợp đồng hướng đi và bản ship lệch nhau thì **bản ship thắng** và được ghi rõ.

Nguồn số duy nhất là `packages/shared/tokens.json` (`theme.ts` đọc, `guest.css`
soi gương, `test_shared_tokens.py` so từng token). Hai mục «Màu, kèm số đo
tương phản» và «Sàn phi-chữ 3:1» bên dưới do `scripts/sinh_token_ui_v2.py`
sinh ra và `test_contrast_floor.py` đối chiếu từng tỉ lệ; không sửa tay.
`.impeccable/design.json` là bản máy đọc, cùng script viết các khối số.

**Phạm vi thật, nói thẳng.** Thế giới v2 phủ **trọn** bốn bề mặt: Welcome,
Login, OTP và `RudiTabBar`. Mọi màn còn lại (Khám phá, Tin nhắn, Lên plan,
Chia bill, Album, Cá nhân, Tài chính, kèo, nhóm) đang chạy **bố cục v1 trên
nền v2**: nhận trang giấy có vân, bảng màu, Bricolage ở tiêu đề và số tiền,
nhưng thẻ, chip, hero, nút vẫn là primitive cũ trong `ui.tsx`. Các lát
UI-2 đến UI-8 sẽ đổi từng họ màn; file này **không mô tả** bố cục chưa tồn
tại, và sẽ được đo lại sau UI-8.

## Overview

**Creative North Star: "Nhật ký chuyến đi sau giờ làm"**

Một cuốn sổ chuyến đi cả hội cùng viết trong một buổi tối. *Bìa* vải indigo
là bề mặt thuyết phục (Welcome, dải đầu trang của Login/OTP); *trang giấy*
trắng ngà có vân là bề mặt làm việc. Ba cuộn *washi* bão hoà mang nghĩa (cam =
lời rủ và hành động, teal = tiền, tím = AI) chỉ dán lên **vùng đang quan
trọng**. Trạng thái là *con dấu* mực, không phải chip màu lẫn chữ. Kế hoạch
là một *đường route bút mực* liên tục. Khung kẻ in trước, màu đổ sau khi có dữ
liệu. Lưới 4pt, snap ô nguyên. Hợp đồng hướng đi nằm nguyên văn trong
`apps/mobile/app/_layout.tsx` (seed `c8e88116`, hướng số 6, rendition bão
hoà); ADR-0020 là thẩm quyền.

Thế giới này **từ chối mặc định của thể loại**: ảnh hoàng hôn + thẻ trắng +
pill cam. Reviewer đã bắt đúng cái pill coral phẳng ở vòng 1 và bản ship đổi
nó thành con dấu (viền mực kép, mực có hạt, nghiêng 1.5°). Cũng bị loại ở
vòng review: giả dập nổi bằng bóng lệch cứng trên wordmark; bản ship là một
lớp phẳng.

Mật độ: một quyết định mỗi màn, cột nội dung tối đa 560dp ở tablet, đích bấm
48dp, sàn chữ 12sp. Không toast, không modal lỗi; lỗi là một câu `warn` dưới
form.

**Key Characteristics:**
- Hai bề mặt vật chất, đo được bằng pixel: vải bìa (stddev ≈ 8 mức trên
  `#1d2140`), giấy (≈ 2 mức trên `#f7f3ec`), mực trong con dấu (≈ 8.6 mức trên
  coral).
- Ba tông mang nghĩa, một tông dẫn mỗi màn; màu thương hiệu `coral` chỉ ở
  mảng lớn (washi, con dấu, FAB, logo).
- Một display face tự host (Bricolage Grotesque, bốn instance tĩnh) cho tiêu
  đề, số tiền, chữ con dấu; body giữ system.
- Trạng thái là con dấu; số tiền là chữ số tabular, không bao giờ animate trước
  domain state.
- Bốn bậc chuyển động (100/200/300/550 ms), Reduce Motion đưa về 0; scale và
  opacity là đường chính.

## Colors

Bảng màu có **hai bề mặt và hai scheme**: giấy (`ground`/`card`) và bìa
(`cover`), mỗi cái có bộ mực riêng; bốn nhóm đo đủ ở sáng và tối. Tầng
thương hiệu (`brand.*`) giữ nguyên số đo từ logo, không chỉnh theo tương phản,
và vì thế bị giới hạn công dụng.
Ba màu tông ở scheme sáng là màu đo từ logo đã **làm tối tới khi qua AA** (cam
#fb693e → #c93900, teal #04a89d → #00756b, tím #8350f6 → #7d49ef); cả hai số
được giữ ở `tokens.json` (`_source`, `_contrastFloor`) và màu đo được vẫn
nguyên trong `brand.*` cho mảng lớn.

### Primary
- **Cam hành động** (`accent` #c93900 sáng / #fb693e tối): tông thương hiệu và
  hành động chính. Chữ cam trên giấy, chỉ báo tab đang chọn, viền chip đã
  chọn. Nút chính v1 (`RudiButton solid`) là gradient `[accent, accentEnd]`
  theo scheme; nút chính v2 (`StampButton`) lại là `brand.coral` với mực tối.
- **Coral thương hiệu** (`brand.coral` #fb693e, cả hai scheme): washi cam,
  mặt con dấu CTA, FAB «Tạo mới», chặng đang ở trên route. Luôn là mảng lớn,
  luôn đi với mực tối tĩnh (xem luật Mực Tĩnh).

### Secondary
- **Teal tiền** (`split` #00756b / #02a498): chia bill, tiền, quyết toán;
  washi teal là `brand.teal` #04a89d.
- **Tím AI** (`ai` #7d49ef / #a27dff): thứ máy sinh ra, người còn sửa được;
  washi tím là `brand.violet` #8350f6.
- **Cảnh báo** (`warn` #c2410c / #e8734b): một câu lỗi dưới form, chữ `body`.

### Neutral
- **Giấy** (`ground` #f7f3ec / #151830): nền trang, luôn có `Grain giayTrang`
  phủ 0.45 (tối 0.30).
- **Thẻ** (`card` #ffffff / #1f2340): thẻ, ô nhập, nút outline, thanh tab.
- **Mực** (`ink` #1f2230 / #f4f1ea) · **mực phụ** (`inkSoft`) · **mực nhạt**
  (`inkFaint`): ba bậc chữ trên giấy, tất cả qua AA ở cả hai nền.
- **Kẻ trang trí** (`line` #e6dfd3 / #363b5e): cạnh thẻ, divider, xương
  skeleton; **cố ý dưới 3:1**.
- **Viền control** (`lineStrong` #a7825d / #7d82a9): ô nhập, chip chưa chọn,
  nút outline, tay nắm sheet; qua sàn 3:1 trên mọi nền nó nằm lên.
- **Bìa** (`cover` #1d2140 / #0f1126) với **mực bìa** (`coverInk`,
  `coverInkSoft`) và hai viền bìa (`coverLine` trang trí, `coverLineStrong`
  control 3:1). Bìa tối ở cả hai scheme; tối chỉ tối hơn một bậc.

### Named Rules
**Luật Một Tông Dẫn.** Một màn có đúng một tông dẫn; hai tông dẫn cùng lúc là
lỗi, không phải lựa chọn. Welcome/Login/OTP dẫn bằng cam (washi + con dấu);
thẻ AI trên Khám phá là tím ở **thành phần**, không đổi tông màn.

**Luật Mực Tĩnh trên Coral.** `brand.coral` không đổi theo scheme nên chữ,
icon và viền đặt lên nó dùng `mauSang.ink` (#1f2230) **tĩnh**, không dùng
`colors.ink`. Đo: 5.41:1 ở cả hai scheme; mực sáng của scheme tối trên coral
chỉ 2.4:1 và đã ship nhầm một lần. Áp cho tagline trên washi, nhãn/viền/icon
`StampButton`, glyph chặng đang ở của `RouteLine`.

**Luật Cam Không Nhỏ trên Bìa.** `accent` sáng trên `cover` đo 3.03:1: cấm
chữ cam nhỏ trên bìa. Cam trên bìa là washi (mảng lớn) hoặc con dấu có mực
tối; chữ trên bìa là `coverInk`/`coverInkSoft`.

**Luật Hai Viền.** Ranh giới của thứ bấm được vẽ bằng `lineStrong` (hoặc
`coverLineStrong` trên bìa); cạnh của container vẽ bằng `line`. Thêm một
control là thêm một dòng trong `interactive_boundaries()` của
`test_contrast_floor.py`; control không có dòng ở đó là control không ai đo.

## Màu, kèm số đo tương phản

50 cặp chữ trên nền mà hệ này thật sự dùng đều được đo, cả trang giấy lẫn bìa sổ. Thấp nhất **4.61:1**, cao nhất **16.50:1**, không cặp nào dưới ngưỡng AA 4.5:1.

Bảng này chỉ đo **chữ**. Ranh giới của thành phần giao diện đi theo ngưỡng khác và nằm ở mục "Sàn phi-chữ 3:1" bên dưới. Đọc thiếu mục đó là cách lỗi viền nút 1.21:1 đã lọt qua một lần.

### Chế độ sáng

| Cặp | Vai trò | Tỉ lệ | Ngưỡng |
|---|---|---|---|
| `ink` #1f2230 trên `ground` #f7f3ec | Chữ thân trên nền trang | **14.28:1** | AAA |
| `ink` #1f2230 trên `card` #ffffff | Chữ thân trên thẻ | **15.79:1** | AAA |
| `inkSoft` #4e5563 trên `card` #ffffff | Chữ phụ trên thẻ | **7.49:1** | AAA |
| `inkSoft` #4e5563 trên `ground` #f7f3ec | Chữ phụ trên nền | **6.77:1** | AA |
| `inkFaint` #676e7b trên `card` #ffffff | Chú thích trên thẻ | **5.13:1** | AA |
| `inkFaint` #676e7b trên `ground` #f7f3ec | Chú thích trên nền | **4.64:1** | AA |
| `accent` #c93900 trên `card` #ffffff | Cam trên thẻ | **5.16:1** | AA |
| `accent` #c93900 trên `ground` #f7f3ec | Cam trên nền | **4.67:1** | AA |
| `accentInk` #ffffff trên `accent` #c93900 | Nhãn trên nút cam | **5.16:1** | AA |
| `accent` #c93900 trên `accentSoft` #fff0ea | Cam trên chip cam nhạt | **4.65:1** | AA |
| `split` #00756b trên `card` #ffffff | Teal trên thẻ | **5.59:1** | AA |
| `split` #00756b trên `ground` #f7f3ec | Teal trên nền | **5.05:1** | AA |
| `splitInk` #ffffff trên `split` #00756b | Nhãn trên nút teal | **5.59:1** | AA |
| `split` #00756b trên `splitSoft` #d5f5f0 | Teal trên chip teal nhạt | **4.83:1** | AA |
| `ai` #7d49ef trên `card` #ffffff | Tím trên thẻ | **5.16:1** | AA |
| `ai` #7d49ef trên `ground` #f7f3ec | Tím trên nền | **4.66:1** | AA |
| `aiInk` #ffffff trên `ai` #7d49ef | Nhãn trên nút tím | **5.16:1** | AA |
| `ai` #7d49ef trên `aiSoft` #f5f1ff | Tím trên chip tím nhạt | **4.64:1** | AA |
| `warn` #c2410c trên `card` #ffffff | Cảnh báo trên thẻ | **5.18:1** | AA |
| `warn` #c2410c trên `ground` #f7f3ec | Cảnh báo trên nền | **4.68:1** | AA |
| `ink` #1f2230 trên `accentSoft` #fff0ea | Chữ thân trên chip cam | **14.22:1** | AAA |
| `ink` #1f2230 trên `splitSoft` #d5f5f0 | Chữ thân trên chip teal | **13.65:1** | AAA |
| `ink` #1f2230 trên `aiSoft` #f5f1ff | Chữ thân trên chip tím | **14.22:1** | AAA |
| `coverInk` #f7f3ec trên `cover` #1d2140 | Chữ trên bìa sổ | **14.13:1** | AAA |
| `coverInkSoft` #c9c6d6 trên `cover` #1d2140 | Chữ phụ trên bìa sổ | **9.33:1** | AAA |

### Chế độ tối

| Cặp | Vai trò | Tỉ lệ | Ngưỡng |
|---|---|---|---|
| `ink` #f4f1ea trên `ground` #151830 | Chữ thân trên nền trang | **15.45:1** | AAA |
| `ink` #f4f1ea trên `card` #1f2340 | Chữ thân trên thẻ | **13.56:1** | AAA |
| `inkSoft` #c4c2cf trên `card` #1f2340 | Chữ phụ trên thẻ | **8.72:1** | AAA |
| `inkSoft` #c4c2cf trên `ground` #151830 | Chữ phụ trên nền | **9.93:1** | AAA |
| `inkFaint` #9b9aae trên `card` #1f2340 | Chú thích trên thẻ | **5.56:1** | AA |
| `inkFaint` #9b9aae trên `ground` #151830 | Chú thích trên nền | **6.33:1** | AA |
| `accent` #fb693e trên `card` #1f2340 | Cam trên thẻ | **5.24:1** | AA |
| `accent` #fb693e trên `ground` #151830 | Cam trên nền | **5.97:1** | AA |
| `accentInk` #1c0d06 trên `accent` #fb693e | Nhãn trên nút cam | **6.48:1** | AA |
| `accent` #fb693e trên `accentSoft` #3d1a10 | Cam trên chip cam nhạt | **5.31:1** | AA |
| `split` #02a498 trên `card` #1f2340 | Teal trên thẻ | **4.93:1** | AA |
| `split` #02a498 trên `ground` #151830 | Teal trên nền | **5.61:1** | AA |
| `splitInk` #04201d trên `split` #02a498 | Nhãn trên nút teal | **5.50:1** | AA |
| `split` #02a498 trên `splitSoft` #0d2f30 | Teal trên chip teal nhạt | **4.61:1** | AA |
| `ai` #a27dff trên `card` #1f2340 | Tím trên thẻ | **5.04:1** | AA |
| `ai` #a27dff trên `ground` #151830 | Tím trên nền | **5.74:1** | AA |
| `aiInk` #150a30 trên `ai` #a27dff | Nhãn trên nút tím | **6.18:1** | AA |
| `ai` #a27dff trên `aiSoft` #251b4a | Tím trên chip tím nhạt | **5.18:1** | AA |
| `warn` #e8734b trên `card` #1f2340 | Cảnh báo trên thẻ | **5.09:1** | AA |
| `warn` #e8734b trên `ground` #151830 | Cảnh báo trên nền | **5.80:1** | AA |
| `ink` #f4f1ea trên `accentSoft` #3d1a10 | Chữ thân trên chip cam | **13.75:1** | AAA |
| `ink` #f4f1ea trên `splitSoft` #0d2f30 | Chữ thân trên chip teal | **12.70:1** | AAA |
| `ink` #f4f1ea trên `aiSoft` #251b4a | Chữ thân trên chip tím | **13.95:1** | AAA |
| `coverInk` #f4f1ea trên `cover` #0f1126 | Chữ trên bìa sổ | **16.50:1** | AAA |
| `coverInkSoft` #c4c2cf trên `cover` #0f1126 | Chữ phụ trên bìa sổ | **10.60:1** | AAA |

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
| `lineStrong` #a7825d trên `ground` #f7f3ec | Viền control trên nền trang | **3.17:1** | 1.4.11 |
| `lineStrong` #a7825d trên `card` #ffffff | Viền control trên thẻ | **3.50:1** | 1.4.11 |
| `coverLineStrong` #8d92bd trên `cover` #1d2140 | Viền control trên bìa sổ | **5.19:1** | 1.4.11 |
| `line` #e6dfd3 trên `ground` #f7f3ec | Cạnh thẻ trên nền trang | **1.20:1** | trang trí |
| `line` #e6dfd3 trên `card` #ffffff | Đường kẻ trong thẻ | **1.32:1** | trang trí |
| `coverLine` #3a3f63 trên `cover` #1d2140 | Đường kẻ trên bìa | **1.54:1** | trang trí |

### Chế độ tối

| Cặp | Vai trò | Tỉ lệ | Ngưỡng |
|---|---|---|---|
| `lineStrong` #7d82a9 trên `ground` #151830 | Viền control trên nền trang | **4.68:1** | 1.4.11 |
| `lineStrong` #7d82a9 trên `card` #1f2340 | Viền control trên thẻ | **4.11:1** | 1.4.11 |
| `coverLineStrong` #9095c0 trên `cover` #0f1126 | Viền control trên bìa sổ | **6.42:1** | 1.4.11 |
| `line` #363b5e trên `ground` #151830 | Cạnh thẻ trên nền trang | **1.61:1** | trang trí |
| `line` #363b5e trên `card` #1f2340 | Đường kẻ trong thẻ | **1.42:1** | trang trí |
| `coverLine` #2e3255 trên `cover` #0f1126 | Đường kẻ trên bìa | **1.51:1** | trang trí |

Số của `line` và `coverLine` ghi ra ở đây **chính vì chúng không đạt 3:1**. Người sau đọc bảng này phải thấy ngay chúng đứng ở đâu, thay vì thấy một token không có số rồi dùng nó cho một cái nút. `coverLineStrong` là viền của control đặt trên bìa sổ (Welcome, Login), đo trên cả hai scheme.

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

## Typography

**Display Font:** Bricolage Grotesque (OFL 1.1, tự host, bốn instance tĩnh cắt
bằng `fontTools.varLib.instancer`; nạp runtime qua `expo-font`, không nhúng
lúc build)
**Body Font:** system (Roboto trên Android, SF trên iOS)
**Wordmark:** SVG từ outline Baloo 2 ExtraBold nghiêng 9° (`ui/Wordmark.tsx`,
tỉ lệ 2.8804), không còn `fontStyle: "italic"` giả wordmark

**Character:** một grotesque «lắp ghép từ mảnh tìm được» cho tiêu đề, số tiền
và chữ con dấu, đứng trên body system trung tính. Bricolage có trục `wdth`
(instance Condensed cho tem) và `tnum` (số tiền tabular). Bộ chữ Việt 527
glyph, đã kiểm «ế ự ỡ ạ ổ ầ ẫ ỹ Đ» ở 12/17/28/40 sp trên emulator ở font 1.0
và 1.3 (ảnh trong `docs/claude/2026-09-05/`). Body giữ system là **quyết định**
(ADR-0020 §2.3): dấu tiếng Việt và cỡ chữ hệ thống chắc chắn, đổi face không
cần rebuild dev client.

### Hierarchy
Thang app trong `theme.ts` (`typography`), `lineHeight` tường minh vì RN không
tự tính; `fontWeight: "normal"` ở các bậc Bricolage vì độ đậm đã nướng vào
instance.

- **Hero** (ExtraBold, 40/44, -1.2): một lần mỗi màn, láng giềng của wordmark;
  «Chào bạn», «Nhập mã 6 số» trong `CoverBand`.
- **Display** (ExtraBold, 34/39, -1.1): số tiền tổng trên thẻ tông, một màn
  một lần.
- **H1** (ExtraBold, 28/34, -0.65): tiêu đề màn. Tiêu đề trang pager Welcome
  dùng cùng face ở 28/33.
- **H2** (Bold, 21/27, -0.3): `SectionHeader`, tiêu đề trạng thái rỗng.
- **Title** (system 700, 17/23, -0.15): tiêu đề `TopBar`, tiêu đề thẻ, chữ số
  OTP.
- **Body** (system 400, 16/23): chữ thân, ô nhập; bề rộng tối đa 520 khi là
  đoạn dẫn.
- **Label** (system 600, 14/19): nhãn nút, nhãn ô nhập, `CoverButton`.
- **Caption** (system 600, 12/16): chip, phụ đề, nhãn tab, pháp lý. **Sàn 12sp.**
- **Stamp** (CondensedBold, 12/14, +0.8, IN HOA): chữ trên con dấu trạng thái
  và tem; đây là chữ in hoa giãn duy nhất của hệ, và nó là **mực dấu**, không
  phải eyebrow.
- **Money** (ExtraBold, 21/27, `tabular-nums`): mọi số tiền qua `Money`
  (kích cỡ `display`/`money`/`body`/`label`/`caption`, luôn ép tabular).
- **Nhãn con dấu CTA** (Bold, 18/22, +0.2): riêng cho `StampButton`.

Thang `tokens.json.type` (display 34/700, h1 28/700, title 20, body 16, label
13, micro 12) là thang của **trang khách web** và không đổi vì `guest.css` còn
đọc; hai thang cùng sàn 12.

### Named Rules
**Luật Một Face.** Bricolage chỉ ở tiêu đề, số tiền, chữ con dấu và thương
hiệu. Nhãn nút, ô nhập, chip, body là system. Một face display thứ hai là
lỗi.

**Luật Số Tabular.** Số tiền luôn `fontVariant: ["tabular-nums"]`, luôn số
nguyên đồng, luôn là chuỗi máy chủ gửi. Một cột tiền mà chữ số nhảy bề
ngang là đọc sai.

## Layout

Lưới 4pt, thang khoảng cách sáu bước `xs` 6 · `sm` 10 · `md` 16 · `lg` 24 ·
`xl` 36 · `xxl` 48; không thêm bước thứ bảy. Nhịp giữa khối trong
`RudiScreen` là 18; cột form Login/OTP `gap` 20.

**Ba size class Android** (`src/rudi/adaptive.ts`, `useAdaptiveLayout`):

| Size class | Bề rộng | Cột | Gutter | Điều hướng | Bề rộng nội dung |
|---|---|---|---|---|---|
| `compact` | < 600dp | 1 | 16 | thanh tab đáy | toàn màn |
| `medium` | 600 đến 839 | 2 | 24 | rail trái 104 | 560 (form), 640 (pager Welcome) |
| `expanded` | ≥ 840 | 3 | 36 | rail trái 104, hai khung | tối đa 1200 |

`heightClass = short` dưới 480dp (máy nằm ngang hoặc IME đè sheet): Welcome hạ
wordmark xuống 72 và bỏ route.

**Bề mặt** (`RudiScreen surface`): `page` = nền `ground` + `Grain giayTrang`,
`SafeAreaView` cạnh top/left/right, lề ngang `md` (`lg` ở tablet),
`bottomInset` 32 (112 dưới thanh tab), status bar tối trên giấy sáng.
`cover` = nền `cover`, **không** cạnh top: `CoverBand underStatusBar` tự cộng
`insets.top` để vải bìa chạy liền dưới status bar (khe giấy 8px ở đây là lỗi
đã sửa), status bar sáng. `CoverBand` `bleed` bằng lề màn (`md` compact,
`lg` tablet) để vải chạm mép.

**Login/OTP** là **một cột 560 bọc cả trang** (`alignSelf: center`); reviewer
bắt hồi quy hai lưới ở tablet (ô số trong cột 560, nút dưới kéo hết 1600) và
bản ship gộp về một cột. **Welcome**: lề 20, wordmark 118 (compact) / 150
(medium+), route `maxWidth` 560, khối đáy `maxWidth` 640 ở medium+.

**Safe area cho thứ ghim đáy** (giữ từ v1, vẫn đúng trên bản ship): thanh tab
`paddingBottom = max(insets.bottom, 10)`; sheet `max(insets.bottom, 16)`;
Welcome `max(insets.bottom, 16) + 6`; composer chat `max(insets.bottom, 8)`.

**Hàng chip cuộn ngang trong form** (v1, còn đúng): ở font 1.3 lưới chip gập
tám hàng đẩy nút gửi khỏi màn; form dùng `ScrollView horizontal`, lưới gập chỉ
khi không có CTA bên dưới.

**`TopBar`** (v1, sửa ở lát này): hai bên đo bề rộng tự nhiên và lấy `max`
cho cả hai để tiêu đề cân giữa (đo: tâm mực lệch 2.5 đến 3px so với tâm màn
ở 360dp); huy hiệu trong `TopBar` dùng `compactLabel` («Demo», «Nháp») vì ở
360dp font 1.3 không thể có cả tiêu đề cân giữa lẫn nhãn dài.

## Elevation & Depth

Hệ này lấy độ sâu từ **chất liệu và khung kẻ**, không từ bóng. Bìa và giấy là
hai lớp vật lý; con dấu **không có bóng** (viền mực kép và hạt giấy nói «đã
đóng lên»); `CoverBand` không bóng, chỉ bo góc dưới 28 để đọc thành mép bìa
lật lên trang. Ba ô chất liệu (`assets/textures/`, 256×256, seed cố định
20260905, sinh bằng Pillow) trải bằng `Grain`: **lưới Image thường**, ô ở
đúng pixel máy, tối đa 60 view; không dùng `resizeMode="repeat"` vì Android
raster một lần theo cỡ view và vân dừng ở một phần ba trên (đo stddev 0.0 từ
y≈700). Opacity đo trên emulator 1x, dưới ngưỡng này là màu phẳng:

| Chất liệu | Ô | Opacity | Đo (stddev) |
|---|---|---|---|
| Vải bìa | `vai-bia.png` | 0.30 | ≈ 8 mức trên `cover`, đều từ y 200 đến 2300 |
| Giấy | `giay-trang.png` | 0.45 sáng / 0.30 tối | ≈ 2 mức trên `ground` («ở ngưỡng, không hạ thêm») |
| Mực dấu | `muc-in.png` | 0.26 | ≈ 8.6 mức trên coral; ô giấy ở đây đo 2.1 nên có ô riêng |

Ô trắng đen trung bình trung tính nên màu token bên dưới đo vẫn đúng trong
một mức: bảng tương phản vẫn áp cho bề mặt có vân.

### Shadow Vocabulary
- **Thẻ native** (`cardShadow`: iOS `#5A3014` 0/8, đục 0.1, mờ 18; Android
  `elevation: 3`): `Card` v1 ship **cả** viền `line` lẫn bóng này, vì bóng
  elevation 3 gần như không thấy trên giấy và ở scheme tối không tách được
  gì; viền giữ cạnh ở cả hai scheme. Đừng «sửa» theo luật web một-trong-hai.
- **FAB** (`elevation: 6`, 0/6, đục 0.22, mờ 10, màu `accent`): thứ duy nhất
  nổi trên thanh tab; vòng 4px màu `ground` tách nó khỏi thanh. Đã hạ từ mức
  nặng hơn sau vòng chụp 1.
- **Scrim sheet** (`lopPhu.toi(0.42)`): lớp phủ ấm gần đen, không xám.

### Named Rules
**Luật Không Dập Nổi.** Không giả độ sâu bằng bóng lệch cứng (hard offset
shadow). Reviewer loại «wordmark dập nổi» ở vòng 1; `WordmarkEmbossed.tsx`
còn trong kit nhưng **không màn nào ship dùng** và không phải hệ.

## Shapes

Bo góc ba bậc từ `tokens.json` giữ tỉ lệ thẻ:nút 2:1: **`base` 20** (thẻ,
sheet, số tiền), **`control` 14** (nút, con dấu CTA, ô nhập, `CoverButton`),
**`small` 10** (chip tĩnh, ảnh trong thẻ, xương skeleton), `pill` 999 (chip
bấm, huy hiệu, FAB tròn 56, nút back tròn 48). Hai giá trị quan sát được mà
tokens.json chưa có tên: **6** cho con dấu trạng thái (`Stamp`) và **28** cho
góc dưới `CoverBand`.

Hình dạng đặc trưng của thế giới:
- **Con dấu**: hình chữ nhật bo 14 (CTA) hoặc 6 (trạng thái), viền mực 2px,
  viền trong 1px lùi 4 (CTA), nghiêng một hơi (-1.5° trên bìa, 0 trong form và
  bảng; `Stamp` cho phép ±2/±3). Mọi góc nghiêng chỉ áp khi khác 0
  (`transform: undefined` làm Reanimated crash, bẫy đã ghi).
- **Washi**: dải SVG mép xé hai đầu (`duongWashiXeMep`), một vạch sáng 1.5px
  `card` ở 0.35 chạy dọc, `fillOpacity` 0.9, nghiêng ±1/±2°; đường SVG sinh
  từ `duong-svg.ts` và có test parse theo cách Java parse (`react-native-svg`
  ném lúc mount nếu chuỗi `d` hỏng).
- **Route**: đường cong S nét 3, đầu tròn; chặng là vòng tròn nét 2.5 (r 16 khi
  có glyph), chặng đang ở tô coral r 21 nét 3 với glyph mực tối.
- **Mép bìa**: `CoverBand` bo hai góc dưới 28, tràn lề.
- **Kẻ**: mọi divider là `StyleSheet.hairlineWidth` màu `line` (cạnh trên
  thanh tab, cạnh phải rail, dòng «hoặc»).

## Components

Kit v2 nằm ở `src/rudi/ui/*.tsx`, **một file một primitive**; kit v1
`src/rudi/ui.tsx` (`RudiScreen`, `TopBar`, `Card`, `Field`, `OtpBoxes`,
`Chip`, `RudiButton`, `Segmented`, `ListRow`, `Stat`, `AiNote`, `DemoBadge`)
vẫn là thứ các màn chưa redesign dùng, và Login/OTP vẫn dùng `Field`,
`OtpBoxes`, `RudiButton outline/ghost` của nó.

### Buttons
- **Con dấu CTA (`StampButton`)**, nút chính của thế giới v2: nền
  `brand.coral`, viền 2px mực tối 0.88, viền trong 1px mực 0.32 lùi 4, `Grain
  mucIn` 0.26, bo 14, cao tối thiểu 56, đệm ngang 22, nhãn Bricolage Bold
  18/22 màu `mauSang.ink`, icon 22 (`arrow-forward` mặc định); `tilt` -1.5 trên
  bìa, 0 trong form; nhấn co 0.97 kèm haptic `impact`; `loading` thay icon bằng
  spinner mực và khoá nút; `disabled` mờ 0.55. Không bóng. Ship ở Welcome «Rủ
  Đi thôi!» và Login «Gửi mã».
- **Nút bìa (`CoverButton`)**, nút phụ trên vải: trong suốt, viền 1px
  `coverLineStrong` (5.19:1 sáng / 6.42:1 tối trên `cover`), bo 14, cao 50,
  nhãn `label` màu `coverInk`, icon 18, haptic `select`. Là thứ duy nhất nói
  «đây là nút» nên viền của nó nằm trong `interactive_boundaries()`.
- **Nút v1 (`RudiButton`)** vẫn ship trên trang giấy: cao 52 (48 `compact`), bo
  14, nhãn `label` một dòng, icon 20; `solid` = gradient `[accent, accentEnd]`
  theo scheme (sáng #c93900 → #c9344a nhãn trắng; tối #fb693e → #e75262 nhãn
  #1c0d06); `outline` = nền `card` viền `lineStrong` chữ màu tông (Login: «Tiếp
  tục với Google», «Tôi có lời mời»); `soft` = nền `<tone>Soft`; `ghost` trong
  suốt. Nhấn mờ 0.82 co 0.98; `disabled` 0.45.
- **Nút back** trên bìa: `PressScale` 48×48 co 0.92, **mặt tròn là View con**
  (nền `coverInk` 0.08, chevron 26 `coverInk`); animate scale, không animate
  opacity, vì lớp opacity theo bounds vuông để lại vệt trên nền có vân.
- **Icon button v1**: 48×48 bo 16, `quiet` không viền không nền.

### Chips
- **Chip bấm được** (v1, còn dùng): cao 48, bo pill; chưa chọn nền `card` viền
  `lineStrong` chữ `inkSoft`; đã chọn nền `<tone>Soft` viền màu tông, chữ màu
  tông **và** dấu check.
- **Chip tĩnh** (sự thật, không control): cao 30, bo 10, không role. Trên các
  màn v1 trạng thái vẫn là chip tĩnh; các lát sau đổi sang `Stamp`.
- **Huy hiệu demo (`DemoBadge`)**: viền `line`, chữ 10/700 `inkFaint`, icon
  `flask-outline`, bo pill; trong `TopBar` rút về `compactLabel`; **render
  rỗng ở chế độ live**.

### Con dấu trạng thái (`Stamp`)
Chữ `stamp` (CondensedBold 12 IN HOA +0.8), viền 2px màu tông, bo 6, đệm 8/4,
cao tối thiểu 26, `alignSelf: flex-start`. `outline` mặc định (chữ màu tông);
`ink` tô đầy với chữ `<tone>Ink`, hiếm: một trạng thái quan trọng nhất mỗi
màn. Nhãn ngắn và đúng sự thật («ĐÃ TỚI», «ĐÃ TRẢ», «AI GỢI Ý»). Primitive
có trong kit, ship ở lát này chưa gọi từ màn nào ngoài kit; ghi ở đây vì
đây là cách trạng thái sẽ đi, không phải chip màu.

### Cards / Containers
- **`Card` v1**: bo 20, đệm 16, viền 1px `line` **và** `cardShadow`; `tone` đổi
  nền sang `<tone>Soft` và viền cùng màu nền. Có `onPress` thì là button, nhấn
  co 0.992 mờ 0.94. Một thẻ tông mỗi màn.
- **`CoverBand`**: nền `cover` + `Grain vaiBia` 0.3, bo góc dưới 28, đệm trên
  `md` (+`insets.top` khi `underStatusBar`), đệm dưới `lg`, tràn lề theo
  `bleed`; chứa logo compact, `hero` `coverInk`, đoạn dẫn `body`
  `coverInkSoft`, nút back tròn.
- **`Sheet`**: nền `card`, bo trên 20, tay nắm 40×4 `lineStrong`, đệm ngang
  `md`, đệm dưới `max(insets.bottom, 16)`; vào bằng spring `settle`, ra bằng
  `standard`; scrim `lopPhu.toi(0.42)`; nút cứng back Android đóng sheet.
- **`Washi`**: dải mép xé cao 30 (40 dưới wordmark), đệm ngang 18, rộng tối
  thiểu 120, tô `brand.coral`/`brand.teal`/`brand.violet` theo tông ở 0.9;
  con là chữ mực tối tĩnh. Chỉ dán lên vùng đang quan trọng.

### Inputs / Fields
- **`Field`**: cao 52 (108 `multiline`), nền `card`, viền 1px `lineStrong`, bo
  14, chữ `body`, placeholder `inkFaint` (5.13:1 trên thẻ), nhãn `label` màu
  `ink` phía trên, icon dẫn 20 `inkFaint`.
- **`OtpBoxes`**: 6 ô 44×54, viền 1.5, một `TextInput` thật phủ lên (chữ trong
  suốt, `autoComplete="sms-otp"`); ô đang nhập viền `accent`, ô khác
  `lineStrong`; chữ số `title`.
- **Lỗi**: một câu `body` màu `warn` ngay dưới control; **không** toast, không
  modal. Đang tải: `StampButton loading` tại chỗ vừa bấm.

### Navigation
- **`RudiTabBar`** tự vẽ (không dùng tab bar mặc định): nền `card`, cạnh trên
  hairline `line`, cao **64 + max(insets.bottom, 10)**; bốn tab `role="tab"`,
  cao tối thiểu 48, icon Ionicons 24 (outline → filled khi chọn), nhãn
  `caption` 12/14 một dòng; đang chọn `accent`, còn lại `inkFaint`. Chỉ báo
  là một **mẩu băng 28×4 `accent`** bo góc dưới, treo ở cạnh trên cột đang
  chọn, trượt bằng `standard` 200ms; container chỉ báo **trong suốt** (bản
  đầu tô cả cột 20% cam, lỗi thấy bằng mắt không thấy bằng code). Bấm tab
  haptic `select`.
- **FAB «Tạo mới»**: cột giữa (giữa Lên plan và Tin nhắn), tròn 56, nền
  `brand.coral`, glyph `add` 30 `accentInk`, vòng 4px `ground`, nhô lên 22,
  elevation 6, nhấn co 0.94 haptic `impact`, mở `/create`.
- **Rail** (medium+): rộng 104, cạnh phải hairline, mỗi mục 72, chỉ báo là
  vạch 4px `accent` bên trái trượt theo `translateY`; FAB không nhô, không
  bóng.
- iOS: `BlurView` 78 theo scheme thay nền `card` (chưa có ảnh iOS; chỉ đọc từ
  code).

### Trạng thái rỗng, tải, lỗi
- **`EmptyState`** năm loại (`first-use`, `no-results`, `filtered`,
  `permission`, `failure`): `h2` + một câu `body` `inkSoft` rộng tối đa 420,
  **một** hành động `RudiButton compact` (`outline` khi `failure`) và một cửa
  phụ `ghost`; `full` căn giữa khung, `inline` nằm trong danh sách; minh hoạ
  chỉ khi có artwork của thế giới, không có thì không vẽ gì.
- **`Skeleton`**: xương màu `line`, bo 10, băng sáng `card` 0.55 chạy 1400ms;
  tắt hẳn dưới Reduce Motion. `SkeletonLines` dòng cuối 62%.
- **`ErrorState`**: cùng khung với `EmptyState kind="failure"`.

### Signature: Bìa mở ra trang (Welcome → Login)
Welcome là bìa đóng: indigo tràn màn với vân vải, wordmark rất lớn ở phần ba
trên (`coverInk`), washi cam nghiêng -2° mang «AI đi chơi, chia bill thông
minh» bằng mực tối, route mực 4 chặng với glyph (people · compass · receipt ·
images) và chặng đang ở tô coral chạy theo trang pager, pager 4 trang (tiêu
đề EB 28/33, body `coverInkSoft`), chấm 7 (đang ở 20 rộng), rồi con dấu «Rủ
Đi thôi!» và nút bìa «Tìm hiểu thêm». Bấm con dấu: bìa **nhấc** (translateY
-48, mờ tới 0.65) trong `shared` 300ms easing `accelerate`, rồi push
`/login`; Login mở với `CoverBand` dưới status bar, tức bìa vẫn còn ở đầu
trang giấy. Reduce Motion: pager nhảy thẳng, bìa không nhấc.

### Chuyển động (đặt cùng thành phần)
`tokens.motion` qua `src/rudi/motion.ts` và `useMotion`: **instant 100**
(bấm, chip, haptic) · **standard 200** (đổi trạng thái, chỉ báo tab, sheet
đóng, skeleton → nội dung) · **shared 300** (bìa mở, thẻ sang chi tiết) ·
**celebrate 550** (một lần mỗi sự kiện, ba khoảnh khắc: chốt kèo, xong bill,
mở huy hiệu; `celebrateOnce` giữ ngân sách). Easing `standard` [0.2,0,0,1],
`decelerate` [0,0,0.2,1], `accelerate` [0.3,0,1,1]. Spring nhấn
{damping 18, stiffness 260, mass 0.6}, thả {20, 180, 0.8}. `PressScale` chỉ
scale (0.97 thẻ/hàng, 0.94 FAB, 0.92 back), không opacity. **Reduce Motion
đưa mọi bậc trừ `instant` về 0.** **Tiền không animate trước khi domain state
hợp lệ**: `moneyCountUpMs` trả 0 khi chưa hợp lệ, `standard` khi có.

## Do's and Don'ts

### Do:
- **Do** dùng `mauSang.ink` tĩnh cho mọi chữ/icon/viền đặt lên `brand.coral`
  (washi, con dấu, chặng route); đo 5.41:1 ở cả hai scheme.
- **Do** vẽ ranh giới control bằng `lineStrong`/`coverLineStrong` và thêm dòng
  trong `interactive_boundaries()`; cạnh container bằng `line`.
- **Do** giữ đích bấm 48dp (nút 52/56, compact 48, chip bấm 48, tab 48, back
  48), sàn chữ 12sp, và chụp lại ở font 1.3 trước khi nói «không cắt».
- **Do** trải chất liệu bằng `Grain` (lưới ô) ở đúng opacity đo được: vải
  0.30, giấy 0.45/0.30, mực 0.26; dưới ngưỡng là màu phẳng, đừng «hạ nhẹ».
- **Do** để `CoverBand underStatusBar` khi màn có bề mặt `cover`, và
  `StatusBar` sáng trên bìa, tối trên giấy sáng.
- **Do** dán washi và đặt con dấu chỉ lên vùng đang quan trọng; phần còn lại
  của trang là giấy và mực.
- **Do** dùng `Money` cho mọi số tiền: số nguyên đồng, tabular, `countUp` chỉ
  khi domain state hợp lệ.
- **Do** giữ một tông dẫn mỗi màn; thẻ AI tím, thẻ tiền teal là tông ở thành
  phần.
- **Do** cuộn ngang hàng chip trong form, ghim đáy bằng `max(insets.bottom, n)`.
- **Do** cấp mọi màu mới qua `tokens.json` → script → `guest.css` + DESIGN.md
  cùng PR; `rudi-khong-hex` giữ `theme.ts` là file duy nhất viết hex.

### Don't:
- **Don't** đặt chữ nhỏ hay icon lên `brand.*` bằng mực của scheme; coral với
  chữ trắng 2.92:1.
- **Don't** đặt chữ `accent` nhỏ trên `cover` (3.03:1).
- **Don't** giả độ sâu bằng bóng lệch cứng hay dập nổi; con dấu và bìa không
  có bóng.
- **Don't** dùng `resizeMode="repeat"` cho chất liệu trên Android.
- **Don't** animate `opacity` trên một pressable tròn nằm trên nền có vân;
  animate scale, mặt tròn là View con.
- **Don't** ghi `transform: undefined` vào style Reanimated; chỉ spread khi
  có góc nghiêng.
- **Don't** dựng hình dạng máy chủ chưa có: không ô mã chuyển khoản, không
  VietQR, không số tài khoản (ADR-0015/0016); sản phẩm nói phần của mỗi người
  rồi dừng.
- **Don't** dùng ảnh stock cho địa điểm thật, ảnh người thật cho avatar;
  minh hoạ vector trước, ảnh có giấy phép sau M12 (ADR-0020 §2.5).
- **Don't** thêm face display thứ hai, hay đưa Bricolage vào body/nhãn/ô nhập.
- **Don't** thêm toast hay modal lỗi; lỗi là một câu `warn` dưới form.
- **Don't** ship nhãn demo trên tiền thật; `DemoBadge` phải rỗng ở phiên live.
- **Don't** mô tả trong file này bố cục của màn chưa redesign; đo lại sau mỗi
  lát.

## Những gì bản ship KHÔNG phong thánh

Có trong cây nhưng không phải hệ; người sau đừng lấy làm mẫu:

- `Eyebrow`, `SurfaceLabel` (nhãn in hoa giãn chữ, ui.tsx) và
  `WordmarkEmbossed.tsx` (dập nổi bằng bóng lệch): có trong kit, **không màn
  nào ship dùng**; hai cái đầu là eyebrow bị craft floor cấm, cái sau bị
  reviewer loại.
- Bố cục v1 của Khám phá, Tin nhắn, Tài chính… trên nền v2 (thẻ trắng bo 20 +
  chip màu + ảnh stock fixture, như ảnh `phone-light-explore-tabbar.png`): là
  **nợ của lát UI-2 đến UI-8**, không phải quy tắc.
- Màn gán món (fixture, bố cục v1) cắt số tổng ở font 1.3: lỗi để lát UI-5,
  không ghi giá trị nào để hợp thức.
- `bangMauFixture`, `giayHoaDon`, `mauSao` trong `theme.ts`: màu của thế giới
  fixture và hoá đơn vẽ tay, không phải token.

## Cổng phải xanh trước khi đổi hệ này

```bash
python3 -m pytest services/api/tests/web -q                   # token guest.css khớp tokens.json; đọc ui/**.tsx và DESIGN.md; mọi tỉ lệ in ở đây đo lại được
python3 scripts/sinh_token_ui_v2.py                           # đổi màu: sinh lại 4 gương, không gõ tay
cd apps/mobile && node --test tests/rudi-khong-hex.test.mjs   # không file nào trong vỏ RuDi tự gõ mã màu ngoài theme.ts
cd apps/mobile && node --test tests/duong-svg.test.mjs        # đường SVG parse được theo cách Java parse
python3 -m pytest tests/test_chat_lieu_tiles.py -q            # ô mực đo trên coral ở 0.26 nằm 6 đến 12 mức (gốc repo)
```

Màn native thì cổng là **emulator**, không phải web export (dòng FINISH của
hợp đồng): light/1.0, dark/1.3, tablet bằng `wm size`, rồi đọc ảnh và đo
pixel; tsc, web export và detector đã mù với ba lỗi thật ở lát này (crash
`transform: undefined`, crash parse `d`, vân dừng ở một phần ba).
