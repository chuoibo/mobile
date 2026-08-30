# FAIL — PR #296 (rd-fe-34, ảnh địa điểm lên Khám phá)

**Lý do:** cổng mới của chính PR — `tools/quet-tab-url.mjs` — **thoát rc=1** trong cây
sạch **tại đúng SHA head của PR**, với `dia-diem: can 1 anh giai ma duoc, dang co 0`.
Mô tả PR khai `rc=0, tổng findings 0` và `dia-diem els=268, 1 anh giai ma duoc`. Ba lượt
chạy độc lập của tôi đều ra `els=265, 0 ảnh, rc=1`. Bằng chứng đầu bảng của PR **không
tái lập được** (blocker loại 5), và merge như hiện trạng là đưa một cổng đỏ vào `main`.

**Phần sản phẩm thì ĐÚNG** và tôi đã chứng minh đỏ-trước/xanh-sau trên bản đã build.
Cái hỏng là cổng đo, không phải bản vá. Chi tiết bên dưới.

- `protocol_version`: v1
- Đo tại `fb9b5ff` = #296(`6cf26b1`) ⊕ `main`(`ca5e7e8`), merge sạch, không xung đột.
  Cổng của PR còn được chạy lại tại **`6cf26b1` trần** (detached) để loại trừ ảnh hưởng
  của phép gộp — kết quả y hệt.
- SHA này **là nhánh chưa merge**.
- Kỹ năng đã dùng: `e2e-testing`, `bug-reproduction`.

---

## 1. Blocker — cổng mới của PR đỏ tại chính SHA của PR

`dia-diem` là một trong ba hàng `anh` mà PR này thêm vào. Nó không đạt điều kiện của
chính nó.

```
tại fb9b5ff (cây gộp), lượt 1:  Error: dia-diem: can 1 anh giai ma duoc, dang co 0  (els=265 chars=587)  rc=1
tại fb9b5ff (cây gộp), lượt 2:  Error: dia-diem: can 1 anh giai ma duoc, dang co 0  (els=265 chars=587)  rc=1
tại 6cf26b1 (head PR trần):     Error: dia-diem: can 1 anh giai ma duoc, dang co 0  (els=265 chars=587)  rc=1
```

Mô tả PR:

```
node tools/quet-tab-url.mjs      rc=0, tổng findings 0
  dia-diem           els=268  1 anh giai ma duoc
```

Lệch đúng **3 phần tử** (265 vs 268) — bằng đúng kích thước cây con của một `<img>`,
đo được ở mục 2 bên dưới (283 → 286). Nên đây không phải sai số đo; đây là "màn đó có
tấm ảnh hay không", và ở cây sạch thì **không**.

**Máy quét không hỏng** — hai canary bắt buộc đều đúng ở cả ba lượt:

```
canary xau        findings=5 exit=2      (cần > 0)   ✔ ĐỎ
canary sach       findings=0 exit=0      (cần = 0)   ✔ XANH
canary nang       findings=3 exit=2                  ✔ ĐỎ
canary nang sach  findings=0 exit=0                  ✔ XANH
kham-pha          findings=0 exit=0, 1 anh giai ma duoc   ✔ (hàng anh KIA thì đạt)
```

`kham-pha` đi qua cùng stub, cùng fixture, và **lấy được ảnh**. Nên byte ảnh có được
phục vụ; chỉ riêng màn chi tiết trong thế giới fixture là không nhận được. Chẩn đoán
gốc là việc của lane frontend — tôi dừng ở chỗ tái lập được.

Chạy với Chrome ghim, đúng luật của lane:
`PUPPETEER_EXECUTABLE_PATH=/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome`

**Tiêu chí gỡ chặn:** `node tools/quet-tab-url.mjs` thoát `rc=0` trong cây sạch tại SHA
được nộp, hoặc hàng `dia-diem` được hạ kỳ vọng kèm lý do — và số trong mô tả PR khớp
với số chạy lại được.

---

## 2. Phần sản phẩm ĐÚNG — đỏ trước, xanh sau, đo trên bản đã build

PR sửa đúng **một** file sản phẩm: `ChiTietDiaDiem.tsx` truyền `uri`/`name` cho
`AnhDiaDiem`. Tôi dựng hai bundle web thật (`expo export --clear`, có kiểm chuỗi
`localhost:8137` đã được nhúng) rồi đi bộ bằng puppeteer ở `390x844`, đếm ảnh bằng
**pixel đã giải mã** (`naturalWidth > 0`), không đọc markup — rnw không đặt địa chỉ ảnh
vào DOM nên grep markup sẽ báo đạt trong khi không có gì tải.

Kịch bản `GIA` = API thật, chèn `photo_url` vào **đúng một** địa điểm đầu tiên:

| bundle | GIA/kham-pha | GIA/dia-diem |
|---|---|---|
| `main` (trước PR) | 1 ảnh `480x360` | **0 ảnh** ← lỗ có thật |
| `#296` (sau PR) | 1 ảnh `480x360` | **1 ảnh `480x360`** ← đã vá |

`els` 283 → 286 và `chars` **1011 ở cả hai** — tức needle bằng chữ hoàn toàn mù với
chuyện tấm ảnh có hay không. Nhận định trung tâm của PR là đúng, và tôi xác nhận nó
bằng phép đo độc lập chứ không phải bằng công cụ của PR.

