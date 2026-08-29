# rd-qa-26 · Cổng đầy đủ trên main, và máy demo đang chạy mã cũ 6 tiếng

- **protocol_version**: v1
- **verdict**: `PASS` cho `main` · **`FAIL` cho môi trường demo `8099`**
- **đo tại**: `96e75f2` (= `origin/main` `6c7d2ab` ⊕ hai file tài liệu/`.mjs` của nhánh này)
- **sha này**: `6c7d2ab` ĐÃ ở main. Nhánh chỉ thêm `docs/` và `tests/qa/*.mjs`, không
  file `.py`/`.ts` nào — nên số của cổng dưới đây là số của chính `main`.
- **blocker còn mở**: 1 (loại "không tái lập được / hỏng tính hợp lệ thí nghiệm"),
  nằm ở **môi trường**, không nằm ở code `main`.

---

## Lý do, viết trước phần chi tiết

`main` xanh toàn phần: 1165 + 224 + 493 + 2 ca, **0 skip ở tầng Postgres**, e2e chạy
thật. Không có lỗi nào trong code.

Nhưng **máy chủ demo `192.168.1.7:8099` — cái leader sẽ cầm điện thoại chĩa vào —
đang chạy mã cũ hơn `main` khoảng 6 tiếng và thiếu 5 route**, trong đó có
`/places/search` (F12 "tìm bằng lời") và cả ba route check-in của F46. Hai trong sáu
tính năng của đợt đẩy độ phủ **chết trên máy demo dù sống trên `main`**.

Và nó **không sửa được bằng cách khởi động lại**: database dùng chung `mobile` đang ở
trạng thái mà `alembic upgrade head` **thất bại**. Cách sửa đã được tôi kiểm chứng
đỏ-trước/xanh-sau trên một DB nháp, ghi ở mục 3.

---

## 1. Cổng đầy đủ trên `main` — tất cả đều xanh

Chạy trong cây sạch (`git status` chỉ có thư mục build untracked của lượt trước,
không có sửa đổi tracked nào).

| Cổng | Lệnh | Kết quả |
|---|---|---|
| Domain + API (fake repo) + repo guard | `python3 -m pytest services/api/tests tests -q` | **1165 passed, 254 skipped**, 4590 subtests passed, 59.66s |
| Tầng PostgreSQL thật | `MOBILE_TEST_DATABASE_URL=…/qatt02 MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q` | **224 passed, 0 skipped**, 16.90s |
| Mobile | `cd apps/mobile && npm test` | **493 pass, 0 fail, 0 skipped**, 2 suites |
| Tiền, hai bề mặt | `node packages/shared/money.test.mjs` | 10 golden + 6 refusals; 9 accepted + 10 refused — all pass |
| Repo guard | `python3 scripts/repo_guard.py tree HEAD` | `Repo guard passed tracked tree: 597 file scan(s).` |
| Migration render DDL (không cần DB) | `command.upgrade(c,'head',sql=True)` | exit 0 |
| Lát cắt dọc e2e | `EXPO_PUBLIC_API_URL=http://127.0.0.1:8077 MOBILE_REQUIRE_E2E=1 npm run test:e2e` | **2 pass, 0 fail, 0 skipped** |

Hai chỗ tôi cố ý **không** đọc thành xanh:

- **254 skipped** ở lệnh đầu là tầng `tests/postgres` tự bỏ qua khi thiếu URL. Nó
  được chạy riêng ở hàng 2 với `MOBILE_REQUIRE_POSTGRES_TESTS=1` và ra **0 skipped**.
  Con số 224 mới là bằng chứng của tầng đó; 254 skipped thì không.
- **e2e mặc định bắn vào `8099`.** Bắn vào đó là đo container của người khác — đúng
  cái hỏng ở mục 2. Tôi dựng máy chủ riêng ở `8077` trên DB riêng `qatt02` migrate
  từ đầu, và ghim `EXPO_PUBLIC_API_URL`. `MOBILE_REQUIRE_E2E=1` biến một lượt skip
  thành một lượt đỏ, nên "0 skipped" ở đây là chạy thật.

Một điều đáng ghi: **DB mới tinh migrate lên `head` sạch, exit 0**, qua đủ
`b2d9f4c781a0 → … → e3b8c1d5720f`. Chuỗi migration của `main` khoẻ. Điều này quan
trọng vì nó tách bạch mục 3: lỗi ở đó là lỗi **trạng thái của một DB cụ thể**, không
phải lỗi migration.

