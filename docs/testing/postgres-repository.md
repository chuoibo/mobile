# Test repository SQLAlchemy trên PostgreSQL thật

## Mục đích

Bộ test API mặc định dùng fake repository để kiểm orchestration nhanh. Nó không
thể chứng minh câu SQL, JSONB, partial unique index, composite foreign key,
view hay trigger append-only hoạt động. Tầng test này chạy đúng
`SqlAlchemyApiRepository` sau khi Alembic migrate một PostgreSQL thật.

Phạm vi hiện được khóa bằng test:

- vòng đời khoản chi → version đã xác nhận → đợt thu → obligation → guest link;
- projection guest từ PostgreSQL đi qua HTTP và hiện tên ngân hàng từ BIN đã biết;
- payment report không tự tất toán;
- hai receipt confirmation dẫn view từ outstanding tới confirmed;
- bank destination trong batch là snapshot, không trôi theo record hiện tại;
- idempotency cho report và receipt;
- partial unique index của bank recipient;
- receipt chỉ được tham chiếu report của cùng obligation;
- mọi bảng material fact từ expense tới audit event từ chối UPDATE/DELETE.

## Chạy local

Khởi động PostgreSQL 16 đã có trong compose:

```bash
docker compose up -d postgres
```

Sau đó chạy từ `services/api`:

```bash
MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
MOBILE_REQUIRE_POSTGRES_TESTS=1 \
python -m pytest tests/postgres -q
```

Fixture tạo schema riêng có prefix `repository_it_`, chạy Alembic vào schema đó,
rồi chỉ `DROP SCHEMA ... CASCADE` đúng schema vừa tạo. Nó không drop database và
không chạm schema `public`. Dù vậy, không bao giờ trỏ biến test vào production.

Nếu không đặt `MOBILE_TEST_DATABASE_URL`, suite thông thường sẽ skip tầng này.
Trong CI, `MOBILE_REQUIRE_POSTGRES_TESTS=1` biến thiếu URL thành lỗi để check không
thể xanh nhờ skip. Workflow `.github/workflows/postgres-repository.yml` pin
`postgres:16-alpine` và chạy tầng này trên mọi PR/push main.

## Ranh giới bằng chứng

Test xanh chứng minh các đường và ràng buộc được liệt kê trên đúng PostgreSQL mà
workflow khởi động. Nó không chứng minh mọi method repository, mọi race hay mọi
plan query đều đúng. Khi thêm persistence behavior mới, phải thêm ca live tương
ứng; không mở rộng fake rồi coi đó là bằng chứng DB.
