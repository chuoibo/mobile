# Font display của Rủ Đi

**Bricolage Grotesque** — SIL Open Font License 1.1 (`OFL-BricolageGrotesque.txt`). Tác giả: Mathieu Triay (Atelier Triay), <https://github.com/ateliertriay/bricolage>. Nguồn file: `google/fonts` `ofl/bricolagegrotesque/BricolageGrotesque[opsz,wdth,wght].ttf` tại commit `6ce172f74aa3` (2026-03-03).

Vì React Native Android không lái trục biến thiên từ style, bốn instance tĩnh được cắt bằng `fontTools.varLib.instancer` (2026-09-05):

| File | wght | wdth | opsz | Dùng cho |
|---|---:|---:|---:|---|
| `BricolageGrotesque-ExtraBold.ttf` | 800 | 100 | 24 | `hero`, `display`, `h1`, số tiền lớn |
| `BricolageGrotesque-Bold.ttf` | 700 | 100 | 24 | `h2`, tiêu đề màn |
| `BricolageGrotesque-SemiBold.ttf` | 600 | 100 | 14 | nhãn thương hiệu nhỏ, chú thích Instax |
| `BricolageGrotesque-CondensedBold.ttf` | 700 | 80 | 12 | chữ trên con dấu trạng thái, vé, tem |

Face có `tnum` nên số tiền vẫn tabular. Body, nhãn nút, ô nhập, chip: system (Roboto / SF) theo ADR-0020. Bộ chữ Việt: đủ 597 glyph (fontTools), đã kiểm dấu «ế ự ỡ ạ ổ ầ ẫ ỹ Đ» ở 12/17/28/40 sp (ảnh trong `docs/claude/2026-09-05/`). Nạp runtime bằng `expo-font` (`src/rudi/fonts.ts`), không nhúng lúc build, để đổi face không cần dựng lại dev client.
