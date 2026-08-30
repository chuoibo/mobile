# QA #312 trên app thật — F24 nháp chi từ chat, F14 nhận lời mời, F26 quét ảnh

```
protocol_version  v1
đo tại            c8cffa9 = origin/main ad9d139 + frontend/rd-fe-37-ba-route-chet 962c3f1
                  (gộp sạch, không xung đột; SHA này là cây gộp, không phải head PR)
đối chứng         origin/main ad9d139 một mình
người đo          lane qa2, qa-tt-0034
kỹ năng đã gọi    e2e-testing · playwright-automation · ai-system-testing
```

Lead hỏi bốn câu. Trả lời ngắn trước, bằng chứng ở dưới.

1. **Ba luồng bấm được từ đầu đến cuối không?** Được, cả ba, trên trình duyệt thật
   với máy chủ thật và Gemini thật. Không luồng nào vẽ kết quả mà không gọi máy chủ.
2. **F26 từ chối ảnh không phải bill có tử tế không?** Có. `422 not_a_transaction`,
   màn hiện đúng một câu tiếng Việt, không traceback, không mã lỗi, không status
   number, và màn vẫn còn đường đi tiếp. Hai chi tiết chưa đẹp ghi ở phần phát hiện.
3. **Ảnh chụp là màn thật, không phải DOM.** `page.screenshot()` của Chromium,
   390×844 và 320×844. Đường dẫn ở cuối file — ảnh **không** vào Git (repo guard
   fail closed với binary, và ADR-0010 6.5).
4. **Lượt `npm test` đỏ bất thường?** Không tái lập được trên cây này (743/743 ×3,
   746/746 sau khi gộp main mới). Nhưng ca đỏ đó **đã có tên** rồi — chính nhánh
   này đặt tên nó ở `962c3f1` — và tôi kiểm cái quan trọng hơn: **bản vá có làm
   phép chờ nuốt mất lỗi thật không.** Không. Đột biến ở phần "Đột biến" bên dưới.

---

## 1. Cổng đã chạy — số thật, cây sạch

| Cổng | Cây | Kết quả |
|---|---|---|
| `cd apps/mobile && npm test` | **main + #312** (c8cffa9) | `# tests 746 · # pass 746 · # fail 0` |
| `cd apps/mobile && npm test` | **main một mình** (ad9d139) | `# tests 708 · # pass 708 · # fail 0` |
| `python3 -m pytest services/api/tests tests -q` | main + #312 | `2373 passed, 477 skipped, 4847 subtests` |
| `MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q` | main + #312 | `419 passed` — **0 skipped** |
| `npm test` ×3 (săn flake) | cây gộp trước đó (d03798c) | `743/743` cả ba lượt |
| `node --test tests/ket-ban-web.test.mjs` ×15 | như trên | 15/15 xanh |

