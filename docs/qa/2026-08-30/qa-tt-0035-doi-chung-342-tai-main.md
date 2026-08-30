# Cổng đầy đủ trên `main`, và đối chứng #342 — qa-tt-0035

`PASS` cho cổng `main`; kèm **một phát hiện hồi quy** do chính bản vá #342 gây ra.

Cổng đầy đủ trên `main` xanh thật (3007 pass, 507 ca PostgreSQL **chạy chứ không
skip**, mobile 751/751). Guard mà #342 ship là guard **thật**: tắt riêng từng bản
vá thì nó đỏ đúng ca tương ứng, với đúng con số của phiếu gốc. Nhưng bản vá PH-1
thu cột tên món 154 → 138pt, và đo trên trang render thật thì vùng chữ còn
**120px**: **5/9** tên món tiếng Việt có thật bị cắt, so với **3/9** trước bản vá.
Hai tên **mới** bị cắt vì #342. Đây là phát hiện, **không phải blocker** — nó
không thuộc 5 loại blocker của charter — nhưng nó nằm trên đường hero và chưa cổng
nào thấy.

```
đo tại   5b8a9f7  (hitSlop / VietQR fold, #342)
sha này  ĐÃ ở main — origin/main == 5b8a9f7 lúc đo
cây      sạch (git status không có file tracked nào bị sửa)
```

