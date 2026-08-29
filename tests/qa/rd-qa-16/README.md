# rd-qa-16 — đi bộ 4 tab và 4 hàng `[+]`

Cổng `apps/mobile/tests/navigation.test.mjs` (#138) chứng minh `tabs.ts` nhất quán
nội tại. Nó không trả lời câu người dùng hỏi: **bấm vào có tới màn không.** Bản đi
bộ này bấm thật 8 lần trên một bundle web đã dựng, đo bằng nội dung đã render.

## Chạy

```bash
# 1. Máy chủ API dựng từ ĐÚNG SHA đang đo — xem "Cái bẫy" bên dưới
cd services/api && MOBILE_DATABASE_URL='postgresql+psycopg://…/mobile_qaNN' \
  python3 -m alembic upgrade head
MOBILE_DATABASE_URL='…' MOBILE_CORS_ORIGINS='http://localhost:4316' \
  python3 -m uvicorn app.api.main:app --port 8117

# 2. Bundle GHIM vào máy chủ đó. `--clear` là bắt buộc: thiếu nó, expo trả
#    bundle cache và EXPO_PUBLIC_API_URL mới không được nhúng.
cd apps/mobile && EXPO_PUBLIC_API_URL=http://localhost:8117 \
  npx expo export --platform web --clear --output-dir dist-qaNN

# 3. Đi bộ. Cần `playwright` + `@axe-core/playwright` resolve được từ thư mục này.
cd tests/qa/rd-qa-16 && node walk.mjs ../../../apps/mobile/dist-qaNN
```

Kết quả là `<pass>/<tổng> PASS`, thoát mã 1 nếu có FAIL.

## Cái bẫy: `8099` là container DÙNG CHUNG, và nó cũ

Không ghim `EXPO_PUBLIC_API_URL` thì bundle bắn vào `http://localhost:8099` —
container `mobile-local-api-1` mà mọi lane dùng chung. Nó **không được dựng lại
theo main**.

Đo thật ngày 2026-08-29, cùng một bundle nguồn:

| Máy chủ | Kết quả |
|---|---|
| `8099` (container dùng chung, tạo lúc 08:05, thiếu route của #135) | **33/35** — 2 FAIL |
| `8117` dựng từ `a6e3a39` (= main lúc đo) | **35/35** — 0 FAIL |

Hai FAIL kia là lỗi console `net::ERR_FAILED` mà trình duyệt **gắn nhãn CORS**:

```
Access to fetch at 'http://localhost:8099/contexts/<id>/outings'
  … blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

Nhãn đó sai và sai theo hướng tốn thời gian nhất. Thứ thật sự xảy ra:

```
GET /contexts/<id>/outings   với X-Actor-ID là UUID thật  →  HTTP 500
```

`install_cors` gắn CORS ở lớp ngoài cùng trong số middleware *của app*, nhưng
`ServerErrorMiddleware` của Starlette còn nằm ngoài nữa. Nên một exception chưa
bắt thoát ra ngoài lớp CORS và trả 500 **không có** `Access-Control-Allow-Origin`
— trình duyệt chỉ thấy header thiếu và báo CORS. Với `curl` thì thấy ngay 500;
với trình duyệt thì đi lạc sang tìm lỗi cấu hình CORS không hề tồn tại.

Cách phân biệt, rẻ, làm trước khi mở phiếu lỗi:

```bash
curl -s -i "<api>/<đường-dẫn-đang-lỗi>" -H "Origin: http://localhost:4316" \
     -H "X-Actor-ID: <uuid thật>" | grep -i '^HTTP\|access-control-allow-origin'
```

Có `HTTP/1.1 500` thì đó là lỗi máy chủ, không phải lỗi CORS. Và kiểm luôn máy
chủ đó có phải code mình đang đo không:

```bash
curl -s <api>/openapi.json | python3 -c "import json,sys; print(len(json.load(sys.stdin)['paths']))"
```

## Ngưỡng "màn sống" đo NỘI DUNG, trừ đi thanh tab

Đếm phần tử thô là oracle sai: màn Nhóm là màn thật vẽ trong 18 node, ngưỡng
chỉnh theo Khám phá (1561 node) gọi nó là chết. Text toàn trang cũng sai theo
hướng ngược lại — thanh tab sống sót qua mọi màn, nên một route trỏ tới tab không
tồn tại vẫn "có chữ".

Hai canary giữ cho con số có nghĩa, và cả hai phải chạy mỗi lượt:

- `canary-man-trang` — xoá React root, oracle phải rớt ngưỡng. Có trong `walk.mjs`.
- đột biến route trỏ tab không có thật — `noiDung=0` trong khi phép so "đổi màn
  thật" vẫn XANH, tức phép so ngây thơ bỏ lọt ca này.

## Cái này KHÔNG chứng minh

- Không chứng minh màn nào đó **đúng** — chỉ chứng minh nó render và bấm tới được.
- `axe` chỉ quét được 30–40% lỗi tiếp cận. `0 vi phạm serious/critical` không phải
  là "đạt WCAG 2.2 AA": 2.4.11, 2.5.7 và một phần 2.5.8 không có luật tự động nào.
- Chưa quét: bàn phím, trình đọc màn hình, khung nhìn 320px, chủ đề tối.
