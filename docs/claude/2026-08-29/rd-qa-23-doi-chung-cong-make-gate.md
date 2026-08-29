# rd-qa-23 · Đối chứng `make gate` (#157), và cổng đầy đủ trên main

- protocol_version: v1
- verdict: **PASS** (nghiệm thu sau merge)
- đo tại: `6c7d2ab` (main) và `cbdeed9` (= #157 ⊕ main@0542b88, do tôi tự dựng)
- sha này: `6c7d2ab` **ĐÃ ở main**. `scripts/gate.sh` trên main **byte-identical** với
  bản tôi đã đâm 9 phép đột biến — `git diff origin/main HEAD -- Makefile scripts/gate.sh
  tests/test_gate_covers_every_workflow_job.py` ra rỗng.
- blocker còn mở: **không có**

## Lý do PASS, viết trước phần chi tiết

Cổng này **đỏ được**, và đỏ đúng chỗ. Tôi không nhận lời hứa của PR: tôi tự dựng chín phép
đột biến, trong đó **bốn phép PR không hề nêu**, và cả chín đều đỏ. Quan trọng hơn cả dấu
xanh: `npm test` **thoát 0 trong lúc nó không nhìn thấy gì** (479 đạt / 0 hỏng / 2 bỏ qua),
còn cùng máy cùng code qua cổng thì **hỏng, thoát 1** (14 ca bị huỷ, có in lý do). Đó đúng
là kiểu hỏng "cổng xanh vì không dựng được gì" mà repo này đã dính nhiều lần.

Hai phát hiện kèm dưới đều là **suggestion**, không phải blocker theo 5 loại của charter.

## Cổng đầy đủ trên main `6c7d2ab` — cây sạch

`make gate STRICT=1`, có `MOBILE_TEST_DATABASE_URL` trỏ DB riêng `qa157`:

```
ĐẠT 8   HỎNG 0   BỎ QUA 0
  đạt: guard ruff api migration shared mobile docker postgres
Tất cả chặng đã chạy đều ĐẠT.                       EXIT=0   (2m23)
```

Số từng tầng, chạy riêng để dán được:

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | `1165 passed, 254 skipped, 4590 subtests passed` |
| `npm test` (qua cổng, `MOBILE_REQUIRE_WEB_A11Y=1`) | `493 tests, 493 pass, 0 fail, 0 skipped` |
| `pytest tests/postgres` (`MOBILE_REQUIRE_POSTGRES_TESTS=1`) | `224 passed`, **0 skipped** |
| `expo export --platform all` | `bundled for web, ios and android` |
| docker | `uid = 10001`, `container healthy sau 6s` |

`STRICT=1` nên **không chặng nào được bỏ qua**. Main không có sự cố.

## Ma trận đột biến — chín phép, chín lần đỏ

Bốn phép dưới đây (M1, M2, M3, M4) **PR không nộp bằng chứng**; tôi tự dựng.

| # | Đột biến | Kỳ vọng | Đo được |
|---|---|---|---|
| M1 | tên FK 69 ký tự trong migration head | `migration` HỎNG | `IdentifierError: ... exceeds maximum length of 63` · EXIT=1 |
| M2 | `USER app` → `USER root` trong Dockerfile | `docker` HỎNG | `container uid = 0` · `ảnh chạy bằng root` · EXIT=1 |
| M3 | đổi tên route `/healthz` → `/healthz-mutant` | `docker` HỎNG | app khởi động BÌNH THƯỜNG, `/healthz` trả 404 ×4, `container không bao giờ healthy` · EXIT=1 (68s) |
| M4 | `touch /venv/bin/pytest` trong ảnh chạy | check dev-tooling bắt được | phát hiện — check **không** rỗng |
| A | thêm biến thừa vào file `.py` mới | `ruff` HỎNG | (PR đã nộp; tôi kiểm gián tiếp qua chặng `ruff` đạt trên cây sạch) |
| B | không có Chrome | `mobile` HỎNG | **xem mục dưới** — cái đáng giá nhất |
| C | thiếu `MOBILE_TEST_DATABASE_URL` | BỎ QUA→EXIT=2; `--strict`→HỎNG EXIT=1 | đúng cả hai |
| D | `mv apps/mobile/package-lock.json /tmp` | HỎNG, **không** phải BỎ QUA | `có mặt nhưng thiếu package-lock.json -- từ chối bỏ qua` · HỎNG · EXIT=1 |
| E | thêm job `cong-moi-khong-ai-goi` vào `test.yml` | test chống trôi ĐỎ | `1 failed, 4 passed`; khôi phục → `5 passed, 8 subtests` |
| F | `gate.sh nonsense` / `gate.sh --bogus` | EXIT=2 | EXIT=2 cả hai |

Sau mỗi phép: khôi phục, `git status --porcelain` rỗng. Không phép nào để lại rác.

### M3 đáng nói riêng

Container **chạy tốt** — `Application startup complete`, `Uvicorn running on 0.0.0.0:8000` —
và cổng vẫn HỎNG, vì `/healthz` trả 404. Cổng phân biệt được "tiến trình còn sống" với
"endpoint trả lời". Nó thăm dò `HEALTHCHECK` của chính container chứ không `curl` vào cổng
host, nên **không thể bị một tiến trình lạ chiếm cổng làm cho xanh** — đúng cái bẫy đã cắn
lane QA trước đây (`imp detect quét nhầm trang của lane khác`).

### B — chỗ giá trị nhất của cả PR (a11y)

Cùng một máy, cùng một commit `6c7d2ab`, `CHROME_BIN` trỏ vào đường dẫn không tồn tại:

```
npm test                          -> # tests 481  # pass 479  # fail 0  # skipped 2   EXIT=0
scripts/gate.sh mobile            -> # tests 493  # pass 479  # fail 0  # cancelled 14 EXIT=1
   ...  MOBILE_REQUIRE_WEB_A11Y=1 nhưng: no Chrome found (set CHROME_BIN, or install one via playwright)
```

**481 so với 493**: mười hai ca biến mất mà `npm test` vẫn thoát 0. Hai suite render web
(`vo-tab-web`, `nhom-chat-web`) tự `SKIP` và dấu xanh trông y hệt lúc chúng chạy thật.
`MOBILE_REQUIRE_WEB_A11Y=1` biến đúng chỗ đó thành cổng. Đây là lý do đủ để nhận PR này
kể cả khi bảy chặng còn lại không tồn tại.

## Hai phát hiện — suggestion, KHÔNG phải blocker

**S1 · chặng `migration` không thêm độ phủ, chỉ thêm chẩn đoán.**
Với M1, chặng `migration` HỎNG — nhưng chặng `api` **cũng** HỎNG, ở
`services/api/tests/db/test_migration_matches_models.py::test_the_migration_actually_renders_to_ddl`.
Nên bước render DDL offline **không** "chỉ tồn tại trong YAML không chạy được" như phần đầu
`scripts/gate.sh` mô tả; nó đã có sẵn dưới dạng một ca pytest trên main. Docstring của
`tests/test_gate_covers_every_workflow_job.py` thật ra đã tự nói điều này ("by hand and by
luck"), nên đây là chuyện câu chữ ở header lệch với thực tế, không phải lỗi thiết kế. Giá
trị còn lại là thật: tách ra để "migration không biên dịch được" không bị báo thành "bộ
test hỏng". Đề nghị sửa một câu trong header cho khớp.

**S2 · check "không có dev tooling" im lặng ĐẠT nếu `/venv/bin` đổi chỗ.**

```bash
docker run --rm --entrypoint sh mobile-api:gate -c "ls /venv/bin" | grep -qE '^(pytest|ruff)$'
```

`ls` lỗi thì kêu ra stderr, stdout rỗng, `grep` không khớp, và check **đạt**. Đo thật:

```
ls /venv-doi-cho/bin -> ls: cannot access ...: No such file or directory
                     -> KHÔNG phát hiện -> im lặng ĐẠT dù không kiểm được gì
```

Hôm nay chưa lộ, vì Dockerfile có bảo vệ riêng ở tầng build (`RUN for tool in pytest ruff`)
và `/venv` đúng chỗ. Nhưng đây đúng hình dạng "cảnh báo chỉ chạy khi chưa cần tới nó". Đề
nghị khẳng định thư mục tồn tại trước khi kết luận nó sạch.

## Ô CHƯA quét — phần quan trọng nhất

- **Cổng này không chứng minh workflow YAML còn đúng.** Nó chạy *cùng các lệnh* trên một máy
  khác. Không ai kiểm được YAML well-formed hay runner image còn khớp trong lúc Actions chết.
  `test_gate_covers_every_workflow_job.py` chỉ giữ lằn ranh **yếu**: mỗi job có một chặng
  **mang tên**, không phải chạy cùng lệnh. Trôi lệnh giữa hai bên vẫn có thể xảy ra và phải
  do người soi — `COVERED_BY` là chỗ ghi lại lần soi đó.
- **Mã VietQR chưa từng được quét bằng app ngân hàng thật.** Không agent nào quét được. Cần
  leader, 15 phút, một điện thoại thật.
- Tôi **không** kiểm chặng `guard` và `shared` bằng đột biến (chúng gọi thẳng một script đã
  có cổng riêng), chỉ thấy chúng ĐẠT trong lượt đầy đủ.
- Không kiểm hành vi của cổng trên máy **không có** docker/node — chỉ suy từ nhánh `check_prereq`.

## Ghi chú quy trình

#157 được merge lúc **12:29:31Z ngay trong lúc tôi đang test nó**, và #158 vào main sau đó,
cũng chưa có phán quyết QA. Báo cáo này phủ **cả hai** một cách hồi tố: main `6c7d2ab` xanh
cả tám chặng, `--strict`, 0 bỏ qua.

Một lần suýt nộp phiếu lỗi giả: `apps/mobile/tests/stacked-branch.test.mjs` đỏ trong cây đo
của tôi. Nguyên nhân là `origin/main` **dịch chuyển giữa lượt đo** (#157 vào main), khiến ba
file của nhánh trùng khít main — test làm đúng việc của nó. Không phải lỗi. Ghi ra để lần
sau không ai mất một lượt vì nó.
