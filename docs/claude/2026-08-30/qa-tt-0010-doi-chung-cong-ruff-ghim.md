# qa-tt-0010 — Đối chứng #246 (cổng lint chấm bằng bản ruff đã ghim)

    protocol_version  v1
    verdict           PASS
    đo tại            77e924b904a011fdf527be338108f1dbcb0acce5  (và 9ccb973 sau rebase)
    sha này           ĐÃ ở main — #246 merge thành aedf647 trong lúc lượt đo đang chạy
    phạm vi           scripts/ruff_pinned.sh · scripts/ruff_changed.sh · scripts/gate.sh
                      tests/test_ruff_pinned.py
    blocker còn mở    không

## Lý do PASS, viết trước phần chi tiết

Tính chất mà #246 ghim là thật, và tôi tái lập được nó độc lập chứ không đọc lại
số của tác giả: trên 322 file `.py` được track, `ruff 0.9.2` (bản ghim, bản CI
cài) báo **31** finding, `ruff 0.15.15` (bản trên PATH máy này) báo **30**, và
đúng một finding chênh — `place_search.py:105:39 UP038`, một luật ruff đời sau đã
gỡ. Bảng đột biến bật đúng chiều: bỏ tính chất thì đỏ, **giữ tính chất mà đổi
hằng số thì vẫn xanh** — nên cái đỏ ở hàng trên là đỏ vì tính chất, không phải vì
một hằng số phụ. Và phần rủi ro nhất của bản sửa — nó thêm một phụ thuộc mạng vào
chặng lint — fail closed đúng: không lấy được bản ghim thì `exit 2` và `HỎNG`,
không bao giờ lặng lẽ lùi về bản 0.15.15 đang nằm sẵn trên PATH.

Hai phát hiện kèm theo đều **không** phải blocker theo 5 loại của charter, nhưng
Lead nên biết cả hai vì cả hai đổi cách đọc PR này chứ không đổi quyết định merge.

## Phát hiện 1 — câu chuyện hậu quả trong mô tả PR không tái lập được

Mô tả #246 viết: *"Ai sửa `services/api/app/domain/place_search.py` sẽ được ĐẠT
tại máy và HỎNG ở CI."* Tôi đi bộ đúng kịch bản đó và **không** ra như vậy.

    # chạm file rồi chạy cổng, bản TRƯỚC #246 (ruff 0.15.15 trên PATH)
    --- ruff check ---            All checks passed!
    EXIT=1                        <- vẫn đỏ, nhưng ở nửa `format`

    # file ở trạng thái pristine, chưa ai chạm:
    ruff 0.9.2   format --check place_search.py  ->  1 file would be reformatted
    ruff 0.15.15 format --check place_search.py  ->  1 file would be reformatted

`place_search.py` **đã** bị nửa `ruff format` từ chối, ở cả hai bản, ngay khi
chưa ai sửa gì. Nên chạm vào nó thì cổng tại máy đã đỏ từ trước #246 — chỉ là đỏ
vì lý do khác. Hệ quả: trên cây hôm nay **không tồn tại file nào** mà cổng tại
máy nói ĐẠT trong khi CI nói HỎNG. Lỗ hổng là thật và bản sửa là đúng, nhưng nó
là lỗ **ngủ**, chưa có ca sống. Điều này cũng làm nhẹ đi dòng "Cần Lead biết"
cuối PR: ai chạm file đó sẽ thấy đỏ, nhưng họ đã thấy đỏ từ trước rồi.

Vì sao vẫn PASS: bộ test của #246 **cố ý không** assert UP038 (tác giả nói rõ lý
do — sự thật đó hết hạn khi ai nâng pin). Tính chất được ghim không dựa vào câu
chuyện này, nên câu chuyện sai không kéo theo bản sửa sai.

## Phát hiện 2 — repo có HAI phán quyết ruff tại máy, #246 ghim một

`tests/test_qa_scripts_are_ruff_formatted.py` (cổng ratchet chặn file chưa định
dạng dưới `tests/qa/`) vẫn gọi `ruff` trần: `shutil.which("ruff")` ở `setUp`, và
`["ruff", "format", "--check", ...]` trong `ruff_rejects_format`. Sau #246, một
đường phán quyết dùng bản ghim, một đường dùng bản trên PATH.

Đo trên main 77e924b, 37 file `.py` dưới `tests/qa/`: cả hai bản gọi tên **cùng
16 file**, tập trùng khớp từng dòng chứ không chỉ trùng số lượng. Nên đường thứ
hai **chưa lệch hôm nay** — cũng là lỗ ngủ. Nhưng đầu ra của `ruff format` có đổi
giữa các bản, và chính #246 đã viết rằng nửa format không lệch *trên cây này*
chứ không phải được bảo đảm.

