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
uvicorn app.api.main:app --host 0.0.0.0 --port 8099   # API
```

`--host 0.0.0.0` không phải trang trí: mặc định uvicorn chỉ nghe `127.0.0.1`,
và điện thoại không tới được loopback của máy khác.

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

## Chạy trên điện thoại thật (Expo Go)

Điện thoại và máy này phải **cùng một Wi-Fi**. Kiểm trước khi mở Expo Go:

```bash
scripts/phone_path.py check     # thoát 1 nếu đường chưa thông, kèm cách sửa
scripts/phone_path.py up        # kiểm rồi phát QR trỏ vào địa chỉ LAN
```

Rồi mở **Expo Go** trên điện thoại và quét mã. `up` in sẵn hai dòng cho biết QR
trỏ đi đâu và app sẽ gọi API ở đâu — đọc hai dòng đó trước khi quét.

Ba lý do app không lên, không cái nào tự nói ra:

| Triệu chứng trên điện thoại | Nguyên nhân | Cách sửa |
|---|---|---|
| Quét xong quay mãi rồi hết giờ | WSL2 chặn kết nối từ ngoài vào (`DefaultInboundAction = Block`) | `scripts/phone_path.py open-firewall` — cần quyền Administrator, mở đúng 2 cổng TCP cho riêng subnet Wi-Fi hiện tại |
| App lên nhưng mọi màn báo lỗi mạng | `BASE_URL` còn là `localhost`, mà trên điện thoại `localhost` là chính nó | dùng `up`, nó tự đặt `EXPO_PUBLIC_API_URL` theo IP LAN |
| Terminal xanh nhưng không có server | cổng 8081 bận; `expo start` hỏi đổi cổng, trong shell không tương tác nó in `Skipping dev server` rồi **thoát mã 0** | `--metro-port 8082` |
| Metro chết ngay khi khởi động: `configs.toReversed is not a function` | `node` trên PATH quá cũ (Debian/Ubuntu cài sẵn 18.x; React Native 0.86 cần `^20.19.4 \|\| ^22.13.0 \|\| ^24.3.0 \|\| >= 25`) | không phải lỗi app. `up` tự dùng bản hợp lệ đã cài (nvm/fnm) và in ra nó đã đổi; nếu máy không có bản nào: `nvm install 20` |

Không cần tự nhớ mình đang ở Node nào — `check` đọc dải phiên bản từ chính
`apps/mobile/node_modules` và nói ra, và `up` chạy Metro dưới bản hợp lệ dù PATH
của bạn trỏ vào đâu. Việc đổi chỉ áp dụng cho tiến trình `up` sinh ra; `npm`/`npx`
bạn gõ tay vẫn là bản trên PATH.

Gỡ luật tường lửa khi không cần nữa:

```powershell
Remove-NetFirewallHyperVRule -Name 'RuDi-ExpoGo'
```

Mặc định là **API 8099**, Metro 8081 — 8099 là con số app tự fallback về khi
không có `EXPO_PUBLIC_API_URL` (`apps/mobile/src/api.ts`), nên đừng đổi nó chỉ
vì quen tay gõ 8000. Khi cổng bận thật, hoặc khi máy có nhiều card mạng:

```bash
scripts/phone_path.py --api-port 8100 --metro-port 8082 up
scripts/phone_path.py up --host <ip-LAN-của-máy-này>
eval "$(scripts/phone_path.py env)"   # chỉ lấy biến, tự chạy expo sau
```

Đổi `--api-port` thì phải bật `uvicorn` ở đúng cổng đó — script chỉ nói cho app
biết gọi đi đâu, nó không dựng server hộ bạn.

Điện thoại không cùng Wi-Fi được (mạng khách chặn máy nói chuyện với nhau) thì
`npx expo start --tunnel` vẫn nạp được app — nhưng tunnel chỉ đưa Metro ra
ngoài, **không** đưa API, nên app lên rồi vẫn không gọi được server.

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
