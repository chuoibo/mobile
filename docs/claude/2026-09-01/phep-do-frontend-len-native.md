# Chuyển sang native: phép đo nào của lane frontend còn đọc được gì?

- commit: `18990f5` trên `frontend/phep-do-nao-song-sot-khi-len-native`, dựng từ `origin/main@f8fbf49`
- protocol_version: v1
- verdict: FYI (báo sớm theo yêu cầu của Lead lúc 00:00), không phải review
- người viết: lane frontend, task `frontend-tt-0002`

Lead hỏi: *"nghĩ trước xem phép đo của bạn chạy trên emulator thì CÁI GÌ GÃY... Nếu bạn
thấy phép đo của mình KHÔNG chuyển được, nói sớm, đừng im."*

Đây là câu trả lời bằng số, kèm lệnh chạy lại được. Không phỏng đoán.

## Kết luận trong ba dòng

1. **Bản dựng native KHÔNG bị chặn.** `expo export --platform android` chạy được ngay
   hôm nay: 738 module, 2.4MB Hermes bytecode. Đây là tin tốt và nó có nghĩa là việc
   chuyển hướng không vướng ở bundler.
2. **106 trong 158 phép đo mất bề mặt đo khi bỏ DOM.** Còn lại 52, tức khoảng một phần ba.
3. **`imp detect` đóng góp 0 trên native**, và số 0 đó trông y hệt "màn hình sạch".
   Đây là chỗ nguy hiểm nhất, vì nó là công cụ lane này dùng để chấm mọi màn.

## Chạy lại được bằng một lệnh

```bash
cd apps/mobile && npm test                       # phải chạy trước: tầng 2 đọc dist-test/
cd apps/mobile && node tools/kha-nang-chuyen-native.mjs
cd apps/mobile && node tools/kha-nang-chuyen-native.mjs --json
```

Kết quả trên `18990f5`:

```
Tong     : 158 file do dac
WEB-ONLY : 99  (mat phep do khi bo DOM)
Grep import truc tiep chi thay : 87
Di theo do thi thay them       : 12
TANG 2  module dist-test bi viet lai sang react-native-web : 47/98
TANG 2  test tang 1 goi la PORTABLE nhung chay tren rnw    : 3
TANG 3  ca doc ban dung web nhu van ban                    : 4
CON LAI THAT SU: 52/158
```

## Ba đường mất phép đo, xếp theo mức khó thấy

### 1. Lái trình duyệt (99 file). Cái này ai cũng đoán được.

Puppeteer, Playwright, `chrome-cdp.mjs`, `renderToStaticMarkup`. Không có DOM thì
không có gì để lái.

Điểm đáng nói: **grep import trực tiếp chỉ thấy 87.** Mười hai file còn lại không nhắc
tên trình duyệt nào; chúng spawn tool khác và tool đó mới lái Chrome. Ví dụ
`dot-bien-quet-duong-di.mjs` chạy `quet-man-sau-tap.mjs` và `screen-snapshots.mjs`.
Một phép đếm bằng grep sẽ báo 12 file này là "chuyển được" - sai theo đúng hướng lạc quan.

### 2. Bản dựng test tự thay thư viện (3 file nữa). Cái này khó thấy hơn nhiều.

`tools/fixup-esm.mjs` duyệt toàn bộ `dist-test/` và viết lại
`from "react-native"` thành `from "react-native-web"`. Đo trên bản dựng thật:
**47/98 module bị viết lại, và 0 module còn giữ `from "react-native"`.**

Nghĩa là một ca test không nhắc chữ "browser" nào vẫn render qua thư viện web ngay khi
nó import một màn. Docstring của chính `fixup-esm.mjs` đã nói thẳng điều này:

> *"What it deliberately cannot prove is anything about iOS or Android, where a
> different library reads the same props."*

Câu đó đã nằm sẵn trong repo từ lâu. Không ai đọc nó thành một con số cho tới hôm nay.

### 3. Cổng đọc bản dựng như văn bản (4 file).

`npm test` dựng bằng `expo export --platform web` rồi grep chuỗi trong output.
Android xuất ra Hermes bytecode (magic `c6 1f bc 03`), không phải text. Đo thật:

| chuỗi | bundle web | bundle android (.hbc) |
|---|---|---|
| `build-check.invalid` | 8 | **0** |
| `VietQR` | 2 | **0** |

Cổng grep không đỏ ở đây. Nó trả "không tìm thấy", đúng bằng câu nó trả cho một tính năng
đã bị xoá thật.

## `imp detect` trên native: đóng góp bằng 0

Đo 4 màn, mỗi màn hai bề mặt, cùng một commit, ảnh chụp dựng lại từ HEAD lúc 00:45:

| màn | nguồn `.tsx` | HTML render của chính màn đó |
|---|---|---|
| ChupBill | 0 finding, exit 0 | 2 finding, exit 2 |
| DotThu | 0 finding, exit 0 | 1 finding, exit 2 |
| KetQuaThanhToan | 0 finding, exit 0 | 2 finding, exit 2 |
| DeXuat | 0 finding, exit 0 | 1 finding, exit 2 |

Toàn bộ số đo của detector đến từ bề mặt HTML. Native không có bề mặt đó, nên detector sẽ
trả `[]` và `exit 0` cho mọi màn. **Đó là hình dạng của một lượt quét sạch.**

Hệ quả trực tiếp: mọi câu "imp detect sạch" sau khi chuyển sang native đều vô nghĩa
cho tới khi có công cụ thay thế. Marker bắt buộc dán `imp detect` của lane này cũng cần
Lead xem lại, vì sau khi chuyển nó sẽ luôn dán được một số 0 hợp lệ về hình thức.

## Công cụ native: chưa có gì trên máy

```bash
which maestro appium adb emulator     # cả bốn: không có
```

Playwright không lái được app native. Cần Appium hoặc Maestro, và cả hai đều chưa cài.

## Cái này KHÔNG chứng minh gì

Nói rõ để không ai đọc quá lên:

- **Chưa có gì được chạy trên máy thật hay emulator.** Không có một phép đo native nào
  trong báo cáo này. Emulator của Lead chưa xong.
- **Tầng 1 và tầng 3 là phép đọc TĨNH văn bản nguồn.** Chúng chứng minh một file có nhắc
  một đường dẫn, không chứng minh đoạn code đó thật sự chạy. Cố ý lệch về phía báo NHIỀU
  hơn: đọc "ít nhất chừng này gãy", đừng đọc là con số chính xác.
- **52 file "còn lại" KHÔNG phải là 52 file đã được chứng minh chạy trên máy.** Chúng chỉ
  là số file không chạm ba đường gãy đã kiểm. Đường gãy thứ tư có thể còn đó và công cụ
  này mù với nó.
- Tầng 2 cần `dist-test/` tồn tại. Thiếu thì công cụ **nói ra và exit 1**, không im lặng
  báo 0.

## Đối chứng: vì sao con số này đáng đọc

Công cụ tự kiểm bằng hai canary và exit 1 nếu canary sai. Đã đột biến để chứng minh chúng
cắn thật, không phải trang trí:

| đột biến | kỳ vọng | thật |
|---|---|---|
| nền, không đột biến | exit 0 | **exit 0** |
| M1: `edgesOf` luôn trả `[]` (giết phép đi đồ thị) | canary A lật thành PORTABLE, exit 1 | **exit 1** |
| M2: `touchesWebDirectly` luôn trả marker (bôi nhoè) | canary B lật thành WEB-ONLY, exit 1 | **exit 1** |
| M3: `DIRS` trỏ thư mục không tồn tại (nguồn rỗng) | exit 1, không báo 0 | **exit 1** |

Một cái bẫy đã đo được và đã ghi vào code: **grep `react-native-web` trần khớp cả BÌNH LUẬN.**
`api.js` giải thích một quirk của react-native-web bằng văn xuôi, nên một phép đo lỏng báo
37 module "import rnw" trong khi số thật là **0**. Tầng 2 tách bình luận rồi mới khớp dạng
import. Nếu không làm thế, báo cáo này đã có một con số sai gấp mười hai lần.

## Đề xuất cho Lead

1. **Đừng đầu tư thêm vào phép đo RN Web.** 106/158 sẽ phải viết lại hoặc bỏ.
2. **52 file còn lại là chỗ nên giữ**, vì phần lớn là logic thuần (tiền, phân bổ, api
   contract) và chúng chạy trên native không đổi dòng nào.
3. **Cần quyết sớm về công cụ lái native** (Maestro nhẹ hơn Appium cho PoC). Chưa có gì
   cài, và đó là đường găng, không phải việc phụ.
4. **Cần một luật mới cho marker**: sau khi chuyển, "imp detect sạch" không còn là bằng
   chứng. Nếu giữ nguyên yêu cầu cũ, lane này sẽ nộp số 0 hợp lệ về hình thức mà rỗng
   về nội dung, đúng kiểu lỗi cả đội đang cố tránh.

---

**Mọi con số ở đây đo trên RN Web trong Chrome và trên bản dựng web/android xuất bằng
`expo export`. CHƯA đo trên native, chưa có một lượt chạy nào trên emulator hay máy thật.**
