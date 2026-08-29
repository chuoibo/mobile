# rd-qa-06 — nửa sau của luồng, đi bằng tay trên giao diện

- **commit đo**: `af605a9` (= `origin/main` lúc bắt đầu, cây sạch)
- **protocol_version**: v1
- **ngày**: 2026-08-29
- **phạm vi**: form nhập khoản chi → chia tiền → mở đợt thu → publish → VietQR →
  trang khách → khách báo đã chuyển → người nhận xác nhận
- **bộ đo**: `tests/qa/rd-qa-06/` (kèm README ghi cách dựng lại và ô chưa quét)

## Kết luận

**Nửa sau đi được tới cuối, tiền đúng ở mọi chỗ đo được, trang khách không rò
một chữ nào — nhưng luồng CỤT ĐƯỜNG ở "mở đợt thu" đối với mọi khoản chi nhập
bằng tay trên app.**

Ba luật tiền giữ nguyên trên màn hình, không chỉ trên API. Quyền riêng tư của
trang khách sạch trên cả hai người và cả bốn kiểu token xấu. Phát hiện chặn nằm
ở chỗ khác: app đòi người ứng tiền phải có tài khoản nhận, và **không có màn nào
trong app để tạo ra thứ đó.**

## Môi trường

Stack riêng, không đụng bộ chung của đội:

```
MOBILE_PROJECT=qa06  API 127.0.0.1:8620  Postgres 127.0.0.1:5488
bản web export ghim EXPO_PUBLIC_API_URL=http://127.0.0.1:8620, phục vụ ở :8631
khung 390×844, deviceScaleFactor 2, isMobile, hasTouch
```

Đã kiểm bundle phục vụ ở `:8631` đúng là bundle vừa dựng
(`index-f0eb92745f40fa92b7829272776be2c6.js`), sau khi lần đầu `http.server`
thoát mã 1 mà `curl` vẫn trả 200 — cổng đã bị một tiến trình khác giữ.

## Bộ đo có còn sống không — chạy trước, tin sau

| Đối chứng | Kết quả |
|---|---|
| `04-selfcheck.mjs` — trồng lỗi vào chính dữ liệu vừa đo | **12/12 pass**: dữ liệu sạch ra 0; Σ lệch 1đ → đỏ; tổng nhóm lọt trang khách → đỏ; tên người khác lọt → đỏ; trang trắng → đỏ; tiền in khác định dạng → đỏ; QR sai số tiền → đỏ |
| `05-a11y.mjs` — trồng `<img>` thiếu alt + nút không tên | **0 → 2 vi phạm**. axe còn sống |

`02`/`03` gọi **đúng** ba hàm mà `04` kiểm (`sumProblems`, `leakProblems`,
`qrProblems` trong `lib.mjs`), không chép lại logic — nếu không thì đối chứng
chỉ kiểm một bản sao.

## Đã đo được gì

### 1. Form nhận đầu vào xấu (`01-form-bad-input.mjs`)

Gõ bằng phím thật, từng ký tự.

| gõ | màn hình nhận | nút "Chia tiền" | báo lỗi |
|---|---|---|---|
| `abc` | — | tắt | "Chỉ nhập chữ số. Dấu chấm, phẩy và khoảng trắng thì được." |
| `-5000` | — | tắt | như trên |
| `0` | — | tắt | **(không có gì)** |
| `000` | — | tắt | **(không có gì)** |
| 13 chữ số `9` | — | tắt | "Số này lớn hơn &lt;trần&gt;đ. Ứng dụng từ chối thay vì làm tròn âm thầm." (trần = `MAX_AMOUNT_VND`, một nghìn tỉ) |
| `1` + 12 số `0` (đúng trần) | in lại đúng số đã gõ | **bật** | — |
| trần + 1đ | — | tắt | báo quá lớn |
| `480001` (lẻ) | 480.001 | bật | — |
| `100.50` | **10.050** | bật | — |
| `480000` | 480.000 | bật | — |

