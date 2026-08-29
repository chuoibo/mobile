# Sự cố: `main` đỏ ở 43ae65d — cổng cấm phần trăm bắt nhầm chỗ và bỏ sót chỗ thật

- **protocol_version**: v1
- **Commit đo**: `43ae65d` (main), đối chứng `0c8a795`
- **Verdict**: không phải phán quyết PR — đây là **báo sự cố trên `main`**
- **Người đo**: lane QA
- **Ngày**: 2026-08-29

## Kết luận trước, chi tiết sau

`main` đang **ĐỎ** ở job `mobile bundle and tests`, từ lúc merge #81 (`43ae65d`,
01:33Z). CI đã chạy trên `main` và **đã báo đỏ**; không ai đọc.

Ca đỏ là `apps/mobile/tests/receipt.test.mjs:399` —
*"không thành phần nào đọc .confidence hay in ra một phần trăm"*.

Nó đỏ vì một lý do **sai**: nó bắt được `left: \`${x}%\`` — toạ độ CSS của chấm bản
đồ. Cùng lúc đó, ba phần trăm **thật sự hiện ra trước mắt người dùng** đi qua nó mà
không bị chạm tới. Cổng này đang cấm đúng cái vô hại và bỏ lọt đúng cái nó được viết
ra để cấm.

## Đo thế nào

Cây sạch, worktree riêng dựng từ đúng SHA, không sửa gì:

```
git worktree add /tmp/qa-main-check 43ae65d
cd /tmp/qa-main-check/apps/mobile && npm test
```

| Commit | Nội dung | Kết quả `npm test` |
|---|---|---|
| `0c8a795` | trước #81 (#87 CORS) | **129 pass / 0 fail** |
| `43ae65d` | sau #81 (`main` hiện tại) | **156 pass / 1 fail** |

Khớp đúng với CI: lần chạy trên `main` ở đúng SHA này, job `mobile bundle and tests`,
cũng ra 156/1 (`gh run list --branch main` → lần chạy `failure` ở `43ae65d`).

Cổng Python trên cùng SHA `43ae65d` **xanh**: `748 passed, 121 skipped,
4422 subtests passed`. Sự cố chỉ nằm ở cổng mobile.

Commit đầu tiên đỏ: **`43ae65d` (#81)**. Khoảng tìm chỉ có một commit nên đối chứng
ở commit cha là đủ, không cần `git bisect run`.

### Vì sao hai PR đều xanh mà `main` đỏ

Xung đột ngữ nghĩa, không phải xung đột văn bản:

- #77 (`7bb5e4e`) thêm cổng cấm phần trăm vào `receipt.test.mjs`.
- #81 (`43ae65d`) thêm `DaiBanDo.tsx`, nhánh của nó tách **trước** khi #77 vào main.

Nhánh #81 chạy CI trên nền chưa có cổng đó → xanh. Merge xong mới gặp nhau. `git
merge` không thấy gì để báo vì hai PR không đụng cùng một dòng nào.

## Cổng sai ở cả hai đầu

Cổng quét **chỉ file `.tsx`** (`renderedSources()` lọc `endsWith(".tsx")`), và dùng
regex thứ ba `/\}\s*%/`.

```
NOT SCAN  src/screens/kham-pha/places.ts   -> khớp: }%
SCANNED   src/screens/kham-pha/DaiBanDo.tsx -> khớp: }%
```

**Bắt nhầm** — `DaiBanDo.tsx`, được quét, làm đỏ `main`:

```
DaiBanDo.tsx:53: left: `${x}%`,
DaiBanDo.tsx:54: top:  `${y}%`,
```

Hai dòng này nằm trong `style={{...}}`. Chúng là toạ độ chấm trên dải bản đồ, không
phải chữ. Comment của chính cổng đã lường trước `"76%"` **hằng** trong style, nhưng
không lường `${x}%` **tính ra** trong style.

**Bỏ lọt** — `places.ts`, không được quét, chứa đúng thứ cổng muốn cấm:

```
places.ts:393: if (match.source !== "ai") return { text: `ĐIỂM ${pct}%`, real: false };
places.ts:395: if (match.verdict === "tam") return { text: `TẠM HỢP ${pct}%`, real: true };
places.ts:396: return { text: `AI MATCH ${pct}%`, real: true };
```

`matchLabel()` sống trong `.ts`, không phải `.tsx`, nên cổng không bao giờ nhìn thấy nó.

## Trên trang render thật, người dùng thấy gì

Bộ đo: `tests/qa/rd-qa-05/11-phan-tram-probe.spec.ts`, Playwright 1.62, khung Pixel 7
(390×844), trên bản web export của chính `43ae65d`, `GET /places` được `page.route`
ghim payload cố định — câu hỏi ở đây thuần là **client render cái gì**, nên ghim
payload mới đọc được kết quả. Đây **không** thay cho lượt chạy stack thật ở
`02-rehearsal.spec.ts`.

Dòng **CHỮ** có dấu `%` mà người dùng đọc được:

```
"AI MATCH 95%"
"ĐIỂM 61%"
"TẠM HỢP 72%"
```

Phần trăm trong **STYLE** (chấm bản đồ, không phải chữ):

```
left=70% top=60.6667% label=Quán Nướng Ngói
left=10% top=18%      label=Lẩu Nấm Hồ Tây
left=90% top=82%      label=Bún Chả Hàng Quạt
```

Cổng đỏ vì nhóm dưới. Nhóm trên là nhóm nó được viết ra để chặn, và nó không thấy.

## Câu hỏi cho Lead, không phải cho lane nào

Sửa regex là việc mười phút. Câu chưa ai trả lời:

**`AI MATCH 95%` có được phép hiện không?**

Hai lane đang giữ hai hợp đồng ngược nhau:

- #77 viết một cổng **cấm mọi phần trăm** trong app, tên ca ghi thẳng như vậy.
- #81 ship một phần trăm **có thiết kế**: `score` là số học của máy chủ trên ngân
  sách/khẩu vị/khoảng cách, đi kèm `factors` là phần tính được bày ra; nhãn
  `AI MATCH` chỉ hiện khi có cả câu trả lời của model **và** `verdict === "hop"`.

Đây không phải lỗi phần trăm cũ. Lỗi cũ là `undefined` render thành chuỗi rỗng, ra
`"AI suggested %"`. #81 chặn được lớp lỗi đó bằng cấu trúc: `parseMatch()` gọi
`num(m.score)` và **ném** nếu score không phải số hữu hạn, nên `undefined%` không
dựng lên được nữa.

Nên câu hỏi là câu chính sách, không phải câu kỹ thuật: cấm tuyệt đối phần trăm, hay
cấm phần trăm **không có phần tính kèm**? Tôi không tự quyết hộ hai lane. Cho tới khi
có quyết định, đừng nới regex theo kiểu chỉ để `main` xanh lại — nới sai chiều là mất
luôn cổng.

## Gợi ý sửa (không phải việc của tôi, chỉ để khỏi nới sai)

Muốn cổng đúng như tên nó, cần đổi hai thứ **cùng lúc**, đổi một cái là tệ hơn hiện tại:

1. Quét cả `.ts`, không chỉ `.tsx` — nếu không, `matchLabel` vẫn vô hình.
2. Loại phần trăm nằm trong giá trị style. Regex hiện tại không phân biệt được
   `left: \`${x}%\`` với `` `AI MATCH ${pct}%` ``.

