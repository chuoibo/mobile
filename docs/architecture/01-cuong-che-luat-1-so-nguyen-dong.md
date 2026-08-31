# Cưỡng chế Luật 1 (số nguyên đồng): ở đâu, bằng gì, và chỗ nào còn hở

> **Đây không phải một quyết định mới.** Ba luật tiền trong `CLAUDE.md` không đổi.
> Trang này mô tả **cách** Luật 1 đang được cưỡng chế trên `main` — thứ đã được xây
> rải rác trong 12 PR đêm 30–31/08/2026 và **chưa được viết ở đâu cả**.
> `CLAUDE.md` đòi ADR khi *đổi* một luật tiền; ta không đổi luật, nên chỗ của trang
> này là `docs/architecture/`. Xem mục 6 về câu hỏi "có nên là ADR không".

- **Ngày:** 2026-08-31 · **DRI:** backend
- **Đo tại:** `2a8362d` — sha này **đã ở `main`** (`git merge-base --is-ancestor origin/main HEAD`)
- **Luật được nói tới:** `CLAUDE.md` → "Ba luật về tiền" → luật 1: *số nguyên đồng,
  không `float`, không `Decimal`, kể cả ở giá trị trung gian*

Mọi con số dưới đây **được đo lại từ đầu khi viết trang này**, không chép từ mô tả PR.
Chỗ nào phép đo mới lệch với PR cũ, trang này ghi con số mới và nói vì sao lệch.

---

## 1. Luật 1 được cưỡng chế ở HAI tầng, và tầng domain mới là tầng bắt buộc

| Tầng | Hình dạng | File | Bắt được gì |
|---|---|---|---|
| Biên HTTP | `MoneyVnd = Annotated[int, Field(strict=True)]` | `app/api/schemas.py:24` | thân request JSON |
| **Domain** | `vnd_violation(amount) == NOT_INTEGER` → `AllocationError("AMOUNT_NOT_INTEGER")` | `app/domain/allocator.py:104` | **mọi** đường vào `allocate()` |

Rào pydantic ở biên HTTP là tầng **đầu tiên**, không phải tầng **đủ**. Hai phép đo độc
lập nói vì sao:

**(a) 5/9 nguồn tiền không đi qua biên HTTP** — #460.

```
TỔNG: 9 nguồn
  đi qua họ rào strict : 4        (PYDANTIC: ExpenseInput + 3 model con)
  KHÔNG đi qua         : 5        (DB_RECORD 4 · COMPUTED 1)
HAI TRỤC: call site = 3   ·   nguồn = 9
```

Phát hiện đắt nhất của #460 nằm ở `POST /bills/{id}/split`: thân request là
`BillSplitRequest`, gồm đúng `for_ledger` và `paid_by_id` — **không có một trường tiền
nào**. Toàn bộ tiền nó chia đến từ database, và cái rào che đường đó nằm ở một
**endpoint khác, trong một request khác, sớm hơn**. Một rào chỉ đứng ở biên HTTP thì
không nhìn thấy đường này.

**(b) 4/7 cơ chế sinh object đi vòng được qua rào** — #459.

Bảy cách một object pydantic ra đời được đo từng cái; bốn cách cho giá trị sai đi qua:
`model_construct`, `model_copy`, `__new__`/`construct`, và **gán thuộc tính sau khi
model đã dựng**. `model_construct` không phải cửa duy nhất — đó là tiêu đề của #459.

