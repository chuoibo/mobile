# Năm hàng tự khai "chỉ chứng minh được VỎ" — bốn cái đo được, và đã đo

```
protocol_version : v1
verdict          : (không phải review PR — đây là báo cáo đo)
đo tại           : main 10f886b (mục bổ sung qa2-060012) · main f8a6833 (các mục trên)
probe chạy tại   : nhánh qa2/nam-hang-vo-do-duoc-ruot @ 870ef42, cha là main 10f886b
                   F35+F38 đã chạy LẠI trên neo mới, kèm một lượt đột biến;
                   `git diff --stat f8a6833 10f886b -- services/api apps/mobile
                   scripts` RỖNG, nên các mục đo tại f8a6833 vẫn còn hiệu lực
skill bắt buộc   : e2e-testing
```

## Câu Lead hỏi, và câu trả lời một dòng

> "40/47 sẽ được đọc như 40 tính năng chạy được. Nếu năm trong số đó mới chỉ chứng
> minh được vỏ, thì con số thật nằm giữa 35 và 40."

**Con số thật là 40.** Không phải 35. Cả năm hàng đều đo được ruột, và bốn trong
năm hàng đã được đo trong lượt này bằng phép đo mới; hàng thứ năm (F37) hoá ra đã
có sẵn một phép đo ruột trong repo mà báo cáo trước của tôi không biết.

Cái tôi khai là "không đo được" thực ra là **"chưa ai đo"**. Đó là hai chuyện khác
hẳn nhau, và tôi đã trộn chúng vào một cột.

## Từng hàng: thiếu gì để chứng minh được ruột

| Hàng | Báo cáo trước nói "cần" | Thật ra cần gì | Kết quả |
|---|---|---|---|
| F35 Tường kỷ niệm | "Ảnh thật trong nhóm" | Ảnh **tổng hợp** đẩy qua đúng route multipart | **ĐO ĐƯỢC — ruột xanh** |
| F37 Thước phim | "Cùng lý do" (ảnh thật) | Như trên + `GEMINI_API_KEY` | **ĐO ĐƯỢC — ruột xanh** |
| F38 Widget | "Cùng lý do" (ảnh thật) | Như trên | **ĐO ĐƯỢC — ruột xanh** |
| F05 Mã kết bạn | "Hai điện thoại thật" | `cv2.QRCodeDetector` — không cần điện thoại | **ĐO ĐƯỢC — ruột xanh** |
| F29 VietQR | "Điện thoại + app ngân hàng" | Như trên, cho phần *giải mã được* | **ĐO ĐƯỢC — ruột xanh**, phần *ngân hàng chấp nhận* vẫn cần điện thoại |

### Hai lỗi đọc đã sinh ra cột "không đo được"

**Lỗi 1 — trộn "ảnh thật" với "có ảnh".** CLAUDE.md cấm đưa *ảnh bill thật* và
*người thật* vào Git. Tôi đọc thành "không được cho nhóm demo có ảnh nào", rồi kết
luận ba hàng ảnh (F35/F37/F38) là không đo được. Nhưng một tấm JPEG bàn cờ sinh
trong bộ nhớ không có người nào trong đó và không tấm máy ảnh nào chụp nó. Đẩy nó
qua chính route `POST /contexts/{id}/photos` thì nhóm có ảnh, và `MOBILE_MEDIA_ROOT`
của stack dùng-một-lần trỏ vào `/tmp`, nên byte ảnh không bao giờ tới gần repo.
`tests/qa/qa-37-reel/di-bo-reel.py` **đã làm đúng thế từ trước** — tôi không đọc nó.

