# rd-qa-35 · PASS #195 — ảnh thật sự lên màn, và một cổng của chính PR đó mù

- protocol_version: v1
- verdict: **PASS** (có 1 phát hiện kèm theo, không chặn merge)
- PR: #195 `frontend/rd-fe-24-khung-anh-that`
- SHA đã test: `1f1d2732d5253aba4533711f09a8f345f177ec74`
- **đo tại**: `13245f934eac32860c36ee11f88b497258117a4e` — kết quả merge #195 ⊕ `origin/main@4156f2d`
- đối chứng "trước PR" đo tại: `7adf961` (đang là `origin/main`)

## Lý do PASS

Tuyên bố trung tâm của PR — "app lần đầu render được một tấm ảnh" — **đúng, và đo
được ở DOM sống**: với `photo_url` là một URL `http://`, trang render một
`<img>` thật, ảnh tải xong (`naturalWidth` 1×1, không phải 0). Trên `main` trước
PR, cùng phép đo cho **0 ảnh**. Chốt chặn scheme (`javascript:` / `data:` /
`file:`) giữ đúng ở DOM chứ không chỉ trong parser, và cổng giữ nó **đỏ được**
khi bị đột biến.

Phát hiện kèm theo là về **cổng**, không về sản phẩm: một trong hai ca mà commit
thứ hai của PR thêm vào không bắt được chính hồi quy nó nêu tên. Code sản phẩm
đúng, nên nó không chặn merge — nhưng nó cần đóng lại, và file này kèm sẵn cổng
thay thế đã chứng minh đỏ-trước/xanh-sau.

## Cổng đã chạy (cây sạch, SHA hợp nhất `13245f9`)

```
python3 -m pytest services/api/tests tests -q
  -> 1278 passed, 293 skipped, 4597 subtests passed in 74.50s

cd apps/mobile && npm test
  -> # tests 546  # pass 546  # fail 0
```

293 skipped là tầng `tests/postgres` — **chưa chạy**, không phải xanh. Xem mục
"ô chưa quét".

## Phát hiện 1 — cổng `<Image> còn đó` là grep văn bản nguồn, đột biến đi lọt

`apps/mobile/tests/anh.test.mjs:100` gác đường ảnh bằng cách **đọc file nguồn**:

```js
const src = readFileSync(join(MOBILE_ROOT, "src/ui/Anh.tsx"), "utf8");
assert.match(src, /<Image\b/);
assert.match(src, /source=\{\{\s*uri:/);
```

Docstring ngay trên nó nêu đúng hồi quy cần chặn:

> 1. `Anh` thôi render `<Image>` thật (ai đó đơn giản hoá về View tô màu).

Đột biến đúng hồi quy đó — `src/ui/Anh.tsx:119`, đổi `{veAnh ? (` thành
`{false ? (`, tức `<Image>` không bao giờ được render, app quay về 0 ảnh:

```
cd apps/mobile && npm test
  -> # tests 546  # pass 546  # fail 0        <-- KHÔNG đỏ
```

Chữ `<Image` vẫn nằm trong nguồn, nên `assert.match` vẫn đạt. Cổng đó đạt với
mọi bản `Anh.tsx` còn *chứa* chữ `<Image`, kể cả bản không bao giờ vẽ nó.

