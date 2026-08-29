# rd-qa-10 — quét quyền riêng tư trên hai bề mặt mới (#112, #115)

**Đo tại `d568ef8`** (main, 2026-08-29). Hệ thật: PostgreSQL 16 trong Docker,
uvicorn do chính lượt này khởi động trên cổng 8117, database `qa_priv` riêng đã
`alembic upgrade head`. Không đo trên container 8099 — nó là bản cũ 9 tiếng và
`GET /openapi.json` của nó **không có** route `memories`, nên mọi con số lấy từ
đó sẽ là con số của một sản phẩm khác. Probe tự vân tay bản dựng trước khi đo.

## Phán quyết theo bốn câu hỏi được giao

| # | Câu hỏi | Kết quả |
|---|---|---|
| 1 | Người ngoài nhóm GET kỷ niệm → 403, thân 403 không mang caption/URL ảnh/tên | **ĐẠT** |
| 2 | Người đã rời nhóm còn đọc được kỷ niệm cũ không | **KHÔNG ĐẠT** — có một khe ~1–2 ms |
| 3 | Số điện thoại có rò vào log/response/DB không | **ĐẠT về chữ, KHÔNG ĐẠT về nghĩa** |
| 4 | A có thấy bạn bè của B không | **ĐẠT** |

25 phép kiểm trên cây sạch: 25 PASS. Con số đó chỉ có nghĩa vì ba đột biến bên
dưới đã làm nó đỏ trước.

## Đột biến — trồng lỗi vào chính phép đo trước khi tin số 0

| Đột biến | Bắt bởi |
|---|---|
| 1. Bỏ hẳn `_require_permission("view_group_memories")` | 6 phép kiểm đỏ (1b, 1c, 1g, 2c, 2d, 4d) |
| 2. `is_member` quên lọc `state`/`left_at` — đúng lỗi #112 nói là nó chặn | 4 phép kiểm đỏ (2c, 2d, 2e, 2f) |
| 3. Đọc dữ liệu trước, kiểm quyền sau, rồi nhét caption vào thân 403 | 3 phép kiểm đỏ (1c, 1g, 2d) |

Phép kiểm rò rỉ không phải một danh sách tên trường viết tay. Nó thu mọi giá trị
mà một thành viên hợp lệ nhìn thấy trong bản 200, rồi khẳng định không chuỗi nào
trong số đó có mặt trong bản 403. Thêm trường mới vào `MemoryResponse` tuần sau
thì phép kiểm phủ luôn, không cần ai nhớ sửa file này.

## Phát hiện 1 — `DELETE .../members/{id}` trả 204 trước commit của chính nó

**Loại: rò dữ liệu người khác.** Không phải lỗi của tường kỷ niệm; tường kỷ niệm
là nơi nó lộ ra.

`get_repository` (`app/api/deps.py`) là dependency `yield` bọc
`with factory.begin() as session`. COMMIT chạy khi context manager thoát, tức là
lúc dependency teardown. Đo trực tiếp bằng một connection psycopg hâm sẵn, SELECT
ngay khoảnh khắc nhận được 204:

```
28/30 vòng trả lời trước khi commit nhìn thấy được
độ rộng khe: min=0.90ms max=2.12ms
```

Đây là tính chất **cấu trúc**, không phải hiếm. Cái hiếm là một client đủ nhanh để
chen một request thứ hai vào khe đó. Lượt đo này chen được **một lần trong ~130
lần thử**, và lần đó để lại vật chứng bền trong database:

```
tác giả                 caption     created_at              trạng thái  left_at
Dung TenThat-ECA4EDE3   quay lai    ...52.150417+00         left        ...52.140771+00
```

Người đã rời nhóm **ghi** một kỷ niệm vào nhóm đó **9,6 ms sau khi rời**, và hàng
đó vẫn nằm trong bảng. Log của chính máy chủ xác nhận thứ tự (dòng 33–35 của
`/tmp/qa_priv_server.log`): `DELETE 204` → `GET 200` → `POST 201` → `GET members 403`.

Không tái lập lại được sau đó: 40 vòng tuần tự, 3 lần khởi động lạnh, 3 lần bật
`--log-level debug`, 72 lần với 12 luồng đồng thời — tất cả 0. Đó là vì khe ~1 ms
hẹp hơn một vòng HTTP; lần trúng là lần khe rộng ~10 ms. Phép đo commit ở trên là
thứ biến "một lần trúng khó tin" thành một tính chất đo được lặp lại.

