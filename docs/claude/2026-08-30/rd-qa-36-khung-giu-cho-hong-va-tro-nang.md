# rd-qa-36 · Khung ảnh: giữ chỗ, tải hỏng, và trình đọc màn hình — đo ở DOM sống

- **commit đo**: `08894082057b2e7adae46d1a09a4730a69872e91` (`origin/main`, tức #195 **đã merge** ở `03fc4d3` + #198 ở `0889408`)
- **protocol_version**: v1
- **verdict**: không có. #195 đã merge trước khi lượt này chạy — đây là đối chứng **sau merge**, không phải cổng trước merge.
- **blocker còn mở**: không
- **kỹ năng đã gọi**: `e2e-testing`, `bug-reproduction`

## Đọc dòng này trước

Việc được giao là test #195 **trước khi Lead merge**. Lúc tôi bắt đầu, `origin/main`
ở `fd3d837` và #195 còn `OPEN` ở head `1f1d273`. Tôi đo trên head đó.

Giữa chừng, hai chuyện xảy ra mà tôi không tạo ra:

1. **#195 đã merge** (`03fc4d3`, 2026-08-29T17:11:07Z) — nên đây không còn là cổng
   trước merge.
2. **Head tôi đo không phải cái đã ship.** `apps/mobile/src/ui/Anh.tsx` khác **64
   dòng** giữa `1f1d273` và `origin/main`. Bản merge thêm hẳn một cổng origin
   (`ui/nguon-anh.ts` + `nguonAnhAnToan`) mà head tôi lấy về không có.

Nên **mọi số trong tài liệu này đã được đo lại trên `0889408`**. Số đo ở `1f1d273`
chỉ còn xuất hiện đúng một chỗ, và được ghi rõ là "trước".

Một lượt trước của chính lane này đã nộp `rd-qa-35` (#198). Nó trả lời câu **"ảnh
thật có lên màn không"** và tìm ra rằng ca `<Image>` trong `anh.test.mjs` mù.
Nó **không** chạm ba câu hỏi dưới đây. Không có phần nào chồng lấn.

## Ba câu hỏi, và câu trả lời đo được

Bộ đo: `tests/qa/rd-qa-35/anh-khung-probe.mjs` — bundle đã export, Chromium thật,
390×844, đọc lại `getBoundingClientRect`, `document.body.innerText`, danh sách
request mạng, và cây AX của chính trình duyệt. **86/86 khẳng định đúng, exit 0.**

### 1. Khung có giữ chỗ thật không — **CÓ**

A/B trên cùng một trang: cùng thẻ, `photo_url = null` so với `photo_url` trỏ vào
PNG thật (480×360) do bộ đo sinh ra và trả lời bằng request interception.

| | uri = null | có ảnh |
|---|---|---|
| hộp khung (thẻ 1) | **172×124** @ (17,382) | **172×124** @ (17,382) |
| hộp khung (thẻ 2) | **172×124** @ (201,382) | **172×124** @ (201,382) |
| tỉ lệ | **1.39** | **1.39** |

Kích thước, tỉ lệ **và vị trí** giống nhau tới từng pixel. Ảnh lấp đúng khung
(172×124), và nằm `position: absolute` — tức nó không đóng góp gì vào layout, nên
ngày ảnh tới không có gì để đẩy.

Hai màn còn lại của #195 không có đường nào truyền `uri` hôm nay, nên A/B không đo
được. Ở đó phép đo là: gỡ **mọi** con của khung khỏi layout (`display:none`) rồi đo
lại. Hộp không đổi nghĩa là kích thước do chính khung khai:

| màn | khung | trước | sau khi gỡ hết nội dung |
|---|---|---|---|
| Cá nhân | băng bìa (`alt=""`) | 390×148 | **390×148** |
| Cá nhân | ảnh đại diện | 84×84 | **84×84** |
| Mở đầu | nền (`alt=""`) | 390×844 | **390×844** |
| Khám phá | thẻ địa điểm | 172×124 | **172×124** |

### 2. Load hỏng thì sao — **không lộ gì, và không thử lại**

Hai kiểu hỏng, cả hai đo thật: `connectionrefused` và `404`.

- **Không mã lỗi nào lọt lên màn.** Quét `document.body.innerText` cho 12 chuỗi
  (`ECONNREFUSED`, `ERR_CONNECTION`, `net::`, `Failed to load`, `404`, `500`,
  `Not Found`, tên file, cả `127.0.0.1`) → **0 chuỗi lọt**, ở cả hai kiểu hỏng, cả
  trước lẫn sau re-render.
- **Quay về chỗ chờ và ở lại.** Hộp sau khi hỏng = **172×124**, đúng bằng lượt
  `uri=null`. Layout không nhảy.
- **Không icon ảnh vỡ.** Phần tử ảnh rời hẳn DOM (`coAnh=false`, `imgConSrc=false`).
- **`hong` dính theo URI.** Gõ 6 ký tự vào ô tìm kiếm Khám phá = 6 lượt set state
  trên `KhamPha` = 6 lần thẻ vẽ lại, **không unmount thẻ nào**:

  | lượt | request ảnh trước | sau 6 re-render |
  |---|---|---|
  | hỏng (refused) | 1 | **1** |
  | hỏng (404) | 1 | **1** |
  | ảnh sống | 1 | **1** |

  Ba dòng đối chứng đi kèm khẳng định mỗi lượt **có** bắn request lần đầu — nếu
  không, số 0 chỉ nói bộ đếm đã chết.

### 3. Trình đọc màn hình — **đọc đúng một lần**

Đo ở cây AX của Chrome, không đọc nguồn — đúng theo bài học `rnw-nuot-accessibilitystate`.

- Khung có ảnh đọc ra **đúng 1 lần** (`image :: "Ảnh Tiệm Nướng Xóm Lào"`), ở cả
  lượt có ảnh lẫn lượt chỗ chờ. `<Image>` bên trong không sinh node riêng.
- **0 node ảnh không nhãn** ("unlabelled image") trên cả bốn màn đã quét.
- Khung trang trí (`alt=""`) vắng mặt hẳn khỏi cây — đúng ý định.
- Khung ảnh đại diện Cá nhân: **đúng 1 lần**.
- Và một câu tôi tự thêm vì nó suýt hỏng: ARIA nói con của `role="img"` là trang
  trí, mà `AnhDiaDiem` đặt huy hiệu **AI MATCH** làm con của khung. Đo thật:
  `StaticText :: "AI MATCH 95%"` **vẫn còn** trong cây. Chrome không cắt. Không
  phải phát hiện, nhưng là một ô đã quét thay vì bỏ trống.

Ghi chú nền tảng: trên web chỉ `aria-hidden` làm việc; `accessibilityElementsHidden`
và `importantForAccessibility` là prop của native và bị react-native-web bỏ im lặng.
Code khai cả ba nên iOS/Android cũng có phần của mình — **nhưng tôi không đo được
native**, và đó là ô chưa quét, không phải ô đã đạt.

## Cổng của chính bộ đo: đỏ được, và đỏ đúng chỗ

Bốn đột biến trên `apps/mobile/src/ui/Anh.tsx` của `0889408`, mỗi lượt dựng lại
bundle rồi chạy lại probe, khôi phục xong xanh lại 86/86.

| đột biến | probe | đỏ ở đâu |
|---|---|---|
| khung chỉ nhận `style` khi có ảnh | **73/86** | mục 1 — hộp tụt còn 172×**32**, Cá nhân/Mở đầu về **cao 0** |
| `hong` bị xoá mỗi lượt render | **83/86** | mục 2 — 12096 → **13262** request, ảnh ở lại DOM |
| `<Image>` tự khai nhãn | **84/86** | mục 3 — đọc ra **3 lần** thay vì 1 |
| gỡ cổng origin trong `Anh` | **86/86 XANH** | *không đỏ ở đâu* — xem phát hiện 1 |

Cộng bốn canary thường trực trong probe (innerText đọc được nội dung thật; cùng
phép so chuỗi đó tìm được một chuỗi **có** trên màn; cây AX đọc được; phép tìm
khung tìm được khung). Không có chúng thì "lọt: []" và "máy đo đã chết" đọc y hệt
nhau.

Một lần đo đã bị vứt: probe báo "khung có ảnh KHÔNG có phần tử ảnh" trong khi khung
đó đang giữ một tấm ảnh. Phép tìm chỉ duyệt con trực tiếp, mà react-native-web bọc
`<Image>` thành `<div><div background-image><img></div>`. Đã sửa thành duyệt sâu,
rồi mới tin bất kỳ số nào của mục đó.

## Phát hiện

### 1 — `npm test` xanh 554/554 khi cổng origin trong `Anh` bị gỡ · **suggestion (cổng mù)**

**Dẫn chứng.** Đổi đúng một dòng trong `apps/mobile/src/ui/Anh.tsx`:

```diff
-  const nguon = nguonAnhAnToan(uri, BASE_URL);
+  const nguon = typeof uri === "string" && uri.trim() !== "" ? uri.trim() : null;
```

```
cd apps/mobile && npm test
  -> # tests 554   # pass 554   # fail 0   # todo 0
```

Ca giữ luật đó là `apps/mobile/tests/anh.test.mjs:195`, tên là *"Anh gọi cổng
origin, không tự nhận uri thô"*:

```js
assert.match(src, /nguonAnhAnToan/);
assert.doesNotMatch(src, /source=\{\{\s*uri:\s*uri\b/);
```

Cả hai vẫn đạt sau đột biến. Vế đầu khớp **dòng `import` còn nguyên**; vế sau đạt vì
`<Image>` vẫn đọc biến tên `nguon`, chỉ có điều `nguon` giờ là `uri` chưa lọc.

**Hậu quả.** Đây là ca duy nhất gác cổng origin ở `Anh`, và `Anh` là chỗ nghẽn duy
nhất dựng `<Image>`. Một PR gỡ phép lọc mà giữ tên biến sẽ đi qua cổng mobile mà
không đỏ một dòng nào.

Đây là **lần thứ hai** cùng một kiểu mù trong cùng một file: #198 đã báo ca ngay
dưới nó (`assert.match(src, /<Image\b/)`) xanh khi app render 0 ảnh. Nên nó là một
khuôn, không phải một lần lỡ.

**Tiêu chí gỡ chặn.** Một ca đỏ được khi phép lọc biến mất chứ không phải khi tên
biến biến mất. Mục 5 của probe làm được điều đó ở DOM sống nhưng **chỉ khi caller
cũng thả** (xem giới hạn quy trách bên dưới); rẻ hơn là một ca gọi thẳng
`Anh` và khẳng định địa chỉ ngoài không tới được `source`.

### 2 — `KHUNG` là export chết, và số của nó mâu thuẫn với layout đang chạy · **suggestion**

`apps/mobile/src/ui/Anh.tsx:186` export `KHUNG = { the: {aspectRatio: 4/3}, bia:
{aspectRatio: 16/9} }`. Docstring của chính nó nói lý do tồn tại: *"khi photo API
lands, câu trả lời cho 'nó sẽ to bằng nào' đã được viết sẵn và giống nhau ở mọi
nơi"*.

`grep -rn KHUNG apps/mobile/{src,tools,tests}` ngoài chính file khai nó: **không ai
dùng**. Và số đo được trên màn không khớp:

| | `KHUNG` nói | màn thật đo được |
|---|---|---|
| thẻ địa điểm | 4/3 = **1.333** | 172×124 = **1.387** |
| băng bìa | 16/9 = **1.778** | 390×148 = **2.635** |

**Hậu quả.** Không phải lỗi hôm nay. Nhưng nó là một cái bẫy đặt đúng chỗ người sau
sẽ giẫm: người nối API ảnh sẽ đọc `KHUNG`, tin nó, và ra một hình khác hình đang
chạy — trong khi cái nó hứa ngăn chính là chuyện đó.

**Tiêu chí gỡ chặn.** Hoặc ba màn dùng `KHUNG` thật (và số được sửa cho khớp), hoặc
xoá `KHUNG` đi. Giữ nguyên là giữ một câu khẳng định sai trong file.

## Giới hạn quy trách của mục 5 — nói ra vì nó suýt thành một dòng xanh giả

Mục 5 dựng một máy chủ thật đóng vai máy của người lạ và hỏi: nó có nhận được
request nào không. Trên `origin/main` câu trả lời là **0** cho cả sáu hình dạng.

Nhưng "0" đó **không tự nó nói cổng nào đã giữ**: trên đường `/places` có **hai**
lần cùng một cổng — `places.ts:parsePhotoUrl` gọi `nguonAnhAnToan` lúc parse, rồi
`Anh` gọi lại lúc render. Tôi phát hiện ra khi đột biến "gỡ cổng trong `Anh`" ra
86/86 xanh: `places.ts` đã chặn trước, `Anh` không bao giờ được hỏi.

Tách bằng cách đột biến từng tầng:

| `places.ts` | `Anh` | máy chủ người lạ nhận |
|---|---|---|
| cổng | cổng | **0** (hôm nay) |
| **thả** | cổng | **0** ← `Anh` một mình giữ được |
| **thả** | **thả** | **3** ← đối chứng: phép đo sống |

**Hàng giữa là câu trả lời cho câu hỏi của Lead**: ngày một caller (ví dụ tường kỷ
niệm, `memories.image_url` — chuỗi người dùng tự khai) nối vào `Anh` mà quên lọc,
`Anh` một mình vẫn từ chối. Chỗ nghẽn giữ được thật.

Và trong sáu hình dạng, **chỉ ba quy được cho app** (`http://host-lạ`, `//host`,
`/\host`). Ba hình dạng kia (`base.nguoi-la.example`, userinfo trước `@`,
`javascript:`) ra 0 **kể cả khi gỡ cả hai cổng** — Chrome chặn thông tin đăng nhập
nhúng trong subresource, `javascript:` không bao giờ là nguồn ảnh, và
`...invalid.nguoi-la.example` không phân giải được nên không thể tới máy thử ở
127.0.0.1. Số 0 của chúng là sự thật về **môi trường**, không phải bằng chứng về
cổng. Chúng đã được phủ đúng tầng bằng ca chuỗi trong `anh.test.mjs`. Probe in kèm
nhãn `[môi trường chặn, KHÔNG quy được cho app]` để không ai đọc nhầm.

## Ô CHƯA quét

- **Native iOS/Android.** Toàn bộ mục 3 đo trên react-native-web. `accessibilityElementsHidden`
  và `importantForAccessibility` chỉ có tác dụng trên native và tôi không chạm được
  tới đó. Trình đọc màn hình thật (VoiceOver/TalkBack) chưa ai bật.
- **Người thật.** Không ai nhìn ba màn này bằng mắt người trong lượt QA nào.
- **Ảnh thật từ máy chủ.** Chưa route nào trả `photo_url`; mọi ảnh trong lượt này là
  PNG do bộ đo sinh ra.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, vẫn là việc của Lead với
  một điện thoại thật (ADR-0010 mục 8).
- **`hong` khi URI đổi qua lại.** `hong` chỉ nhớ **một** URI hỏng gần nhất. A hỏng →
  B hỏng → quay lại A thì A được thử lại. Đọc ra từ nguồn, **chưa đo**, và chưa màn
  nào đổi `uri` nên chưa chạm được.
- **Ba hình dạng bypass không quy được cho app**, đã nói ở trên.

## Cổng đã chạy (cây sạch, `0889408`)

```
cd apps/mobile && npm run build:check     -> Exported: .expo-build-check
cd apps/mobile && npx tsc --noEmit        -> exit 0
cd apps/mobile && npm test                -> # tests 554  # pass 554  # fail 0
node tests/qa/rd-qa-35/anh-khung-probe.mjs -> 86/86 khẳng định đúng, exit 0
python3 scripts/repo_guard.py staged      -> Repo guard passed
```

Ảnh chụp mỗi lượt và số liệu thô: `.qa-anh-probe/` (không commit — repo guard đúng
khi từ chối nhị phân).

## Câu không được bỏ

Repo này vẫn **chưa có bằng chứng hành vi nào** (ADR-0006). 86 khẳng định xanh nói
rằng khung ảnh làm đúng điều tác giả nghĩ và điều Lead hỏi; nó không nói người thật
mở app lên và hiểu.
