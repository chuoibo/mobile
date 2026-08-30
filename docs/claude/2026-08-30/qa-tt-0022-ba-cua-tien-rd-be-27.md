# PASS — #286 (rd-be-27): ba cửa tiền F24 / F26 / F34

**Lý do:** ba route mới hành xử đúng như PR khai, đo bằng đường chạy thật chứ không
bằng tên route: cửa khai danh tính **không tồn tại** (`paid_by_id` lấy từ tác giả
trong DB, không phải người bấm — kiểm bằng model Gemini thật), ngân sách nhóm từ
chối người lạ **nói dối header** `X-Actor-Contexts` (403), và ba luật tiền đứng
vững ở cả ba cửa. Chặng docker **đỏ lúc tôi bắt đầu là do #283 trên main, không
phải do #286** — tôi chứng minh bằng cách vô hiệu hoá đúng một khiếm khuyết của
#283 rồi thấy app import được và cả ba route của #286 đăng ký bình thường trên
fastapi **bản ghim** 0.115.6. devops đã vá thật ở #288 giữa lượt đo; tôi đo lại
trên cây gộp và container **healthy**.

- protocol_version: v1
- verdict: **PASS**
- SHA head PR đã đo: `bffdea0e2d8d0ff26020088ff15d68bd377f4ca5` (không đổi từ lúc bắt đầu tới lúc kết thúc)
- SHA cây gộp đã đo: `13d4aae4929ac0f7cb1f76dbec28483855a03bcd` = `bffdea0` ⊕ `origin/main@65319b5`
- blocker còn mở: **không có**

---

## Cảnh báo hạ tầng — đọc trước, nó ảnh hưởng tới mọi lane

**`scripts/gate.sh docker` dùng tên ảnh và tên container TOÀN CỤC trên một docker
daemon dùng chung, nên hai lane chạy cùng lúc đọc nhầm cây của nhau.**

```
scripts/gate.sh:381   ( cd services/api && docker build -t mobile-api:gate . )
scripts/gate.sh:395   docker rm -f mobile-api-gate
```

Tôi vấp phải nó thật, không phải suy đoán. Sau khi gộp bản vá #288 vào cây của
mình, chặng docker **vẫn đỏ ở đúng `memories.py:143`** — trong khi file trong cây
tôi đã có bản vá ở dòng 153. Mở ảnh ra xem thì nguồn bên trong **không phải cây của
tôi**:

```
# trong cây tôi (đã gộp #288)
18:from fastapi import APIRouter, Depends, Query, Response, status
153:) -> Response:

# trong ảnh mobile-api:gate mà chặng vừa dựng
18:from fastapi import APIRouter, Depends, Query, status
    response_model=MemoryReactionResponse,      <- hình dạng ĐỘT BIẾN của lane khác
```

Dựng lại đúng cây đó dưới tên riêng `mobile-api:qa286merge` thì ra đúng nguồn của
mình và app import được. Hai dòng `Error response from daemon: No such container:
mobile-api-gate` trong log lượt đầu của tôi là cùng một hiện tượng: một tiến trình
khác đã xoá container giữa chừng.

**Hậu quả — và đây là chiều nguy hiểm:** lần này nó cho tôi một dấu **ĐỎ** giả, dễ
phát hiện. Chiều ngược lại là một dấu **XANH** giả — lane A dựng cây sạch của mình,
lane B đọc ảnh đó và kết luận cây *của B* khởi động được. Không có gì trong đầu ra
của chặng phân biệt được hai trường hợp. Đây đúng là hình dạng Lead mô tả: một cổng
nhập "không biết" vào "đạt".

**Tiêu chí gỡ:** đặt tên ảnh và container theo lane hoặc theo SHA
(`mobile-api:gate-$(git rev-parse --short HEAD)`), hoặc khoá chặng docker lại. Việc
này thuộc devops, tôi không sửa. Phân loại: **không tái lập được** (blocker loại 5)
— nhưng với *cổng*, không với PR #286.

---

## Tầng nào đã THẬT SỰ chạy

