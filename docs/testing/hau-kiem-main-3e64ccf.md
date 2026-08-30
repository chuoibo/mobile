# Hậu kiểm `main` sau ba lần merge liên tiếp

- **SHA đo:** `3e64ccf` (không phải `56a2c19` như lúc giao việc — main đã đi thêm 4 commit)
- **Ngày:** 2026-08-30
- **Lane:** qa3
- **Kỹ năng dùng:** `e2e-testing`
- **Cây đo:** worktree sạch `/tmp/qa3-main-hk` tạo từ `3e64ccf`, `git status --porcelain` rỗng trước khi chạy

Việc được giao neo vào `56a2c19`. Khi bắt việc, `origin/main` đã ở `3e64ccf`
(thêm #302, #305, #304, #297). Đo ở `3e64ccf` là tập cha của việc được giao,
nên báo cáo này phủ cả ba PR trong đề bài lẫn hai PR vào sau.

## 1. Cổng trên cây main sạch

`scripts/gate.sh --strict` — 5 phút 13 giây:

```
ĐẠT 12   HỎNG 2   BỎ QUA 0
  đạt:   guard contract client-routes cors api migration pinned-import
         shared mobile docker postgres e2e
  hỏng:  guard-range ruff
```

**Hai chặng "hỏng" không phải lỗi của main.** Cả hai đo theo diff so với
`origin/main`, mà lượt này đang *đứng trên* `origin/main` — phạm vi rỗng:

```
guard-range: nhánh không thêm commit nào trên origin/main -- không có gì để quét
ruff:        nhánh không đổi file Python nào so với origin/main -- ruff không kiểm được gì
```

`--strict` biến BỎ QUA thành HỎNG, đúng như thiết kế. Hai chặng này chỉ nói được
điều gì khi chạy trên một nhánh có diff; chúng **chưa gác gì cho lượt hậu kiểm
này**, và không được đọc là "main sạch ruff".

### Hai chặng đề bài chỉ đích danh

`pinned-import` — chặng duy nhất nạp app bằng bản fastapi đã ghim:

```
fastapi trong ảnh = 0.115.6 (pin: 0.115.6)
--- canary xấu (phải ĐỎ, và phải đỏ ĐÚNG LÝ DO)
canary xấu đỏ đúng lý do (assert 204) — cổng còn răng
--- nạp app.api.main bằng fastapi 0.115.6
IMPORT OK, 62 đường dẫn
ĐẠT     pinned-import (6s)
```

Chặng này tự chứng minh nó chưa mù: canary xấu đỏ, và đỏ đúng lý do.

`docker`:

```
--- base image pinned by digest       (python:3.12-slim@sha256:09f7da3b...)
--- build                             ok
--- runs as a non-root user           container uid = 10001
--- no test tooling in the runtime image   (pytest/ruff không lọt vào /venv/bin)
--- the container actually serves /healthz  container healthy sau 6s
ĐẠT     docker (9s)
```

Tag ảnh là `mobile-api:gate-qa3-main-hk-...` — bản vá tên ảnh theo lane đã ở trên
main, nên lượt này không đọc nhầm cây của lane khác.

### Số ca thật

| Chặng | Kết quả |
|---|---|
| `api` | **2182 passed, 420 skipped**, 4797 subtests passed — 181.52s |
| `postgres` → `tests/postgres` | **368 passed**, 0 skipped — 39.06s |
| `postgres` → `tests/qa` | **89 passed**, 19 subtests — 10.77s |
| `mobile` | **705 tests, 705 pass, 0 fail, 0 skipped** |
| `e2e` | **7 pass, 0 fail, 0 skipped** |
| `migration` | `migration renders` |
| `check_alembic_heads.py` | một head duy nhất (`c5e14b7a9d02`) |

**Truy 420 ca `skipped` ở chặng `api`** (một lượt bỏ qua không được đọc là xanh):

- ~410 ca là tầng `tests/postgres`, bỏ qua vì thiếu `MOBILE_TEST_DATABASE_URL`.
  Chúng **có chạy** ở chặng `postgres` (368 + 89 = 457 ca, 0 skipped). Đã phủ.
- 10 ca là `services/api/tests/live/test_gemini_receipt.py`, bỏ qua vì
  `MOBILE_LIVE_GEMINI` không đặt. **Không chặng nào phủ** — xem mục 4.

Chặng `e2e` lúc đầu **BỎ QUA** ("chưa `npm ci` trong apps/mobile"). Bỏ qua không
phải đạt, nên đã cài `node_modules` (`cp -al` từ một cây có `package-lock.json`
giống hệt — hardlink chứ không symlink, vì `expo export` chết với symlink) rồi
chạy lại cho tới khi nó thật sự chạy.

## 2. Máy demo 8099

```
GET http://127.0.0.1:8099/healthz -> {"status":"ok"}
Route máy chủ: 62 phục vụ / 62 cây này khai — đủ, không thiếu route nào.
DB revision: c5e14b7a9d02 (khớp head của mã nguồn).
```

`make smoke` exit 0. `scripts/check_server_routes.py --url http://127.0.0.1:8099`
exit 0. Route: **62 phục vụ / 62 khai**, 72 operation.

**Đếm route khớp chưa đủ, và suýt nữa đọc nhầm ở đây.** Ảnh demo được tạo lúc
`14:49:48`, còn commit HEAD của main là `15:04:47` — ảnh *cũ hơn HEAD 15 phút*.
Nếu chỉ nhìn con số 62 = 62 thì kết luận "máy demo bằng main" là suy đoán:
một PR vừa thêm vừa bớt một route sẽ giữ nguyên tổng, và #297 sửa *hành vi* của
`GET /places` chứ không thêm đường dẫn nào — đúng loại thay đổi mà phép đếm mù.

Phép kiểm dứt điểm là so mã nguồn, không so số đếm:

```
main tree app/ digest = bc6e1061c7c6f59b6d75cb75786d2036bbb65c0c9a2d02976a75e4bd0994b39c
container app/ digest = bc6e1061c7c6f59b6d75cb75786d2036bbb65c0c9a2d02976a75e4bd0994b39c
```

Byte-identical. **Máy demo đang chạy đúng mã của `3e64ccf`**, không tụt lại sau
main. (Mốc thời gian ảnh cũ hơn là do ảnh dựng từ head nhánh PR trước khi squash;
nội dung trùng.) Lần trước máy demo tụt 37/42 route — lần này không tái diễn.

## 3. Đường hero chia bill

Đi hết trong **một lượt chạy**, qua đúng các module client mà app import
(`dist-test/api.js`, `dist-test/receipt.js`, `dist-test/screens/chat/nhom.js`),
không hand-roll request, bắn vào máy demo 8099:

```
1. QUÉT BILL   ảnh tổng hợp -> POST /receipts/scan (Gemini thật)
               AI đọc 4 món, tổng 270000                        HTTP 200, 5.9s
2. MỐI NỐI     readingFromWire(): 4 dòng, Σ dòng = 270000, mọi giá trị nguyên
3. MỞ NHÓM     contextId=3423b032..., 9 người active, lấy 3
4. GÁN MÓN     bill=493045df... items_total=270000
               ai_suggested -> (người chốt) -> confirmed
5. KHOẢN CHI   Σ phân bổ = 270000 = tổng 270000 (3 người, đều nguyên)
               version=a3dc75fd... acknowledged=true
6. ĐỢT THU     tài khoản nhận BIDV (nhận diện=true)
               batch=b51fb783..., 2 nghĩa vụ, người ứng tiền KHÔNG tự nợ
               publish xong, 2 envelope
7. TRANG KHÁCH HTTP 200, có "Phần của"
               phần của khách 90.000₫ CÓ trên trang
               tổng nhóm    270.000₫ KHÔNG lộ
```

**Đường hero không đứt ở đâu.** Ba luật tiền giữ nguyên trên đường đi: số nguyên
đồng ở mọi dòng và mọi phần chia, `Σ` phân bổ `=` đúng tổng, và phần chia là câu
trả lời của server chứ không phải phép tính lại trong walk.

Phép kiểm rò rỉ khẳng định cái **có** trước rồi mới khẳng định cái **không có** —
`90.000` phải tìm thấy trước, nếu không thì `!includes("270.000")` sẽ pass rỗng
trên một trang trắng hoặc một trang in tiền ở định dạng khác.

Walk này **đã đỏ ba lần** trước khi xanh (sai slug, sai số thành viên, sai chữ ký
`luuGanMon`), nên các assert của nó có cắn, không phải trang trí.

Ngoài ra, tầng live AI chạy được khi bật lên: `MOBILE_LIVE_GEMINI=1 pytest
tests/live/test_gemini_receipt.py` → **10 passed in 9.64s**.

## 4. Ô CHƯA QUÉT — phần quan trọng nhất

1. **Mã QR chưa từng được quét bằng app ngân hàng thật.** `test_vietqr.py` kiểm
   chuỗi EMVCo và CRC; một chuỗi đúng CRC vẫn có thể là chuỗi không app ngân hàng
   Việt nào chấp nhận. Không agent nào quét được mã QR. Cần leader, một điện
   thoại thật, 15 phút. **Ô này vẫn mở.**

2. **Mối nối `POST /receipts/scan` → `readingFromWire()` → `POST /bills` không có
   cổng nào đi qua.** `duong-bill.test.mjs` bắt đầu từ `toBill()` — một reading
   tổng hợp viết tay, không phải từ ảnh; `tests/live/test_gemini_receipt.py` đọc
   ảnh thật nhưng dừng ngay sau khi đọc. Hai nửa đều xanh, chưa cổng nào nối
   chúng lại. Lượt này tôi đi qua nó **bằng tay một lần** và nó đạt — nhưng một
   lần chạy tay không phải một cổng. Đây đúng hình dạng đã làm hỏng sản phẩm hai
   lần (#235, #247): backend xanh, client xanh, hợp lại thì 422.

3. **Tầng live Gemini không có ai gọi.** `grep -rn MOBILE_LIVE_GEMINI` trên toàn
   repo chỉ ra chính file test. Không `scripts/`, không `.github/`. 10 ca đó chỉ
   chạy khi có người nhớ ra.

4. **`ruff` và `guard-range` chưa gác gì trong lượt này** — phạm vi diff rỗng khi
   đứng trên main. Không được đọc báo cáo này thành "main sạch ruff".

5. **Ma trận hình ảnh trang khách chưa quét lượt này**: trạng thái (`one`/`two`/
   `expired`/`revoked`/`limited`/`reported`/`confirmed`/`not-me`/`not-me-done`/
   `wrong-amount`/`evidence-asked`) × sáng/tối × 320/390/1440. Lượt này chỉ chứng
   minh trang render, có phần của khách, và không lộ tổng nhóm — **không** chứng
   minh nó đọc được, bấm được, hay tương phản đạt.

6. **Chưa có bằng chứng hành vi nào** (ADR-0006, Giai đoạn 0 bị gác theo quyết
   định của chủ sản phẩm). Bộ test xanh nói code làm đúng điều tác giả nghĩ; nó
   không nói người thật hiểu sản phẩm.

## 5. Rủi ro còn mở

Không phát hiện nào rơi vào 5 loại blocker của charter. Main ở `3e64ccf` **khoẻ**
trên cả 12 chặng chạy được.

Hai việc nên giao, đều là *thiếu cổng* chứ không phải *lỗi đang chảy máu*:

- Nối mối `scan → bill` thành một ca e2e thật (ô chưa quét #2).
- Cho tầng live Gemini một người gọi, dù chỉ là chặng opt-in trong `gate.sh`
  (ô chưa quét #3).

## 6. Điều phải nói ra: lượt đo này có ghi vào DB dùng chung

Đường hero ở mục 3 chạy trên máy demo 8099, tức là nó **đã ghi dữ liệu thật vào
DB dùng chung**: một bill (`493045df...`), một khoản chi
(`a3dc75fd...`), một đợt thu (`b51fb783...`) và 2 envelope đã publish, trong
context `3423b032...`. Lane nào có ca đếm hàng trên DB 8099 thì con số đã đổi.
Không xoá vì xoá bằng tay trên DB dùng chung nguy hiểm hơn là để lại và nói ra.

## 7. Lệnh chạy lại được

```bash
git worktree add /tmp/hk 3e64ccf && cd /tmp/hk
cp -al <cây-có-lockfile-giống>/apps/mobile/node_modules apps/mobile/node_modules
scripts/gate.sh --strict                       # 12 đạt / 2 không chạy được vì đứng trên main
scripts/gate.sh pinned-import docker           # hai chặng đề bài chỉ đích danh

cd /home/lakiet/mobile && make smoke            # 62/62 route, DB revision khớp
python3 scripts/check_server_routes.py --url http://127.0.0.1:8099

# phép kiểm dứt điểm "máy demo có đúng là main không"
docker exec mobile-local-api-1 sh -c "cd /srv && find app -name '*.py' | sort | xargs sha256sum | sha256sum"
( cd /tmp/hk/services/api && find app -name '*.py' | sort | xargs sha256sum | sha256sum )

# tầng live AI (không cổng nào gọi)
export GEMINI_API_KEY="$(cd /home/lakiet/mobile && sh scripts/env_value.sh GEMINI_API_KEY </dev/null)"
cd /tmp/hk/services/api && MOBILE_LIVE_GEMINI=1 python3 -m pytest tests/live/test_gemini_receipt.py -q
```
