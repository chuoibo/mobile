# Ảnh chết trả HTTP 200 với 0 byte — số liệu để Lead quyết

- **Task**: qa2-062305
- **Neo**: `main` @ `6def9a1`; nhánh đo `qa2/anh-chet-200-rong` dựng thẳng từ `origin/main`
- **Nguồn phát hiện**: lượt đột biến F35 (`qa2-060012`, PR #428) ép `PhotoStorage.read`
  trả `b""` và thấy route trả **200 với 0 byte**, không phải 404
- **Loại**: báo cáo đo đạc. Lead yêu cầu số liệu, không yêu cầu đề xuất — nên phần
  "nên trả 404 hay 502" **không có ở đây**.

---

## 0. Một dòng

Có **hai** route phát byte ảnh và **cả hai** trả `200` + `0 byte` khi file trên đĩa bị
cắt về rỗng — nhưng **không đường nào trong sản phẩm tạo ra được trạng thái đó**: cả
bốn phép đo lên cửa upload đều cho thấy mọi thứ được nhận đều > 0 byte, và một lần ghi
hỏng giữa chừng không để lại file nào. Điều kiện *thật sự* xảy ra với người dùng là
**file bị xoá cả** (mất volume), và điều kiện đó đã trả `404` đúng.

---

## 1. Hai route phát byte — danh sách đầy đủ, và cách lấy nó

```
grep -rn "Response(content=...)" services/api/app/api/routes/*.py
  → services/api/app/api/routes/photos.py:76   GET /contexts/{context_id}/photos/{photo_id}
  → services/api/app/api/routes/photos.py:115  GET /people/{person_id}/avatar
```

Không còn route nào khác trong `app/api/routes/` dựng `Response` với `content=` +
`media_type=`. `guests.py` trả `TemplateResponse`/`RedirectResponse`, phần còn lại trả
model pydantic. Nên bảng dưới đây là **toàn bộ** bề mặt phát ảnh, không phải mẫu.

---

## 2. Máy chủ trả gì — mỗi điều kiện một dòng

Đo bằng `tests/qa/qa2-anh-chet-200-rong/do-dieu-kien-anh-chet.py` trên stack sống do
`scripts/e2e_slice.sh --keep` dựng (API `127.0.0.1:45313`, pid 74547, cwd =
worktree này, `MOBILE_MEDIA_ROOT=/tmp/tmp.RVLOzjkCPB/media`, Postgres riêng ở
`127.0.0.1:44968`). **14/14 dòng PASS, exit 0.**

| # | Điều kiện | `photos` | `avatar` | Cách dựng điều kiện |
|---|---|---|---|---|
| H | **đối chứng dương** — ảnh lành | `200`, 2403 byte, giải mã 320×240 | `200`, 2403 byte, 320×240 | upload qua chính route multipart |
| A | id ảnh không có trong DB | `404 photo_not_found` | — | `GET` với một uuid ngẫu nhiên |
| B | có bản ghi DB, **file bị xoá khỏi đĩa** | `404 photo_not_found` | — | `os.unlink` file trong media root |
| C | người gọi không phải thành viên | `403 permission_denied` | — | actor là người thứ ba |
| **D** | có bản ghi, **file bị cắt về 0 byte** | **`200`, 0 byte, `content-length: 0`, `content-type: image/jpeg`** | **`200`, 0 byte** | `path.write_bytes(b"")` |
| **E** | có bản ghi, **file bị ghi đè bằng rác** | **`200`, 26 byte không giải mã được, `content-type: image/jpeg`** | — | ghi `b"khong phai anh, chi la chu"` |
| F | đường dẫn bị thay bằng thư mục | `500` | — | `unlink` rồi `mkdir` cùng tên |
| G | file `chmod 000` | `500` | — | `chmod(0o000)` |

Hàng H đo **trước** mọi hàng khác và là điều kiện để tin phần còn lại: một stack chết
trả mọi hàng giống nhau, và không đọc được "route hỏng" khác "probe của tôi hỏng".

**Chi tiết đắt nhất ở hàng D**: response upload khai `byte_size=2403`, DB giữ con số
đó, và route đọc **không đối chiếu** — nó phát 0 byte trong khi chính máy chủ biết
đáng lẽ phải là 2403. Số dùng để phát hiện đã nằm sẵn trong bản ghi.

### Chỉ D và E là im lặng. F và G thì hét.

`grep -c ERROR` trên log uvicorn của stack sau khi chạy hết tám điều kiện:

```
2 dòng "ERROR: Exception in ASGI application"
  1 × IsADirectoryError: [Errno 21]     ← hàng F
  1 × PermissionError:  [Errno 13]      ← hàng G
```

Hàng D và hàng E **không để lại một dòng nào** trong log máy chủ. Đó là điểm khác biệt
đáng chú ý nhất giữa hai nhóm: hai điều kiện dễ nhận ra nhất lại là hai điều kiện ồn ào
nhất, còn hai điều kiện nhìn giống hệt "nhóm chưa có ảnh" thì không xuất hiện ở đâu cả
— không ở màn hình, không ở log, không ở monitoring.

---

## 3. Client hiện làm gì khi nhận 200 với 0 byte

Ba tầng, mỗi tầng một phép đo khác nhau, vì không tầng nào tự trả lời được tầng kế.

### 3a. `taiAnhCoQuyen` — coi 200-rỗng là **thành công**

`tests/qa/qa2-anh-chet-200-rong/do-client-nhan-200-rong.mjs`, chạy chính
`apps/mobile/dist-test/api.js` (module các màn import) trên cùng API sống. **7/7 PASS.**

```
[PASS] H đối chứng dương: ảnh lành  → trả về blob:nodedata:99cf8b5b-…
[PASS] đối chứng âm: 404            → NÉM ApiError status=404 code=photo_not_found
                                       message="Không tìm thấy tấm ảnh này trên máy chủ."
[PASS] máy chủ vẫn 200 khi client tự fetch
        status=200 size=0 type=image/png content-length=0  (DB khai 70)
[PASS] LỖ HỔNG: taiAnhCoQuyen coi 200-rỗng là THÀNH CÔNG, không ném gì
        trả về "blob:nodedata:8af9632c-d6cf-430c-9546-6e73c4ff8d3c"
[PASS] cái nó trả về là nguồn ảnh HỢP LỆ về mặt kiểu — Anh.tsx sẽ vẽ nó
        nguồn Anh.tsx nhận được: {"size":0,"type":"image/png","kind":"blob:"}
[PASS] tường kỷ niệm VẪN liệt kê kỷ niệm trỏ vào ảnh chết (n=1, có url chết=true)
```

Lý do nằm ở `apps/mobile/src/api.ts:1797` — `if (!response.ok)`. `ok` đúng với mọi
`200` bất kể sau đó có bao nhiêu byte. Đối chứng âm là phần bắt buộc: nó chứng minh
client **có** đường nhìn thấy lời từ chối (404 ném `ApiError` kèm câu tiếng Việt cho
người đọc) — nên việc 200-rỗng đi lọt không phải vì client mù, mà vì nó không hỏi.

### 3b. Trình duyệt — sự kiện `error`, đo trên Chrome thật

`tests/qa/qa2-anh-chet-200-rong/do-trinh-duyet-ve-gi.mjs`, headless Chrome
`chromium-1234`, byte lấy từ chính API sống rồi dựng lại `Blob` với đúng
`content-type` route đã gửi. **4/4 PASS.**

```
H ảnh lành (đối chứng dương)   blob=   78 byte  sự kiện=load    naturalSize=8x8   complete=true
D file 0 byte                  blob=    0 byte  sự kiện=error   naturalSize=0x0   complete=true
E file rác                     blob=   26 byte  sự kiện=error   naturalSize=0x0   complete=true
```

Đây là cơ chế react-native-web dùng cho `<Image>` chứ không phải một cơ chế tương tự:
`node_modules/react-native-web/dist/modules/ImageLoader/index.js:104-105` gán
`image.onerror` / `image.onload` lên một `new window.Image()` — đúng thứ vừa đo.

### 3c. `Anh.tsx` — vẽ lại **chỗ đứng**, im lặng

`sự kiện=error` → `onError` → `setHong(nguon)` (`apps/mobile/src/ui/Anh.tsx`) →
`trangThai = "hong"` → khung vẽ `cho`, tức stand-in do màn gọi cung cấp.

Docblock của chính file đó nói rõ đây là hành vi cố ý (ghi chú 2: *"A failed load goes
back to the stand-in and stays there. It does not show a broken-image glyph, and it
does not show the server's reason"*). Nên **client không báo gì cả**:

- không glyph ảnh vỡ
- không câu chữ (câu `ApiError` ở 3a bị `.catch(() => …)` bỏ đi, kể cả với 404)
- không retry
- không dòng console

Và stand-in của trạng thái `hong` **là cùng một thứ** với stand-in của `khong-co`. Trên
màn Kỷ niệm đó là ô chờ; trên Cá nhân đó là chữ cái đầu của tên — đúng cái người chưa
có ảnh đại diện nhìn thấy. Nghĩa là: **màn hình của một ảnh chết và màn hình của "chưa
có ảnh" là một**, còn tường thì vẫn liệt kê kỷ niệm đó (đo ở 3a, dòng cuối) — nên người
dùng thấy một ô kỷ niệm có caption mà không có ảnh, và không có gì nói vì sao.

---

## 4. Điều kiện nào THỰC SỰ xảy ra với người dùng — và điều kiện nào không

Câu hỏi này bảng ở mục 2 không trả lời được: probe dựng hàng D–G bằng cách **với tay
qua sản phẩm** sửa thẳng media root. Probe làm được không có nghĩa người dùng làm được.
Phần 3 của probe đo đúng chỗ đó — cửa duy nhất sản phẩm mở vào thư mục ấy.

| Điều kiện | Người dùng thật có gặp không | Bằng chứng |
|---|---|---|
| **B — file bị xoá cả** | **CÓ, và đã xảy ra rồi** | `docker-compose.yml:113-122` ghi lại lần đo trên stack chung: sau một `up --build`, `select count(*) from uploaded_images` = 4, `find ~/.local/share/rudi/media -type f` = 0. Volume `mobile-media-data` được thêm để vá. Route trả `404` — **đúng** |
| A — id không có trong DB | Gần như không | Không có route `DELETE` nào cho ảnh (`grep -n delete services/api/app/api/routes/photos.py` → rỗng), nên bản ghi không tự mất. Chỉ tới được bằng URL gõ tay / link cũ |
| C — không phải thành viên | Có, bình thường | `403`, đúng thiết kế |
| **D — file 0 byte** | **KHÔNG — sản phẩm không tạo ra được** | bốn phép đo dưới |
| **E — file rác** | **KHÔNG — cùng lý do** | cùng bốn phép đo |
| F, G — thư mục / chmod 000 | Không | Cùng lý do với D/E, và `500` + traceback nên không im lặng |

Bốn phép đo cho hàng D/E, tất cả PASS:

```
R1  upload thân RỖNG (0 byte)           → 415 not_an_image, không tạo bản ghi
R2  upload JPEG CẮT CỤT (nửa file)      → 415 not_an_image
R3  ảnh 1×1 (nhỏ nhất được nhận)        → trên đĩa 285 byte, byte_size=285
R4  sanitize_image trên 7 đầu vào:
      rỗng            → TỪ CHỐI (not_an_image)
      một byte        → TỪ CHỐI (not_an_image)
      chữ thuần       → TỪ CHỐI (not_an_image)
      jpeg cắt cụt    → TỪ CHỐI (not_an_image)
      jpeg chỉ header → TỪ CHỐI (not_an_image)
      ảnh 1×1         → NHẬN 285 byte
      ảnh 320×240     → NHẬN 2403 byte
    → không đầu vào nào được NHẬN mà cho ra 0 byte
R5  ghi hỏng giữa chừng dưới trần RLIMIT_FSIZE=4096, ghi 200000 byte:
      RAISED 27 (EFBIG — cùng lớp lỗi với ENOSPC đĩa đầy)
      FINAL_EXISTS False · FINAL_SIZE -1 · LEFTOVERS []
    → không để lại file rỗng, không để lại file cụt, không để lại file tạm
```

R5 là phép đo quan trọng nhất vì nó là cách duy nhất *sản phẩm* có thể tự tạo ra một
file 0 byte: ghi thành công một nửa rồi chết. `RLIMIT_FSIZE` là trần thật của kernel,
không phải mock — write raise `EFBIG` đúng như `ENOSPC` khi đĩa đầy. Kết quả: đường
dẫn cuối không tồn tại, vì `PhotoStorage.write` ghi vào file tạm rồi `os.replace`.

Và `PhotoStorage.write` có đúng **một** người gọi trong toàn bộ máy chủ
(`grep -rn "photo_storage.write" services/api` → `service.py:1081`), nên không có cửa
thứ hai vào thư mục đó.

**Kết luận mục 4**: D và E chỉ tới được khi có thứ **ngoài sản phẩm** sửa
`MOBILE_MEDIA_ROOT` — người vận hành, một bản khôi phục backup dở, một lần copy volume
đứt giữa chừng, hỏng filesystem. Không phải người dùng, và cũng **không phải kẻ tấn
công**: một người ghi được vào media root thì đã có quyền trên máy rồi, còn qua HTTP
thì cửa duy nhất là `POST /photos` và nó từ chối 5/7 đầu vào ở R4.

---

## 5. Tái lập

```bash
scripts/e2e_slice.sh --keep                      # in ra URL API + đường dẫn media
export ANH_API=http://127.0.0.1:<port>
export ANH_MEDIA=<MOBILE_MEDIA_ROOT của stack>   # đọc từ /proc/<pid>/environ

python3 tests/qa/qa2-anh-chet-200-rong/do-dieu-kien-anh-chet.py     # 14/14, exit 0
node    tests/qa/qa2-anh-chet-200-rong/do-client-nhan-200-rong.mjs  #  7/7,  exit 0
node    tests/qa/qa2-anh-chet-200-rong/do-trinh-duyet-ve-gi.mjs     #  4/4,  exit 0
```

Cả ba probe đều dựng dữ liệu của riêng chúng qua chính API, đều có đối chứng dương ở
dòng đầu, và không probe nào đụng vào dữ liệu thật: ảnh là JPEG/PNG bàn cờ sinh trong
bộ nhớ, media root là thư mục tạm ngoài repo, không ảnh bill, không tên người thật.

---

## 6. Cái ba probe này **không** chứng minh

- **Không** chứng minh hàng D/E xảy ra trên máy demo 8099 hay bất kỳ máy nào đang
  chạy. Chúng chứng minh route *sẽ* trả gì nếu điều kiện đó có mặt.
- **Không** đo được `<Image>` của React Native trên **điện thoại thật**. Mục 3b đo
  đường web (react-native-web → `new window.Image()`). Trên RN gốc, `taiAnhCoQuyen`
  rơi vào nhánh `FileReader.readAsDataURL` trong `nguonCucBo` (`api.ts:1824`) chứ không phải
  `createObjectURL`, và decoder là của nền tảng. Kết cục *có thể* giống — nhưng chưa ai
  đo, và tôi không viết nó thành đã đo.
- **Không** trả lời "nên đổi thành gì". Lead giữ quyết định đó; mục 2 và mục 4 là số
  liệu để quyết.
- Hàng A/B/C/E/F/G chỉ đo trên route `photos`. Route `avatar` đo hàng H và hàng D
  (cùng hình dạng, cùng kết quả) — phần còn lại suy từ code đi chung một nhánh
  `except FileNotFoundError`, và **suy không phải đo**.
