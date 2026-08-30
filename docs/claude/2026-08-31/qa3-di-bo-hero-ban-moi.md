# Đi bộ lại toàn bộ đường hero bằng tay người dùng — bản dựng a222e66

- **task_id**: qa3-053352 (hậu tố lượt: 78780701)
- **commit đo**: `a222e66` (origin/main lúc bắt đầu; nhánh đo cắt thẳng từ đó)
- **protocol_version**: v1
- **skill bắt buộc đã gọi**: `e2e-testing`
- **verdict**: không có. QA nộp phát hiện, không ký `APPROVE`/`REQUEST_CHANGES`/`REJECT` (ADR-0007).

## Đo trên cái gì

Không đo trên máy demo 8099. `check_demo_matches_main.py` báo "khớp origin/main:
77 route, không thiếu, không thừa", nhưng container `mobile-local-api-1` đã chạy
5 tiếng, còn main tối nay nhích thêm bốn commit (#422, #423, #424, #425). Route
khớp không chứng minh thân trả về khớp — và #423 là một thay đổi **thân**, đúng
loại thứ mà lượt đi bộ này phải nhìn thấy. Nên dựng riêng:

| Mảnh | Ở đâu | Bằng chứng nó là của mình |
|---|---|---|
| API + PostgreSQL | `127.0.0.1:48585`, dựng bằng `scripts/e2e_slice.sh --keep` | `/proc/<pid>/cwd` → `wt/qa3/services/api`; có `GEMINI_API_KEY` và `MOBILE_PERSON_ID_KEY` trong environ; 77 route |
| Bundle web | `127.0.0.1:48489`, `expo export` với `EXPO_PUBLIC_API_URL` ghim vào API trên | sha256 `index.html` phục vụ == sha256 file mình vừa dựng |
| Trình duyệt | Chromium 1234 qua `tests/qa/tim-trinh-duyet.mjs` | — |
| Ảnh bill | `/tmp/qa3-hero-anh/ro.jpg`, sinh bằng `tests/qa/rd-qa-37/tao-anh-bill.py` | tổng hợp, không phải ảnh bill thật |

**Một cái suýt làm hỏng cả lượt đo, ghi lại vì nó sẽ cắn người sau.** Cổng 8763
đã bị lane khác chiếm và đang phục vụ một bundle expo **khác**. `curl` trả 200 và
`metadata.json` hợp lệ, trong khi `python3 -m http.server` của mình đã chết với
`Errno 98`. Nếu tin con 200 đó thì cả báo cáo này nói về cây của người khác. Phép
kiểm duy nhất cứu được: so sha256 của file mình dựng với file máy chủ trả về.

Lượt đi bộ chạy bằng chuột thật ở toạ độ thật (`page.mouse.click`), 390x844,
không nhảy URL, không dùng `?man=`, không gọi API để đẩy app đi tiếp — vì câu hỏi
là "người có tới được không", mà nhảy URL trả lời một câu khác.

Kịch bản: `tests/qa/qa3-di-bo-hero/di-bo.mjs` + `buoc.mjs`.
Ảnh: `/tmp/qa3-di-bo/*.png` (ngoài git — repo guard fail closed với binary).

## ĐẠT — đi hết đường, và tiền khớp

19 chặng, `RC=0`, 0 lỗi console trên toàn tuyến trừ hai con đã ghi ở phần dưới.

| # | Chặng | Thấy gì |
|---|---|---|
| 1–3 | Mở app → đăng nhập SĐT | Màn chào nói thẳng Google/Apple là vỏ, SĐT là thật. Tạo tài khoản trên máy chủ. |
| 4–5 | Cá nhân hoá | "Chào Minh QA" — tên đi qua được. Chọn sở thích + ngân sách. |
| 6 | Vỏ tab | 1 `role=tablist`, 4 `role=tab`: Khám phá · Lên plan · Tin nhắn · Cá nhân. |
| 7 | Khám phá | 4 thẻ địa điểm thật, `AI MATCH 96%` / `TẠM HỢP 81%` / `AI: CHƯA HỢP`. |
| 8 | Chi tiết địa điểm | Địa chỉ, giờ mở, khoảng giá, và lý do AI có căn cứ (budget/sở thích/nhóm). |
| 9–10 | Chat nhóm | Gemini **thật** trả lời, kèm thẻ địa điểm. |
| 13–14 | Chụp/chọn ảnh bill → quét | Model đọc **5 món**, tổng **235.000đ**, và tự nói "Khớp với dòng Tổng cộng in trên bill". |
| 15–16 | Gán món | Ba người: 78.334đ / 78.333đ / 78.333đ. |
| 17–18 | Chia | "Chia không hết chẵn. Minh QA chịu thêm 1đ lẻ, vì là người trả trước." |
| 18b | Ghi vào sổ | Ghi thật. |
| 19 | Cá nhân | Đã trả **78.334đ** · Còn nhận **156.666đ** · Còn phải trả **0đ**. |

**Ba luật tiền giữ được trên đường đi thật**, không phải trên golden vector:

```
78.334 + 78.333 + 78.333 = 235.000      Σ phân bổ = tổng khoản chi   (luật 2)
mọi số hiển thị là số nguyên đồng                                     (luật 1)
78.334 (đã trả) + 156.666 (còn nhận) = 235.000                        khớp sổ
```

Và 1đ lẻ **được nêu tên, được gán cho một người, kèm lý do** — không bị giấu.

**Không có UUID nào trên màn hình, suốt cả 19 chặng.** Khối nợ cũ in
"Ngọc trả Minh QA 256.666đ / Trang trả Minh QA 56.666đ" — tên người, đúng như
#423 hứa. Máy quét của lượt này liệt kê đủ vai trò tương tác (`button`,
`role=button|tab|link|menuitem|switch|checkbox|radio|option`, `a`, `input`,
`select`, `textarea`) chứ không chỉ `button`, nên con số 0 ở đây là 0 thật.