Và tầng sau rào không đỡ được (#459, ĐO 7):

```
dataclass AllocationRow (frozen=True)
   amount_vnd=82000.5 -> 82000.5 (float)  KHÔNG chặn, KHÔNG cảnh báo
sqlalchemy ConfirmedAllocation
   amount_vnd=82000.5 -> 82000.5 (float)  KHÔNG chặn
```

`int` trong dataclass và `Mapped[int]` trong SQLAlchemy là **chú thích cho người đọc,
không phải phép kiểm lúc chạy**.

**Kết luận kiến trúc:** tầng domain là nơi **duy nhất mọi đường đều đi qua**. Nguồn có
thể tránh biên HTTP; object có thể ra đời bằng bốn cách đi vòng; nhưng không có đường
nào chia được tiền mà không gọi `allocate()`. Nên phép kiểm bắt buộc đặt ở đó.

Đối chứng sau bản vá #450 — 21/21 ca đầu vào xấu bị chặn, kể cả 5 nguồn không qua rào:

```
$ cd services/api && PYTHONPATH=. python3 tests/qa/qa-tt-0057-gac-450/probe_nam_nguon_khong_qua_rao.py
TONG: BLOCKED=21
```

Cần đọc kèm: ADR-0012 ghi lại **quyết định** thêm mã `AMOUNT_NOT_INTEGER` vào danh sách
đóng của ADR-0004. Trang này mô tả bố cục; ADR-0012 mới là chỗ quyết định.

---

## 2. Một bộ kiểm duy nhất, và cổng chống bản sao thứ 14

Phép kiểm hình dạng số nguyên chỉ được viết ra ở **một** chỗ: `app/domain/money.py`,
hàm `_not_an_integer`. Hai hàm công khai (`vnd_violation`, `count_violation`) dùng chung
nó và **trả về lý do thay vì tự ném**, nên mỗi module vẫn giữ đúng exception và mã lỗi
của mình — đó là lý do gộp được mà gần như không ca ghim nào phải sửa (#437).

Cổng giữ điều đó: `services/api/tests/test_one_money_check.py`.

**Nền trước → sau, cùng một máy quét** (một số 0 không có nền thì không phân biệt được
với một máy quét hỏng):

| | bản sao trong `SCOPE` (`domain`, `payments`, `api`, `db`) |
|---|---|
| trước #437 (`f6c4518`) | **13** |
| trên `main` hôm nay (`2a8362d`) | **1** — và 1 đó là `money.py::_not_an_integer`, tức là **nhà** |

Cổng bắt **ba** cách viết, vì mỗi cách đã từng làm mù một lượt đếm:

```
isinstance(V, bool)  cặp với  isinstance(V, int)     (V phải trùng, thứ tự tự do)
type(V) is int  /  type(V) is not int                (không cần lời gọi bool nào)
```

Cổng tự kiểm chính máy so khớp bằng 8 ca (thứ tự đảo, ternary, `type(...) is not bool`
là cờ chứ không phải lượng, và ca gần-trượt `place_search._distance_km` ở cả hai cách
viết), cộng một **đối chứng dương**: `money.py` phải **còn** chứa hình dạng — xoá nó
không được đọc thành "sạch bản sao". #437 đã đột biến cổng ở cả hai cách viết và cả hai
đều đỏ.

**Còn nợ, ghi thẳng:** `app/web/guest_view.py:format_vnd` là bản sao thứ 14, là tiền
thật, và **nằm ngoài `SCOPE`** vì `app/web/` thuộc lane Claude. Hằng `SCOPE` trong file
test là ranh giới trung thực của phép đo, không phải lời khai về cả cây. Cần Lead giao
cho lane web.

---

## 3. Đơn vị đếm: đếm bằng thứ NGƯỜI ĐI CHÉP KHÔNG ĐỔI ĐƯỢC

Đây là bài học đắt nhất của cả chuỗi việc, và nó lặp lại ở **hai** chỗ khác nhau trong
cùng một đêm.

| Đếm bản sao bộ kiểm theo | Ra | Mù cái gì |
|---|---|---|
| mã lỗi `AMOUNT_NOT_INTEGER` | 4 | 3 bản sao ném mã riêng của module |
| tên export / hình dạng `isinstance` | 6 | 3 bản sao viết bằng `type(v) is not int` |
| **hình dạng, cả ba cách viết** | **13** | ghi thẳng trong docstring của cổng |

| Đếm slot tiền theo | Ra |
|---|---|
| tên export | 7 |
| tham số | 9 |
| **máy đi bộ cây đối số, suy ra từ 41 golden vector** | **11** |

Cùng một kiểu sai: **đếm bằng thứ mà người đi chép được tự do đổi.** Người copy-paste
đổi được tên hàm, đổi được mã lỗi, viết lại được hình dạng. Đếm theo những thứ đó thì
**chính người bị đếm quyết định con số**.

Ba đơn vị đang dùng, và vì sao mỗi cái không bị người chép ảnh hưởng:

| Phép đo | Đơn vị | Vì sao không đổi được |
|---|---|---|
| bản sao bộ kiểm (#437) | *(hàm bao gần nhất, biểu thức chủ thể)* | mất cặp `isinstance` thì không còn là bản sao của phép kiểm đó nữa |
| nguồn tiền (#460) | *(ô tiền, biểu thức sinh ra giá trị)*, ô tiền đọc từ **chính phép subscript của `allocator.py`** | đổi `expense["total_vnd"]` thì allocator không đọc được nữa |
| slot tiền (#450) | suy ra từ **41 golden vector** | corpus vàng là thứ duy nhất trong repo không ai sửa lẻ được |
| cửa đi vòng (#459) | **cách object ra đời** | `model_construct` là API của pydantic, không phải tên ta đặt |

**Một cảnh báo về đơn vị, đo được ngay trong lúc viết trang này.** Chạy đúng máy quét
của cổng hôm nay lên cây trước #437:

- đếm theo **hàm bao** → **12**
- đếm theo **(hàm bao, biểu thức chủ thể)** → **13**

Chênh một, và chỗ chênh là `money_skill.validate_context` — một hàm chứa **hai** phép
kiểm trên hai chủ thể khác nhau (`manifest.get('message_count')` và `max_messages`).
Con số 13 của #437 đúng; nó chỉ đúng ở **đơn vị chủ thể được kiểm**, không phải đơn vị
hàm. Bài học tự lặp lại một lần nữa: **con số không tự bảo vệ được, đơn vị thì có.**
Ai trích lại số 13 mà không kèm đơn vị sẽ làm người sau đo lại ra 12 và tưởng có hồi quy.

---

## 4. Cái KHÔNG phải do ta — và đây là cảnh báo cho tương lai

Không có `float` nào nằm được trong sổ cái. Nhưng **lý do không phải rào ta chọn** — là
**kiểu cột** (#467). Đo trên PostgreSQL 16 thật, schema do Alembic migrate:

```
money columns   : 24
distinct types  : ['bigint']
jsonb columns   : 2 -> ['audit_events.event_data', 'messages.card']
```

**Sửa một chữ trong cách nói phổ biến về chuyện này:** Postgres **không "từ chối"**
`float`. Nó **làm tròn, im lặng**. Đo trực tiếp, ghi ORM + commit, không qua HTTP:

```
float .5     sent 300.5    -> stored 300 (int)  <-- STORED NUMBER != SENT NUMBER
float .4     sent 300.4    -> stored 300 (int)
float .0     sent 300.0    -> stored 300 (int)
bool True    sent True     -> REFUSED  (psycopg.errors.CannotCoerce) cannot cast boolean to bigint
int (base)   sent 300      -> stored 300 (int)

candidates tried: 5 · refused by the database: 1 · stored: 4
stored with a CHANGED number: 2 -> [('float .5', 300.5, 300), ('float .4', 300.4, 300)]
stored still NON-INT: 0
```

Phân biệt cho rõ, vì hai câu này khác nhau về hậu quả:

- ✅ **Đúng:** không giá trị **không nguyên** nào *nằm lại* trong 24 cột tiền.
- ❌ **Sai:** "database chặn giá trị sai". Nó chặn `bool`; với `float` nó **giữ lại một
  con số KHÁC** con số được gửi. Triệu chứng là một dòng tiền hơi lệch trong sổ, **không
  phải một lỗi 500 ai đó nhìn thấy**.

### Ba điều cần biết trước khi tin hàng rào này

1. **Nó là hệ quả của lựa chọn kiểu cột, không ai đang gác nó.** Không có cổng nào
   khẳng định "mọi cột tiền phải là `bigint`". Thêm một cột tiền kiểu `numeric` hay
   `double precision` ngày mai thì **không có gì đỏ**, và tầng bảo vệ này biến mất im
   lặng ở đúng cột đó. Đây là chỗ đáng thêm cổng nhất trong cả trang này.
2. **`jsonb` là lỗ có sẵn.** Cột `jsonb` **không có kiểu số nào cả**. Một số tiền sống
   trong `audit_events.event_data` hay `messages.card` thì Postgres không ép kiểu, và
   `float` ở đó **là `float` mãi mãi**. (Chính tính chất này được probe dùng làm đối
   chứng dương để chứng minh nó *nhìn thấy được* một `float` trong DB.)
3. **5 bảng tiền không có trigger append-only:** `bills`, `bill_items`,
   `bill_surcharges`, `bill_discounts`, `outings`. 14 bảng có. Đo được:
   `UPDATE expense_versions.total_amount_vnd = 999.5` → **REJECTED** (append-only),
   nhưng `UPDATE bills.items_total_vnd = 999.5` → **ACCEPTED**, dòng nay giữ `1000`.
   Bảng `bills` là bản nháp trước khi vào sổ, nên có thể đúng chủ ý — nhưng nó chưa được
   viết ra ở đâu là chủ ý.

---

## 5. Cái CHƯA làm: cửa thứ tư mở, 0 người đi qua

Cửa thứ tư của #459 — **gán thuộc tính tiền sau khi model đã dựng** — vẫn **MỞ**. #462
đếm xem hôm nay có ai đi qua không:

```
Trường tiền khai trong schemas.py + models.py: 29
File quét: 130
MẪU SỐ — tổng chỗ gán/đặt thuộc tính mọi loại: 125
Trường tiền đã khai bị gán sau khi dựng: 0 chỗ
Tên GIỐNG tiền nhưng không phải trường tiền đã khai: 1 chỗ (cần người phán)
```

**0/125.** Và mẫu số 125 là mẫu số **thật** — máy đếm có đối chứng
`[OK] phép đếm chạm được vào cây thật (125 chỗ, không phải 0 vì hỏng)`, nên số 0 này
phân biệt được với một máy quét chết.

Đọc cho đúng: đây là **"đóng một cửa trước khi có người đi"**, không phải **"vá một lỗ
đang chảy"**. #459 đo được rằng **một dòng config** (`model_config` với
`validate_assignment=True`) đóng được cửa này, và đóng được là **đo được**. Chưa làm vì
chưa ai đi qua, và vì nó không đóng ba cửa kia (`model_construct`, `model_copy`,
`__new__`) — ba cửa đó không có config nào đóng được.

**Không cổng nào gác điều này.** Nguyên văn kết luận của #459:

> không phải vì rào kín, mà vì chưa ai viết dòng code đi vòng.
> KHÔNG chứng minh: rằng ngày mai vẫn thế — một `obj.amount_vnd = x` thêm vào tuần sau
> sẽ không làm đỏ cái gì cả.

---

## 6. Chỗ của trang này, và câu hỏi gửi Lead

Đặt ở `docs/architecture/` **có chủ ý**. `CLAUDE.md` đòi ADR khi **đổi** một trong ba
luật tiền; ở đây không luật nào đổi — ta chỉ mô tả cách cưỡng chế luật đã có. Quyết định
duy nhất thật sự được ra trong cả chuỗi việc này là *thêm mã `AMOUNT_NOT_INTEGER` vào
danh sách đóng của ADR-0004*, và nó **đã có nhà riêng** ở ADR-0012.

Nếu Lead muốn nâng thành ADR thì thứ đáng nâng **không phải trang này**, mà là một quyết
định chưa ai ra: **"cột tiền bắt buộc là `bigint`, và có cổng gác"** (mục 4.1). Đó mới
là một ràng buộc mới lên code, tức là một quyết định. Trang này chỉ ghi lại cái đã có.

---

## Tự đo lại — mọi con số ở trên, bằng lệnh

Chạy từ **gốc repo** trừ chỗ ghi khác. Ba lệnh đầu không cần database.

```bash
# mục 2 — bản sao bộ kiểm: phải xanh, và cổng tự kiểm chính máy so khớp
cd services/api && python3 -m pytest tests/test_one_money_check.py -q

# mục 1 — 21/21 ca xấu bị chặn, gồm cả 5 nguồn không qua rào HTTP
cd services/api && PYTHONPATH=. python3 tests/qa/qa-tt-0057-gac-450/probe_nam_nguon_khong_qua_rao.py

# mục 1 — 9 nguồn · 4 qua rào · 5 không
cd services/api && PYTHONPATH=. python3 tests/qa/backend-092115-nguon-tien-vao-allocate/dan_xuat_nguon.py

# mục 1 & 5 — 7 cơ chế / 4 cửa mở, và tầng sau rào không chặn
cd services/api && python3 tests/qa/qa2-085832-duong-vong-tien/probe_duong_vong_rao_tien.py

# mục 5 — 0/125 chỗ đi qua cửa thứ tư
cd services/api && python3 tests/qa/qa2-095741-cua-thu-tu/probe_cua_thu_tu_gan_thuoc_tinh.py

# mục 4 — CẦN Postgres thật; thiếu URL thì nó in SKIP-NOT-GREEN chứ không giả vờ xanh
docker compose up -d postgres
cd services/api && PYTHONPATH=. \
  MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 tests/qa/qa2-101428-ghi-thang-so-cai/probe_ghi_thang_so_cai.py
```

Nền "13 trước → 1 sau" ở mục 2 đo bằng **chính máy so khớp của cổng hôm nay**, chạy trên
cây cũ. Chạy từ `services/api/`:

```bash
# SAU — cây hôm nay
python3 tests/qa/backend-111300-trang-kien-truc-luat-1/dem_ban_sao_bo_kiem.py app

# TRƯỚC — cây ngay trước #437
mkdir -p /tmp/nen437
git archive f6c4518 services/api/app | tar -x -C /tmp/nen437
python3 tests/qa/backend-111300-trang-kien-truc-luat-1/dem_ban_sao_bo_kiem.py \
  /tmp/nen437/services/api/app
```

Script in **cả hai đơn vị** (`scope` và `subject`) chứ không in một con số, đúng vì lý do
ở mục 3. Nó `exit 1` — chứ không in "0 bản sao" — khi phạm vi rỗng hoặc khi chính máy so
khớp không thấy hình dạng trong đối chứng dương của nó.

> `mkdir -p` là bắt buộc: `tar -x -C` vào thư mục chưa tồn tại sẽ hỏng, và **qua pipe nó
> vẫn trả `exit 0`** — đúng kiểu "cổng xanh vì không dựng được gì" mà repo này đã dính
> nhiều lần.

### Chính máy đếm nền này đã bị đột biến, không chỉ được hứa

Một máy đếm nền không cắn được thì nó không đo gì cả — nó chỉ mô tả. Ba đột biến, chạy
trên cây đã commit rồi hoàn nguyên:

| Đột biến | Kết quả | Đọc là gì |
|---|---|---|
| làm mù máy so khớp (`isinstance` → tên không tồn tại) | `FAIL: the matcher cannot find the shape in its own control` · `exit 1` | đối chứng dương **cắn** |
| làm mù máy so khớp **và gỡ bỏ đối chứng dương** | in `unit = subject: 0` · **`exit 0`** | **đây là thứ đối chứng dương mua được** |
| rút ruột `SCOPE` thành `()` | `FAIL: only 0 files ... SCOPE looks wrong` · `exit 1` | phạm vi rỗng là **đỏ**, không phải "0 bản sao" |

Hàng giữa là hàng đáng đọc. Không có đối chứng dương, một máy so khớp hỏng in ra số **0**
— **đẹp hơn** con số thật (`1`) — và thoát `0`. Người đọc sẽ thấy "sạch hơn cả trước" và
không có dấu hiệu nào báo rằng phép đo đã chết.

## Dẫn nguồn

| PR | Đóng góp cho trang này |
|---|---|
| #437 | gộp 13 bản sao về `money.py`; cổng đếm theo hình dạng, ba cách viết |
| #450 | phép kiểm ở tầng domain (`AMOUNT_NOT_INTEGER`); cổng slot tiền suy từ 41 golden vector |
| #452 | Luật 1 ở allocator: 0/5 đường HTTP lọt; tiền chỉ sai ở đúng ca `bool` |
| #459 | 7 cơ chế sinh object, 4 cửa đi vòng; tầng sau rào không chặn |
| #460 | 9 nguồn tiền vào `allocate()`, 5 không qua `MoneyVnd`; Postgres làm tròn |
| #461, #466 | hậu kiểm QA cho #450: `model_construct` bị đóng, 5 nguồn bị chặn |
| #462 | cửa thứ tư mở, 0/125 chỗ đi qua |
| #467 | 24 cột tiền đều `bigint`; lý do là kiểu cột, không phải rào |
| #469, #475 | `bill.py:104` không có `/` trên tiền; `SUM()` của Postgres trả `Decimal` |
| ADR-0012 | quyết định thêm `AMOUNT_NOT_INTEGER` vào danh sách đóng của ADR-0004 |