Hai cột đối chứng ở trên tồn tại vì một lý do cụ thể: **lượt đo đầu của tôi sai.**
Tôi `cp -al` node_modules từ worktree cũ, main vừa thêm `puppeteer-core@24.43.1`
vào devDependencies (#326/#329), và bốn file test chết ở `ERR_MODULE_NOT_FOUND`.
Bảng đầu tiên tôi đọc được là "main + #312 = 7 fail". Đối chứng main-một-mình ra
**đúng 7 fail, đúng tên ca đó**, nên nó không phải của #312 — và sau `npm ci` thì
cả hai cây đều xanh. Ghi lại ở đây vì con số 7-đỏ đó đọc y hệt một PR làm hỏng CI.

## 2. Máy đã dựng để đo — không dùng máy demo chung

`apps/mobile/src/api.ts` fallback về `http://localhost:8099`, là stack `make up`
dùng chung của cả máy. Bắn vào đó thì đo cây người khác dựng lần cuối. Nên:

```
database   mobile_pr312 riêng, migrate bằng MOBILE_DATABASE_URL (không phải
           MOBILE_TEST_DATABASE_URL — alembic/env.py bỏ qua biến TEST im lặng)
           40 bảng, alembic head a7d3f2b81c56
API        uvicorn 127.0.0.1:8312, GEMINI_API_KEY + MOBILE_PERSON_ID_KEY nạp từ
           `.env` ở gốc checkout `mobile/` (nằm NGOÀI worktree của lane, nên
           không có trong repo và không lấy được từ đây)
bundle     expo export --clear, EXPO_PUBLIC_API_URL=http://127.0.0.1:8312
           phục vụ tĩnh ở 127.0.0.1:8313
dữ liệu    scripts/seed_demo_data.py (7 người, 3 chuyến, 5 khoản chi) + tin nhắn
           và lời mời buổi đi tạo qua HTTP, không câu SQL nào
```

Màn Chụp bill in ra `Máy chủ: http://127.0.0.1:8312` ở chân màn, và ảnh chụp có
dòng đó — đấy là bằng chứng bundle đang nói chuyện với máy chủ này chứ không phải 8099.

## 3. Đi bộ ba luồng — `di_bo_312.py`

```
390×844   35/37 ĐẠT
320×844   35/37 ĐẠT   (cùng 2 phát hiện, không vỡ layout ở màn hẹp)
```

Hai ca HONG ở cả hai lượt **là phát hiện**, không phải phép đo hỏng — chi tiết ở mục 5.

Mỗi luồng kiểm ba tầng theo thứ tự: màn vẽ ra và bấm được · **request thật sự rời
trình duyệt và máy chủ thật sự trả lời** · câu chữ đúng cái thiết kế ghim. Tầng
giữa là tầng dễ bỏ nhất: một cái thẻ vẽ ra mà không có request là client tự bịa.

**F24 — chat → Tách tiền → thẻ nháp chi**

```
POST /contexts/{ctx}/messages/{msg}/expense-draft → 200
trên thẻ:  tiền lẩu · 480.000đ · Người trả: Minh
           Người chia: Đức, Minh, Trang, Quân, Hải, Linh, Ngọc
           Cần xem lại
           Chưa ghi khoản chi nào. Đây mới là bản đọc, bạn còn phải chốt.
```

Không uuid nào lọt ra màn. Câu "chưa ghi khoản chi nào" **cuộn tới được và nhìn
thấy được** (bounding box 33,469 324×36) chứ không chỉ nằm trong DOM dưới thanh
soạn tin — kiểm riêng vì ảnh chụp đầu tiên cho thấy nó bị thanh soạn che.

**F14 — link → Nhận lời mời**

```
mở #moi=<token>   "Bạn được mời vào một buổi đi"
                  "App chưa biết đây là buổi đi nào cho tới khi nhận."
                  (không bịa tên nhóm, không bịa tên chuyến — đúng contract)
bấm Nhận          POST /outing-invites/{token}/accept → 200 → "Bạn đã vào buổi đi."
```

Kiểm ở database, không chỉ ở màn: `outing_invites.accepted_at` đã set,
`accepted_by_id = 93c153f7…` (Quân). Cú bấm đó ghi thật.

**F26 — Tạo khoản chi → Ảnh chụp màn hình → thẻ kết quả**

```
POST /screenshots/scan → 200
thẻ:   Grab · 85.000đ · Ngày 29/08/2026 · Cần xem lại
       Chưa ghi khoản chi nào. Chốt thì số này vào form nhập tay, chưa vào sổ.
Chốt → form "Khoản chi mới", ô tiền mang sẵn 85000, ô tên mang "Grab"
```

Ảnh mẫu do `tao_anh_mau.py` vẽ ra, không phải bill thật của ai. Gemini đọc thật:

| ảnh | máy chủ trả |
|---|---|
| grab.png | `{"source":"grab","merchant":"Grab","total_vnd":85000,"occurred_on":"2026-08-29","needs_review":true}` |
| shopeefood.png | `{"source":"shopeefood","merchant":"Bun bo Hue Co Ba","total_vnd":167000,"occurred_on":"2026-08-28"}` |
| khong-phai-bill.png (tranh phong cảnh) | `422 {"code":"not_a_transaction"}` |

`needs_review: true` ở cả hai ảnh đọc được — đúng, mọi số máy đọc ra đều là bản nháp.

## 4. Đột biến — bản vá flake có nuốt mất lỗi thật không

`962c3f1` vá ca đỏ bằng cách **thêm một phép chờ**. Thêm chờ là cách sửa flake dễ
biến thành cách giấu bug: chờ tới khi lỗi biến mất thì ca test hết cắn. Nên đo:

| Đột biến | Kỳ vọng | Kết quả |
|---|---|---|
| `KetBan.tsx`: `Bạn bè ({ds.ban.length})` → `({ds.ban.length + ds.ra.length})`, tức là danh sách bạn bè **tự tăng khi mới gửi lời mời** — đúng cái ca đó tồn tại để bắt | ĐỎ | `# pass 742 # fail 1`, `not ok 255 - màn kết bạn, đo trên trang render thật`, `error: 'danh sách bạn bè đã tự tăng khi mới chỉ gửi lời mời'` |

Đỏ đúng ca, đúng dòng assert. Phép chờ mới khớp `/Bạn bè \(\d+\)/` — **một con số
bất kỳ** — còn con số đó phải là 0 vẫn do assert phía dưới phán. Bản vá đúng.
File đã khôi phục, `git diff` trống.

## 5. Phát hiện

Phân loại theo 5 loại blocker của charter. **Không cái nào thuộc 5 loại đó**, nên
theo charter cả bốn là *suggestion*, không phải blocker. Xếp theo giá trị sửa.

### PH-1 · Máy chủ đọc đúng, chuẩn hoá tiền từ chối — F24 chết với chữ "đồng"

**KHÔNG phải lỗi của #312.** `app/domain/receipt.py` (Codex sở hữu), đã ở main từ trước.

`_CURRENCY_MARKER = (?:VND|VNĐ|đ|₫|d)` — ký hiệu, không có **chữ**. Trong khi
prompt của `chat_expense_gemini.py` dặn model chép nguyên dạng tiền người ta viết.
Nên người nhắn "480000 đồng" thì model chép đúng, `normalize_vnd` từ chối, route
trả `422 chat_expense_unreadable`, và thẻ nói **"Không đọc được khoản chi từ tin
nhắn"** — đổ lỗi cho tin nhắn trong khi máy đọc nó hoàn toàn đúng.

Tái lập không cần server: `python3 tests/qa/qa-tt-0034/do_tien_viet.py` → 4/13 cách
viết bị từ chối, gồm `480000 đồng`, `480.000 đồng`, `480000 dong`, `2 trăm nghìn`.
Đo lại ở tầng model: reader trả `{'is_expense': True, 'title': 'tiền lẩu',
'amount_text': '480000 đồng'}` — đúng hoàn toàn.

Hậu quả: F24 trên đường demo hỏng với một trong những cách viết tiền phổ biến nhất
của người Việt. Gỡ chặn: thêm `đồng|dong` (và cân nhắc `trăm`) vào marker, kèm ca
test cho từng dạng. Đã `bug-to backend`.

### PH-2 · F14 chẩn đoán sai hai lỗi thường gặp nhất của một cái link

Của #312. Máy chủ **có** phân biệt ba trạng thái bằng code riêng:

| tình huống | máy chủ trả | app nói |
|---|---|---|
| link đã bị thu hồi / token lạ | `404 invite_not_found` | "Máy chủ không có phần này. Nhiều khả năng app đang trỏ vào một bản API cũ hơn, kiểm tra lại địa chỉ máy chủ ghi ở cuối màn hình." |
| link đã nhận rồi, bấm lại | `409 invite_already_accepted` | "Lần bấm trước chưa chạy xong nên chưa biết máy chủ đã ghi hay chưa. Chờ một chút rồi mở lại màn hình để xem." |

Cả hai câu đều sai sự thật. Link chết thì app **không** cũ; link đã dùng rồi thì
máy chủ **đã** ghi và người đó **đã** ở trong buổi đi. Đây là hai kết cục thường
gặp nhất của một cái link người ta chuyển cho nhau, nên nó không phải ca hiếm.

Chỗ sửa nhỏ và khuôn đã có sẵn **trong chính file này**: `SCREENSHOT_REFUSALS`
trong `api.ts` map code → câu tiếng Việt cho F26. F14 gọi `call()` trần nên rơi vào
câu 404/409 chung. Ba dòng map là xong.

### PH-3 · F26 vẽ câu từ chối hai lần

Cùng một câu "Ảnh này không thể hiện một giao dịch đã xong…" xuất hiện **2 lần**
trên màn: một lần trong khung camera, một lần ở băng lỗi dưới chân màn. Đo bằng
`inner_text().count(...) == 2`, thấy được trên ảnh `f26-tu-choi-390.png`.

### PH-4 · Chọn tệp không phải ảnh thì hiện câu tiếng Anh của thư viện

Chọn một `.txt` ở màn Ảnh chụp màn hình: app hiện
`Unsupported file type: text/plain. Only images and videos are supported.` —
câu của `expo-image-picker`, tiếng Anh, cho người dùng Việt. Không nổ, không
traceback, nhưng cũng không phải "từ chối tử tế".

Chỉ có trên web (trên điện thoại bộ chọn ảnh chỉ đưa ra ảnh). Sửa: bắt lỗi picker
và thay bằng câu tiếng Việt, giống cách `SCREENSHOT_REFUSALS` đã làm cho lỗi máy chủ.

## 6. Ô CHƯA QUÉT — đọc phần này trước khi tin phần trên

- **Điện thoại thật: chưa.** Tất cả đo trên Chromium desktop ở khung 390 và 320.
  Camera thật, bộ chọn ảnh thật của iOS/Android, bàn phím thật: chưa ai chạm.
- **Mã QR quét bằng app ngân hàng thật: chưa.** Không luồng nào ở đây chạm VietQR,
  nhưng ô này vẫn mở trên sản phẩm và chỉ leader đóng được (ADR-0010 mục 8).
- **F24 với các cách viết tiền khác:** tôi chỉ đi bộ dạng `480k` trên trình duyệt.
  Chín dạng còn lại đo ở tầng domain (`do_tien_viet.py`), không đo qua màn.
- **Ảnh chụp màn hình banking:** `source: "banking"` có trong hợp đồng nhưng tôi
  không dựng ảnh chuyển khoản nào. Chưa quét.
- **Ảnh mờ / ảnh bill giấy chụp lệch / ảnh > 8 MB:** chưa quét. Đường 413 và
  `screenshot_unreadable` chưa ai đi qua trên màn.
- **Nhịp (429):** `screenshots/scan` và `expense-draft` đều có limiter; tôi không
  vắt kiệt cửa nhịp nên câu 429 trên màn chưa được nhìn.
- **Chế độ tối:** chưa. Ma trận ADR-0010 có sáng/tối, tôi chỉ chạy sáng.
- **Trình duyệt khác Chromium:** chưa. Firefox/WebKit không chạy.
- **Bốn route F39/F42 (`POST /posts`, tường cá nhân):** không đo trong lượt này.
  Lead giao ba luồng; tường cá nhân là đợt 2 của cùng PR và cần một lượt riêng.
- **`npm test` đỏ 1/40 lượt:** 18 lượt xanh liên tiếp (3 suite + 15 file) **không**
  chứng minh một flake tỉ lệ 1/40 đã hết. Cái tôi chứng minh được là bản vá không
  làm ca test hết cắn (mục 4).

## 7. Chạy lại

```bash
# 1. ảnh mẫu
python3 tests/qa/qa-tt-0034/tao_anh_mau.py /tmp/qa-tt-0034-anh

# 2. bảng cách viết tiền (không cần server, không cần khoá)
python3 tests/qa/qa-tt-0034/do_tien_viet.py

# 3. đi bộ ba luồng — cần stack riêng dựng như mục 2
export MOBILE_QA_WEB=http://127.0.0.1:8313
export MOBILE_QA_CTX=<uuid nhóm đã seed>
export MOBILE_QA_MOI=<token lời mời chưa ai nhận>
export MOBILE_QA_ANH=/tmp/qa-tt-0034-anh
export MOBILE_QA_TACH_INDEX=2      # bong bóng nào mang chữ "480k"
export MOBILE_QA_RONG=390          # rồi chạy lại với 320
python3 tests/qa/qa-tt-0034/di_bo_312.py
```

`MOBILE_QA_MOI` dùng được **một lần** — nhận rồi thì token đó thành 409, phải tạo
lời mời mới cho lượt sau.

Ảnh chụp nằm ở `/tmp/qa-tt-0034-shot/` (`f24-the-nhap-390.png`,
`f14-sau-390.png`, `f26-ket-qua-390.png`, `f26-tu-choi-390.png`, và bản `-320`).
Không đưa vào Git: repo guard fail closed với binary, và ADR-0010 6.5 cấm ảnh QA
đi kèm dữ liệu phiên.

## 8. Điều lượt này KHÔNG chứng minh

Bộ test xanh nói code làm đúng điều tác giả nghĩ. Nó không nói người thật hiểu
sản phẩm — ADR-0006 gác Giai đoạn 0 và repo này vẫn **chưa có bằng chứng hành vi
nào**. Verdict `APPROVE`/`REQUEST_CHANGES`/`REJECT` là chữ ký người; lượt này nộp
phát hiện, không ký.