Kịch bản `THAT` (điều khiển) chứng minh con số 0 ở trên là sự thật về màn hình chứ
không phải phép đo hỏng: cùng bundle, cùng script, chỉ khác là không chèn gì.

Không có phần tử nào tràn viewport ở màn chi tiết. Ở Khám phá, 5 phần tử nằm ngoài
viewport — tôi đã soi từng cái: **cả 5 đều là chip danh mục nằm trong dải cuộn ngang**
(`Tất cả / Quán ăn local / Cafe / Vui chơi / Đi chơi đêm`, mỗi cái đều có tổ tiên cuộn
ngang). Đây là guard của tôi quá ngây thơ, **không phải lỗi bố cục**, và có mặt y hệt
trên `main`. Ghi ra để không ai đọc nhầm thành finding.

Script: `tests/qa/qa-tt-0025/di-bo-296.mjs` (chạy lại được, nhận đường dẫn dist làm tham số).

---

## 3. Không phải blocker, nhưng tiêu đề PR đang nói quá: ảnh **chưa** lên Khám phá

Tiêu đề PR là "Ảnh thật lên Khám phá". Đo trên máy chủ thật dựng từ chính cây này
(`uvicorn` cổng 8137, không phải container demo 8099 vốn hay tụt lại sau main):

```
GET /places                12 địa điểm, 0/12 có khoá photo_url
                           photo_count = [7,8,9,11,12,14,15,18,21,24,26,32]
GET /places/{id}           photo_url KHÔNG có · photos_available = false
openapi.json tại fb9b5ff   Place       -> photo_url present? False
                           PlaceDetail -> photo_url present? False
```

Và đi bộ trên bundle đã build, chống vào API thật, không chèn gì (kịch bản `THAT`):

```
THAT/kham-pha   els=630  chars=699   img=0  giải mã=0
THAT/dia-diem   els=283  chars=1011  img=0  giải mã=0
```

**Không một tấm ảnh địa điểm nào render trong sản phẩm hôm nay**, ở cả hai màn. Bản vá
là đúng nhưng **đang ngủ** — nó có tác dụng vào đúng ngày backend gửi `photo_url`.

Đây là hình dạng "lỗ hổng ngủ chờ tính năng bật lên", và bản thân công cụ của PR ghi
rất thành thật ở `tab-snapshots.mjs:654`: *"`photo_url` is deliberately absent from all
six. `GET /places` has no such field today"* — rồi `themAnhDiaDiem()` chèn vào để quét.
Mục "Nói rõ cái chưa làm" của PR cũng có khai. Vấn đề là tiêu đề và bảng bằng chứng đọc
lên như thể ảnh đã ship, nên tôi nêu ra để Lead không đếm F02 thành "đã có ảnh".

Sửa rẻ: đổi tiêu đề thành "ảnh địa điểm lên được **máy quét**, và vá lỗ màn chi tiết".

---

## 4. Không phải blocker: bản vá sản phẩm không có cổng nào giữ

Gỡ đúng hai dòng `uri={place.photoUrl}` / `name={place.name}` khỏi `ChiTietDiaDiem.tsx`
rồi chạy lại bộ test đã commit:

```
npm test (bản đầy đủ)        705 pass / 0 fail / 0 skipped
npm test (đã gỡ bản vá)      705 pass / 0 fail / 0 skipped   ← không đổi một ca nào
```

Bộ test trong `npm test` **không** bắt được việc gỡ chính bản vá mà PR này tồn tại để
làm. Ca mới PR thêm vào `anh.test.mjs` đo độ sáng ảnh thử của **máy quét**, không đo
màn hình. Thứ duy nhất bắt được là `quet-tab-url.mjs` — mà nó cần Chrome ghim nên nằm
ngoài `npm test` (PR có khai), **và nó đang đỏ** (mục 1). Nên trên thực tế lỗ này hiện
không có cổng nào canh.

File đã khôi phục nguyên vẹn sau đột biến (md5 khớp, `git diff` rỗng).

---

## Cổng đã chạy

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2172 passed, 420 skipped**, 4797 subtests, 155s |
| `cd apps/mobile && npm test` | **705 pass / 0 fail / 0 skipped** |
| `npx tsc --noEmit` | sạch, `rc=0` |
| `node tools/quet-tab-url.mjs` | **rc=1** — mục 1 |
| `node tests/qa/qa-tt-0025/di-bo-296.mjs` | mục 2 |
| `git merge origin/main` | sạch, không xung đột |

420 ca skip là tầng `tests/postgres` (thiếu `MOBILE_TEST_DATABASE_URL`). **Skip không
phải xanh** — nhưng PR này không chạm backend nên tôi không coi đó là ô còn nợ của nó.

## Ô CHƯA quét

- **Điện thoại thật.** Mọi phép đo trên là Chromium desktop giả lập `390x844`. Không có
  iOS/Android thật, không có Safari.
- **Ảnh production.** Phép đo dùng PNG fixture đáy sáng. Ảnh thật có thể sáng hơn nữa;
  không có gì canh chuyện đó (PR cũng đã tự khai).
- **`soi-tuong-phan-anh.mjs`** — tôi chưa chạy. Lượt này dừng ở blocker mục 1.
- **Chặng docker.** PR không đổi khai báo route nên không kích hoạt ràng buộc của Lead.
- **Chủ đề tối** và các khung nhìn `320` / `1440`: chưa quét.
- **Mã QR chưa được quét bằng app ngân hàng thật** — vẫn nguyên, chờ leader.
