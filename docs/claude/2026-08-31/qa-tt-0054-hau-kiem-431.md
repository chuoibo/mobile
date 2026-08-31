# Hậu kiểm #431 + cổng đầy đủ trên `main`

- **protocol_version**: v1
- **Đo tại**: `69938b7` — SHA này **đã ở `main`** (`git merge-base --is-ancestor origin/main HEAD` → đã có toàn bộ main)
- **Verdict cổng `main`**: `PASS`
- **Verdict hậu kiểm #431**: `PASS` (đã merge, **không đề nghị revert**) + một suggestion có bằng chứng

## Lý do, viết trước phần chi tiết

`main` tại `69938b7` xanh cả ba tầng, gồm cả tầng PostgreSQL thật với 0 skip.

\#431 đã merge và nó làm `main` **tốt lên thật**: lỗi nó sửa là lỗi thật (chip
"Level N" ở 1.11:1 sáng / 1.10:1 tối — chữ có mặt mà không đọc được), và cổng nó
thêm **có cắn**: đưa lỗi cũ trở lại thì cổng đỏ ngay, ở cả hai bảng màu.

Cái tôi tìm ra không phải lỗi của bản vá mà là **độ rộng của điểm mù**: cùng đúng
cặp màu đó, viết qua một biến cục bộ, thì biến mất khỏi cổng — và cả **ba** cơ chế
chống mục ruỗng của chính #431 (đếm `boQua`, sàn coverage, neo hồi quy) đều không
kêu. Đây là **suggestion**, không phải blocker: docstring của cổng CÓ khai báo rằng
màu đi qua biến không được giải. Việc tôi đo là hệ quả của lời khai đó lên hai cơ
chế được bán ra như "chống mục ruỗng".

## Cổng đầy đủ trên `main` @ `69938b7`

| Tầng | Lệnh | Kết quả |
|---|---|---|
| domain + API (fake repo) + repo guard | `python3 -m pytest services/api/tests tests -q` | **2709 passed, 580 skipped, 4901 subtests** in 349.98s |
| mobile | `cd apps/mobile && npm test` | **974 pass, 0 fail, 0 skipped**, 23 suites |
| PostgreSQL thật | `MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q` | **523 passed, 0 skipped** in 101.24s |

580 skip ở hàng một là tầng Postgres tự bỏ qua khi thiếu URL; hàng ba chạy lại đúng
tầng đó với `MOBILE_REQUIRE_POSTGRES_TESTS=1` nên **0 skipped** — skip đã được đóng,
không đọc thành xanh.

## Bảng đột biến trên cổng của #431

Cây sạch, mutate → chạy → khôi phục → xác nhận cây sạch lại. Cổng đo là
`apps/mobile/tools/cap-mau-tinh.mjs` + `tests/tuong-phan-cap-mau.test.mjs`.

| # | Đột biến | Cổng | Đọc |
|---|---|---|---|
| D1 | Hoàn nguyên bản vá: `color: c.ai` → `c.aiInk` | **ĐỎ** (exit 1, 2 cặp hỏng, cả `sang` lẫn `toi`) | Cổng cắn được lỗi khai sinh của nó |
| D2 | Cùng lỗi, viết bằng **ternary tương quan** — đúng hình dạng cổng cố ý bỏ qua | **ĐỎ** (exit 1, 2 cặp hỏng) | Phép ghép nhánh-với-nhánh **đúng**; không mù vì suppression |
| D3 | Cùng lỗi, viết qua **biến cục bộ** | **XANH** (exit 0, 0 cặp hỏng) — `npm test` 974/974 | Điểm mù, chi tiết bên dưới |

D2 đáng nói riêng: tôi vào với giả thuyết rằng phần suppression hai hình dạng sẽ là
chỗ hở. Nó **không phải**. Cổng ghép nhánh-với-nhánh nên vẫn soi được nhánh xấu.
Giả thuyết của tôi sai và bảng ghi lại đúng như vậy.

### Một lần đỏ nhầm lý do, ghi lại để không ai trích dẫn nhầm

Bản D3 đầu tiên của tôi làm `npm test` đỏ **2 ca** — và nó **không** phải cổng bắt
được lỗi. Tôi đặt hai `const` lên trước dòng `const c = usePalette()`, nên đỏ là
`TS2448: Block-scoped variable 'c' used before its declaration`. Đặt lại cho đúng
chỗ thì tsc sạch và cả suite xanh 974/974. Con số dùng được là bản sau.

## D3 — điểm mù, và vì sao ba cơ chế chống mục ruỗng không kêu

Bản vá của #431 và đột biến D3 dùng **đúng hai token đó, đúng một cặp màu đó**.
Khác nhau duy nhất là chỗ đặt tên:

