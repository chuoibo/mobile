# rd-qa-21 · Cổng đầy đủ trên main, và đối chứng #151 bằng máy chủ thật

    đo tại   d210e1b  (nhánh qa/rd-qa-21-cong-main-va-doi-chung-151 cắt thẳng từ đó)
    sha này  ĐÃ ở main — d210e1b chính là origin/main lúc đo
    ngày     2026-08-29

**PASS.**

Main xanh cả ba tầng, kể cả tầng Postgres với 0 skip. Cổng của #151 là cổng thật —
ba đột biến đều đỏ. Hai phát hiện, **cả hai đều KHÔNG phải blocker** theo 5 loại của
charter; và hai phép đo tôi tự vứt vì chúng là finding giả.

---

## 1. Tầng nào đã THẬT SỰ chạy

| Cổng | Kết quả | Ghi chú |
|---|---|---|
| `python3 -m pytest services/api/tests tests -q` | **1148 passed, 254 skipped**, 4582 subtests | 254 skip = tầng Postgres, chạy riêng ở dưới |
| `cd apps/mobile && npm test` | **474 passed, 0 failed, 0 skipped** | gồm cả bước bundle |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **224 passed, 0 skipped** | DB riêng `qa21`, không đụng DB chung |
| `npm run test:e2e` ghim `EXPO_PUBLIC_API_URL=127.0.0.1:8821` | **2 passed, 0 skipped** | KHÔNG in "khong co server" |
| `alembic heads` | **e3b8c1d5720f (head)** — đúng MỘT dòng | không có bẫy hai head |

DB riêng là có chủ ý: `tests/postgres` dùng chung một schema, và ca live commit hàng
sẽ làm đỏ test đếm số hàng ở file khác. Tạo `qa21`, chạy, rồi `DROP DATABASE`.

E2E ghim cổng cũng là có chủ ý: mặc định nó bắn vào 8099, là container của lane khác.

---

## 2. Đối chứng #151 — cổng có đỏ được không?

#151 chuyển ba header quyền riêng tư của trang khách về middleware. Một cổng chỉ
đáng tin khi nó đỏ được, nên tôi làm hỏng đúng thứ nó phải bảo vệ:

| Đột biến | Kết quả |
|---|---|
| Xoá `referrer-policy` khỏi dict | **2 failed** |
| Middleware thành no-op (`if True: pass through`) | **2 failed** |
| `_is_guest_path` chỉ khớp `/g`, bỏ nhánh `/g/...` | **2 failed** |
| Revert cả ba | `git status` sạch, **2 passed** |

Cổng thật. Và điều #151 nói về việc hai bên không lệch nhau được là đúng: router lẫn
middleware cùng đọc một hằng `GUEST_PATH_PREFIX`, nên "lệch prefix" không phải là
thứ sửa một chỗ mà tạo ra được.

### Quét bằng máy chủ uvicorn THẬT, không phải TestClient

TestClient không đi qua origin HTTP thật. Tôi dựng uvicorn và bắn curl vào từng route:

    7/7 route khách (GET/POST · da-chuyen · khong-phai-toi · doi-so-tien · xin-cach-tinh)   3/3 header
    404 (token UUID hợp lệ nhưng không tồn tại)                                            3/3 header
    405 (DELETE, HEAD) · 422 (token sai định dạng) · /g · /g/ · route con không tồn tại     3/3 header
    200 THẬT trên phong bì có tiền                                                          3/3 header
    ĐỐI CHỨNG ÂM: /healthz và /openapi.json                                                 0/3 header

Dòng cuối là dòng làm cho các dòng trên có nghĩa. Nếu route không phải khách cũng ra
3/3 thì phép đo của tôi chỉ đang nói "curl thấy header ở mọi nơi", không nói gì về
middleware.

### Riêng tư trên trang khách 200

Khẳng định cái CÓ trước, rồi mới khẳng định cái KHÔNG có — một trang trắng làm dòng
phủ định pass rỗng tuếch:

    "100.000" (phần của chính Quyên)   xuất hiện 2 lần   ✓ có
    "Quyên"   (tên chính mình)         xuất hiện 2 lần   ✓ có
    "300.000" (tổng cả nhóm)           xuất hiện 0 lần   ✓ không lộ
    "Hà"      (tên người khác)         xuất hiện 0 lần   ✓ không lộ

---

## 3. Hai phát hiện

### PH-1 · 500 dưới `/g` không mang header nào — LOW, không phải blocker

Mô tả của #151 nói "mọi câu trả lời dưới /g phải mang no-store, no-referrer và
noindex". Có một phản ví dụ: **500**.

`add_middleware` đặt `ServerErrorMiddleware` ra NGOÀI middleware người dùng. Khi
handler ném lỗi, exception đi ngược lên tới `ServerErrorMiddleware`, và nó trả lời
bằng `send` GỐC — không đi qua wrapper gắn header.

Tái lập, dùng **chính code sản phẩm không sửa gì**, chỉ trỏ vào một DB không tồn tại:

    MOBILE_DATABASE_URL=postgresql+psycopg://...@localhost:5432/khong_ton_tai_db \
      uvicorn app.api.main:app --port 8822
    curl -D - http://127.0.0.1:8822/g/<token-uuid-hop-le-nhung-khong-ton-tai>

    HTTP/1.1 500 Internal Server Error
    (không có cache-control, không có referrer-policy, không có x-robots-tag)