Một chỗ từ chối đúng và đẹp: sau khi ghi sổ, app thử `POST /batches`, máy chủ trả
**409**, và màn hình nói "Người ứng tiền chưa có tài khoản nhận. Chưa biết chuyển
tiền về đâu thì chưa mở đợt thu được." kèm nút đi sửa. Một con 409 biến thành một
câu tiếng Việt và một đường đi tiếp.

## LỖI — ba cái người dùng thấy ngay, không cổng nào bắt

### L1 · Thẻ địa điểm của AI in `quan-an-local` giữa khung chat

Ngay dưới tên quán, chỗ lẽ ra là loại quán, màn chat in **`quan-an-local`** —
một slug máy. Cùng lúc màn Khám phá in "Quán ăn local" cho đúng chỗ đó.

Nhãn người đọc **đã nằm sẵn trên dây**:

```
GET /places  →  categories: [{"id":"quan-an-local","label":"Quán ăn local"},
                             {"id":"cafe","label":"Cafe"},
                             {"id":"vui-choi","label":"Vui chơi"},
                             {"id":"di-choi-dem","label":"Đi chơi đêm"}]
```

Client lấy `id` rồi in thẳng: `apps/mobile/src/screens/chat/ke-hoach.ts:147`
`const loai = chuoi(o.category)`, rồi `TheKeHoach.tsx:175` vẽ `diaDiem.loai`.

- **Hậu quả**: câu chữ kỹ thuật nằm trong bong bóng AI — đúng chỗ leader nhìn đầu
  tiên sau khi gõ câu đầu tiên. Ba trong bốn danh mục đọc như mã máy
  (`quan-an-local`, `vui-choi`, `di-choi-dem`); chỉ `cafe` tình cờ vô hại.
- **Tái lập**: chat nhóm → gõ "Tối nay 6 đứa mình đi ăn nướng đi, tầm 250k/người
  ok không?" → đợi AI trả lời → đọc dòng thứ hai của thẻ.
- **Ảnh**: `/tmp/qa3-di-bo/10-da-gui-tin.png`
- **Gỡ chặn**: tra `categories[].label` theo `id` thay vì in `id`.
- **Loại**: suggestion theo charter (không sai tiền, không rò quyền riêng tư).
  Nhưng nó nằm trên đường hero và sửa được bằng một phép tra.

### L2 · Cùng một người, hai chữ cái đại diện khác nhau, trong một phiên

"Minh QA" hiện **`M`** ở màn Gợi ý chia, và **`Q`** ở màn Cá nhân.

Ba bản cài đặt rời nhau cho cùng một khái niệm:

