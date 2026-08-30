# Phán quyết QA cho PR 389 — hậu kiểm, vì nó đã lên `main` trước khi tôi đo xong

**PASS.**

**Lý do, viết trước chi tiết.** `receivable_vnd` — số tiền mới "Còn nhận" trên màn
Cá nhân — đúng trên máy chủ sống ở cả năm mốc của vòng tiền, và **cổng gác nó là
cổng thật**: 5/5 đột biến giết được đều ĐỎ, hàng no-op vẫn XANH. Hai câu sản phẩm
in thẳng cho người dùng đọc — *"chỉ rời khỏi còn nhận khi bạn xác nhận đã nhận"* và
*"người kia báo đã chuyển thì chưa tính"* — tôi đo được **cả hai chiều** trên API
sống, và chúng đúng. Không có blocker.

Kèm **một chuyện quy trình, không phải lỗi code**: PR 389 đã được merge vào `main`
lúc `19:24:59Z` **trong lúc tôi đang chạy cổng cho nó**, tức là nó lên `main` mà
chưa có phán quyết QA nào. Chi tiết ở mục cuối.

| | |
|---|---|
| **đo tại** | `33d16d8cc744` (và các mốc phụ ghi rõ từng chỗ dưới) |
| **sha này** | **ĐÃ ở main** — PR 389 nằm trong đó, merge tại `8dbd772` |
| **bản trước để đối chứng** | `703db387` (merge-base), nhánh PR `0e0f3569` |
| **kỹ năng** | `e2e-testing`, `bug-reproduction` |

---

## 1. Bản TRƯỚC thật sự thiếu cái PR này nói nó thêm

Đây là phần `bug-reproduction` đòi trước mọi thứ khác: nếu bản cũ không hỏng được ở
đúng chỗ PR tuyên bố sửa, thì PR chưa chứng minh được gì.

**Đo bằng hành vi trên dây, không bằng đọc source.** Một probe duy nhất, chạy
**không sửa đổi gì** trên cả hai cây, gọi `GET /people/{id}/finance` qua TestClient
và in ra các khoá tiền máy chủ thật sự phát ra
(`doi-chung-truoc-sau-tren-day.py`):

```
=== TRƯỚC 389 (703db38) ===
money keys on the wire: ['outstanding_vnd', 'settled_vnd', 'spend_vnd']
receivable_vnd present: False

=== SAU 389, main 33d16d8 ===
money keys on the wire: ['outstanding_vnd', 'receivable_vnd', 'settled_vnd', 'spend_vnd']
receivable_vnd present: True
```

Cùng một probe, cùng một câu hỏi, hai câu trả lời khác nhau. Chênh lệch đó nằm ở
sản phẩm chứ không nằm ở phép đo.

**Và ca mới ĐỎ được ở bản cũ.** Chép *chỉ* file test (không chép một dòng code sản
phẩm nào) sang cây `703db38`:

```
6 failed, 222 passed in 3.61s
```

Trong sáu ca đỏ đó, **năm ca đỏ vì `TypeError`** — dataclass chưa có trường — và
đó là loại đỏ yếu, đỏ vì dựng không nổi chứ không vì hành vi. Ca thứ sáu mới là ca
đáng kể:

```
pydantic_core.ValidationError: 1 validation error for PersonFinanceResponse
receivable_vnd
  Extra inputs are not permitted [type=extra_forbidden, input_value=120000]
```

`extra_forbidden` từ **chính response model của route** là bằng chứng trường này
chưa từng nằm trên hợp đồng API, chứ không phải nó có mà chưa ai hiển thị.

---

## 2. Đi bộ hết vòng tiền trên API sống — phần walk của tác giả dừng trước

Walk của chính tác giả (`tests/qa/qa2-000443/di-bo-con-nhan.py`) tốt, có đối chứng
dương, có đọc JSON thô để bắt `Decimal`. Nhưng nó **dừng ở lúc vừa chia xong, chưa
ai trả một đồng nào**. Hai lời hứa in trên màn hình đều nói về chuyện xảy ra *sau*
mốc đó, nên chưa cái nào được đo.