| Cổng | Kết quả | Đo trên |
|---|---|---|
| `pytest services/api/tests tests -q` | **2133 passed, 421 skipped, 4795 subtests**, 0 failed | `bffdea0`, cây sạch |
| `pytest services/api/tests tests -q` | **2135 passed, 420 skipped**, 1 failed *(file nháp của chính tôi)* | cây gộp `13d4aae` |
| `tests/postgres` `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **368 passed, 0 skipped** — PostgreSQL thật | `bffdea0` |
| `apps/mobile && npm test` | **680 pass, 0 fail, 0 skipped** (7 suite) | `bffdea0` |
| Ảnh Docker, fastapi **ghim 0.115.6** | **APP IMPORT OK**, 67 route, cả 3 route mới có mặt | cây gộp `13d4aae` |
| Container thật phục vụ `/healthz` | **healthy sau 6s**, `healthz=200` | cây gộp `13d4aae` |

Một ca đỏ duy nhất là cổng ratchet ruff bắt `tests/qa/rd-qa-36/di-bo-ban-be.py` —
**file nháp chưa commit của chính tôi**, không thuộc #286. Cổng này quét filesystem
chứ không quét cây git. Dời file ra khỏi cây rồi chạy lại thì **0 failed**. Đây là
cổng làm đúng việc, không phải cổng phiền.

---

## Đi bộ thật qua ba cửa (không phải đọc tên route)

Máy chủ thật, PostgreSQL riêng (`qa286`, không đụng DB chung), **Gemini thật**
(`GEMINI_API_KEY` đọc từ `.env` ngoài repo; chỉ in độ dài, không bao giờ in giá trị).

### F24 — `POST /contexts/{cid}/messages/{mid}/expense-draft`

Hà viết *"Mình vừa trả 180k tiền bún bò cho cả nhóm nhé"*. **Nam** — một người
khác trong nhóm — bấm tạo nháp:

```
paid_by_id = TÁC GIẢ (Hà)?        True
paid_by_id = NGƯỜI BẤM (Nam)?     False     <- True ở đây là sai thẩm quyền
shared_by  = roster ACTIVE?       True (2 người)
amount_vnd = 180000  kiểu=int               <- luật tiền 1, "180k" đọc đúng
needs_review = True                         <- không tự động ghi sổ
trường tên người do model sinh:   []
```

Tin nhắn không phải khoản chi → `detected: false`, `draft: null`, nêu lý do bằng
tiếng Việt. Không bịa ra khoản chi.

**Quyền riêng tư — `message_id` của nhóm khác:**

```
msg của nhóm B    -> 404 {"code":"message_not_found","detail":"Message does not exist"}
msg không tồn tại -> 404 {"code":"message_not_found","detail":"Message does not exist"}
GIỐNG HỆT NHAU? CÓ
```

Byte-identical. Một UUID đoán mò không trở thành cửa sổ nhìn vào hội thoại nhóm khác.

### F34 — `GET /contexts/{cid}/budget`

Cửa đáng lo nhất, vì `X-Actor-Contexts` là **header do người gọi tự khai**. PR nói
quyền đòi hàng thành viên ACTIVE trong DB chứ không đọc header. Đo:

```
chủ nhóm A (ACTIVE)         : 200
NGƯỜI LẠ + NÓI DỐI header   : 403     <- lời nói dối KHÔNG ăn
người lạ, không khai ctx    : 403
thành viên nhóm KHÁC        : 403
```

Luật tiền 1 trên `candidate_per_person_vnd`:

```
bool true -> 422 | float lẻ -> 422 | float integral -> 422 | âm -> 422 | int hợp lệ -> 200
```

`180000.0` bị từ chối là chỗ đáng khen: nó *integral* nhưng đã là float, tức đã qua
biên tiền rồi.

Nhóm chưa có chuyến nào xong, vẫn truyền tham số ứng viên:

```
{"outing_count":0,"active_member_count":1,"avg_per_person_vnd":null,"in_progress":[],"comparison":null}
```

Không bịa số để có cái mà so. Đúng như PR khai.

### F26 — `POST /screenshots/scan`

```
file thực thi (.exe)     -> 415 unsupported_image_type
SVG có <script>          -> 415 unsupported_image_type
PNG cắt ngang            -> 415 unsupported_image_type
12 MiB                   -> 413 image_too_large ("vượt quá giới hạn 8 MB")
PNG thật                 -> 422 not_a_transaction
PNG khai man là JPEG     -> 422 not_a_transaction   <- xử theo PIXEL, không theo lời khai
```

Ngưỡng byte cắn **trước** khi giải mã, và content_type client khai không quyết định
gì — đúng hai điều PR nói.

---

## Đối chứng: cổng có thật sự cắn không?

Cổng quyền riêng tư của F34 là thứ tôi vừa xác nhận bằng tay. Câu hỏi còn lại: nó
đúng vì **có test gác**, hay đúng do may? Một đột biến **PR không liệt kê**:

```python
# app/domain/permissions.py
"view_group_budget": {"roles": {"group_admin","member"}, "requires": ()}  # bỏ is_group_member
```

```
1 failed, 14 passed
FAILED test_group_budget_requires_active_membership_before_reading_ledger
```

Đỏ, và đỏ **đúng lý do** — tên ca khớp đúng tính chất bị phá, không phải đỏ vì một
hằng số phụ. Hoàn nguyên → `15 passed`.

---

## Phát hiện — không chặn merge

**Danh sách chặn key hình-dạng-người chỉ bắt tiếng Anh.** PR nói lý do từ chối cả
câu là "bỏ qua im lặng là lỗ ngủ chờ ngày có người đọc key đó". Đo thật trên
`read_chat_expense`:

```
tiếng Anh   : từ chối 14/14   (paid_by, payer, person_id, shared_by, who_paid, …)
tiếng Việt  : từ chối  0/14   (nguoi_tra, ai_tra, chia_cho, thanh_vien, nguoi_ung, …)
khác        : từ chối  1/12   (uid, actor, owner, user_id, … lọt)
```

**Vì sao đây KHÔNG phải blocker:** tôi assert trên từng ca rằng giá trị buôn lậu
không bao giờ tới được đầu ra — **0/40 ca rò rỉ**. Domain chỉ đọc đúng ba khoá
`is_expense` / `title` / `amount_text` và trả về đúng bốn trường không có danh tính;
`paid_by_id` và `shared_by` do service lấy từ DB. Khoá lạ bị **bỏ qua**, không được
đọc. Tiền không đi sai, không ai lộ.

Và một điểm làm nhẹ thêm, tôi nêu cho công bằng: prompt gửi model viết bằng **tiếng
Anh** và liệt kê rõ ba trường được phép, nên khả năng model tự đẻ khoá tiếng Việt là
thấp — dù đầu vào là hội thoại tiếng Việt.

Cái không đạt được chỉ là **tính chất PR tự đặt ra cho mình**: "không bỏ qua im
lặng". Với sản phẩm tiếng Việt, hình dạng dễ xuất hiện nhất lại đúng là hình dạng
danh sách không phủ. Phân loại: **suggestion**, không phải blocker. Gợi ý nếu backend
muốn siết: đảo sang *allowlist* — bất kỳ khoá nào ngoài ba khoá hợp đồng đều 422 —
thì tính chất đúng với mọi ngôn ngữ mà không phải đuổi theo từ vựng.

---

## Ô CHƯA QUÉT — phần quan trọng nhất

- **Độ chính xác của F26 trên ảnh chụp màn hình THẬT.** Tôi chỉ bắn ảnh tổng hợp
  (PNG trắng, exe, SVG, file cắt ngang). Ảnh Grab / ShopeeFood / app ngân hàng thật
  **chưa từng được đưa vào**. Tôi đo *biên tải lên*, không đo *model đọc đúng số tiền*.
- **F34 với nhóm ĐÃ có chuyến xong.** Nhóm thử của tôi có `outing_count: 0`, nên
  tôi chứng minh được "không có dữ liệu thì không bịa", nhưng **đường tính trung
  bình và phép so sánh chỉ được test đơn vị phủ, chưa chạy qua HTTP thật**.
- **Không có màn hình nào.** PR là API thuần, tự khai như vậy. Ba tính năng này chưa
  có client gọi — theo cách đếm đã chốt, chúng **chưa phải tính năng sống**, mới là
  route sống.
- **Mã VietQR chưa từng được quét bằng app ngân hàng thật.** Không liên quan PR này,
  nhưng vẫn là ô mở của cả sản phẩm cho tới khi leader cầm điện thoại thật kiểm.
- **`npm run test:e2e` (lát cắt dọc) tôi KHÔNG chạy trong lượt này.** #286 không
  chạm lát cắt dọc và không đổi client. Nói rõ ra vì đó là chặng duy nhất có cả
  client lẫn server thật, và một báo cáo giấu chuyện mình bỏ chặng nào thì vô dụng.
- **Bảng đột biến 17 hàng của chính PR tôi không chạy lại toàn bộ.** Tôi chạy một
  đột biến **độc lập** mà PR không liệt kê (ở trên). Con số 17/17 là của tác giả,
  chưa được tôi kiểm chứng lại từng hàng.

---

## Ghi chú thứ tự merge

Cây gộp `13d4aae` khởi động được **chỉ vì** #288 đã vào main trước. #286 tự nó
không gây và không làm nặng thêm sự cố 204; nó chỉ thừa hưởng. Không còn ràng buộc
thứ tự nào cho #286 tại thời điểm này.

Ràng buộc Lead tự đặt (PR đổi khai báo route thì chặng docker phải xanh trước khi
merge) đã được thoả — nhưng xin đọc kèm phần cảnh báo hạ tầng ở đầu: **hãy dựng
dưới tên ảnh riêng**, đừng tin `mobile-api:gate` khi có lane khác đang chạy.
