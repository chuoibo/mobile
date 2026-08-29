# rd-qa-08 — bản đồ đường đi của vòng demo, đo trên `main`

Đi hết vòng demo mà PM viết, bằng tay, trên bản web export thật của
`apps/mobile` (khung điện thoại 390×844), API thật, Postgres thật, Gemini thật.
Kết quả là một **bản đồ**: chặng nào đi hết được, chặng nào cụt.

Đo tại `main` @ `d8833c2`.

```
mở app → đăng nhập → Khám phá (AI MATCH) → vào nhóm → chat, AI gợi ý chỗ ăn → chốt
→ CHỤP BILL → AI đọc từng món → gán món cho người → AI chia
→ kết quả + VietQR → Cá nhân thấy tài chính cập nhật
```

## Ba giá trị, và vì sao phải phân biệt

- **ĐI HẾT** — chặng chạy thật, sang được chặng sau.
- **VỎ** — màn hình có, và **tự khai** là chưa dựng. Trung thực với người xem demo.
- **CỤT** — bấm vào thì không có đường đi tiếp, và màn không nói gì.

Vỏ không phải lỗi. Vỏ giấu mình mới là lỗi. Bộ này chấm VỎ khi màn tự nói ra,
và CỤT khi nó im lặng.

## Bản đồ