Tôi đi tiếp tới hết vòng: `chia → mở đợt thu → phát → khách BÁO đã chuyển →
người nhận XÁC NHẬN`, đo `receivable_vnd` ở từng mốc.

Máy chủ: uvicorn `127.0.0.1:47679`, dựng bởi `scripts/e2e_slice.sh --keep` từ cây
`/tmp/qa47-main` tại `33d16d8`, Postgres container dùng một lần.
**Không** phải máy demo 8099. Kiểm trước khi tin số:
`curl openapi.json | grep -c receivable_vnd` → `1`, 77 route.

```
ĐẠT  PHẢI XANH (đối chứng dương): A ứng cho B thì A có tiền để nhận
       A.receivable = 150000 (chờ 150000)
ĐẠT  BẤT BIẾN CHÉO: 'còn nhận' của A = tổng 'còn phải trả' của người kia
       A.receivable=150000 vs B.outstanding=150000
ĐẠT  A không tự nợ chính mình: chỉ một nghĩa vụ, người gửi là B
ĐẠT  mở đợt thu KHÔNG làm đổi 'còn nhận'          A.receivable = 150000
ĐẠT  phát đợt thu KHÔNG làm đổi 'còn nhận'        A.receivable = 150000
ĐẠT  khách báo đã chuyển được                     POST /g/<token>/da-chuyen -> 201
ĐẠT  CÂU IN TRÊN MÀN, nửa 1: B *báo* đã chuyển thì 'còn nhận' của A KHÔNG giảm
       A.receivable = 150000 (chờ vẫn 150000)
ĐẠT  đối xứng: B tự báo cũng KHÔNG tự xoá được nợ của chính B
ĐẠT  CÂU IN TRÊN MÀN, nửa 2: A xác nhận đã nhận thì 'còn nhận' về 0
       A.receivable = 0 (chờ 0)
ĐẠT  BẤT BIẾN CHÉO sau khi trả xong: A.receivable == B.outstanding
ĐẠT  tiền về KHÔNG làm đổi 'đã trả' của A         A.spend = 150000
ĐẠT  xác nhận lần hai không đẩy 'còn nhận' xuống âm  lần hai -> HTTP 201; = 0
ĐẠT  mọi số tiền là số nguyên đồng, không Decimal/float lọt ra dây
========================================================================
ĐẠT 13   HỎNG 0
```

Dòng đầu là **đối chứng dương** và nó tồn tại vì một lý do: mười hai dòng còn lại
kiểm một số `0` hoặc một số *không đổi*, và một máy chủ chết trả về đúng những thứ
đó. Chỉ khi dòng đầu thấy `150000` thì các dòng dưới mới có nghĩa.

**Bất biến chéo người** là dòng tôi thêm mà không tầng nào trong repo có: `A.receivable`
và `B.outstanding` do **hai truy vấn khác nhau** tính ra, đi từ hai đầu ngược nhau
của cùng một món nợ. Chúng lệch nhau là màn hình nói dối theo cách không assert đơn
lẻ nào bắt được. Chúng khớp ở cả hai mốc — trước khi trả và sau khi trả.

**Một phép thử của tôi đã hỏng, và tôi ghi lại thay vì im.** Bản đầu của dòng cuối
("số nguyên đồng") hỏi `".0" in raw` trên **toàn thân** phản hồi. Thân đó có cả
`movements`, và một dấu thời gian `...:14.077000+00:00` chứa `.0` — nên lượt chạy
thứ hai in **HỎNG** trong khi cả bốn số tiền đều là `int`. Cùng một máy chủ, cùng
một sản phẩm, khác nhau ở phần lẻ của giây.

Nếu tôi đọc chữ HỎNG đó là kết quả, tôi đã mở một phiếu lỗi tiền cho một sản phẩm
không sai. Phạm vi bây giờ neo vào chính bốn khoá tiền
(`"<khoá>":` phải theo sau bởi chữ số thuần), và đọc từ text thô chứ không từ dict —
`json.loads` đã biến `150000.0` thành float trước khi ai kịp nhìn. Kết quả sau khi
sửa, đọc thẳng từ dây:

```
trên dây: {'spend_vnd': '150000', 'settled_vnd': '150000',
           'outstanding_vnd': '0', 'receivable_vnd': '0'}
```

**Một quan sát, không phải blocker:** xác nhận nhận tiền lần thứ hai được máy chủ
**chấp nhận** (`HTTP 201`), không bị từ chối. Màn hình không sai vì `max(0, ...)`
kẹp lại, và `settled` của B cũng không bị thổi lên vì nó cũng kẹp. Nhưng chuyện
"nhận tiền hai lần cho một nghĩa vụ" được ghi vào sổ như một sự kiện hợp lệ, và cái
giữ cho màn hình đúng là phép kẹp ở tầng đọc chứ không phải một cổng ở tầng ghi.
Ghi lại ở đây cho lane backend, không chặn PR này.

---

## 3. Cổng gác `receivable_vnd` có thật sự gác không

19 ca xanh ở tầng Postgres nói con số đúng trên dữ liệu tác giả nghĩ ra. Chúng
**không** nói chúng đỏ được khi con số sai. `dot-bien-con-nhan.py` hỏi câu đó.

DB riêng, container riêng (`qa47-pg-*`), **không** dùng chung schema với lane khác.

| Hàng | Loại | Hình dạng | Chờ | Được | pytest |
|---|---|---|---|---|---|
| BASE | BASE | cây chưa đột biến | XANH | **XANH** | `19 passed` |
| M1 | CHẾT | bỏ `participant_id != person_id` → phần của chính người ứng tiền bị tính là tiền người khác nợ họ; "còn nhận" bằng cả hoá đơn | ĐỎ | **ĐỎ** | `6 failed, 13 passed` |
| M2 | CHẾT | đếm `PaymentReport` thay `ReceiptConfirmation` → **người nợ tự báo là xoá được tiền của chủ nợ**, đúng cái màn hình hứa không xảy ra | ĐỎ | **ĐỎ** | `4 failed, 15 passed` |
| M3 | CHẾT | bỏ nửa `version_number` của mối nối `newest` → sửa khoản chi thì cả hai bản cùng tính, "còn nhận" gấp đôi | ĐỎ | **ĐỎ** | `1 failed, 18 passed` |
| M4 | CHẾT | bỏ kẹp `max(0, ...)` → chủ nợ đọc một số **âm** | ĐỎ | **ĐỎ** | `1 failed, 18 passed` |
| K1 | SỐNG | đổi tên biến cục bộ `advanced_vnd` → `ung_truoc_vnd`, không đổi nghĩa | XANH | **XANH** | `19 passed` |

Cần đủ ba loại hàng mới đọc được bảng. **BASE xanh** loại trừ "cây đỏ sẵn nên hàng
nào cũng đỏ". **M1–M4 đỏ** là cổng thật đang cắn. **K1 xanh** loại trừ khả năng cổng
chỉ đang ghim byte của file — một cổng đỏ với *mọi* thay đổi thì cũng vô dụng như
một cổng không bao giờ đỏ.

Harness **từ chối chạy** nếu không tìm thấy nguyên văn đoạn định thay, và
`assert moi != goc`. Đột biến no-op in ra XANH và đọc y hệt một cổng đang giữ.
Khôi phục trong `finally`, có kiểm lại byte.

### Nửa giao diện cũng bị hỏi câu đó

Một cổng backend thật vẫn có thể đứng cạnh một màn hình in nhầm ô. Đột biến thứ
sáu, trên `CaNhan.tsx:512` — ô "Còn nhận" vẽ `outstanding_vnd` thay vì
`receivable_vnd`, tức là hoán hai ô cho nhau:

```
not ok 626 - số nào vào ô nấy — hoán đổi hai ô thì ca này đỏ
# tests 888   # pass 887   # fail 1
```

Khôi phục file → `888 pass, 0 fail`. Đỏ-có-đột-biến, xanh-không-đột-biến, trên cả
hai nửa.

---

## 4. Cổng đầy đủ trên `main` tại `33d16d8`, cây sạch

`scripts/gate.sh` trong worktree tách riêng, `git status` trống.

