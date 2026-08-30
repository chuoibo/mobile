# qa-tt-0017 — Cổng chống drift của #271 vẫn nhầm LỆNH với NHẮC TỚI LỆNH, chỉ là lùi xuống một tầng

- **đo tại** `6b84f0eea620fa5a1cacde781af1c39f2144b9f9`
- **sha này** ĐÃ ở main (là chính `origin/main` lúc đo, gồm #270 và #271)
- **protocol_version** v1
- **verdict** — không phải phán quyết PR. #271 đã merge. Đây là **phiếu lỗi trên main**.
- **lane sở hữu** devops (`devops/cong-drift-workflow-khop-comment`)
- **kỹ năng đã dùng** `e2e-testing`, `bug-reproduction`

## Kết luận trước, chi tiết sau

`tests/test_postgres_tier_runner.py` sau #271 vẫn **xanh** khi
`.github/workflows/postgres-repository.yml` được sửa để CI **không chạy gì cả**.

Năm hình dạng viết lại cùng một vi phạm — CI quay về tầng hẹp `tests/postgres`,
hoặc không chạy gì — **cả năm đều lọt**, `exit 0`, `14 passed`.

## Vì sao đây là cùng một lỗi #271 tuyên bố đã sửa

#271 chẩn đoán đúng: *"A substring over a whole file cannot tell a command from a
mention of one."* Bản sửa chuyển từ đọc **toàn văn file** sang đọc **thân bước
`run:`**.

Nhưng phép so vẫn là tìm chuỗi con, chỉ đổi phạm vi:

```python
calling = [s for s in steps if "scripts/postgres_tier.sh" in s.body]
```

Một **comment shell nằm bên trong chính thân `run:`** vẫn là một phần của
`s.body`. Nên câu *"không phân biệt được một LỆNH với một lần NHẮC TỚI lệnh đó"*
vẫn đúng nguyên văn — nó chỉ lùi từ phạm vi file xuống phạm vi bước.

Nửa thứ hai bắt inline pytest thì khớp **theo từng dòng**:

```python
inline = re.compile(r"pytest\s+(?:[^\s]+\s+)*tests/postgres\b")
... for line in s.body.splitlines() if inline.search(line)
```

`splitlines()` cắt trước khi shell nối dòng, và biểu thức đòi đúng chuỗi
`tests/postgres` như một token đứng sau các token có khoảng trắng theo sau. Bốn
cách viết thường gặp đều trượt khỏi hình dạng đó.

## Bảng đột biến

Chạy: `python3 tests/qa/qa-tt-0017/mutants.py` (từ gốc repo). Nó tự khôi phục
workflow trong `finally`, và **từ chối chạy** nếu không tìm thấy nguyên văn bước
nó định thay — một đột biến no-op sẽ in GREEN và đọc y hệt một cổng đang giữ.

| Hàng | Loại | Hình dạng | Chờ | Được |
|---|---|---|---|---|
| BASE | — | cây chưa đột biến | GREEN | **GREEN** `14 passed` |
| C1 | CONTROL | inline pytest, tên runner còn trong comment (= M7 của PR) | RED | **RED** `1 failed, 13 passed` |
| K1 | KEEP | vẫn gọi runner, thêm một cờ (= M8 của PR) | GREEN | **GREEN** `14 passed` |
| K2 | KEEP | vẫn gọi runner, đổi tên bước (= M9 của PR) | GREEN | **GREEN** `14 passed` |
| E1 | EVADE | cùng inline pytest, cắt bằng `\` nối dòng shell | RED | **GREEN** ← lọt |
| E2 | EVADE | cùng tầng, `cd services/api/tests && pytest postgres` | RED | **GREEN** ← lọt |
| E3 | EVADE | cùng đường dẫn, viết `./tests/postgres` | RED | **GREEN** ← lọt |
| E4 | EVADE | cùng đường dẫn, giữ trong biến shell `$TIER` | RED | **GREEN** ← lọt |
| E5 | EVADE | **không chạy gì cả**, runner chỉ còn trong comment | RED | **GREEN** ← lọt |

`HOLES: 5 of 5 evasion shapes pass the gate`

Ba loại hàng đều cần để đọc được kết quả:

- **C1 ĐỎ** chứng minh harness đang đo thật — không có nó thì mọi hàng dưới vô nghĩa.
- **K1/K2 XANH** chứng minh cổng không phải một phép ghim byte trá hình; nó vẫn
  chịu được thay đổi giữ nguyên tính chất.
- **E1–E5 XANH** là lỗ.

Ghi chú về C1: PR ghi M7 ra `2 failed, 12 passed`, tôi đo được `1 failed,
13 passed`. Chênh lệch này **không phải nhiễu** — nó chính là phát hiện. M7 của
PR làm cả hai nửa cùng đỏ; C1 của tôi cố tình để lại tên runner trong comment,
nên nửa "có bước gọi runner" **được thoả mãn bởi comment** và chỉ còn một ca đỏ.
Đó là bằng chứng trực tiếp cho nửa thứ nhất còn mù.

## E5 — hình dạng đáng lo nhất

```yaml
      - name: Migrate an isolated schema and exercise the real repository
        run: |
          # was: scripts/postgres_tier.sh -q
          echo "tam thoi bo qua tang live"
```

CI không chạy một ca nào. Cổng in `14 passed`, `exit 0`.

Đây đúng là hình dạng "tạm thời tắt cho qua CI rồi bật lại sau" mà người ta hay
viết thật, và nó là hình dạng cổng này tồn tại để chặn.

## Tái lập tối thiểu

```bash
git checkout 6b84f0e
python3 -m pytest tests/test_postgres_tier_runner.py -q     # 14 passed  (nền)
# thay bước cuối của .github/workflows/postgres-repository.yml bằng khối E5 ở trên
python3 -m pytest tests/test_postgres_tier_runner.py -q     # 14 passed  <- lỗ
```

Tất định: chạy lại E5 ba lượt liên tiếp, `rc=0` / `14 passed` cả ba. Không có
thời gian, ngẫu nhiên hay mạng trong đường đo.

## Phân loại blocker

Loại 1 — **vi phạm spec/cổng**. Cổng tuyên bố một tính chất ("CI và cổng máy này
không thể định nghĩa 'tầng live' theo hai cách") mà nó không cưỡng chế được.

Hậu quả: 293 ca tầng live là bằng chứng duy nhất repo này có về SQL, index, view,
trigger. Một sửa đổi workflow theo bất kỳ hình dạng nào ở trên sẽ tắt chúng mà
không cổng nào kêu — đúng lại `bug-082455`, thứ #267 vừa đóng.

Tiêu chí gỡ chặn: `mutants.py` in `ALL ROWS AS EXPECTED` (C1 đỏ, K1/K2 xanh,
E1–E5 đỏ). Hàng KEEP phải còn xanh — sửa bằng cách ghim byte của bước là đổi lỗ
này lấy một lỗ khác.

## Ô CHƯA quét

- Không quét các workflow khác xem cùng khuôn tìm-chuỗi-con có ở đó không.
  `test_gate_covers_every_inline_step.py` dùng chung parser `_workflow_steps.py`
  và có thể mang cùng giả định; **chưa đo**.
- Không đề xuất bản sửa. Lane QA chứng minh, không vá.
- Năm hình dạng ở trên là năm hình dạng tôi nghĩ ra. Không hình dạng nào lọt
  **không** chứng minh không còn hình dạng nào lọt.

## Trạng thái cổng đầy đủ trên main tại `6b84f0e`

Chạy trong cây sạch (`/tmp/qa-tt-0017-main`, worktree tách riêng, `git status` sạch):

| Chặng | Lệnh | Kết quả |
|---|---|---|
| pytest, có tầng Postgres thật | `MOBILE_TEST_DATABASE_URL=…/qatt0017 MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest services/api/tests tests -q` | **1953 passed, 35 skipped**, 4736 subtests |
| pytest, KHÔNG có tầng Postgres | `python3 -m pytest services/api/tests tests -q` | 1622 passed, **366 skipped** |
| mobile | `npm test` | **670 pass, 0 fail, 0 skipped** |
| lát cắt dọc | `EXPO_PUBLIC_API_URL=http://127.0.0.1:8137 MOBILE_REQUIRE_E2E=1 npm run test:e2e` | **7 pass, 0 fail, 0 skipped** |
| migration render DDL | (lệnh ở CLAUDE.md) | rc=0 |
| repo guard | `python3 scripts/repo_guard.py tree HEAD` | `Repo guard passed tracked tree: 794 file scan(s)` |
| money golden hai bề mặt | `node packages/shared/money.test.mjs` | 10 golden + 6 refusals; 9 accepted + 10 refused |

**Main không đỏ.** Hai dòng đầu là cùng một lệnh khác đúng hai biến môi trường:
366 → 35 skip. Con số 366 là hình dạng "bỏ qua đọc thành đạt" mà báo cáo nào
không nói rõ sẽ giấu mất.

Máy chủ dùng cho lát cắt dọc là uvicorn riêng ở cổng 8137 trên DB riêng
`qatt0017`, **không** phải container dùng chung ở 8099 — container đó trả 37
route trong khi bản main tại `6b84f0e` trả **52**.

## Chưa quét, ở mức sản phẩm

- **Mã QR chưa được quét bằng app ngân hàng thật.** Vẫn nguyên. Chỉ leader đóng
  được câu này, bằng một điện thoại thật.
- Ma trận hình ảnh trang khách (trạng thái × sáng/tối × 320/390/1440): lượt này
  không quét.
- Tầng live Gemini: 35 ca còn skip vì opt-in (`MOBILE_REQUIRE_GEMINI_TESTS=1`),
  không chạy trong lượt này.