Không có gì lọt qua. Biên đúng chính xác ở `MAX_AMOUNT_VND` (một nghìn tỉ đồng): đúng trần thì nhận, trần cộng 1đ thì từ chối. Hai chỗ đáng
nói ở phần phát hiện.

### 2. Luật tiền 2, đo TRÊN MÀN HÌNH (`02-nua-sau-walk.mjs`)

Ca cố ý chọn số lẻ chia 3 không hết: **480.001đ / 3 người**.

```
Hà (trả trước) 160.001đ   Nam 160.000đ   Linh 160.000đ
Σ đọc từ màn = 480001   |   "Tổng" in trên màn = 480001   |   gõ vào = 480001
```

Bằng nhau cả ba. Mọi phân bổ là số nguyên đồng. Màn hình còn nói ra chỗ lẻ:
*"Chia không hết chẵn. Hà chịu thêm 1đ lẻ, vì là người trả trước."* — người ứng
tiền chịu phần lẻ, đúng ADR-0004, và nói ra chứ không giấu.

Người ứng tiền không tự nợ mình: bảng đợt thu ra đúng 2 nghĩa vụ
(Nam→Hà 160.000, Linh→Hà 160.000), không có dòng Hà→Hà.

### 3. Publish + VietQR (`03-trang-khach.mjs`)

Mã QR **có hiện ra** (thẻ 358×344pt) và **giải mã được**:

```
cv2.QRCodeDetector -> 00020101021238580010A00000072701280006970418011400000000
                      00TEST0208QRIBFTTA53037045406160000 5802VN62150811TT ...
khớp đúng payload máy chủ gửi về ✓      tag 54 (số tiền) = 160000 ✓
```

Nghĩa là: ảnh vẽ trên màn là một mã QR đọc được, nội dung đúng bằng chuỗi máy
chủ dựng, và số tiền mã hoá bên trong khớp con số in bên cạnh. **Không** có
nghĩa là app ngân hàng thật chấp nhận nó — xem ô chưa quét.

### 4. Trang khách — quyền riêng tư (`03-trang-khach.mjs`)

Khẳng định cái CÓ trước, rồi mới khẳng định cái KHÔNG có:

| kiểm | Linh | Nam |
|---|---|---|
| thấy phần của chính mình (160.000) | ✓ | ✓ |
| thấy tên mình ("Phần của …") | ✓ | ✓ |
| **có tổng nhóm 480.001** | không | không |
| **có phần người ứng tiền 160.001** | không | không |
| **có tên người kia** | không | không |
| `group_balance` / `group_history` / `other_allocations` / `invocation_thread` trong HTML | không | không |

Token xấu:

| ca | mã | rò dữ liệu |
|---|---|---|
| đổi 1 ký tự cuối của token thật | 404 | không |
| token bịa đúng dạng (43 ký tự) | 404 | không |
| token quá ngắn | 422 | không |
| ký tự lạ / `%3Cscript%3E` | 422 | không |

Link hết hạn / thu hồi (đo trên `app.web.preview`): cả hai in "Link không còn
dùng được" và **giấu số tài khoản**, đúng như `guest_view.py` hứa.

Trang khách còn tự nói ra giới hạn của nó: *"Chỉ hiển thị phần của bạn. Trang
này không cho xem gì khác của nhóm."* Và màn chia sẻ cảnh báo đúng chỗ: *"Dán
chung vào nhóm thì cả nhóm thấy phần của nhau, và app không biết được điều đó đã
xảy ra."*

### 5. a11y nửa sau (`05-a11y.mjs`, WCAG 2.2 AA, axe)

| màn | critical + serious |
|---|---|
| Nhập khoản chi (đã điền) | 0 |
| Đề xuất chia | 0 |
| Đợt thu | 0 |
| Kết quả thanh toán + VietQR | 0 |
| Chia sẻ link | 0 |
| Trang khách (server-rendered) | 0 |

Đọc kèm đối chứng `0 → 2` ở trên. axe phủ 30–40% vấn đề a11y; phần bàn phím và
trình đọc màn hình cho nửa sau **chưa** quét hết.

## Phát hiện

