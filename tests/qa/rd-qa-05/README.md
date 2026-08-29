# rd-qa-05 — bộ diễn tập demo

Kịch bản Playwright đi hero path trên **bản web export thật** của `apps/mobile`,
ở khung hình điện thoại (Pixel 7, 390×844), với **AI thật** và **Postgres thật**.

Không nằm trong CI: nó cần một stack đang chạy, một `GEMINI_API_KEY`, và một ảnh
bill tổng hợp không được đưa vào Git. Đây là bộ chạy tay trước buổi demo.

## Dựng lại

```bash
# 1. Stack riêng, dữ liệu gieo lại từ đầu
MOBILE_PROJECT=qa-rehearsal MOBILE_API_PORT=8399 MOBILE_POSTGRES_PORT=5459 make demo

# 2. API CÓ khoá Gemini — container KHÔNG có, xem phát hiện #1 trong báo cáo
cd services/api && set -a && . /đường/dẫn/.env && set +a
MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5459/mobile' \
  python3 -m uvicorn app.api.main:app --host 127.0.0.1 --port 8499

# 3. Bản web ghim vào đúng API đó — KIỂM lại chuỗi cổng trong bundle
cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8499 \
  npx expo export --platform web --output-dir /tmp/qa-web --clear
grep -o "127.0.0.1:8499" /tmp/qa-web/_expo/static/js/web/*.js   # phải ra kết quả
cd /tmp/qa-web && python3 -m http.server 4799 --bind 127.0.0.1

# 4. Ảnh bill tổng hợp (KHÔNG dùng ảnh bill thật, KHÔNG commit ảnh)
#    Sinh bằng PIL: 8 dòng món, tổng in trên giấy 1.215.000đ.

# 5. Chạy
WEB_URL=http://127.0.0.1:4799 npx playwright test
```

## Đọc kết quả

`07-axe-detail.spec.ts` có một ca **đối chứng**: nó trồng một `<img>` thiếu alt và
một `<button>` không tên vào chính trang đang đo, rồi đòi axe phải báo nhiều lỗi
hơn trước. Ca đó đỏ nghĩa là detector đã chết và **mọi con số 0 ở các ca khác là
giả**. Chạy nó trước, tin các ca khác sau.

## Cạm bẫy đã dính, đừng dính lại

- `page.accessibility.snapshot()` không còn trong Playwright 1.62 — dùng
  `locator.ariaSnapshot()`.
- Món ăn ở màn kết quả nằm trong `TextInput`, nên `innerText` **không** thấy tên
  món. Mốc chờ đúng là chuỗi `"Đã nhận diện 8 món"`, không phải tên một món.
- `locator.fill()` trên `TextInput` của react-native-web **không** mô phỏng đúng
  việc gõ: nó cho ra một tổng sai cỡ 150 tỉ đồng, một lỗi hoàn toàn do bộ đo. Muốn đo
  "tổng có tính lại theo từng ký tự không" thì phải `keyboard.type()` từng ký tự
  như `10-edit-probe.spec.ts` làm.
- `page.goBack()` một mình không chứng minh được gì: app không đẩy lịch sử nào,
  nên `goBack()` rời khỏi app và trang trắng là lỗi của bộ đo. Đo `history.length`
  và `location.href` thay vì đọc trang trắng.
