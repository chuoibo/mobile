# qa-tt-0008 — Đối chứng PR #240 (rd-be-23): trần quét bill được gác ở tỉ lệ

- protocol_version: v1
- verdict: **PASS** (tương đương `APPROVE`)
- PR: #240 · head `c364bd729e21d502054c52c1d549b7556d64fa18`
- blocker còn mở: **không có**

## Nơi đo

```
đo tại   6154821 = merge c364bd7 (head #240) ⊕ origin/main b12ca44
nền      b12ca44 — main hiện tại, ĐÃ gồm #239
sha này  là nhánh chưa merge; base của PR (b178be5) đã tụt lại 1 commit sau main
```

Base của PR là `b178be5`, main đã đi tiếp tới `b12ca44` (#239). Nên mọi số dưới
đây đo trên **cây gộp**, không đo trên head PR — head PR không phải thứ sẽ được
merge.

Merge sạch, không xung đột: `1 file changed, 69 insertions(+)`, đúng bằng diff PR.

## Cổng đầy đủ

| cây | lệnh | kết quả |
|---|---|---|
| `b12ca44` (main, KHÔNG có PR) | `python3 -m pytest services/api/tests tests -q` | **1539 passed**, 335 skipped, 4732 subtests |
| `6154821` (main ⊕ #240) | như trên | **1540 passed**, 335 skipped, 4732 subtests |

Đúng `+1`, và không ca nào khác đổi trạng thái. Đây cũng là bằng chứng thực
nghiệm cho lời khai "ca này tiêu 0 trong 7 lượt headroom của limiter mức tiến
trình": nếu nó ăn headroom, một ca khác đã lật.

`ruff check tests/api/test_receipts_scan_rate_limit.py` → `All checks passed!`

## Tái lập chỗ hở TRƯỚC khi nhận cổng (kỹ năng `bug-reproduction`)

PR tuyên bố cặp `(limit=30, window=300)` thoả **cả hai** biên của `qa-tt-0005`
trong khi siết trần thật gấp 5 lần. Tôi không đọc lại bảng của tác giả — đo lại
từ đầu trên cây sạch của mình.

Biên của `qa-tt-0005`, đọc thẳng từ file, không suy:

```
TRAN_TOI_DA = 60 · BURST_NGUOI_THAT = 20      → limit ∈ (20, 60]
CUA_SO_TOI_THIEU = 60 · CUA_SO_TOI_DA = 300   → window ∈ [60, 300]
```

`(30, 300)` nằm hợp lệ trong cả hai. **Chỗ hở có thật.**

Đột biến `RECEIPT_SCAN_WINDOW_SECONDS` `60 → 300`, giữ nguyên hằng số 30, chạy
**toàn bộ repo** trên `b12ca44` — tức bản KHÔNG có PR:

```
1539 passed, 335 skipped, 4732 subtests passed     ← bằng đúng nền sạch
```

Không một ca nào đỏ. Bộ test cũ mù hoàn toàn với việc trần bị siết 5 lần.

Cùng đột biến đó trên cây gộp:

```
1 failed, 1539 passed, 335 skipped
FAILED test_the_human_burst_gets_through_in_every_minute_not_just_the_first
```

Đúng một ca đỏ, và là ca mới.

## Đỏ có đúng lý do không

Đỏ vì hằng số phụ hay vì tính chất? Đọc nguyên văn:

```
AssertionError: scan 11 of minute 2 was refused. A ceiling of 30 per 300s is
6 scans per minute, below the 20 one person produces re-shooting a blurry bill.
Both numbers are individually inside the band qa-tt-0005 allows; it is their
ratio that is not a ceiling any more
```

Số học khớp chính xác dự đoán: 20 lượt ở phút 1, còn 10 suất trong cửa sổ 300s,
nên lượt thứ 11 của phút 2 bị từ chối. Đỏ đúng tính chất nó tuyên bố gác, và
câu báo lỗi nói ra hậu quả sản phẩm chứ không chỉ nói số.

## Ma trận đột biến — đo lại độc lập, cộng một hàng PR không có

Mỗi lượt `grep` xác nhận đột biến đã ăn trước khi chạy; neo không khớp thì in
`DOT BIEN KHONG AN` chứ không im lặng báo xanh. Cột `qa-tt-0005` chạy bằng
`-k tran_quet_bill` trên lời gọi đầy đủ — xem cạm bẫy ở mục dưới.

| đột biến | ca mới | `qa-tt-0005` | PR khai | khớp |
|---|---|---|---|---|
| **đối chứng — giữ 30/60** | xanh | 3 xanh | xanh / xanh | ✔ |
| `30/300` — cửa sổ ×5, limit nguyên | **ĐỎ** | 3 xanh | ĐỎ / xanh | ✔ |
| `21/300` | **ĐỎ** | 3 xanh | ĐỎ / xanh | ✔ |
| `30 → 3` | **ĐỎ** | 1 ĐỎ | ĐỎ / ĐỎ | ✔ |
| `30 → 3000` | xanh | 1 ĐỎ | xanh / ĐỎ | ✔ |
| **`150/300` — TỈ LỆ GIỮ NGUYÊN (30/phút)** | **xanh** | 1 ĐỎ | *(PR không có hàng này)* | — |

Cả 5 hàng PR khai đều tái lập đúng.

**Hàng cuối là hàng tôi thêm, và nó là hàng quyết định.** Năm hàng của PR chứng
minh ca mới đỏ khi cửa sổ giãn — nhưng chúng **không** phân biệt được "gác tỉ lệ"
với "ghim hằng số 60 bằng một đường vòng". Nếu ca này chỉ ghim cửa sổ, thì
`150/300` — cùng nhịp 30 lượt/phút, chỉ đổi mẫu số và tử số cùng lúc — cũng phải
đỏ. Nó **xanh**. Vậy thứ ca này gác đúng là **nhịp**, không phải con số. Đây là
điều PR tuyên bố và nó đúng.

(`qa-tt-0005` đỏ ở hàng đó vì `150 > TRAN_TOI_DA = 60` — đúng phân công: chặn
trên là việc của nó, tỉ lệ là việc của ca mới.)

## Tính tất định

Ca mới thay đồng hồ (`FixedWindowLimiter` nhận clock lúc dựng) chứ không ngồi đợi
5 phút thật. Chạy 10 lượt liên tiếp: **10/10 `1 passed`**, chỉ khác nhau ở thời
gian chạy (0.01–0.02s). Không có nguồn bất định nào lọt vào.

Ca này không `import app.api.main.app` — nó dựng limiter riêng từ
`build_receipt_scan_limiter()` với một `uuid` mới, nên không đụng limiter dùng
chung mức tiến trình.

## Một cạm bẫy đo lường tôi đã sa vào, ghi lại

Lượt đầu tôi chạy cột `qa-tt-0005` bằng đường dẫn thư mục:

```
python3 -m pytest tests/qa/qa-tt-0005 -q      →  "1 error in 0.08s"
```

`1 error` **không phải** một phán quyết — đó là lỗi thu thập:

```
ModuleNotFoundError: No module named 'app'
```

`pythonpath` đến từ `services/api/pyproject.toml`; truyền thẳng đường dẫn file
làm mất nó. Nếu đọc lướt "1 error" thành "không đỏ" thì cả cột phải của ma trận
trên là số rác. Phải lọc bằng `-k` trên lời gọi đầy đủ. Toàn bộ ma trận ở trên đã
được đo lại sau khi phát hiện.

## `ruff format` — lời khai của PR chính xác

PR khai `ruff format` vẫn đòi sửa file này, nhưng diff nằm trong code có sẵn của
`#231`, không phải dòng nó thêm. Kiểm: chạy `ruff format --diff` trên **bản main
KHÔNG có PR** ra **đúng hai hunk đó** (`client.post("/places/search"…)` và
`scan_codes = [...]`). Lời khai đúng. Cổng ratchet `tests/qa` không áp dụng —
file này ở `services/api/tests/api/`.

## Ô CHƯA quét

- **`apps/mobile` (`npm test`)** — chưa chạy. PR không chạm file nào trong
  `apps/mobile/`; `node_modules` chưa cài trong cây đo (335 skipped có gồm
  `tests/test_phone_path.py::…` vì lý do này).
- **`tests/postgres`** — chưa chạy (nằm trong 335 skipped, thiếu
  `MOBILE_TEST_DATABASE_URL`). Trần quét bill là bộ đếm **trong bộ nhớ, mức tiến
  trình**; không có bề mặt persistence nào để ca này chạm tới.
- **Chặng `e2e` của `make gate`** — đang ĐỎ trên chính `main` từ trước PR này
  (`participant_not_in_context`), Lead đã ghi nhận và frontend đang sửa. #240 chỉ
  thêm một file test Python nên không thể ảnh hưởng chặng đó, và tôi không đo lại.
- **Trần này vẫn không phải quota.** Per-process, trong bộ nhớ: hai replica là
  hai cửa sổ, restart tha cho tất cả. Không cổng nào ở đây gác điều đó — PR đã
  nói thẳng, tôi xác nhận vẫn đúng.
- **`self._lock` và quét-theo-kích-thước** vẫn không ai gác. `#234` đã nêu; lượt
  này không chạm.

## Kết luận

`PASS`. Đây là một cổng test-only, không đổi dòng code sản phẩm nào, tái lập được
đầy đủ, đỏ đúng lý do, xanh khi tính chất được giữ, và tất định. Nó bịt một chỗ
hở có thật mà toàn bộ 1539 ca còn lại của repo mù hoàn toàn.