Đã cắm cọc: `tests/qa/qa-tt-0010/test_duong_phan_quyet_ruff_thu_hai.py`, một ca
`xfail(strict=True)` theo đúng tiền lệ `tests/test_gate_ruff_skip_hides_pin_check.py`.
Cọc được kiểm là cọc thật, không phải dòng TODO: khi tôi vá tạm cổng ratchet cho
nó phân giải qua `scripts/ruff_pinned.sh`, ca này chuyển thành
`XPASS(strict) -> 1 failed`, tức nó sẽ bắt người đóng lỗ phải gỡ marker. Đóng lỗ
là sửa `scripts/`, mà `scripts/` không thuộc QA.

## Biên của bảo đảm — nói cho đúng phạm vi

Cái được cưỡng chế là *"binary **khai** đúng số hiệu bản ghim mới được ra phán
quyết"*, không phải *"đúng binary đó"*. Tôi viết lại vi phạm bằng một hình dạng
**khác** với shim của #246 — shim của tôi nói dối `--version` là `ruff 0.9.2` rồi
cho mọi thứ qua:

    ruff 0.9.2 (bản ghim) tại /tmp/qa246-shim/ruff
    All checks passed!
    EXIT=0                        <- file bẩn đi lọt

Đây **không** phải lỗi: không phép kiểm version nào bắt được một binary nói dối,
và mô hình đe doạ ở đây không có kẻ cố tình cắm ruff giả. Ghi ra vì người đọc dễ
hiểu bảo đảm rộng hơn thực tế.

## Bảng đột biến — chạy lại được

`tests/qa/qa-tt-0010/doi-chung-246.sh <cây>` dựng lại toàn bộ bảng dưới.

| hàng | đột biến | mong đợi | đo được |
|---|---|---|---|
| 1 | `ruff_changed.sh` về bản trước #246 | ĐỎ | `2 failed, 5 passed` |
| 2 | **giữ** tính chất, đổi thư mục cache | XANH | `7 passed` |
| biên | shim nói dối đúng số hiệu bản ghim | lọt | `exit 0` |
| biên | cache rỗng + không tới được PyPI | `exit 2` | `exit 2`, không lùi bản |

Hàng 2 là hàng quan trọng nhất của bảng và nó đã tự chứng minh giá trị: bản đầu
của script neo mốc "trước bản sửa" vào `origin/main`, và khi #246 merge vào main
giữa lượt đo thì hàng 1 hoá ra không đột biến gì cả — nó in `XANH` trong khi
tuyên bố đã bỏ tính chất. Một bảng toàn đỏ sẽ không nhìn thấy chuyện đó. Script
giờ suy mốc từ commit **thêm** `scripts/ruff_pinned.sh` rồi lùi một bước, và từ
chối chạy nếu mốc đó đã chứa bản sửa — thà không đo còn hơn gọi sai tên kết quả.

## Đã chạy — số thật

```
# cây gộp main(dbc1e35) ⊕ #246, trước khi #246 được merge
python3 -m pytest services/api/tests tests -q
  1563 passed, 340 skipped, 4736 subtests passed in 126.86s

bash scripts/gate.sh --strict guard guard-range ruff contract client-routes cors migration shared
  ĐẠT 8   HỎNG 0   BỎ QUA 0
bash scripts/gate.sh --strict e2e      ĐẠT (10s)  — # pass 2, # skipped 0
bash scripts/gate.sh --strict mobile   ĐẠT (29s)  — tsc + npm test + expo export cả ba nền

# đối chứng độc lập, không đọc lại số của tác giả
ruff 0.9.2   check 322 file .py  ->  Found 31 errors.
ruff 0.15.15 check 322 file .py  ->  Found 30 errors.
diff  ->  chỉ place_search.py:105:39 UP038
```

Nội dung merge khớp head PR từng byte (sha256 bốn file: `ruff_pinned.sh`,
`ruff_changed.sh`, `gate.sh`, `test_ruff_pinned.py` — TRÙNG cả bốn), nên số đo
trên cây gộp áp thẳng được vào `main`.

## Ô CHƯA quét

- Chặng `postgres`, `docker`, `api` — chưa chạy riêng. `api` được phủ gián tiếp
  bởi lượt pytest ở trên; hai chặng kia thì không.
- `tests/postgres` chạy ở dạng **skipped** trong lượt pytest (không đặt
  `MOBILE_REQUIRE_POSTGRES_TESTS=1`). #246 không chạm tầng persistence, nhưng
  skip không phải xanh và tôi không báo cáo nó như xanh.
- Hành vi trên máy **chưa từng** dựng cache ruff và **có** mạng: tôi chỉ đo được
  nhánh cache-đã-có và nhánh không-tới-được-PyPI. Lần dựng thật đầu tiên (2.5s
  theo mô tả PR) tôi không tái lập.
- Không có ô trang khách / VietQR nào trong lượt này: #246 không chạm sản phẩm.
- **Mã QR vẫn chưa được quét bằng app ngân hàng thật.** Câu này còn nguyên.

## Kỹ năng đã dùng

`e2e-testing` (chặng 2 cổng rẻ, chặng 4 lát cắt dọc, chặng 6 thăm dò biên,
chặng 7 kết luận) · `bug-reproduction` (bước 5 đỏ-trước, bước 6 revert-to-verify,
bước 7 phân loại lỗ ngủ so với lỗ sống).