| Nơi | Cách tính | "Minh QA" | "Nguyễn Văn Hải" |
|---|---|---|---|
| `GoiYChia.tsx:1044` `initial()` | ký tự đầu **cả tên** | `M` | `N` |
| `vao-cua/danh-tinh.ts:126` `chuDau()` | ký tự đầu **từ cuối** | `Q` | `H` |
| `ca-nhan/ban-be.ts:267` `chuDau()` | ký tự đầu **từ cuối** (bản sao) | `Q` | `H` |

Hai bản dưới trùng nhau và theo đúng quy ước Việt (tên gọi đứng cuối). Bản trên
lấy họ. Với tên Việt thật thì lệch vẫn còn: `N` so với `H`.

- **Hậu quả**: avatar nhảy chữ khi chuyển màn. Nhỏ, nhưng là loại chi tiết làm
  người dùng nghi phần còn lại.
- **Tái lập**: so `/tmp/qa3-di-bo/16-da-chon-nguoi-an.png` (`M`) với
  `/tmp/qa3-di-bo/19-tab-ca-nhan.png` (`Q`).
- **Gỡ chặn**: một hàm dùng chung. Hai bản `chuDau` đã là bản sao của nhau, nên
  gộp ba thành một cũng dọn luôn một mối trùng đang có sẵn.
- **Loại**: suggestion.

### L3 · Bảng gán món mở ra không thấy món nào trong năm món

Màn "Gợi ý chia theo người" có chip xanh "**Đã nhận diện 5 món**" ngay dưới một
thẻ trắng **chỉ hiện hàng tiêu đề** (`M T N Giá`) và khoảng trắng.

Đo trên trang sống, không đoán từ ảnh:

```
khung cuộn quanh hàng món:  clientHeight 161px   scrollHeight 758px   scrollTop 0
                            → 597px nội dung nằm ngoài cửa sổ
hàng "Cơm tấm sườn bì chả": top 572, bottom 590   ·  mép dưới khung cắt: 567
sau khi đặt scrollTop = scrollHeight: top -25  → hàng CÓ tới được bằng cuộn
```

Nên đây **không phải mất dữ liệu** và không phải màn hỏng: năm hàng có thật, tick
sẵn, cuộn là thấy. Cái sai là ở nghỉ: một cửa sổ 161px nhìn vào 758px nội dung,
mở ra ở vị trí không có hàng món nào, ngay dưới một dòng chữ khẳng định có 5 món.

- **Hậu quả**: bước "gán món cho người" — bước bán cả tính năng — trông như chưa
  đọc được gì. Người dùng bấm "Xem kết quả" mà chưa từng nhìn thấy món nào.
- **Tái lập**: đi tới màn Gợi ý chia sau khi quét bill; xem
  `/tmp/qa3-di-bo/16-da-chon-nguoi-an.png`, đối chiếu
  `/tmp/qa3-di-bo/16b-cuon-xuong-bang-mon.png`.
- **Gỡ chặn**: cho khung cao đủ vài hàng, hoặc bỏ cuộn lồng và để cả trang cuộn.
- **Loại**: suggestion, nhưng là cái đắt nhất trong ba cái này nếu leader bấm thử.

## Ghi chú — đã kiểm, KHÔNG phải lỗi mới

Ba thứ trông như lỗi và không phải, ghi ra để lượt sau khỏi nộp lại:

- **"Máy chủ: http://127.0.0.1:48585" in dưới chân màn khoản chi.** Cố ý, có
  chú thích tại `App.tsx:1093-1097`: nó thay cho banner "dữ liệu giả" từng đúng
  rồi thành sai. Leader **sẽ** nhìn thấy dòng này khi demo — đó là lựa chọn đã
  ghi, không phải rò rỉ.
- **Tên món bị cắt trong ô nhập** ("Cơm tấm sườn bì c"). Đã biết và đã đánh đổi
  ở #342; `apps/mobile/tests/ten-mon-bi-cat.test.mjs:95` viết thẳng rằng đúng tên
  "Cơm tấm sườn bì chả" vẫn bị cắt sau bản sửa. Tên đầy đủ vẫn còn trong
  `aria-label`, nên không mất dữ liệu.