```
ĐẠT 12   HỎNG 0   BỎ QUA 4
  đạt: guard contract client-routes server-routes cors api migration
       pinned-import demo-watch shared docker postgres
```

**Bỏ qua không phải đạt**, nên tôi chạy tay bốn chặng đó:

| Chặng bị bỏ qua | Lý do gate bỏ | Tôi chạy tay | Kết quả |
|---|---|---|---|
| `mobile` | chưa `npm ci` | `npm ci && npm test` | **888 pass, 0 fail, 0 skipped** |
| `e2e` | chưa `npm ci` | `scripts/e2e_slice.sh` | **7 pass, 0 fail, 0 skipped** |
| `guard-range` | nhánh không thêm commit nào trên `origin/main` | — | đúng: tôi đứng *trên* main |
| `ruff` | nhánh không đổi file Python nào | — | đúng, cùng lý do |

Thêm, trên nhánh PR đứng một mình (`0e0f3569`):
`python3 -m pytest services/api/tests tests -q` → **2628 passed, 571 skipped**.

Tầng Postgres cho riêng màn này, DB riêng, `MOBILE_REQUIRE_POSTGRES_TESTS=1`:
**19 passed, 0 skipped**.

---

## 5. Chuyện quy trình: PR này lên `main` trước khi có phán quyết QA

Không phải lỗi code, và không đổi kết luận PASS ở trên. Nhưng nó là lý do một dấu
đỏ trong lượt đo này **trông** như lỗi của PR mà không phải:

`scripts/gate_merge.sh 389` chạy lúc `02:2x` cho **HỎNG** ở chặng `mobile`:

```
not ok 598 - nhánh này không mang lại file nào đã có nguyên vẹn trên origin/main
  12/12 file hien trong diff ma noi dung y het origin/main.
```

Đọc kỹ thì đó không phải bug — đó là `stacked-branch.test.mjs` báo đúng: PR đã được
merge (`8dbd772`, `19:24:59Z`) **trong lúc cổng đang chạy**, nên `merge(PR, main)`
bằng đúng `main`, và cả 12 file đều giống hệt. Cổng nói thật; nếu tôi dừng ở chữ
"HỎNG" thì tôi đã mở một phiếu lỗi cho một PR không có lỗi.

Ghi ra đây vì đây là lần thứ hai trong đêm nhịp merge làm một phép đo QA hết hiệu
lực giữa chừng, và vì cách phòng nó rẻ: đọc lý do đỏ trước khi tin chữ đỏ.

---

## Ô CHƯA quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Không agent nào đóng được;
  chỉ leader, 15 phút với một điện thoại. Còn nguyên.
- **Ma trận hình ảnh của màn Cá nhân**: lượt này **không** quét. Tôi đo `TaiChinh`
  qua `renderToStaticMarkup` và qua đột biến, không đo bằng ảnh chụp ở 320/390/1440
  hay ở chủ đề tối. Câu "ba ô có vỡ layout ở 320pt không" chưa có câu trả lời.
- **Tương phản và trình đọc màn hình** cho ô "Còn nhận" mới: chưa đo.
- **Nhiều nhóm, nhiều người ứng tiền cùng lúc**: walk của tôi có đúng hai người và
  một khoản chi. Bất biến chéo người mới được kiểm ở `n = 2`.
- **Nghĩa vụ có người nhận khác người ứng tiền**: `collected_vnd` đếm theo
  `CollectionObligation.recipient_id`, `advanced_vnd` đếm theo
  `ExpenseVersion.paid_by_id`. Trên đường đi tôi quét thì hai cái đó là cùng một
  người. Nếu sản phẩm sau này cho nhóm cử một người đứng thu hộ, hai con số này
  rời nhau — **chưa đo**, và không phải lỗi hôm nay.
- **Xác nhận nhận tiền hai lần** được máy chủ chấp nhận (mục 2). Đã đo là màn hình
  không sai; **chưa đo** hậu quả ở bảng đợt thu và ở dòng thời gian.
- Tầng live Gemini: còn skip theo opt-in, không thuộc PR này.