### P1 — Nửa sau CỤT ĐƯỜNG ở "mở đợt thu": app đòi một thứ nó không có màn nào để tạo ra

**Loại blocker: vi phạm spec/cổng.** Repro tối thiểu: `06-repro-cut-duong.mjs`.

Mọi khoản chi nhập bằng tay trên app đều đúc id mới cho từng người, nên **không
ai có tài khoản nhận**. Bấm "Đúng rồi, ghi vào sổ":

```
POST /expenses           201
POST /expenses/…/confirm 201
POST /batches            409   ← dừng ở đây
màn hình: "Người ứng tiền chưa có tài khoản nhận.
           Chưa biết chuyển tiền về đâu thì chưa mở đợt thu được."
```

Thông báo **đúng và rõ**. Vấn đề là không có đường đi tiếp. Liệt kê mọi control
đang thấy được sau khi bị chặn:

```
· Đóng khoản chi, quay lại các tab
· Đúng rồi, ghi vào sổ
· Sửa lại
```

Không cái nào dẫn tới việc ghi tài khoản nhận. `grep` cả `apps/mobile/src/` và
`App.tsx`: **không một chỗ nào gọi `POST /bank-recipients` hay
`PUT /people/{id}/bank-recipient`.** Route có trên máy chủ và chạy tốt — bộ đo
gọi nó và được 201 — nhưng app không có màn nào cho nó.

*Hậu quả*: trong buổi demo, nửa sau của hero path dừng ở đây nếu khoản chi được
nhập tay. Ghi vào sổ rồi mà không thu được.

*Tiêu chí gỡ chặn*: một màn (hoặc một bước trong luồng) ghi được tài khoản nhận
cho người ứng tiền, rồi `06-repro-cut-duong.mjs` không còn tái lập được 409.

*Ghi chú*: `tests/e2e/seed_bank_recipient.py` đã nói ra vấn đề này từ tầng HTTP —
"nothing in the HTTP surface writes `bank_recipients`". Điều đó nay đã cũ (route
có rồi), nhưng **giao diện** thì vẫn đúng như thế.

### P2 — Khách báo "đã chuyển", người nhận không hề biết

**Loại blocker: vi phạm spec/cổng** (đề nghị Lead phân loại).

Khách bấm "Tôi đã chuyển", trang khách trả lời:

> "Bạn đã báo là đã chuyển. **Đang chờ NGUOI UNG TIEN xác nhận.** Bạn không cần
> chuyển lại."

Bấm "Đọc lại từ máy chủ" trên màn đợt thu, sau khi khách đã báo:

```
Linh gửi Hà   chưa gửi   160.000đ
Nam  gửi Hà   chưa gửi   160.000đ
```

**Y hệt một người chưa làm gì.** Máy chủ có ghi lời khai
(`save_payment_report`), nhưng `obligation_status` chỉ tính từ
`ReceiptConfirmation`, và `GET /batches/{id}/obligations` chỉ trả
`obligation_status` + `disputed` — không có trường nào nói "người gửi đã báo".

*Hậu quả*: app hứa với khách rằng có người đang chờ xác nhận, trong khi người đó
không nhận được tín hiệu nào. Người thu tiền phải tự nhớ, hoặc bấm "Tiền đã về"
theo trí nhớ — đúng cái mà `receiver_confirmed` không nên trở thành.

*Tiêu chí gỡ chặn*: bảng đợt thu phân biệt được "chưa gửi" với "người gửi đã báo
đã chuyển, chưa xác nhận".

### P3 — Màn đợt thu ghi "đã nhận" mà không nói đó là lời một người

**Loại: suggestion nghiêng về spec.**

Sau khi bấm "Tiền đã về": `Linh gửi Hà **đã nhận** 160.000đ`. Không một chữ nào
trên màn nói đây là lời một người chứ không phải xác nhận của ngân hàng.

Trang khách thì **có** nói, đúng và đủ: *"Báo ở đây chỉ để NGUOI UNG TIEN biết
mà đối chiếu. Khoản chỉ đóng khi họ xác nhận."*