## 2. BLOCKER · Máy demo `8099` thiếu 5 route so với `main`

`192.168.1.7:8099` và `127.0.0.1:8099` là cùng một thứ: container
`mobile-local-api-1`, `Up 6 hours (healthy)`, map `0.0.0.0:8099->8000/tcp`.

So bộ route của hai máy chủ, cùng một lúc:

```
main (8077, mã 6c7d2ab): 42 route
demo (8099):             37 route

THIẾU trên máy demo:
  - /places/search                                  ← F12 "tìm bằng lời" (#155)
  - /contexts/{context_id}/checkins                 ← F46 check-in nhóm (#136)
  - /outings/{outing_id}/checkins                   ← F46 (#136)
  - /outing-stops/{stop_id}/checkins                ← F46 (#136)
  - /outings/{outing_id}/invites/{invite_id}/revoke ← thu hồi lời mời
```

Không có route lạ nào trên demo mà `main` không có — nên đây đúng là "cũ hơn", không
phải "khác nhánh".

**Đối chứng, cùng một request, hai máy chủ:**

```
POST /contexts/{ctx}/checkins   {"place_id":"p-tiem-nuong-xom-lao","caption":"Tới nơi rồi"}

8077 (mã main 6c7d2ab, DB ở head)  -> 201 Created
  {"kind":"checkin","place_name":"Tiệm Nướng Xóm Lào","lat":11.9404,"lng":108.4383,…}

8099 (máy demo)                    -> 404 {"detail":"Not Found"}
```

Cùng `ctx`, cùng `actor`, cùng header, cùng body. Khác nhau duy nhất là máy chủ. Nên
404 này **không đổ cho dữ liệu hay quyền được** — route không tồn tại ở đó.

**Vì sao đây là blocker chứ không phải phiền toái:**

1. Leader xem PoC bằng điện thoại trỏ vào `192.168.1.7:8099`. Trên máy đó **F12 tìm
   bằng lời và F46 check-in không tồn tại** — bấm vào ra 404, dù cả hai đã ở `main`.
   Hai trong sáu tính năng của đợt đẩy độ phủ 47% → 60%.
2. Nó **hỏng tính hợp lệ của mọi phép đo khác** chạy vào `8099`. Một lane test F46 ở
   đó sẽ nhận 404 và kết luận "tính năng chưa làm" — sai, nó đã merge ở `#136` lúc
   `09:20Z`. Đây đúng loại phiếu lỗi mà ghi chú vai trò QA đã cảnh báo: đo trên hiện
   vật không truy được về `main`.

**Tiêu chí gỡ chặn:** `curl -s http://192.168.1.7:8099/openapi.json | grep -c places/search`
trả `1`, và POST check-in ở trên trả `201`. Lưu ý: **khởi động lại container là chưa
đủ** — xem mục 3.

## 3. BLOCKER phụ · DB dùng chung không `upgrade head` được

Ghi chú Lead lúc 17:40 nói DB `mobile` "đã sửa xong, alembic ở `d4a2e7b91c30`". Câu
đó đúng lúc đó, nhưng `head` đã tiến lên từ khi ấy:

```
DB chung `mobile` :  d4a2e7b91c30
head hiện tại     :  e3b8c1d5720f     (sau d7a2e05c9b14)
```

Chạy `alembic upgrade head` trên DB chung thì **đỏ**:

```
psycopg.errors.DuplicateColumn: column "kind" of relation "memories" already exists
[SQL: ALTER TABLE memories ADD COLUMN kind VARCHAR(7) DEFAULT 'photo' NOT NULL]
```

Nguyên nhân đã xác định bằng cách soi schema, không phải đoán: DDL của
`d7a2e05c9b14` **đã áp dụng đủ** nhưng `alembic_version` **không được đẩy theo**.

| | DB chung `mobile` | DB đã ở head (đối chứng) |
|---|---|---|
| cột `memories` | `kind, place_id, place_name, lat, lng` — **có đủ** | có đủ |
| constraint | `ck_memories_memory_kind`, `…_payload_matches_kind`, `…_lat_range`, `…_lng_range` — **có đủ 4** | đúng 4 cái đó |
| bảng `outing_stop_checkins` | **KHÔNG có** | có |
| `alembic_version` | `d4a2e7b91c30` | `e3b8c1d5720f` |