- **Bong bóng chat của chính mình đề "Thành viên" thay vì "Minh QA".**
  `TEN_CHUA_BIET` tại `screens/chat/tin-nhan.ts:56`, có chú thích dài giải thích
  đây là lựa chọn *tốt hơn* việc in `2bb00000`: `MessageResponse` chỉ mang
  `author_id`, không có tên, và chưa có `GET /people/{id}`. Hành vi đúng như tài
  liệu. Điều đáng nói thêm — và mới — là nó rơi vào **tên của chính người đang
  dùng máy**, người vừa tự gõ tên mình ở màn đăng ký, và cùng lúc màn Gợi ý chia
  lại gọi đúng "Minh QA". Không nộp thành lỗi; nộp thành một quan sát cho lane
  chủ quản quyết.
- **`404 GET /people/{id}/avatar`** trên màn Cá nhân: người này chưa có ảnh, màn
  rơi về chữ cái đại diện đúng như thiết kế. Không hiện gì hỏng cho người dùng.
- **`409 POST /batches`**: đúng, xem phần ĐẠT.
- **`480000` mà máy quét của tôi kêu lên** là *placeholder* của ô Tổng tiền, còn
  giá trị thật là `235000` và màn in "235.000 đ". Lỗi của máy quét tôi viết (nó
  nối placeholder với value), không phải của sản phẩm. Ghi ra vì một lượt sau
  chạy lại kịch bản này sẽ thấy y hệt.

## CHƯA ĐO — phần quan trọng nhất của báo cáo này

Không ô nào dưới đây được lượt này chạm tới. Đừng đọc phần ĐẠT ở trên thành
"đường hero đã xong".

| Ô | Vì sao chưa đo |
|---|---|
| **Mã VietQR có quét được bằng app ngân hàng thật không** | Không agent nào quét được mã QR (ADR-0010 mục 8). Cần leader, một điện thoại, 15 phút. Vẫn là ô mở. |
| **Trang khách `/g/{token}`** | Không tới được: đợt thu không mở nổi vì người ứng tiền chưa có tài khoản nhận (409). Đường đi dừng đúng ở đó. |
| **Đợt thu → publish → envelope** | Cùng lý do trên. |
| **Điện thoại thật** | Chỉ đo Chromium ở 390x844. Không có iOS, không có Android, không có Metro. |
| **Chủ đề tối, khung 320 và 1440** | Chỉ đi một khung, một chủ đề sáng. |
| **Bấm "Ghi tài khoản nhận cho Minh QA"** | Nút có thật, chưa bấm — hết lượt trước khi đi tiếp được. |
| **Tab Lên plan, bình chọn, album, kỷ niệm** | Ngoài đường hero của lượt này. |
| **Tương phản, vùng chạm, bàn phím, trình đọc màn hình** | Lượt này không chạy `accessibility-testing`. |
| **Lần chạy thứ hai trên cùng tài khoản** | Có chạy (nên "Lần chia bill" lên 2 rồi 3), nhưng không kiểm idempotency có chủ đích. |

Và câu không được bỏ: **repo này vẫn chưa có bằng chứng hành vi nào.** ADR-0006
gác Giai đoạn 0 theo quyết định của chủ sản phẩm. Lượt đi bộ này chứng minh sản
phẩm chạy được dưới tay một cái máy; nó không nói người thật hiểu nó.

## Lệnh chạy lại

```bash
set -a && . /home/lakiet/mobile/.env && set +a
scripts/e2e_slice.sh --keep                      # ghi lại cổng API nó in ra
cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:<API> \
  npx expo export --platform web --output-dir /tmp/qa3-hero-web --clear
cd /tmp/qa3-hero-web && python3 -m http.server <WEB> --bind 127.0.0.1 &
# so sha256 index.html trước khi tin bất cứ con số nào
python3 tests/qa/rd-qa-37/tao-anh-bill.py /tmp/qa3-hero-anh
cd tests/qa && npm ci                            # puppeteer-core cho tests/qa
node tests/qa/qa3-di-bo-hero/di-bo.mjs --web http://127.0.0.1:<WEB> \
  --sdt <số tổng hợp 10 chữ số> --anh /tmp/qa3-hero-anh/ro.jpg --out /tmp/qa3-di-bo
```

`--sdt` không có mặc định trong mã nguồn, và đó là chủ ý: repo guard chặn một
literal 10 chữ số trong file được theo dõi (`vn-phone`), và nó đúng — một file
không phân biệt được số tổng hợp với số thật của người ta. Lượt này bị chặn đúng
ở đó, và cách sửa là bỏ số ra khỏi repo, không phải xin allowlist.

```bash
```