| # | Chặng | Kết quả | Ghi chú |
|---|---|---|---|
| L1 | mở app → màn mở đầu | ĐI HẾT | |
| L2 | đăng nhập → vỏ tab | ĐI HẾT | không có OAuth thật; màn **tự khai** và mở picker 7 người của nhóm demo |
| L3 | Khám phá → thẻ + nhãn AI | ĐI HẾT | 12 thẻ, `AI MATCH 96%`, lời giải thích do máy chủ cấp |
| **L4** | **chọn quán → tạo buổi đi** | **CỤT** | màn chi tiết chỉ có `Quay lại danh sách` · `Chỉ đường` · `Lưu địa điểm` |
| L5 | tab Tin nhắn | VỎ | tự khai, ghi rõ sẽ là `TinNhan`, lane frontend, việc `rd-fe-03` |
| L6 | tab Lên plan | VỎ | tự khai, ghi rõ sẽ là `LenPlan`, "chưa xếp" |
| L7 | `[+]` → menu tạo | ĐI HẾT | 4 mục; 3 mục tự khai là vỏ |
| L8 | `[+]` → luồng khoản chi | ĐI HẾT | |
| L9 | chọn ảnh bill → AI đọc món | ĐI HẾT | Gemini thật, **8.4s**, 8 món, tổng khớp dòng in trên bill |
| L10 | màn gán/chia | ĐI HẾT có điều kiện | màn báo **"Chưa có ai trong nhóm"**, `Xem kết quả` bị tắt cho tới khi gõ tay từng người |
| L11 | chia tiền → kết quả | ĐI HẾT | `456.667 + 456.666 + 456.667 = 1.370.000` |
| L12 | ghi vào sổ → đợt thu | ĐI HẾT | chặn có lý do rõ + nút `Ghi tài khoản nhận cho Minh` (đường ra của #102) |
| **L13** | **Cá nhân thấy tài chính cập nhật** | **CỤT** | số **không đổi** sau khi ghi sổ — xem dưới |

Ba luật tiền, đọc trên con số màn hình hiện (bộ đo **không** tự chia lại):

- luật 1 — số nguyên đồng: **đạt**, không phần nào có phân số.
- luật 2 — Σ phân bổ = tổng: **đạt**, `456.667+456.666+456.667 = 1.370.000`, lệch 0.
- app còn nói ra chỗ lẻ: *"Chia không hết chẵn. Minh, Hải chịu thêm 1đ lẻ, vì là người trả trước."*

## Hai chỗ cụt, và cái thứ hai là chỗ hai nửa không nối

**L4 — Khám phá không dẫn đi đâu.** Chọn được quán, xem được lời AI giải thích
vì sao hợp, rồi hết. Không có đường tạo buổi đi hay rủ nhóm. Đo bằng cách
**liệt kê nút**, không bằng regex: lượt đầu chấm nhầm ĐI HẾT vì chuỗi
`"Lên plan"` khớp — nhưng đó là **nhãn một tab ở đáy màn**, có mặt trên mọi màn.

**L13 — khoản chi vừa tạo không tới sổ của người tạo.** Cơ chế, đã đối chứng
trong database:

- Người đăng nhập là Minh của nhóm demo, `personId = 46b55e67-…` (dẫn xuất
  `uuid5` từ `seed_demo_data.py`). Màn Cá nhân hỏi máy chủ về đúng id đó.
- Luồng khoản chi **không mang nhóm theo**. Nó báo "Chưa có ai trong nhóm" và
  bắt gõ tên bằng tay.
- Mỗi lần gõ "Minh" là **một hàng `people` MỚI, uuid ngẫu nhiên**. Sau ba lượt
  chạy, bảng `people` có 4 hàng tên "Minh", 4 hàng "Hải", 4 hàng "Trang".
- Nên khoản chi 1.370.000đ được ghi cho một Minh **khác** người đang đăng nhập.
  Cá nhân của Minh-demo vẫn đúng `1.063.666đ` như trước — một câu trả lời
  **đúng về một người khác**.

Tiền không sai. Đường nối giữa "vỏ tab / nhóm demo" và "luồng khoản chi" là
thứ chưa có.

## Dựng lại

```bash
# stack riêng, đừng đụng cổng của lane khác
MOBILE_PROJECT=qa08 MOBILE_API_PORT=8690 MOBILE_POSTGRES_PORT=5498 make up
MOBILE_PROJECT=qa08 MOBILE_API_PORT=8690 MOBILE_POSTGRES_PORT=5498 make demo   # BẮT BUỘC, xem dưới

cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8690 \
  npx expo export --platform web --output-dir dist-qa08 --clear
grep -o "127.0.0.1:8690" dist-qa08/_expo/static/js/web/*.js     # phải ra kết quả
cd dist-qa08 && python3 -m http.server 8692 --bind 127.0.0.1
curl -s http://127.0.0.1:8692/index.html | grep -o 'index-[a-f0-9]*\.js'   # đối chiếu với ls

# ảnh bill TỔNG HỢP, 8 dòng món, tổng 1.370.000đ. Không dùng bill thật, không commit ảnh.
python3 -c "..."   # công thức PIL ghi trong 02-doi-chung-hai-cut.mjs

cd tests/qa/rd-qa-08 && ln -sfn ../rd-qa-02/node_modules node_modules
MOBILE_WEB=http://127.0.0.1:8692 MOBILE_BILL=/tmp/bill-qa08.jpg node 01-ban-do-duong-di.mjs
# ... 02 → 11 theo thứ tự
```

## `make demo` là bắt buộc, và bỏ nó ra một phán quyết SAI

`make up` chạy `seed_dev_data.py` (An/Bình/Chi). Bảy người ở màn đăng nhập đến
từ `seed_demo_data.py`, mà **chỉ `make demo` gọi**.

Chạy thiếu bước đó thì màn Cá nhân hỏi về một người chưa có gì trong sổ và trả
lời `0đ` — **một câu trả lời đúng**. Lượt 10 của bộ này đã chấm nó là lỗi sản
phẩm và đã phải **rút lại** (`11-ca-nhan-sau-khi-seed-demo.mjs` là bộ đối chứng
làm việc rút đó: đo cả 7 người, cả 7 đều có số khác 0).

## Cạm bẫy đã dính trong lượt này — bốn phán quyết CUT sai trước khi ra được hai cái đúng

Ghi ra vì cả bốn đều là **lỗi của bộ đo tự tin vào chính nó**, và cả bốn đều
suýt thành phiếu bug gửi lane khác đi sửa thứ không hỏng.

1. **Bấm khi màn còn đang tải.** L4 lượt 1 chấm CUT trong lúc Khám phá còn in
   "Đang hỏi máy chủ chỗ nào hợp với nhóm…". Chưa có thẻ nào để bấm.
2. **Đoán tên nút.** Bộ đo dò `Chia|Xác nhận|Tiếp tục`; nút thật lần lượt tên là
   `Chọn ảnh bill`, `Xem kết quả`, `Chia tiền`. Không thấy thì kết luận cụt.
   Cách đúng: **liệt kê nút rồi mới bấm**.
3. **`document.body.innerText` trả về `""`** trên màn chia (react-native-web
   dựng scroll container mà innerText của body không thấy xuyên qua). Ba lượt
   đọc thành "màn trống". Ảnh chụp mới nói ra sự thật — và màn đó có hẳn dòng
   chữ đỏ giải thích. Đọc bằng `textContent`, và **đối chiếu với ảnh**.
4. **Regex nuốt số trong câu văn.** Σ cộng nhầm `1đ` trong câu *"chịu thêm 1đ
   lẻ"* thành một phần chia, rồi báo lệch 1đ trên một phép chia **đúng**. Một
   phiếu "sai tiền" gửi đi từ đây là phiếu tệ nhất có thể gửi.
5. **Hai nút cùng tên "Thêm"** trên màn chia: nút tròn `[+]` mở ô nhập, nút xanh
   gửi tên. Bấm nhầm cái đầu thì gõ xong không ai được thêm.
6. **Bấm hết mọi nút để dò đường** — vòng lặp bấm `Đúng rồi, ghi vào sổ` rồi bấm
   tiếp `Sửa lại` đứng ngay cạnh, tự huỷ đúng thứ vừa ghi, rồi báo sổ không đổi.

## Ô KHÔNG quét được ở lượt này

- **Mã QR quét bằng app ngân hàng thật.** Lượt này còn không tới được màn
  VietQR: dừng ở "chưa có tài khoản nhận". Câu đó vẫn chỉ đóng được bằng một
  điện thoại thật trong tay leader.
- **Bản native.** Đo trên web export ở khung điện thoại, không phải iOS/Android.
- **Chế độ tối và các khung nhìn khác.** Chỉ đo 390×844, sáng.
- **Trang khách** ở lượt này (đã đo ở rd-qa-06).
- **Nửa sau đợt thu**: ghi tài khoản nhận → publish → trang khách → xác nhận.
  Dừng đúng trước bước đó.
- **`Lưu địa điểm`** bấm được và màn đổi, nhưng chưa đo nó lưu vào đâu và có
  đọc lại được không.
