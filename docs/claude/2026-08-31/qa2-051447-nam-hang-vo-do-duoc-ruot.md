# Năm hàng tự khai "chỉ chứng minh được VỎ" — bốn cái đo được, và đã đo

```
protocol_version : v1
verdict          : (không phải review PR — đây là báo cáo đo)
đo tại           : main f8a6833
probe chạy tại   : main 2fcd723 + nhánh qa2/nam-hang-vo-do-duoc-ruot
                   f8a6833 chỉ chạm scripts/check_actor_headers.py và hai file
                   tests/ gác cổng; `git diff --stat 2fcd723 f8a6833 -- services/api
                   apps/mobile` RỖNG, nên số đo dưới đây còn hiệu lực ở f8a6833
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