Đáng nói vì bình luận trong `DotThu.tsx` khẳng định ngược lại:

> *"Pressing this says one person saw it land -- it is not a bank telling anybody
> anything, and the wording keeps saying so."*

Câu chữ trên màn **không** nói thế. Đây là một lời tự khai trong comment chưa ai
kiểm. `CLAUDE.md` xếp "`receiver_confirmed` không phải bằng chứng ngân hàng" vào
luật, nên chỗ này nên đóng.

### P4 — Gõ `0` thì nút tắt mà không một chữ nào nói vì sao

**Loại: suggestion.** `parseAmountVnd("0")` trả `{ok: true, value: 0}`, nên
`amountProblem` là `null` và không câu cảnh báo nào hiện ra; nhưng
`ready = totalVnd > 0` nên nút "Chia tiền" tắt. Người dùng thấy một nút chết
không lời giải thích. Ba ca xấu còn lại (`abc`, `-5000`, quá trần) đều báo rõ
ràng và làm được việc — chỉ ca này im lặng.

### P5 — `100.50` lặng lẽ thành `10.050đ`

**Loại: suggestion.** Dấu chấm/phẩy bị bỏ đi không kiểm, nên `100.50` → `10050`.
Với cách người Việt gõ tiền (`1.000.000`) thì đây là hành vi ĐÚNG và cần thiết.
Giảm nhẹ: màn hình in lại `10.050 đ` ngay dưới ô nhập, nên người dùng nhìn thấy
được. Ghi lại để không ai "sửa" cái đúng.

## Cổng đã chạy (cây sạch, `af605a9`)

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **842 passed, 139 skipped**, 4434 subtests |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` (DB `:5488`) | **122 passed, 0 skipped** |
| `cd apps/mobile && npm test` | **203 passed, 0 fail** (gồm bước bundle) |
| `node --test 04-selfcheck.mjs` | **12 passed** (đối chứng) |
| `node 01-form-bad-input.mjs` | 2 vấn đề → P4 |
| `node 02-nua-sau-walk.mjs` | 0 vấn đề chặn |
| `node 03-trang-khach.mjs` | 1 vấn đề → P3 |
| `node 05-a11y.mjs` | 0 critical/serious, đối chứng 0→2 |
| `node 06-repro-cut-duong.mjs` | tái lập được 409 → P1 |

139 skipped ở dòng đầu là tầng postgres tự bỏ qua khi thiếu URL — đã chạy riêng
ở dòng thứ hai với `MOBILE_REQUIRE_POSTGRES_TESTS=1`, **0 skipped**.

## Ô CHƯA quét

- **Mã QR quét bằng app ngân hàng thật.** Đã giải mã bằng `cv2` và đối chiếu
  đúng chuỗi máy chủ, nhưng một chuỗi giải mã được vẫn có thể là chuỗi không app
  ngân hàng Việt nào chấp nhận. **Chỉ leader đóng được ô này**, 15 phút với một
  điện thoại thật.
- **Bản native iOS/Android.** Tất cả đo trên web export ở khung điện thoại.
- **Link khách hết hạn / thu hồi trên dữ liệu sống.** Mới đo trên
  `app.web.preview`.
- **Bàn phím và trình đọc màn hình** cho nửa sau — mới có axe (30–40%).
- **Chế độ tối, khung 320 và 1440** cho nửa sau.
- **Bấm hai lần đồng thời** vào "Phát đợt thu"; đua giữa hai `confirm-receipt`.
- **Ca nhiều người nhận** (một người gửi cho hai người) — mọi ca ở đây một người
  ứng tiền.

## Nhắc lại điều không được bỏ

Repo này **chưa có bằng chứng hành vi nào** (ADR-0006). Báo cáo trên nói code
làm đúng điều tác giả nghĩ, và nói ba luật tiền giữ được trên màn hình. Nó không
nói người thật hiểu sản phẩm.

Digest này **không phải bằng chứng tự thân**. Mọi lệnh ở bảng trên chạy lại được
trong cây sạch theo README của bộ đo.