Nên DB chung đang mắc kẹt đúng giữa `d7a2e05c9b14`: hiệu lực có, con dấu không.

**Cách sửa — tôi đã kiểm chứng đỏ-trước/xanh-sau trên DB nháp `qascratch`**, dựng lại
đúng trạng thái đó (`upgrade d7a2e05c9b14` rồi ép `alembic_version` về
`d4a2e7b91c30`):

```bash
# ĐỎ — tái lập đúng lỗi của DB chung:
alembic upgrade head
#   psycopg.errors.DuplicateColumn: column "kind" … already exists   (exit 1)

# XANH — cách sửa:
alembic stamp d7a2e05c9b14     # công nhận phần đã áp dụng, không chạy lại DDL
alembic upgrade head           # chỉ còn e3b8c1d5720f
#   -> alembic_version = e3b8c1d5720f, bảng outing_stop_checkins được tạo
```

`stamp` ở đây an toàn **vì** bảng so sánh trên đã chứng minh cả 5 cột và cả 4
constraint của `d7a2e05c9b14` đều đã có mặt — không có phần nào của revision đó bị
bỏ sót mà con dấu lại che đi.

**Tôi KHÔNG chạy lệnh này trên DB chung.** Hạ tầng dùng chung không thuộc quyền tôi,
và vai trò QA là chứng minh chứ không vá. DB chung lúc tôi rời tay vẫn nguyên
`d4a2e7b91c30`. Hai DB nháp `qatt02`/`qascratch` đã `DROP`.

## 4. Đối chứng `#158` (phần đã commit ở lượt trước, `96e75f2`)

Giữ nguyên, không đo lại. Tóm tắt để Lead không phải mở file: hai bundle web dựng từ
hai commit thật, cùng bắn vào **một** máy chủ mã `main` không sửa — nên 401 ở bản
trước không đổ cho môi trường được.

- **TRƯỚC (`df3f1a1`)**: header ra `null` → 401, màn in nguyên mã lỗi tiếng Anh kèm
  địa chỉ API nội bộ. F12 chết 100% trên `main` trong quãng giữa `#155` và `#158`.
- **SAU (`6c7d2ab`)**: header ra `personId` thật → 200, panel "AI hiểu câu của bạn"
  và 2 chỗ, AI thật.

Chi tiết đầy đủ ở `docs/claude/2026-08-29/rd-qa-25-doi-chung-158-tim-kiem.md`.

## 5. Ô CHƯA quét — phần quan trọng nhất

- **Mã QR VietQR chưa được quét bằng app ngân hàng thật.** Không agent nào làm được
  câu này. Còn nguyên là ô trống cho tới khi leader cầm điện thoại thật (ADR-0010 §8).
- **Ma trận hình ảnh trang khách** (11 trạng thái × sáng/tối × 320/390/1440): lượt
  này **không quét**. Không có số liệu mới từ tôi.
- **F46 trên máy demo**: chưa quét được, vì route không tồn tại ở đó (mục 2). Chỉ
  chứng minh được nó chạy trên mã `main` với DB ở head.
- **`/places/search` trên máy demo**: cùng lý do, chưa quét.
- **Ba route check-in ở tầng giao diện**: lượt này chỉ chạm tầng HTTP. Chưa đi bộ
  bằng trình duyệt thật, chưa quét `imp detect`.
- **F16, F36, F17**: ngoài phạm vi lượt này.

## 6. Ghi chú nhỏ, không phải blocker

`X-Actor-Roles` là header do client tự đặt và máy chủ tin. Gửi
`group_admin,member,advancer,recipient,batch_owner` thì tạo được nhóm và check-in
được. Đây **đã** được ghi trong `CLAUDE.md` là chỗ tạm của lát cắt dọc, không phải
auth production — nên tôi ghi lại cho đủ hồ sơ, **không** nộp nó như phát hiện mới.

Một điều tốt đáng ghi: check-in F46 trả `lat/lng` **của địa điểm trong catalogue máy
chủ** (`11.9404, 108.4383` cho "Tiệm Nướng Xóm Lào"), không phải GPS của máy người
dùng — client chỉ gửi `place_id`, không gửi được toạ độ. Đây là câu trả lời cho câu
hỏi 3 mà Lead đặt ở `rd-qa-17`: **check-in không lộ GPS người dùng.**