```tsx
// Cổng THẤY (D1):
<View style={{ backgroundColor: c.aiSoft }}>
  <Text style={{ ...type.label, color: c.aiInk }}>Level {tien.cap}</Text>

// Cổng KHÔNG THẤY (D3) — 1.11:1 sáng, 1.10:1 tối, y hệt:
const nenChip = c.aiSoft;
const mucChip = c.aiInk;
<View style={{ backgroundColor: nenChip }}>
  <Text style={{ ...type.label, color: mucChip }}>Level {tien.cap}</Text>
```

Ba cơ chế #431 dựng lên để cổng không mục ruỗng, và vì sao cả ba im lặng ở D3:

1. **Đếm `boQua`** — chỗ không giải được được đếm ra chứ không lặng lẽ bỏ qua. Ở D3
   con số đi **110 → 112**. Cộng 2 vào một biển 110 không phải là tín hiệu ai đọc được.
2. **Sàn coverage** (`assert.ok(soCap > 300)`) — thật ra là `soCap = 670`. D3 làm nó
   thành 668. **Còn 55.1% số cặp có thể tắt đi mà cổng vẫn xanh.** Sàn chỉ bắt được
   một cú sập toàn phần, không bắt được xói mòn từng màn — mà xói mòn từng màn mới
   là cách một cây code thật mục.
3. **Neo hồi quy** — ca tên `"chip Level không dùng aiInk trên aiSoft"`, viết riêng
   để chặn đúng lỗi này quay lại. Nó gọi `quetFile()` rồi `assert.deepEqual(loi, [])`,
   nên nó chỉ thấy cái bộ đọc giải được. Ở D3 nó **XANH**. Ca chống hồi quy cho lỗi
   X bị vô hiệu bởi đúng cái refactor mà lỗi X có thể núp sau.

Điểm 3 là cái đắt nhất: tên ca đọc như một lời bảo lãnh ("neo hồi quy"), và
`CLAUDE.md` đã có sẵn bài học rằng một cái tên hứa nhiều hơn thân ca là chỗ không
ai đi kiểm lại.

### Tái lập

```bash
node tests/qa/qa-tt-0054/do-mu-cua-cong-cap-mau.mjs
```

Probe tự mang **đối chứng dương**: dạng trực tiếp phải ra > 0 lỗi, nếu không nó
thoát 2 và tự nói là hỏng — nên con số 0 ở dạng-qua-biến mới có nghĩa. Nó không
sửa file nguồn nào; nó ghi mẩu `.tsx` ra thư mục tạm rồi xoá, đúng cách
`tests/tuong-phan-cap-mau.test.mjs` của #431 đang làm.

Kết quả tại `69938b7`:

```
dang TRUC TIEP  : 2 loi   <- doi chung duong
dang QUA BIEN   : 0 loi   <- cung mot cap mau
san coverage    : soCap=670, san=300
                  mat toi 369 cap (55.1%) van XANH
```

## Phân loại và đề nghị

Theo 5 loại blocker của charter, đây **không** thuộc loại nào: không sai tiền, không
rò rỉ, không hỏng tính hợp lệ thí nghiệm, tái lập được, và không vi phạm spec — cổng
làm đúng cái docstring của nó nói. Nên: **suggestion**, gửi lane sở hữu `apps/mobile/`.

Hai việc rẻ, không cần đổi kiến trúc bộ đọc:

- **Nâng sàn sát giá trị thật và neo theo từng file**, thay vì một tổng toàn cây.
  `soCap > 300` trong khi thật là 670 thì không gác gì; một sàn per-file bắt được
  cảnh "màn X rơi khỏi tầm đọc" mà tổng toàn cây nuốt mất.
- **Neo hồi quy nên đo giá trị, không đo sự vắng mặt.** `assert.deepEqual(loi, [])`
  xanh cả khi không đọc được gì. Ca đó nên đòi thêm rằng chip Level **có** được đọc
  (số cặp của `ThanhTich.tsx` > 0) — cùng đúng cái ý "im lặng vì không đọc được gì
  thì không phải là đạt" mà #431 đã viết ở ca đối chứng dương, chỉ là chưa áp cho
  neo hồi quy.

## Ô CHƯA quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Chỉ leader đóng được câu này.
- `npm run test:e2e` (lát cắt dọc qua server sống) **chưa chạy** lượt này — #431
  không chạm route hay domain nào, và cổng `main` ba tầng ở trên đã chạy đủ.
- Không quét ảnh / a11y bằng trình duyệt lượt này: phát hiện ở đây là **tĩnh**, và
  nó nói về cổng chứ không nói màn hiện tại xấu. `main` hiện **không có** cặp hỏng
  nào ở dạng đọc được (0 cặp hỏng / 66 file).
- **110 chỗ cổng không giải được** trên `main` vẫn là 110 chỗ chưa ai đo tương phản
  bằng bất cứ cách nào — số này do chính cổng in ra, không phải tôi ước lượng.
- Repo này **chưa có bằng chứng hành vi nào** (ADR-0006). Ba tầng xanh nói code làm
  đúng điều tác giả nghĩ; nó không nói người thật đọc được màn hình.