Tác giả **đã nói ra giới hạn này** trong chính docstring ("bằng chứng render
thật nằm ở ảnh chụp kèm PR"), nên đây không phải chuyện giấu giếm. Vấn đề là ảnh
chụp kèm PR không có ai chạy lại: sau khi merge, thứ duy nhất còn canh đường ảnh
là hai ca đọc nguồn ở trên.

Đối chứng cho thấy cổng thứ hai của PR thì **thật**. Đột biến gỡ lọc scheme
(`places.ts`, xoá dòng `if (!/^https?:\/\//i.test(s)) return null;`):

```
  -> not ok 4 - photo_url không phải http/https bị bỏ, không đưa vào <Image>
  -> # tests 546  # pass 545  # fail 1
```

Đỏ đúng một ca, đúng chỗ. Nên phát hiện này hẹp: **một** trong hai ca mù, không
phải cả đường ảnh không được gác.

### Cổng thay thế, đã chứng minh đỏ-trước/xanh-sau

`tests/qa/rd-qa-35/anh-song-probe.mjs` đo ở DOM sống thay vì đọc nguồn. Ba ca,
vì một lượt chỉ đo URL độc thì không phân biệt được "chốt chặn đã giữ" với "máy
đo đã chết":

| ca | `photo_url` | mong đợi |
|---|---|---|
| `anh-that` | `http://127.0.0.1:<port>/theo-doi.png` | CÓ `<img>`, tracker NHẬN request |
| `scheme-doc` | `javascript:alert(1)` | KHÔNG `<img>`, tracker không nhận gì |
| `khong-anh` | `null` | KHÔNG `<img>` (đối chứng: làm số 0 của ca 2 có nghĩa) |

Ma trận đo được:

| cây | `anh-that` | probe | `npm test` |
|---|---|---|---|
| `main@7adf961` (trước #195) | img=0, hit=0 | **exit 2** | xanh |
| #195 ⊕ main `13245f9` | img=1, hit=1 | **exit 0** | 546/546 |
| #195 + đột biến `{false ?` | img=0, hit=0 | **exit 2** | 546/546 xanh |

Hàng cuối là điểm của cả file này: probe đỏ đúng lúc `npm test` xanh.

Hàng đầu đồng thời là đối chứng cho tuyên bố của PR — trước #195 app render 0
ảnh, nên "lần đầu render được một tấm ảnh" là mô tả đúng chứ không phải cách nói.

## Phát hiện 2 — cơ chế theo dõi bằng ô nhập liệu: có thật, chưa chạm được

Ca `anh-that` đo thêm một thứ chưa cổng nào trong repo đo: **`photo_url` không
đi qua fetch stub**. Nó vào thẳng `<Image>`, nên trình duyệt của người đang xem
màn hình bắn một request THẬT tới host mà URL đó nêu tên. Tracker nhận được:

```
tracker nhan: /theo-doi.png tu 127.0.0.1 referer=http://127.0.0.1:45573/
   ua=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ...
```

Tức host kia học được: màn hình đã được mở, lúc nào, từ địa chỉ IP nào, bằng
trình duyệt nào.

**Hôm nay đây chưa phải lỗ hổng**, vì `photo_url` do máy chủ tự sinh
(rd-be-05) — người trong nhóm không viết được vào nó. `parsePhotoUrl` lại còn
lọc scheme dù nguồn đã là máy chủ, và cổng giữ nó đỏ được. #195 làm đúng.

Nó thành lỗ hổng vào ngày một URL **client tự khai** đi vào cùng cái `<Anh>`.
Hai trường như vậy đã tồn tại trên `main`, không trường nào được lọc:

| trường | nơi khai | kiểm ở server | kiểm ở client khi đọc |
|---|---|---|---|
| `MemoryCreateRequest.image_url` | `services/api/app/api/schemas.py:619` | `StrictStr, min_length=1` — **không kiểm scheme** | — |
| `MessageCreateRequest.image_url` | `services/api/app/api/schemas.py:686` | `StrictStr, max_length=2000` — **không kiểm scheme** | `chat/tin-nhan.ts:130` dùng `strOrNull`, **không lọc** |

Chưa màn nào render hai trường này (`grep -rn "imageUrl\|image_url" apps/mobile/src/`
chỉ ra khai báo kiểu và đường ghi, không có `<Image>`), nên lỗ hổng **đang ngủ**.
Nhưng #195 vừa dựng đúng cái khung sẽ đánh thức nó, và khung đó tên là `Anh`,
dùng chung cho mọi màn.

Tiêu chí gỡ: PR nào nối `image_url` (kỷ niệm hoặc ảnh trong chat) vào `<Anh>`
phải mang theo lọc scheme ở **server** (chỗ chặn đúng, vì client nào cũng có thể
bị thay) và một ca kiểm đỏ được. Đây là suggestion cho lượt sau, không phải
blocker của #195.

## Ô CHƯA QUÉT

- **Tầng `tests/postgres`**: 293 ca skipped, **0 chạy**. Không có DB trong lượt
  này. Ba luật tiền và mọi hành vi chỉ tồn tại trên PostgreSQL đều không được
  lượt này chạm tới.
- **Điện thoại thật**: probe chạy chromium headless ở khung 390×844,
  `isMobile: true`. Đó không phải một chiếc điện thoại. Ảnh trên màn hình thật,
  ở mạng thật (ảnh tải chậm, tải hỏng giữa chừng) — chưa quét.
- **Trạng thái `hong` khi tải ảnh lỗi**: `Anh.tsx` có `onError` quay về chỗ chờ
  và `hong` sticky theo URI. Probe không đo đường này (tracker luôn trả 200).
- **Ba màn còn lại của #195**: probe chỉ đi qua Khám phá. `MoDau` và `CaNhan`
  cũng gọi `<Anh>`, và cả hai truyền `uri` là biến chưa có nguồn máy chủ — chưa
  quét ở DOM sống.
- **Tương phản chữ trên ảnh thật**: docstring của `Anh.tsx` tự nêu rủi ro này
  ("scrim đo trên chỗ chờ tô màu, ảnh thật có thể sáng hơn"). Chưa đo.
- **Mã QR quét bằng app ngân hàng thật**: vẫn chưa ai làm. Không liên quan PR
  này, giữ trong danh sách cho tới khi leader kiểm.

## Tái lập

```bash
git worktree add --detach /tmp/qa195 1f1d2732d5253aba4533711f09a8f345f177ec74
cd /tmp/qa195 && git merge origin/main --no-edit
cp -al <cây có node_modules>/apps/mobile/node_modules /tmp/qa195/apps/mobile/node_modules

python3 -m pytest services/api/tests tests -q
cd apps/mobile && npm test                      # dựng luôn .expo-build-check
cd /tmp/qa195 && node tests/qa/rd-qa-35/anh-song-probe.mjs

# đột biến làm cổng của PR lộ ra là mù:
#   src/ui/Anh.tsx:119   {veAnh ? (   ->   {false ? (
#   npm test  -> vẫn 546/546 xanh
#   probe     -> exit 2
```

`node_modules` phải `cp -al`, không `ln -s`: expo export chết với
`node_modules` là symlink.