**Vì sao tôi xếp LOW chứ không phải blocker quyền riêng tư:**
body của 500 là đúng chuỗi `Internal Server Error` — tôi đã grep, **không lộ chuỗi
kết nối, không lộ mật khẩu, không lộ tên DB**. Trang không có link nên không có
`Referer` đi đâu; không có subresource; 500 không nằm trong nhóm status cache theo
heuristic của RFC 9111. Nên hôm nay đây là **lỗ hổng trong một bất biến đã tuyên bố**,
không phải một vụ rò rỉ.

Nó thành vấn đề thật vào đúng ngày ai đó làm trang 500 đẹp hơn — một trang lỗi
thân thiện có link "quay lại" là chuyện rất dễ xảy ra trên bề mặt hướng tới khách,
và lúc đó URL-chính-là-thông-tin-xác-thực sẽ đi theo `Referer`.

Tiêu chí gỡ: gắn `ServerErrorMiddleware` vào trong, hoặc gắn header ở tầng ngoài cùng.

### PH-2 · Link khách bị cắt ngắn trả JSON tiếng Anh, trong khi trang tiếng Việt ĐÃ CÓ SẴN — MEDIUM UX, không phải blocker

Repo đã thiết kế đúng câu trả lời cho tình huống này rồi, nó chỉ không bắn ra ở
nhánh not-found:

| Đường đi | Khách nhìn thấy |
|---|---|
| token có thật, đã hết hạn | "Link này đã hết hạn. Khoản cần gửi vẫn còn. Nhắn cho Nam để xin link mới." |
| token có thật, đã thu hồi | "Link này đã bị thu hồi. Khoản cần gửi vẫn còn. Nhắn cho Nam để xin link mới." |
| **token không tìm thấy** | `{"code":"guest_link_not_found","detail":"Guest link does not exist"}` |

Tái lập — cắt 4 ký tự cuối, đúng thứ ứng dụng chat làm với URL dài khi chuyển tiếp:

    link đầy đủ                 -> 200  text/html
    link cắt 4 ký tự cuối       -> 404  application/json
                                   {"code":"guest_link_not_found", ...}

Đây là màn hình DUY NHẤT người ngoài nhóm nhìn thấy, và nó đang hỏi họ tiền. Chính
mô tả #151 gọi câu 404 là "câu trả lời most likely to be forwarded". Câu chữ đúng đã
tồn tại trong `app/web/preview.py`; việc còn lại là cho nhánh not-found dùng nó.

Không phải blocker: không sai tiền, không lộ dữ liệu, không vi phạm spec/cổng.

---

## 4. Hai phép đo tôi TỰ VỨT vì là finding giả

Ghi ra vì một báo cáo chỉ khoe cái tìm được thì không kiểm được.

- **"Trang 404 có 2 lỗi a11y (thiếu `<title>`, thiếu `lang`)"** — SAI. Câu trả lời là
  `application/json`; cái axe quét là **trình xem JSON của chính Chrome**, không phải
  markup của sản phẩm. Kiểm `content-type` trước khi tin một finding trên trang lỗi.
- **"Mã QR render 0×0px"** — SAI. QR là data-URI PNG 342×342 nằm sau nút mở
  "Đúng, xem cách chuyển"; bấm xong nó render **200×200 CSS px**. Phép đo đầu chụp
  DOM lúc khối còn đóng.

---

## 5. Quét a11y — có canary, nếu không thì số 0 vô nghĩa

Máy quét không tới được trang cũng trả 0 vi phạm + exit 0, trông y hệt "trang sạch".
Nên mỗi lượt chạy kèm một cặp canary:

    canary XẤU  (thiếu lang, img không alt, tương phản #eee/#fff, input không label)
        -> 4 vi phạm, exit 2      ✓ máy quét đỏ được
    canary SẠCH
        -> 0 vi phạm, exit 0      ✓ máy quét không báo bừa

    TRANG KHÁCH THẬT (200, có tiền), wcag2a + wcag2aa + wcag22aa
        -> 0 vi phạm

Bàn phím ở 390×844: 4 điểm dừng, tất cả **318×50px trở lên** — vượt ngưỡng 24×24 của
WCAG 2.5.8. Không tràn ngang ở 320 / 390 / 1440.

---

## 6. Ô CHƯA quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Không agent nào làm được. 342×342
  nguồn, hiển thị 200×200 — kích thước hợp lý, nhưng "hợp lý" không phải "quét được".
  Cần leader, một điện thoại, 15 phút.
- Trình đọc màn hình thật (VoiceOver/NVDA/TalkBack) — chưa chạy. axe phủ 30–40%.
- Chủ đề tối: chưa quét. Ma trận ADR-0010 đòi sáng × tối; tôi mới đi nhánh sáng.
- Các state `limited` / `reported` / `confirmed` / `not-me*` / `wrong-amount` /
  `evidence-asked`: chưa đi bộ bằng trình duyệt lượt này.
- F34 ngân sách (#150) và F12 tìm kiếm: không thuộc lượt này.
- Tầng live Gemini: opt-in, không bật.

## 7. Nhắc lại điều không được quên

Repo này **chưa có bằng chứng hành vi nào** (ADR-0006, Giai đoạn 0 gác theo quyết định
của chủ sản phẩm). 1846 ca xanh nói code làm đúng điều tác giả nghĩ. Nó không nói
người thật hiểu sản phẩm.
