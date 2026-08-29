# rd-qa-06 — nửa sau của luồng, đi bằng tay

Kịch bản Playwright đi **nửa sau** của lát cắt dọc trên bản web export thật của
`apps/mobile`, khung điện thoại 390×844, Postgres thật, API thật:

```
form nhập khoản chi → chia tiền → mở đợt thu → publish → VietQR
→ trang khách → khách báo đã chuyển → người nhận xác nhận
```

Nửa đầu (chụp bill → AI đọc → gán món) đã đo ở `rd-qa-05`. Bộ này phủ ô mà báo
cáo rd-qa-05 tự ghi là chưa quét: **mới có `npm run test:e2e` ở tầng HTTP, chưa
ai bấm bằng tay.**

Không nằm trong CI: cần một stack đang chạy. Đây là bộ chạy tay.

## Dựng lại

```bash
# 1. Stack riêng, không đụng bộ chung của đội
MOBILE_PROJECT=qa06 MOBILE_API_PORT=8620 MOBILE_POSTGRES_PORT=5488 make up

# 2. Bản web ghim vào đúng API đó — KIỂM lại chuỗi cổng trong bundle
cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8620 \
  npx expo export --platform web --output-dir dist --clear
grep -o "127.0.0.1:8620" dist/_expo/static/js/web/*.js   # phải ra kết quả
cd dist && python3 -m http.server 8631 --bind 127.0.0.1

# 3. KIỂM cổng 8631 phục vụ đúng bundle vừa dựng, không phải của lane khác
curl -s http://127.0.0.1:8631/index.html | grep -o 'index-[a-f0-9]*\.js'
ls dist/_expo/static/js/web/     # hai con số phải khớp

# 4. Chạy
cd tests/qa/rd-qa-06
ln -sfn ../rd-qa-02/node_modules node_modules   # playwright + @axe-core/playwright
node --test 04-selfcheck.mjs      # ĐỐI CHỨNG — chạy CÁI NÀY TRƯỚC
node 01-form-bad-input.mjs
node 02-nua-sau-walk.mjs
node 03-trang-khach.mjs
node 05-a11y.mjs
node 06-repro-cut-duong.mjs
```

## Đọc kết quả — chạy đối chứng trước, tin số sau

Hai ca đối chứng, và chúng là điều kiện để đọc mọi con số khác:

- **`04-selfcheck.mjs`** lấy chính dữ liệu thật vừa đo, trồng lỗi vào, rồi đòi
  ba hàm phán quyết trong `lib.mjs` phải đỏ: Σ lệch 1đ, tổng nhóm lọt lên trang
  khách, tên người khác lọt lên trang khách, QR mã hoá sai số tiền. Nó cũng đòi
  **dữ liệu sạch cho ra 0** — để một hàm "luôn đỏ" cũng không lọt.
  Ba hàm đó là `sumProblems` / `leakProblems` / `qrProblems`, và `02`/`03` gọi
  **đúng** ba hàm ấy chứ không chép lại logic. Đối chứng mà kiểm một bản sao thì
  không chứng minh gì.
- **`05-a11y.mjs`** trồng một `<img>` thiếu alt và một nút không tên vào chính
  trang đang đo, đòi axe báo nhiều hơn (`0 -> 2`), rồi mới đọc các số 0 kia.

Ca đối chứng đỏ nghĩa là bộ đo đã chết và **mọi số 0 ở các ca khác là giả.**

## Cạm bẫy đã dính trong lượt này

- `chromium.launch()` không có `browser.close()` thì script treo tới hết timeout
  và trông y hệt một trang không tải được. Ba lần đầu tiên mất vào đúng cái này.
- **Cổng 8631/8621 có thể đã bị lane khác chiếm.** Lần đầu `python3 -m
  http.server` thoát mã 1 mà `curl` vẫn trả 200 — vì đó là server của người
  khác. Đối chiếu tên bundle trước khi tin bất kỳ phép đo nào.
- Tìm ô vuông QR bằng cách quét `getBoundingClientRect` cho ra **nhầm cái
  footer**, và cv2 báo "không giải mã được" — một phát hiện giả hoàn toàn do bộ
  đo. Cách đúng: bắt thẻ mang chữ `VIETQR · NAPAS 247` rồi chụp đúng phần tử đó.
- `locator.fill()` trên `TextInput` của react-native-web vẫn là cái bẫy
  rd-qa-05 đã ghi. Mọi thứ ở đây gõ bằng `keyboard.type()`.
- Route `PUT /people/{id}/bank-recipient` trả **403** nếu thiếu
  `X-Actor-Roles`. App có gửi header đó; bộ đo thì quên. Suýt thành một phiếu
  bug sai địa chỉ — kiểm lại app trước khi đổ cho máy chủ.
- Trang khách **giấu phần chuyển tiền sau một bước** ("Đúng, xem cách chuyển").
  Đọc `innerText` ngay khi mở trang thì không thấy nút "Tôi đã chuyển" và cũng
  không thấy câu cảnh báo — dễ kết luận nhầm là app không nói gì.

## Ô KHÔNG quét được ở lượt này

- **Mã QR quét bằng app ngân hàng thật.** Bộ này giải mã được ảnh QR trên màn
  bằng `cv2.QRCodeDetector` và đối chiếu đúng chuỗi máy chủ gửi về — nhưng một
  chuỗi giải mã đúng vẫn có thể là chuỗi không app ngân hàng Việt nào chấp nhận.
  Câu đó chỉ đóng lại bằng một điện thoại thật trong tay leader.
- **Bản native.** Đo trên web export ở khung điện thoại, không phải iOS/Android.
- **Link hết hạn / thu hồi trên dữ liệu sống.** Đã đo trên `app.web.preview`
  (`?state=expired`, `?state=revoked`): cả hai giấu số tài khoản đúng như
  `guest_view.py` hứa. Chưa đo trên một link thật đã già đi.
- **Chế độ tối và các khung nhìn khác** cho nửa sau.
- **Bấm hai lần đồng thời** vào "Phát đợt thu".