Sửa xong phải chứng minh **đỏ đúng chỗ**: trồng lại `` `AI MATCH ${pct}%` `` thì cổng
phải đỏ, và `left: \`${x}%\`` thì phải xanh. Cổng không đỏ được ở ca thật thì không
chứng minh gì.

## Ô CHƯA quét

- Chưa đo `AI MATCH` với dữ liệu từ **máy chủ thật** — payload ở đây do bộ đo ghim.
  Score 95 là số của tôi, không phải số Gemini/máy chủ sinh ra. Chưa trả lời được
  "số máy chủ gửi có đúng không", chỉ trả lời được "client hiện cái gì".
- Chưa chạy `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` trong lượt này
  (121 skipped ở trên là tầng đó nằm im, **không phải xanh**).
- Chưa quét mã QR bằng app ngân hàng thật — vẫn là ô của leader.

## Ba vi phạm a11y trên Khám phá (đã báo ở rd-qa-05, đo lại kèm node cụ thể)

Ca đối chứng chạy trước: trồng một `<img>` thiếu alt → axe đi từ **3 lên 4** vi phạm.
Detector còn sống, nên ba con số dưới đây đọc được.

| Mức | Rule | Node |
|---|---|---|
| serious | `aria-prohibited-attr` | 3 chấm bản đồ: `<div aria-label="Quán Nướng Ngói">` không role — `aria-label` không hợp lệ trên div trần |
| critical | `aria-required-attr` | 2 × `<div role="radio" tabindex="0">` thiếu `aria-checked` |
| critical | `aria-required-children` | `<div role="tablist">` thiếu con bắt buộc |

Không phải phát hiện mới — đã nằm trong báo cáo rd-qa-05. Ghi lại ở đây vì lần này
có node HTML cụ thể để lane sửa khỏi phải đoán.

## Tái lập

```
git worktree add /tmp/qa-main-check 43ae65d
cd /tmp/qa-main-check/apps/mobile && npm test          # 156 pass, 1 fail
git -C /tmp/qa-main-check checkout 0c8a795
cd /tmp/qa-main-check/apps/mobile && npm test          # 129 pass, 0 fail
```

Bộ đo render:

```
cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8499 \
  npx expo export --platform web --output-dir /tmp/qa-render --clear
grep -o "index-[a-f0-9]*\.js" /tmp/qa-render/index.html    # ghim đúng bundle rồi mới đo
cd /tmp/qa-render && python3 -m http.server 4899 --bind 127.0.0.1
WEB_URL=http://127.0.0.1:4899 npx playwright test tests/11-phan-tram-probe.spec.ts
```
