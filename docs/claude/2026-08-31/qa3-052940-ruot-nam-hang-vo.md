# Năm hàng "chỉ chứng minh được vỏ": thiếu gì để chứng minh ruột

- **SHA đo**: `main` tại `2fcd723`
- **protocol_version**: v1
- **verdict**: không phải review PR — đây là phép đo trả lời một câu hỏi của Lead
- **skill**: `exploratory-testing` (phiên có charter), `superpowers:systematic-debugging`
  (khi phép đo của tôi ra đỏ)
- **Nhận hộ**: qa2 đang RATE_LIMITED. Số gốc 40/47 là của qa2 tại `880cd6d` (#421).

## Câu hỏi

qa2 đếm 40/47 BẤM-ĐƯỢC và **tự khai** năm hàng trong số đó mới chỉ chứng minh
được vỏ: **F35 · F37 · F38 · F05 · F29**. Lead hỏi đúng một câu cho mỗi hàng:
*thiếu gì để chứng minh được ruột?*, và xếp câu trả lời vào ba ô:

1. thiếu dữ liệu demo → nói rõ dữ liệu gì, Lead cho seed
2. cần nhiều người thật / nhiều máy → **KHÔNG-ĐO-ĐƯỢC**, xếp ra khỏi 40
3. đo được mà chưa ai đo → đo luôn nếu rẻ

## Trả lời gọn

**Con số không tụt. Nó bớt mờ.** Hai trong năm hàng thuộc ô 3 và **tôi đã đo
xong lượt này**. Ba hàng còn lại thuộc ô 1, và cái thiếu **không phải ảnh thật** —
đó là chỗ khung của qa2 sai, không phải con số.

| F## | qa2 xếp | Thực tế | Ô |
|---|---|---|---|
| F29 | cần app ngân hàng thật | Chuỗi EMVCo đã đúng *và* **tấm hình mang đúng chuỗi đó** — 4/4 giải ngược qua OpenCV | 3 → **đã đo** |
| F05 | cần hai điện thoại thật | Luồng kết bạn đã có test trình duyệt; **ô vuông chưa ai giải ngược** — nay 9/9, version 5→12 | 3 → **đã đo** |
| F35 | cần ảnh thật trong nhóm | Cần **một tấm ảnh bất kỳ**. Ảnh sinh ra bằng code là đủ | 1 |
| F38 | cùng lý do | Cùng dữ liệu — widget đọc chính bảng `memories` đó | 1 |
| F37 | cùng lý do | Cùng dữ liệu, **cộng** một phép đo grounding chưa ai thiết kế | 1 |

## 1. F29 và F05 — ô 3, và chúng chia chung một khúc ruột

`src/ui/qr.ts` là **encoder QR tự viết 521 dòng** (ISO/IEC 18004: dòng bit,
Reed-Solomon, chọn mask). Nó có đúng hai người gọi:

```
ui/MaVietQr.tsx            F29 — chuỗi thanh toán EMVCo
screens/ca-nhan/MaCuaToi   F05 — link kết bạn do linkMaBan dựng
```

"Chuỗi đúng" và "tấm hình mang đúng chuỗi đó" là **hai mệnh đề khác nhau**. Ba
luật tiền và 41 golden vector gác mệnh đề thứ nhất. Mệnh đề thứ hai — thứ quyết
định camera đọc được hay không — không luật nào chạm tới.

### F29: công cụ đã có sẵn, chưa cổng nào chạy nó

`apps/mobile/tools/qr-roundtrip.py` làm đúng việc này: lấy payload từ chính
`app/payments/vietqr.py` của máy chủ, cho `qr.ts` vẽ, rồi bắt **OpenCV** đọc lại.
Đáp án đến từ một thư viện không chung tác giả, không chung dòng code nào.

Nó chỉ được **một comment** trong `tests/thanh-toan.test.mjs` nhắc tên. Không
Makefile, không npm script, không CI nào gọi. Tôi chạy nó, trên cây dựng lại
sạch từ `2fcd723`:

```
ok   45x45 120 bytes
ok   49x49 123 bytes
ok   45x45 115 bytes
ok   49x49 126 bytes
4/4 exact round-trips via OpenCV 4.13.0
```

Ruột của F29 đo được thêm một tầng: **ô vuông thật sự mang chuỗi thanh toán**.
Phần còn lại — ngân hàng có nhận không — vẫn là ô 2 và vẫn cần một cái điện
thoại. Nhưng đó là một phần hẹp hơn nhiều so với "chỉ chứng minh được vỏ".

### F05: người gọi thứ hai chưa ai giải ngược

Bốn ca VietQR rơi vào 45x45 và 49x49 — **version 7 và 8**. `chooseVersion` khai
version **1 đến 15**. Nghĩa là mười ba nhánh version, cùng toàn bộ bảng
alignment pattern đổi hình theo chúng, chưa từng có máy đọc độc lập nào nhìn vào.

Ô vuông F05 nằm đúng trong khoảng chưa ai chạm, và nó chịu một áp lực riêng:
`URLSearchParams` mã hoá mỗi dấu tiếng Việt thành ba ký tự ASCII, nên
"Nguyễn Thị Hà" — 13 ký tự trên màn — là **43 byte** trong payload. Cái phình đó
đẩy mã lên version, và nó vô hình với người đọc cái tên.

`tests/qa/qa3-ruot-nam-hang/probe_ma_qr_giai_nguoc.py` gọi `linkMaBan` **thật**
và `encodeQr` **thật** (không viết lại logic — chấm điểm bản sao của chính mình
là cái bẫy `CLAUDE.md` đã nêu), rồi bắt OpenCV đọc lại:

```
ok   v 5 37x37 mask2  74 bytes  tên   2 ký tự  khớp 5/5 cách vẽ
ok   v 5 37x37 mask2  75 bytes  tên   8 ký tự  khớp 5/5 cách vẽ
ok   v 6 41x41 mask2 101 bytes  tên  13 ký tự  khớp 5/5 cách vẽ
ok   v 7 45x45 mask2 112 bytes  tên  21 ký tự  khớp 5/5 cách vẽ
ok   v 8 49x49 mask2 142 bytes  tên  33 ký tự  khớp 3/5 cách vẽ
ok   v 8 49x49 mask2 127 bytes  tên  60 ký tự  khớp 5/5 cách vẽ
ok   v11 61x61 mask2 250 bytes  tên  88 ký tự  khớp 5/5 cách vẽ
ok   v11 61x61 mask2 227 bytes  tên 160 ký tự  khớp 4/5 cách vẽ
ok   v12 65x65 mask2 267 bytes  tên 200 ký tự  khớp 5/5 cách vẽ
tu choi  tên 176 ký tự  encodeQr: PAYLOAD_TOO_LONG

9/9 giải ngược khớp tuyệt đối qua OpenCV 4.13.0
version chạm được: [5, 6, 7, 8, 11, 12]  (1 bậc bị encoder từ chối)
```

Bậc bị từ chối **không phải lỗi**: `MaCuaToi.tsx` bắt `QrError` và hiện câu
"Tên hiển thị dài quá mức vẽ được thành mã". Một ô vuông từ chối được vẽ an toàn
hơn một ô vuông vẽ dở — vẽ dở vẫn quét được, vào một thứ khác.

Canary hai chiều, vì một cổng chưa ai chạy mà xanh ngay thì phải chứng minh nó
đỏ được:

```
CANARY: cứ 5 module lật 1, rải khắp symbol
v 5 37x37 lật  274 module  khớp 0/5  lech (không giải được)
...
9/9 bậc lệch khi bị phá. PHÉP ĐO SỐNG.
```

Mắt xích cuối của F05 — quét xong thì mở ra cái gì — **có đường**:
`navigation/lien-ket.ts:207` đọc `ban=` qua `docMaBan` và mở màn nhóm với thẻ
bạn. Cái chưa có là một lượt đi bộ trình duyệt qua chính fragment đó; mọi test
`#ban=` hiện nay dừng ở tầng đơn vị. Đó là việc ô 3 còn lại của F05, rẻ, và tôi
chưa làm lượt này.

## 2. Phép đo của tôi hỏng hai lần trước khi cho số đúng

Ghi ra vì cả hai lần đều **suýt cho kết luận ngược**, và vì cách hỏng thứ hai là
loại mà đọc code không bắt được.

**Lần một — suýt báo lỗi sản phẩm không tồn tại.** Bản đầu vẽ mỗi symbol đúng
một kiểu (quiet 4, scale 8 — chính hai con số `qr-roundtrip.py` dùng). Một bậc
ra `FAIL`, OpenCV trả chuỗi rỗng. Trông y hệt lỗi encoder.

Hai đối chứng gỡ nó ra. `segno` — encoder không chung gì với `qr.ts` — dựng cho
**đúng chuỗi đó** một symbol mà OpenCV **cũng** không đọc được, ở mask 0 và
mask 2. Và chính symbol của `qr.ts` đọc lại tốt ở quiet 4/scale 4 và quiet
8/scale 8. Cùng module, cùng decoder, đổi cách vẽ là đổi câu trả lời.

Nên cái mà một-cách-vẽ đo được là **độ khoẻ của `cv2.QRCodeDetector` trên một
tấm bitmap**, không phải cái `qr.ts` mã hoá.

> Hệ quả cho lane frontend (chủ `apps/mobile/`), **suggestion không phải blocker**:
> `tools/qr-roundtrip.py` cũng chỉ vẽ một kiểu. 4/4 của nó là thật, nhưng thiết kế
> đó sai cả hai chiều — nó có thể gọi một encoder đúng là hỏng, và màu đỏ nó tạo
> ra đọc y hệt "encoder vừa hồi quy" với người nhìn tiếp theo.

**Lần hai — canary báo sống trong khi nó chết.** Hai hình dạng canary đầu đều
cho 9/9 "vẫn khớp" sau khi phá. Hình dạng đầu là lỗi code: vòng đồng tâm đi lại
ô cũ nên lật rồi lật ngược. Hình dạng thứ hai **không** phải lỗi code, và đó mới
là chỗ đáng nhớ: 40 module **phân biệt** dồn vào một khối 7x7 giữa symbol chỉ
rơi vào vài codeword, và Reed-Solomon mức M dựng lại vài codeword là đúng việc
của nó. Symbol trả về giống hệt bản gốc vì sửa lỗi đã làm tròn vai.

Phá phải **rải**, không được dồn. Một module trên năm, khắp symbol, thì số
codeword hỏng vượt xa mọi mức EC — và đó cũng là hình dạng mà một encoder sai
thật sự sẽ tạo ra.

Nói cách khác: cả hai lần, thứ hỏng là dụng cụ của tôi. Nếu tôi dừng ở lần một
thì đã gửi Lead một lỗi sản phẩm không có thật; nếu dừng ở lần hai thì đã gửi
một con số 9/9 mà không có quyền gọi là bằng chứng.

## 3. F35 · F38 · F37 — ô 1, và cái thiếu KHÔNG phải ảnh thật

qa2 viết: *"Đổ ảnh thật vào là sai luật `CLAUDE.md`, nên đây là việc phải quyết
định cách làm."* Tiền đề đó sai, nên kết luận "phải quyết định" cũng sai.

`CLAUDE.md` cấm đưa **ảnh bill, mặt người, số tài khoản, tên người thật** vào
Git. Ba hàng này không cần thứ nào trong đó. Tường Kỷ niệm chỉ cần **một tấm ảnh
bất kỳ** — pixel sinh ra bằng code là đủ, và nó không đi vào Git: nó đi vào
database demo qua chính API của sản phẩm.

Đường đó **có thật và đang được gác**:

```
POST /contexts/{context_id}/photos      multipart file=<PNG>  -> UploadedImageResponse
POST /contexts/{context_id}/memories    {image_url, caption}  -> 201, lên tường
```

`get_photo_storage()` nối vô điều kiện (`deps.py:136`), và
`scripts/check_media_persists.sh` là **cổng sống** chứng minh ảnh API ghi ra
sống lâu hơn container đã ghi nó.

Cái đang thiếu là seed: `scripts/seed_demo_data.py` dựng `outings` (chuyến đi)
nhưng **không dựng ảnh hay ký ức nào**. Chính tác giả script đã ghi nhận hệ quả
này ở dòng 239 — *"the demo an empty memory wall beside a group that has visibly
been to Đà Lạt twice"* — nhưng ghi cho `outings`, không cho ảnh.

### Dữ liệu tôi xin Lead seed, nói rõ như đã hứa

Cho nhóm demo (`Team Đà Lạt`), gắn vào hai chuyến đã có:

- **6–10 ký ức `kind=photo`**, ảnh sinh bằng code (PNG đặc màu kèm chữ là đủ),
  caption tiếng Việt có nội dung — caption là thứ F37 đọc, ảnh đặc màu không
  caption sẽ cho F37 một bài toán rỗng.
- Rải trên **cả hai** `outings`, không dồn một chuyến: F36/F37 gom theo chuyến.
- Vài `checkins` nếu rẻ — tường trộn hai `kind`, và một tường chỉ có một loại
  không cho biết thứ tự trộn có đúng không.

Có ngần đó thì **F35 và F38 đo được ruột ngay**: tường hiện đúng số ảnh đã đổ,
widget hiện tấm mới nhất thay vì câu "Nhóm chưa có ảnh nào".

### F37 cần thêm một thứ nữa, và nó không đến từ seed

F37 là tính năng AI. Có ảnh rồi thì `GET .../reel` sẽ chạy thật thay vì trả
"Chưa dựng được thước phim". Nhưng ruột của F37 **không phải** "có trả về chữ
không" — mà là **thước phim có bám vào ký ức có thật của nhóm không**, hay AI
bịa ra khoảnh khắc. `api/reel_gemini.py` dựng prompt từ chính các memory, nên
câu hỏi grounding là câu hỏi đúng.

Không phép đo nào trong repo này đang hỏi câu đó cho F37. Nó cần
`ai-system-testing` (đối chứng grounding: mọi khoảnh khắc reel nêu phải truy được
về một memory có thật), và đó là **một việc riêng**, không phải hệ quả của seed.
Nên sau khi seed: F35 ✅ F38 ✅ F37 vẫn còn nợ một phép đo.

## 4. Con số

Không hàng nào tụt. Đề nghị ghi lại cho chính xác hơn thay vì đổi số:

```
40 BẤM-ĐƯỢC · 3 TẮC (F43 F44 F45) · 4 KHÔNG-CÓ-ĐƯỜNG (F21 F23 F30 F47)

Trong 40, ô mờ co từ 5 hàng xuống 3:
  F29  ruột đã đo thêm một tầng — hình mang đúng chuỗi (4/4 OpenCV)
  F05  ruột đã đo thêm một tầng — hình mang đúng link (9/9, v5→v12)
  F35  chờ seed ảnh — rồi đo được ngay
  F38  chờ seed ảnh — rồi đo được ngay
  F37  chờ seed ảnh + một phép đo grounding chưa ai thiết kế
```

Phần **thật sự** KHÔNG-ĐO-ĐƯỢC sau lượt này hẹp hơn nhiều so với "năm hàng vỏ",
và tôi ghi nó ra đúng như nó là:

- app ngân hàng thật có nhận chuỗi VietQR không (F29)
- camera điện thoại thật có bắt được ô vuông ở khoảng cách thật không (F05)

Cả hai đều cần phần cứng, và không script nào thay thế được. Chúng **không** làm
F05/F29 rớt khỏi 40 — đường bấm có thật, và giờ tấm hình cũng đã được một máy
đọc độc lập xác nhận.

## Ô chưa quét (nói rõ, không giấu)

- Chưa đi bộ trình duyệt qua fragment `#ban=<id>&tenban=` để thấy thẻ bạn mở ra.
  Có đường (`lien-ket.ts:207`), chưa bấm. Ô 3, rẻ, chưa làm.
- Chưa dựng stack lượt này — không đụng `:8099`, không đụng Postgres dùng chung.
  Ba hàng ảnh trả lời bằng đọc hợp đồng route + cổng `check_media_persists.sh`,
  **không** bằng một lượt upload thật.
- Chỉ đo `qr.ts` qua OpenCV 4.13.0. Một decoder thứ hai (ZXing) sẽ mạnh hơn;
  máy này không có.
- 35 hàng còn lại của bảng 47 tôi **không** đo lại — Lead dặn chỉ năm hàng.
