# QA #350 — dựng lại dữ liệu demo mà không xoá sổ

- **protocol_version**: v1
- **PR**: [#350](https://github.com/chuoibo/mobile/pull/350) — devops, `devops/cong-du-lieu-may-demo`
- **PR head đã đo**: `0e6caf07b9379d014f7f9f3d00d6fa5cf5557d11`
- **main lúc bắt đầu**: `ba510d8` · **main lúc viết**: `66a6990` (nhích 2 lần giữa lượt đo)
- **Máy đo**: 8099 (`mobile-local-api-1`), database dùng chung `127.0.0.1:5432/mobile`
- **Verdict QA**: **PASS** — không tìm được blocker nào trong 5 loại của charter.
  Chữ ký `APPROVE`/`REQUEST_CHANGES`/`REJECT` vẫn là của người review (ADR-0007).
- **Kỹ năng đã gọi**: `e2e-testing` (điều phối), `database-testing` (chặng sổ cái)

Lead hỏi bốn câu. Trả lời từng câu, kèm lệnh chạy lại được.

---

## 1. Con số 3/5/7/3 có thật không — đếm lại độc lập

Đếm bằng SQL của tôi, **không** gọi `check_demo_data.py`, để con số không đến từ
chính cái đang được kiểm:

```
nhóm 'Team Đà Lạt'  5cacfdee-955f-4743-9cc4-c6a019480c96   (tạo 13:42:59Z 30/08)
  outings                  3
  collection_batches       3
  memberships (active)     7
  expenses                 5
```

Khớp đúng báo cáo của devops. Nhóm cũ vẫn còn, dưới tên
`Team Đà Lạt (tồn dư 30/08 — KHÔNG dùng để demo)` (`3423b032…`), giữ nguyên 8 đợt
thu / 22 khoản chi / 9 người của nó.

Số dư còn nợ của nhóm demo là **1.422.165** trên 5/7 người (21 nghĩa vụ, 15 đã xác
nhận nhận được) — nên màn tài chính cá nhân ở cuối đường hero có số khác 0 để hiện.
`seed_demo_data.py` có cảnh báo trường hợp "không ai còn nợ"; trường hợp đó không xảy ra.

## 2. "Không xoá sổ" — đúng, và đây là cách chứng minh

Đếm dòng **không trả lời được câu này**. Máy dùng chung, lane khác ghi liên tục, nên
`confirmed_allocations` 22027 → 22082 vừa khớp với "không xoá gì" vừa khớp với "xoá
50 thêm 100". Phải so **chính các dòng**.

devops đã `pg_dump` trước khi làm (`/tmp/demo-8099-truoc-khi-dung-lai-<dấu-thời-gian>.sql`,
12.464.215 byte, 20:38:47 +07). Tôi so từng dòng của dump đó với DB sống, theo đúng
mã hoá COPY của PostgreSQL nên không có tầng chuyển kiểu nào ở giữa:

```
$ scripts/qc/probe_so_cai_sau_bao_tri.py --dump /tmp/demo-8099-truoc-khi-dung-lai-<dấu-thời-gian>.sql

bảng                                 trước     sau    MẤT   thêm
*audit_events                         7841    7902      0     61
*bank_recipient_snapshots              192     203      0     11
*collection_batch_versions             190     200      0     10
*collection_envelopes                  357     390      0     33
*collection_obligation_sources         429     472      0     43
*collection_obligations                426     464      0     38
*confirmed_allocations               22027   22082      0     55
*expense_versions                     7331    7343      0     12
*payment_reports                         5       9      0      4
*receipt_confirmations                 100     119      0     19
 contexts                               21      39      1     19
 idempotency_keys                      877    1041     27    191
rc=0    Không bảng append-only nào mất dòng.
```

**Mười bảng append-only: 0 dòng mất.** Bất biến 3 còn nguyên cho cả hai nhóm.

Hai bảng có dòng rời đi, đúng hai bảng script khai là nó ghi:

- `contexts` — **1 dòng đổi**, và chỉ đổi `display_name`. `id`, chủ sở hữu,
  `created_at` giống hệt trước. Đây là cái UPDATE có chủ ý.
- `idempotency_keys` — 27 dòng. Kiểm thêm một tầng: so theo **cặp
  `(scope, idempotency_key)`**, số cặp biến mất là **0**. Nghĩa là 27 dòng đó bị xoá
  rồi được lần seed sau ghi lại với `id` mới; không guard nào mất hẳn. Và không cặp
  nào nằm ngoài tập key mà fixture tự sinh được — reset không chạm key của lane khác.

### 27 chứ không phải 29 — không phải PR khai sai

PR nói 29 key. Tôi đo 27, vì 2 key được tạo **sau** lúc dump (20:38:47) rồi mới bị
xoá, nên chúng chưa từng có trong nền so sánh. Có dấu vết khớp: dump có `idempotency_keys`
= 877 còn script khai 879, và nhóm cũ có 1 `outings` tạo lúc 20:40:29 trong khi toàn
máy lúc dump có 0 outing. Tức là giữa dump và reset đã có một lượt `make demo` chạy
dở — đúng lượt đâm vào 422 mà PR mô tả. Ba con số tự khớp nhau, không có gì lệch.

## 3. Hero path trên máy demo sau khi dựng lại — đi hết được

### 3a. Đường ghi: 27/27 chặng

```
$ scripts/qc/probe_hero_path_may_demo.py --base-url http://127.0.0.1:8099
CHẶNG ĐI ĐƯỢC: 27/27
```

Chạy trong **nhóm thăm dò riêng**, không đâm vào `Team Đà Lạt`: `expenses` và
`expense_versions` là append-only nên một lượt đi bộ qua nhóm demo là không gỡ lại
được, và `check_demo_data` so bằng dấu bằng nên chỉ một khoản chi thừa cũng làm cổng
của chính máy đỏ. Cùng container, cùng database, cùng khoá Gemini, cùng code.

| chặng | kết quả |
|---|---|
| `POST /receipts/scan` — Gemini thật | 200, **5/5 món**, `items_total` 745.000 == tổng in trên giấy, `totals_agree=true`, 4,2–9,2s |
| `POST /bills` | 201 |
| `PUT /bills/{id}/assignments` | 200, gán 5 món **lệch nhau có chủ ý** |
| `POST /bills/{id}/split` | 200, `state=confirmed`, 162.500 / 392.500 / 117.500 / 72.500 |
| luật 2: Σ phân bổ == tổng | 745.000 == 745.000 |
| luật 1: mọi phần là số nguyên đồng | đúng |
| **phân bổ trong SỔ == phân bổ theo MÓN** | **khớp từng người** |
| `POST /expenses/{id}/confirm` | 201 |
| `POST /batches` → `publish` | 201 `frozen` → 200, 3 link khách |
| người ứng tiền không có nghĩa vụ | đúng — 3 nghĩa vụ, tổng 627.500 = 745.000 − 117.500 |
| 3 trang khách | mỗi người thấy **đúng phần khác nhau** 162.500 / 392.500 / 72.500 · không lộ số người khác · không lộ tổng nhóm · có mã VietQR |

Dòng in đậm là dòng đáng giá nhất. Lượt đầu tôi tạo khoản chi chỉ bằng `total` +
`participants`, và allocator chia đều 745.000/4 = 186.250 mỗi người — **28/28 xanh
trong khi bước "gán món" không hề ảnh hưởng tới đồng nào**. Ba trang khách khi đó
hiện cùng một con số. Phải đẩy `items` vào `POST /expenses` thì phân bổ theo món mới
tới được sổ, và lúc đó ba trang khách mới hiện ba số khác nhau. Một lượt đi bộ hero
không kiểm dòng này thì xanh mà rỗng.

### 3b. Đường đọc: 16/16 link khách của chính nhóm demo vừa dựng

`guest_links` chỉ giữ digest SHA-256 nên không lấy lại token từ đó được. Lấy được từ
`idempotency_keys.response_body` của các key `publish:` — thân trả lời của lần publish
được lưu để replay, và trong đó có đường dẫn link.

Cả 16 link: **200**, phần tiền của chính người đó có trên trang, **không** có tổng
nghĩa vụ của nhóm (5.721.332), không có tên thành viên nào ngoài người nhận và người
ghi khoản chi.

> Hai lần đầu phép đo của tôi báo cả 16 trang đều "lộ tên người khác". Sai ở phép đo,
> không ở sản phẩm: `Trang` khớp vào câu chân trang *"**Trang** này không cho xem gì
> khác của nhóm"*, và `Linh` khớp vào địa danh *"Cà phê sáng Mê **Linh**"*. So tên
> người bằng chuỗi con với tiếng Việt là hỏng ngay từ đầu. Bản sửa đọc ba ô mà trang
> thật sự nêu tên ai, rồi so với tập được phép.

## 4. Cổng `check_demo_data` có răng không — có, đo hai lớp

### 4a. Ma trận đột biến trên Postgres cách ly

```
$ scripts/qc/dot_bien_cong_du_lieu_demo.py
M0  nền, không đổi gì                             rc=0  mong 0  ĐÚNG
M1  xoá một buổi đi                               rc=1  mong 1  ĐÚNG
M2  thêm buổi đi thứ tư                           rc=1  mong 1  ĐÚNG
M3  xoá một đợt thu                               rc=1  mong 1  ĐÚNG
M4  xoá một khoản chi                             rc=1  mong 1  ĐÚNG
M5  một thành viên rời nhóm                       rc=1  mong 1  ĐÚNG
M6  thêm người thứ tám                            rc=1  mong 1  ĐÚNG
M7  đổi tên nhóm demo                             rc=1  mong 1  ĐÚNG
M8  đổi tiêu đề buổi đi, không đổi số lượng       rc=0  mong 0  ĐÚNG   <- đối chứng dương
M9  đổ chín buổi đi vào NHÓM KHÁC                 rc=0  mong 0  ĐÚNG   <- đối chứng dương
rc=0    Bảy đột biến bị bắt, ba đối chứng dương giữ xanh.
```

Ba hàng xanh là phần làm bảng này đọc được. Một bảng đỏ toàn tập không phân biệt được
cổng cắn với cổng hỏng — cổng chết lúc khởi động cũng đỏ cả mười hàng. **M9 là hàng
chịu lực**: `check_demo_data` tự khai nó "nói không gì về các nhóm KHÁC trên database
dùng chung"; nếu M9 đỏ thì nó đang đếm toàn cục và dữ liệu thăm dò của mọi lane sẽ làm
máy demo trông như hỏng.

### 4b. Trên chính máy thật — xanh → ĐỎ → xanh

Ma trận trên chạy trên schema tổng hợp, nên nó nói về **số học** của cổng, không nói
về schema máy demo. Đóng nốt nửa kia bằng một đột biến thật, chỉ chèn rồi gỡ một dòng
do chính tôi tạo (`outings` không mang trigger bất biến — đã kiểm `pg_trigger`):

```
[1] NỀN                    rc=0  "batches 3, expenses 5, members 7, outings 3 — ĐỦ"
    chèn 1 outing giả  ->  outings = 4
[2] ĐÃ ĐÂM MỘT SỐ          rc=1  "outings   4/3   -> Khám phá, kỷ niệm và album hiện RỖNG"
    gỡ 1 dòng probe    ->  outings = 3   (bằng nền: True)
[3] SAU KHI HOÀN NGUYÊN    rc=0  "... — ĐỦ, đúng bộ script khai."
```

Cổng có răng, trên cả hai lớp.

---

## Phát hiện

Không cái nào thuộc 5 loại blocker của charter. Xếp theo mức đáng làm.

### PH-1 · suggestion — câu hậu quả chỉ viết cho một chiều

`CONSEQUENCE` trong `check_demo_data.py` có đúng một chuỗi cho mỗi khoá, và chuỗi đó
viết cho chiều **thiếu**. Khi số dư ra, người đọc nhận một câu sai:

```
outings   4/3   -> Khám phá, kỷ niệm và album hiện RỖNG (F13/F14/F15/F16)
```

Với 4 buổi đi thì mấy màn đó không rỗng, chúng **thừa một chuyến không ai thiết kế**.
Docstring của chính file đã nói "Too many rounds is as wrong as too few", nên chiều
này là chiều tác giả biết có. Người đi sửa theo dòng trên sẽ đi tìm một màn trống
không tồn tại. Gỡ chặn: câu hậu quả rẽ theo `got > want` hay `got < want`.

### PH-2 · observation — token trang khách lấy lại được từ `idempotency_keys`

`seed_demo_data.py` viết trong comment rằng `guest_links` chỉ lưu digest nên "một link
không được in ra lúc publish thì không lấy lại được". Lấy lại được: thân trả lời của
`POST /batches/{id}/publish` nằm trong `idempotency_keys.response_body`, và trong đó
có đủ 16 đường dẫn. Tôi đã dùng đúng đường đó để quét 16 trang ở mục 3b.

Không phải leo thang quyền — cần quyền đọc database, mà có quyền đó thì đã xong rồi.
Nhưng phát biểu trong comment là **sai**, và ai suy luận về thu hồi link từ câu đó sẽ
suy từ tiền đề sai. Đáng sửa câu comment; nếu muốn tính chất đó là thật thì phải lọc
token khỏi thân trả lời trước khi lưu, và đó là quyết định của Codex chứ không phải
của lượt QA này.

### PH-3 · fact — 6/51 replay key của fixture không có trên máy sau reset+seed

4 key `bank:`, 1 `invite:`, 1 `accept:`. Không mất dữ liệu (hệ quả của các lượt ghi
đó vẫn nằm trong bảng), chỉ nghĩa là lượt `make demo` sau sẽ **ghi lại** 6 lượt đó
thay vì replay. Hậu quả thấp, nhưng nên biết trước khi đọc "reset là idempotent".

### PH-4 · disclosure — lượt đo này để lại rác trên máy dùng chung

7 nhóm `QA3 tham do PR350 …` / `QC thăm dò hero …` cùng bill và khoản chi của chúng.
Không đụng nhóm demo, và `check_demo_data` vẫn xanh sau đó (M9 giải thích vì sao).
Xoá được hay không là việc của devops — `expense_versions` là append-only.

---

## Sự cố phát hiện trong lúc đo — KHÔNG do PR này

Lúc 21:43–21:51 (+07), **đang có lane khác đổ dữ liệu vào chính nhóm `Team Đà Lạt`**:

```
expenses của nhóm demo 5cacfdee:  5 -> 28 và vẫn đang tăng
  (20 -> 23 chỉ trong 45 giây, từng cụm 3 dòng cách nhau ~60-70s)
  22/28 dòng KHÔNG có expense_version: ai đó gọi POST /expenses lên
  context_id của nhóm demo rồi không confirm.
  1 dòng thì CÓ version — tức là có cả một lượt confirm ghi vào sổ nhóm demo.
9 membership của nhóm lưu trữ 3423b032 bị set state='left' lúc 14:44:14Z.
```

Hậu quả nhìn thấy được: **`check_demo_data.py` đã đỏ** —
`Dữ liệu demo 'Team Đà Lạt' KHÔNG dùng để demo được: expenses 17/5`. Lúc 21:39 nó còn
rc=0. Bộ dữ liệu devops dựng lại lúc 20:42 hỏng lại sau một tiếng.

Không phải tôi: 7 nhóm thăm dò của tôi có tên riêng, context riêng, tạo lúc
14:40:07–14:42:07Z; các khoản chi rác bắt đầu 14:43:20Z, sau lượt chạy cuối của tôi,
và tiếp tục sau khi tôi dừng hẳn. Đã báo Lead lúc 21:51 (`tell-lead qa3 blocked`).

Điểm đáng ghi: cổng mà PR #350 đi kèm **bắt được trong vài phút**. Đây đúng là trường
hợp nó sinh ra để bắt.

---

## Ô chưa quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Tôi chỉ kiểm *có* ảnh trên trang.
  Chuỗi đúng CRC vẫn có thể là chuỗi không app ngân hàng Việt nào nhận. Cần leader +
  một điện thoại, 15 phút (ADR-0010 §8). Không agent nào đóng được ô này.
- **Trang khách chưa được nhìn bằng mắt** ở lượt này: không ảnh chụp, không ma trận
  sáng/tối × 320/390/1440, không kiểm tương phản hay vùng bấm.
- **`tests/postgres` không chạy trong lượt này** — PR #350 không chạm
  `SqlAlchemyApiRepository`, và cây này không phải cây tôi đo (tôi đo *máy*).
- **Ma trận đột biến 4a chạy trên schema tổng hợp**, không phải schema sản phẩm. Một
  vụ đổi tên cột trên máy thật sẽ làm cổng exit 2 ở đó mà vẫn qua cả mười hàng ở đây.
  Mục 4b là thứ đóng nửa còn lại; đừng đọc 4a một mình.
- **Cửa sổ trước lúc dump không được phủ.** Dòng nào sinh ra sau 20:38:47 rồi bị xoá
  trước khi tôi đo là vô hình với phép so này.
- Repo này **chưa có bằng chứng hành vi nào** (ADR-0006). Bộ test xanh nói code làm
  đúng điều tác giả nghĩ; nó không nói người thật hiểu sản phẩm.