## 1. Cổng đầy đủ trên `main`

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2500 passed, 547 skipped**, 4857 subtests, 208s |
| cùng lệnh + `MOBILE_TEST_DATABASE_URL` + `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **3007 passed, 40 skipped**, 4857 subtests, 307s |
| `cd apps/mobile && npm test` | **751 pass, 0 fail, 0 skipped** |
| `python3 -m alembic upgrade head` (DB riêng) | 43 bảng, head `d1e2f3a4b5c6` |

547 → 40 skipped là điểm đáng đọc: **507 ca PostgreSQL đã thật sự chạy**, không
phải "xanh vì bỏ qua". 40 ca còn lại đều là tầng live Gemini opt-in
(`MOBILE_REQUIRE_GEMINI_TESTS=1`), không có ca nào skip vì thiếu môi trường ngoài ý muốn.

DB đo trên một database riêng `mobile_qa_tt0035` chứ không phải DB chung — hai lane
chạy `tests/postgres` cùng lúc trên một schema là nguồn đỏ giả đã biết. Và alembic
chạy bằng `MOBILE_DATABASE_URL`, không phải biến `TEST` (biến `TEST` bị `env.py` bỏ
qua im lặng rồi migrate nhầm DB chung).

## 2. Đối chứng #342 — tắt riêng từng bản vá

Guard `apps/mobile/tests/vung-cham-va-ma-qr.test.mjs` mà #342 ship. Nền xanh trước
đã, rồi tắt **riêng từng** bản vá — tắt cả hai cùng lúc thì một tầng hở vẫn đọc ra
"đỏ", nên không phân biệt được cái gì gác cái gì.

| Trạng thái cây | Ca 1 (vùng chạm 44) | Ca 2 (mã QR trong fold) | exit |
|---|---|---|---|
| `main` 5b8a9f7 nguyên | ✅ `44x44` ×3 | ✅ y=346, 196/196px (100%) | 0 |
| M1: trả `W_DELETE=28` + `hitSlop` | ❌ **`28x44`** ×3 | ✅ 100% | 1 |
| M2: trả `KetQuaThanhToan.tsx` về bản trước | ✅ `44x44` | ❌ **y=728..924, 116/196px (59%)** | 1 |
| khôi phục | ✅ | ✅ | 0 |

Hai đột biến giết đúng ca của mình và **không** giết ca kia — nên guard không phải
một cổng thô đỏ vì bất cứ lý do gì. Con số đột biến khớp từng chữ số với phiếu gốc
trong #338: `28x44`, và `y=728`, `116/196pt`, `59%`. Đây là điều kiện
red-without-fix / green-with-fix, chạy trên bản dựng lại từ chính SHA đang đo.

Guard cũng đã chạy **thật**, không phải skip: ép `MOBILE_REQUIRE_WEB_A11Y=1` để
biến skip thành đỏ, và nó in ra bản dựng + đường dẫn Chrome + số đo từng nút.

## 3. Phát hiện — cột tên món bị thu 16pt và 2 tên nữa rơi ra ngoài

`KetQuaNhanDien.tsx` ghi rõ bản vá lấy 16pt của cột tên trả cho nút xoá
(154 → 138pt), và lập luận rằng 138 "vẫn hơn 110pt của bản đầu từng cắt cụt sáu
trong tám món". Lập luận so hai con số cột; nó chưa bao giờ so với **tên món thật**.

Đo trên trang render thật (`tests/qa/qa-tt-0035/soi-cat-ten-mon.mjs`), đi bộ tới
`ket-qua` bằng đúng kịch bản `MAN_SAU_TAP` mà guard dùng, ở 390x844:

| | trước #342 (`5b8a9f7^`) | sau #342 (`5b8a9f7`) |
|---|---|---|
| hộp ô tên | 158px | **142px** |
| vùng chữ (trừ padding) | 136px | **120px** |
| tên bị cắt | **3/9** | **5/9** |

Hai tên **mới** bị cắt, cả hai đều vừa ở bản trước:

| Tên món | Rộng | 136px | 120px |
|---|---|---|---|
| `Gỏi cuốn tôm thịt` | 121px | vừa | **CẮT** → `Gỏi cuốn tôm thị…` |
| `Cá lóc nướng trui` | 124px | vừa | **CẮT** → `Cá lóc nướng tr…` |

Vì sao không cổng nào thấy: ô tên là `TextInput` → `<input>` trên web, mà `<input>`
**không xuống dòng, nó cắt** — phần thừa chỉ đọc được khi đặt con trỏ vào và cuộn
trong ô. Và fixture của chính guard là `Lẩu thái` / `Nước sâm` / `Cơm rang`, ba tên
57–75px, ngắn hơn ngưỡng 120px quá xa để một cột đang cắt có thể lộ ra trong đó.

Phân loại: **không phải blocker** theo 5 loại của charter (không sai tiền, không rò
rỉ, không vi phạm cổng, không hỏng tính hợp lệ, tái lập được). Là phát hiện chất
lượng trên đường hero — người dùng sửa tên món trên chính màn này, và `Gỏi cuốn tôm
thịt` là một món có thật ở độ dài rất thường gặp. Quyết định giữ hay đổi là của
lane sở hữu `apps/mobile/`; QA không tự vá.

Giới hạn thành thật của phép đo: probe đọc bề rộng content-box thật của ô rồi đo
chuỗi bằng canvas với **chính font computed của ô đó**. Nó đo bố cục chữ — thứ
thuộc về DOM và font — chứ không gõ vào state của React, nên nó không phải phép thử
nhập bàn phím. Nó trả lời đúng câu "tên này có nằm trên màn không", không hơn.

## 4. Ô chưa quét

- **Mã QR quét được bằng app ngân hàng thật hay không** — vẫn chưa ai kiểm. OpenCV
  giải lại được payload từ ảnh chụp (#338) chứng minh mã *đúng*, không chứng minh
  app ngân hàng Việt nào chấp nhận. Chỉ leader đóng được, bằng một điện thoại thật.
- **iOS / Android**: mọi số ở trên đo trên bản export web trong Chrome. Trên native
  `hitSlop` là thật và safe area khác — cả hai phát hiện của #342 lẫn phát hiện ở
  mục 3 đều chưa có phép đo native nào.
- **Khung nhìn khác 390x844**: cột tên co giãn theo bề rộng, nên ngưỡng 120px là
  con số của đúng một máy. Màn hẹp hơn cắt nhiều hơn; chưa quét.
- **40 ca live Gemini** không chạy (opt-in, cần `MOBILE_REQUIRE_GEMINI_TESTS=1`).
- Đường hero từ `chia-se` trở đi, và trang khách ở các trạng thái
  `expired`/`revoked`/`limited`, không nằm trong lượt này.

Và câu không được bỏ: repo này **chưa có bằng chứng hành vi nào** (ADR-0006). Cổng
xanh nói code làm đúng điều tác giả nghĩ; nó không nói người thật hiểu sản phẩm.

## 5. Lệnh tái lập

```bash
git checkout 5b8a9f7
docker exec mobile-local-postgres-1 psql -U mobile -d postgres -c "CREATE DATABASE mobile_qa_tt0035;"
cd services/api && MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile_qa_tt0035' \
  python3 -m alembic upgrade head && cd -
MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile_qa_tt0035' \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest services/api/tests tests -q

cd apps/mobile && npm test && npm run build:check
MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/vung-cham-va-ma-qr.test.mjs   # nền xanh 2/2
cd - && node tests/qa/qa-tt-0035/soi-cat-ten-mon.mjs                      # exit 2, 5/9 cắt

# đối chứng cột tên trước bản vá:
git checkout 5b8a9f7^ -- apps/mobile/src/screens/KetQuaNhanDien.tsx
cd apps/mobile && npm run build:check && cd -
node tests/qa/qa-tt-0035/soi-cat-ten-mon.mjs                              # exit 2, 3/9 cắt
git checkout HEAD -- apps/mobile/src/screens/KetQuaNhanDien.tsx
```
