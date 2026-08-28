# Chia tiền nhóm bạn

Ứng dụng cho nhóm bạn Việt đi chơi cùng nhau: ghi khoản chi, chia tiền, và **thu tiền về**.

Spec kết luận rằng phần đau thật **không phải chia tiền mà là đi thu tiền** — nhắn riêng từng người, gửi số tài khoản, nhớ ai đã chuyển, nhắc mà không mất lòng. Nên màn hình trung tâm là **bảng thu tiền**, không phải màn chia tiền.

## Trạng thái

Lát cắt dọc chạy được: `POST /expenses` → chia tiền → xác nhận → đợt thu → VietQR → trang cho khách.

**Chưa có bằng chứng hành vi nào.** `ADR-0006` ghi rõ: Giai đoạn 0 bị gác lại theo quyết định có ý thức của chủ sản phẩm, nên đây là một canh bạc, không phải một giả thuyết đã được kiểm chứng. Đừng đọc bộ test xanh thành "sản phẩm này đúng".

## Chạy

```bash
docker compose up -d                        # Postgres
cp .env.example .env
pip install -r services/api/requirements-dev.txt
cd services/api && alembic upgrade head
uvicorn app.api.main:app --reload           # API

cd apps/mobile && npx expo start            # app, quét bằng Expo Go
```

Xem thử trang cho khách mà không cần database:

```bash
cd services/api && python3 -m app.web.preview
```

Dựng ảnh API:

```bash
cd services/api && docker build -t mobile-api .
```

Build context là `services/api/`, **không phải** gốc repo. Docker chỉ đọc
`.dockerignore` ở gốc build context, nên file đó phải nằm trong `services/api/`;
đặt ở gốc repo là không có tác dụng.

## Test

```bash
python3 -m pytest services/api/tests tests -q   # unit/domain + API fake repository
node packages/shared/money.test.mjs             # hai bề mặt cùng một bộ golden
scripts/setup-hooks.sh                          # bật repo guard trước khi commit
```

Repository production có một tầng riêng chạy trên PostgreSQL thật; xem
[`docs/testing/postgres-repository.md`](docs/testing/postgres-repository.md).

## Bố cục

```
services/api/app/domain/     thuần: tiền, sổ, đợt thu, quyền, hiển thị
services/api/app/db/         SQLAlchemy + Alembic
services/api/app/api/        FastAPI, 7 endpoint
services/api/app/web/        trang cho khách, render từ server
apps/mobile/                 Expo + TypeScript
packages/shared/             token thiết kế và định dạng tiền dùng chung
docs/decisions/              ADR — đọc cái này trước khi đổi hành vi
```

`domain/` **không được import** `db`, `api` hay `payments`. Có test biên cưỡng chế điều đó, và lý do là bất biến 3 của spec: số dư luôn tính lại được từ sổ, cache không bao giờ là nguồn sự thật.

## Ba luật về tiền, không thương lượng

1. **Số nguyên đồng.** Không `float`, không `Decimal`, không ở bất kỳ tầng nào.
2. **`Σ` phân bổ `=` đúng tổng khoản chi.** 100%, không ngoại lệ. 41 golden vector tính tay giữ điều này.
3. **Số dư tính lại được từ sổ.** Cache không bao giờ là nguồn sự thật.

Đổi bất kỳ điều nào ở trên thì mở ADR trước, đừng sửa code trước.