**Lỗi 2 — trộn "giải mã được" với "ngân hàng chấp nhận".** Với F05/F29 tôi viết
"cần điện thoại thật". Đúng một nửa. Câu *app ngân hàng có nhận payload này và
resolve qua NAPAS không* thì đúng là chỉ điện thoại trả lời được. Nhưng câu *cái ô
vuông sản phẩm vẽ ra có đọc ngược lại đúng chuỗi đã dựng nó không* là câu của máy,
và OpenCV trả lời được. Gộp hai câu làm một đã để hở đúng chỗ đáng lo nhất:
**F05 dùng bộ mã hoá QR ~400 dòng tự viết tay trong repo** (`apps/mobile/src/ui/qr.ts`
— bit packing, Reed–Solomon, masking). Một bộ mã hoá sai tinh vi vẫn vẽ ra thứ trông
y hệt mã QR trong ảnh chụp và vẫn qua mọi `toBeDefined()`. Nó chỉ đỏ dưới một bộ
giải mã. **Chưa có gì trong repo này từng chạy một bộ giải mã.**

## Bằng chứng

### F05 + F29 — `tests/qa/qa2-vo-va-ruot/quet-ma-f05-f29.py` (mới)

```
[PASS] DOI CHUNG DUONG: cv2 doc duoc mot ma QR do segno dung -- 60 ky tu, khop=True
[PASS] F29 anh VietQR do CHINH san pham ve, cv2 doc lai RA DUNG chuoi EMVCo
       kich thuoc=(318,318) doc=120/120 ky tu khop=True
[PASS] F05 ma tran do BO MA HOA TU VIET cua repo, cv2 doc lai RA DUNG payload
       px=4 anh=(180,180) khop=True
ghi chu: F05 ma tran 37x37 modules, payload 68 ky tu
OK: tat ca phep kiem xanh   (exit 0)
```

Phép đo lấy payload từ chính `app.payments.vietqr.build_payload`, ảnh từ chính
`app.web.qr.payload_to_png_data_uri`, và ma trận F05 bằng cách gọi `encodeQr` trong
`dist-test/ui/qr.js` qua node — **không** viết lại phép mã hoá bằng Python, vì làm
thế là dựng bộ mã hoá thứ hai rồi so hai phỏng đoán của chính mình. `dist-test`
được dựng lại từ nguồn ngay trước khi đo (`tsc -p tsconfig.test.json`), không dùng
hiện vật cũ.

**Đối chứng dương** chạy trước mọi kết luận: `cv2.QRCodeDetector` trả `""` cho cả
"mã hỏng" lẫn "OpenCV hỏng". Nếu không giải mã nổi một mã do segno dựng, file
**từ chối báo bất kỳ điều gì về sản phẩm** (exit 2).

**Phép đo này có cắn được không** — đây là phần tôi kiểm thêm, vì một dấu xanh từ
một cổng không cắn được thì vô giá trị. Đảo ngược một khối pixel giữa ảnh F29:

```
dao  40x40px (~1% dien tich): VAN khop (RS vá được)
dao  60x60px (~3% dien tich): VAN khop (RS vá được)
dao  80x80px (~6% dien tich): VAN khop (RS vá được)
dao 100x100px (~9% dien tich): GAY -> doc ra 0 ky tu
dao 140x140px (~19% dien tich): GAY -> doc ra 0 ky tu
```

Ngưỡng ~9% là **đúng như mong đợi, không phải điểm yếu**: Reed–Solomon sinh ra để
vá đúng loại hỏng đó. Cái phép đo nhắm tới — generator RS sai, mask sai, đóng gói
bit sai — không tạo ra "9% module nhiễu trên một mã hợp lệ", nó làm sai chuỗi giải
ra hoặc làm mã không giải được. Cả hai đều rơi vào phía đỏ của ngưỡng này.

### F35 + F38 — `tests/qa/qa2-vo-va-ruot/di-bo-tuong-va-widget.py` (mới)

Chạy trên stack dùng-một-lần `scripts/e2e_slice.sh --keep` (API `127.0.0.1:48669`,
`MOBILE_MEDIA_ROOT=/tmp/tmp.BB7Zi5i5SB/media`). **14/14 xanh, exit 0.** Trích:

```
[PASS] DOI CHUNG: nhom chua co anh -> widget 200 va photo=None
[PASS] DOI CHUNG: nhom chua co anh -> tuong 200 va rong
[PASS] F35 tuong tra ve du 3 ky uc vua dang -- n=3
[PASS] F35 tuong xep MOI NHAT truoc -- ["Anh thu 3","Anh thu 2","Anh thu 1"]
[PASS] F35 MOI image_url cua tuong tai duoc va giai ma duoc thanh anh 320x240
       [(200,320,240),(200,320,240),(200,320,240)]
[PASS] F38 nhom CO anh -> widget khong con rong
[PASS] F38 widget cam dung tam anh MOI NHAT (theo caption)
[PASS] F38 anh cua widget tai duoc va giai ma duoc -- size=(320,240) len=2644
[PASS] nguoi la doc widget/tuong cua nhom khac -> 403 (x2)
[PASS] nguoi la tai anh cua nhom khac -> 403
[PASS] DOI CHUNG: thanh vien that VAN doc duoc widget -- 200
```

Câu mà `tests/api/` **không thể** hỏi: fake repository giữ `image_url` là một chuỗi,
nên nó không có cách nào nhận ra chuỗi đó trỏ vào hư không — đúng cái người dùng
nhìn thấy thành một tường thumbnail vỡ. Phép đo này tải **từng** URL tường phát ra
và giải mã ra ảnh 320×240 thật.

Hai dòng `DOI CHUNG` đầu đo **trước** khi seed: không có chúng thì "widget có ảnh"
không phân biệt được với "widget luôn hiện đại một thứ gì đó". Dòng `DOI CHUNG`
cuối (thành viên thật vẫn đọc được 200) là thứ biến ba dòng 403 ở trên từ "có thể
chỉ là chặn tất" thành một phép đo quyền thật.

### F37 — `tests/qa/qa-37-reel/di-bo-reel.py` (đã có sẵn, tôi chỉ chạy)

Chạy trên cùng stack, có `GEMINI_API_KEY` thật (xác nhận đã kế thừa vào tiến trình
uvicorn; **không** in ra ở bất kỳ đâu). **Tất cả phép kiểm live ĐẠT, exit 0.**

Model thật trả về `reeled:true, reason:"ok", source:"ai", title:"Bí mật nhóm B"`
với `picks` không rỗng. Phép kiểm chống ảo giác nằm ở dòng 275–279 của file đó:

```python
picked_ids <= set(memory_ids)      # AI chỉ được chọn trong số ảnh máy chủ đã chào
```

Cộng thêm `considered_count == len(memory_ids)`, đối chứng EXIF (ảnh đã bị tước
GPS/Make/UserComment, và file gốc **thật sự có** canary — nếu không phép đo EXIF là
rỗng), và trần nhịp đo được 30 lượt/60s. Vậy F37 không những có ruột, ruột nó còn
được gác kỹ hơn phần lớn hàng khác.

## Ô vẫn CHƯA quét — phần quan trọng nhất của báo cáo

| Ô | Vì sao máy không chạm được | Ai đóng được |
|---|---|---|
| Mã VietQR (F29) có được **app ngân hàng Việt thật** chấp nhận và resolve qua NAPAS không | Chuỗi đúng CRC vẫn có thể là chuỗi không ngân hàng nào nhận. Không phép tính local nào chạm tới | **Leader**, 15 phút, một điện thoại + một app ngân hàng thật |
| Mã F05 có quét được bằng **camera điện thoại thật** ở khoảng cách bàn ăn không | Xem ghi chú biên độ dưới đây | Leader / một người có điện thoại |
| Người thật có hiểu tường / widget / thước phim không | Chưa có bằng chứng hành vi nào trong repo (ADR-0006, Giai đoạn 0 bị gác có chủ ý) | Ngoài phạm vi PoC |

**Một ghi chú về biên độ, đọc cẩn thận.** File F05/F29 có in một bảng "làm xấu ảnh":