**Hậu quả rộng hơn tường kỷ niệm.** Cùng một dependency phục vụ mọi route, nên mọi
"ghi xong rồi đọc lại" đều nằm trên khe này — kể cả đường tiền
(`confirm` → đọc số dư, khoá idempotency → retry). Lượt này **chưa quét** phía tiền;
nó cần một việc riêng.

**Tiêu chí gỡ chặn:** commit trước khi handler trả về, rồi `do_commit_sau_phan_hoi.py`
phải ra 0/30 thay vì 28/30.

## Phát hiện 2 — câu nói với người dùng về số điện thoại rộng hơn sự thật

**Loại: quyền riêng tư / consent.**

Phần chữ đã đạt, và đạt sạch. Quét toàn bộ: 0 số điện thoại trong mọi thân phản
hồi (cả dạng `0…`, `84…`, `+84…`), 0 trong log uvicorn, 0 trong log container
postgres, 0 trong `pg_dump --data-only` của cả database. `PersonRegistrationRequest`
đúng là chỉ có `display_name`.

Nhưng `people.id` **là** một digest không khoá của chính số đó — FNV-1a + fmix64,
hằng số nằm trong repo. Và `GET /contexts/{id}/members` trả `person_id` của mọi
thành viên cho mọi thành viên. Đo tốc độ khôi phục:

```
142,630 ứng viên/giây  (Python thuần, một lõi)
toàn không gian di động VN = 5 × 10^8
=> quét cạn kiệt: ~1.0 giờ (Python thuần) / ~3.5 giây (C hoặc GPU)
```

`danh-tinh.ts` nói thẳng điều này trong docstring (dòng 26–33) — với kỹ sư thì
lane đã trung thực. Câu **hiện trên màn hình cho người dùng** thì chưa:

> "Số này chỉ nằm trên máy bạn. App không gửi số lên máy chủ và không lưu số ở
> đâu cả — nó chỉ dùng để nhận ra bạn khi quay lại."

Đúng từng chữ, sai về nghĩa: thứ được gửi lên và lưu lại là một hàm một-một của
số, đảo ngược trong một giờ bằng laptop. Người đọc câu đó trước khi gõ số sẽ hiểu
là số của họ không rời máy. Đây là câu chữ ở `app/web`-side của lane frontend, sửa
rẻ; không phải lỗi kiến trúc.

**Tiêu chí gỡ chặn:** câu trên màn nói đúng cái đang xảy ra — số không được lưu
dạng đọc được, nhưng id suy ra từ số và người cùng nhóm thấy id đó.

## Ô CHƯA quét

- **Đường tiền dưới khe commit ở Phát hiện 1** — chưa đo. Đây là ô quan trọng nhất.
- Ảnh kỷ niệm: `image_url` là chuỗi, chưa có upload thật, nên chưa quét được
  quyền truy cập tệp ảnh (URL đoán được? hết hạn? CDN công khai?).
- Phân trang `before` của tường: chưa thử cursor của nhóm khác cắm vào nhóm mình.
- `X-Actor-ID` giả mạo: đã biết và đã ghi trong `CLAUDE.md`, không nộp lại.
- Trang khách, mã QR quét bằng app ngân hàng thật: ngoài phạm vi lượt này, vẫn nợ.
- Giao diện màn `vao-cua`: lượt này đo API và dữ liệu, không đo màn hình.

## Chạy lại

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U mobile -d mobile -c "CREATE DATABASE qa_priv OWNER mobile;"
cd services/api && MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/qa_priv' python3 -m alembic upgrade head
MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/qa_priv' python3 -m uvicorn app.api.main:app --port 8117 &

python3 tests/qa/rd-qa-10/probe_quyen_rieng_tu.py --base http://127.0.0.1:8117 --log <log>
python3 tests/qa/rd-qa-10/do_commit_sau_phan_hoi.py --base http://127.0.0.1:8117 --rounds 30
python3 tests/qa/rd-qa-10/repro_dong_thoi.py --base http://127.0.0.1:8117 --workers 12 --rounds 6
```

Không file nào ở đây viết ra một số điện thoại: `repo_guard.py` từ chối dãy số
hình dạng số di động VN và không phân biệt được số bịa với số thật, nên fixture
được ghép từ mảnh lúc chạy. `danh_tinh.py` là bản chép Python của `danh-tinh.ts`
và đã đối chiếu khớp 20/20 vector với bản TS đã biên dịch trước khi dùng.