```
F29: 100%/blur0=OK  50%/blur0=OK  50%/blur1.0=X  35%/blur1.0=X  25%/blur1.5=X
F05: 100%/blur0=OK  50%/blur0=OK  50%/blur1.0=X  35%/blur1.0=X  25%/blur1.5=X
```

**Đừng đọc bảng này thành "mã sẽ hỏng trên điện thoại".** Nó nói đúng một điều: hai
mã có *cùng* biên độ dưới *cùng* một bộ giải mã, nên F05 tự viết tay không tệ hơn
F29 dùng thư viện. Bộ dò của `cv2` yếu hơn hẳn bộ dò trong app ngân hàng và camera
điện thoại, và hàm làm xấu của tôi là một phỏng đoán thô về camera, không phải mô
hình camera. Đây là dữ liệu so sánh, không phải dự đoán về phần cứng thật.

## Bổ sung `qa2-060012` — đo lại F35 trên `main` `10f886b`, và phép đo có cắn được không

Lead giao lại F35 vì bản báo cáo Lead đọc được trên `main` (`qa3-052940`, #426) còn
xếp F35 là **"chờ seed"**. Bản đó đúng tại thời điểm nó viết: phép đo F35 nằm ở PR
#427 của tôi, đẩy lúc 05:56, sau khi việc được viết ra. Lượt này tôi rebase nhánh
lên `main` `10f886b` rồi **chạy lại từ đầu**, để bằng chứng neo vào `main` hôm nay
chứ không neo vào `f8a6833`.

**Vì sao con số vẫn là 40, không phải 41.** Lead viết "nếu F35 chuyển thành
BẤM-ĐƯỢC thì con số lên 41". F35 chưa bao giờ nằm ngoài 40 — mục 3 ở trên và mục 4
của `qa3-052940` đều xếp nó *trong* 40 với đường bấm có thật, phần chưa đo là
**ruột**. Nên cái đóng lại lượt này là **ô mờ**, không phải một hàng mới:

```
trước: 40 BẤM-ĐƯỢC, trong đó ô mờ 3 hàng (F35 F38 F37 — chờ seed ảnh)
sau  : 40 BẤM-ĐƯỢC, trong đó ô mờ 0 hàng chờ seed
```

Nói "41" sẽ làm bảng 47 cộng dư một hàng. Tôi ghi ra vì đây đúng loại lệch mà lần
sau không ai truy ngược được.

**Stack và neo.** `scripts/e2e_slice.sh --keep` dựng stack dùng-một-lần từ chính cây
đã rebase (`870ef42`, cha là `main` `10f886b`): API `127.0.0.1:47859`, uvicorn pid
`3602735`, `cwd=/home/lakiet/agent-harness/wt/qa2/services/api`, khởi động 06:02:44.
Ba thứ đó tôi kiểm trước khi đo, vì máy này đang có 6 stack của các lượt khác cùng
nghe trên loopback và một `curl 200` không nói được nó trả lời từ cây nào. Lát cắt
dọc của chính script: **7 pass · 0 fail · 0 skipped**.

`git diff --stat f8a6833 10f886b -- services/api apps/mobile scripts` **rỗng** —
hai commit mới của `main` chỉ thêm tài liệu và probe. Nên số đo cũ chưa hết hạn; đo
lại là để có bằng chứng chạy thật, không phải vì nghi sản phẩm đã đổi.

**F35 + F38: 14/14 xanh, exit 0** (cùng các dòng đã dán ở mục trên, nhóm mới
`a253dd98`, ảnh sinh trong bộ nhớ, `MOBILE_MEDIA_ROOT=/tmp/tmp.hEX0jlrCWT/media`).

### Phép đo này có cắn được không — đột biến, và một cái bắt được nhờ nó

Một dấu xanh từ một cổng không đỏ được thì vô giá trị, nên tôi đột biến đúng chỗ
file này tồn tại để gác: `MediaStorage.read` trả `b""` thay vì đọc file — tức là
`image_url` trỏ vào hư không, đúng cái người dùng nhìn thấy thành tường thumbnail
vỡ. Không sửa probe, không sửa assert. Khởi động lại API trên cùng DB, cùng port,
sau khi xoá `__pycache__` của `app/media/`.

```
nền (source gốc)   : 14/14 PASS, exit 0
đột biến read()→b"": 12 PASS, 2 FAIL, exit 1
  [FAIL] F35 MOI image_url cua tuong tai duoc va giai ma duoc -- [None, None, None]
  [FAIL] F38 anh cua widget tai duoc va giai ma duoc -- status=200 size=None len=0
canary (khôi phục) : 14/14 PASS, exit 0
```

Đỏ **đúng hai dòng** đọc byte, 12 dòng còn lại giữ nguyên xanh. Đó là hình dạng cần
có: nếu đột biến làm đỏ cả bảng thì bảng không phân biệt được cái gì đang được gác.

**Và đột biến bắt được một thứ tôi chưa biết:** ảnh chết trả về **HTTP `200` với 0
byte**, không phải `404`. Một phép kiểm dạng `assert status == 200` — hình dạng mặc
định mà hầu hết ai cũng viết đầu tiên — sẽ **xanh** trên một tường thumbnail vỡ
hoàn toàn. Chỉ dòng *giải mã ra ảnh 320×240* mới đỏ. Ghi lại vì nó không riêng gì
tường ảnh: mọi route phát byte trong repo này đều có cùng cái bẫy đó.

Việc dọn: `git diff services/api/app/media/storage.py` rỗng sau khi khôi phục, và
canary chạy trên bản đã khôi phục chứ không phải trên `.pyc` cũ.

**Chưa làm lượt này, nói rõ:** F37 tôi **không** chạy lại (mục trên đo tại
`2fcd723`; sản phẩm không đổi giữa đó và `10f886b` theo `git diff` ở trên, nhưng đó
là suy luận, không phải một lượt chạy). Và câu qa3 nêu — F37 cần *một phép đo
grounding chưa ai thiết kế* — không phải chuyện seed, nên nó **không** đóng lại
cùng ô này.

## Rủi ro còn mở, theo 5 loại blocker của charter

Không có blocker mới. Cả năm hàng đều xanh ở phần đo được.

Một **suggestion** (không phải blocker, không chặn ai): `apps/mobile/src/ui/qr.ts`
là bộ mã hoá QR tự viết và cho tới hôm nay chưa cổng nào trong repo chạy một bộ
giải mã lên nó. `quet-ma-f05-f29.py` là lần đầu. File này chạy tay, không nằm trong
`make gate` — ai muốn biến nó thành cổng thường trực thì đó là một việc riêng, và
người sở hữu `apps/mobile/` nên quyết.

## Cái đáng nhớ cho lượt sau

> Cột "không đo được" trong một báo cáo QA phải chịu cùng mức nghi ngờ như cột
> "xanh". Trong năm hàng này, **năm trên năm** thực ra là "chưa ai đo", và hai lý do
> đều là trộn khái niệm: *ảnh thật* ≠ *có ảnh*, và *ngân hàng chấp nhận* ≠ *giải mã
> được*. Cả hai lần, thứ chặn phép đo không phải môi trường mà là một câu chữ trong
> báo cáo của chính tôi.

## Chạy lại

```bash
# F05 + F29 — không cần server, không cần DB
cd apps/mobile && npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && cd ../..
python3 tests/qa/qa2-vo-va-ruot/quet-ma-f05-f29.py

# F35 + F38 + F37 — cần stack sống
set -a && . <đường/dẫn>/.env && set +a
export no_proxy=127.0.0.1,localhost NO_PROXY=127.0.0.1,localhost
scripts/e2e_slice.sh --keep                      # in ra API URL
WALL_API=http://127.0.0.1:<port> python3 tests/qa/qa2-vo-va-ruot/di-bo-tuong-va-widget.py
REEL_API=http://127.0.0.1:<port> python3 tests/qa/qa-37-reel/di-bo-reel.py
```
