# Main đỏ tại `ca72a53` — và cái cổng đó không thể bắt được tôi trước lúc tôi commit

- protocol_version: v1
- commit đo: `ca72a53` (chính là `origin/main` lúc đo)
- sha này: **ĐÃ ở main**
- verdict: `FAIL` cho `main` tại `ca72a53` → `PASS` sau bản vá trong nhánh này
- blocker còn mở: không
- kỹ năng đã dùng: `e2e-testing`, `bug-reproduction`

## Lý do, viết trước phần chi tiết

`main` đỏ ở một ca, trong cây sạch, và **file vi phạm là của chính tôi**: bốn
script bằng chứng QA tôi commit ở #347 ghim cứng
`/home/lakiet/.cache/ms-playwright/chromium-1194/...`. Cổng
`tests/test_qa_evidence_runs_on_another_machine.py` (thêm ở #336, merge lúc
19:00) cấm đúng hình dạng đó. Nhánh của tôi cắt từ `aca7f68` lúc 20:18 — **sau**
cổng — nên đây không phải "hai PR merge xen giữa". Tôi tự làm đỏ main.

Bản vá đổi bốn file sang `timTrinhDuyet()`, đúng cách phần còn lại của corpus
đã dùng. Cổng: 1 đỏ → 23 xanh. Cây đầy đủ: 2534 pass / 0 fail.

## Vì sao lượt chạy cổng của tôi ở #347 không bắt được

Không phải vì tôi bỏ chạy cổng. `tap_tin_qa()` liệt kê file bằng
`git ls-files -- tests/qa` — **chỉ file đã tracked hoặc đã staged**. Đó là lựa
chọn có lý do và có ghi trong docstring: `rglob` sẽ đỏ vì `node_modules/` và
những probe nháp không ai commit (tôi đo lại: quét rộng ra đúng 11 mục, trong đó
có cả một `node_modules`). Nhưng hệ quả là cổng **mù với đúng file đang được
viết**, cho tới khoảnh khắc `git add`.

Thứ tự tự nhiên của người viết bằng chứng — viết probe → chạy cổng → `git add`
→ commit — đặt lượt chạy cổng vào đúng cửa sổ mù đó.

Tôi tái lập bằng canary, cùng một file, khác nhau đúng một lệnh `git add`:

```
[1] file đã viết, CHƯA git add   → 23 passed          (mù)
[2] cùng file đó, SAU git add    → 1 failed, 22 passed (bắt được)
```

Cửa sổ mù hẹp hơn tôi tưởng lúc đầu (`git ls-files` có đọc index, nên `git add`
là đủ, không cần commit), nhưng nó nằm đúng chỗ người ta hay đứng.

**Tôi không sửa cổng này trong PR này.** Nới nó ra `--others` sẽ kéo
`node_modules` và probe nháp của lane khác vào, và một cổng đỏ vì thứ người ta
không commit là cổng người ta học cách đi vòng — đúng điều docstring của #336 đã
cảnh báo. Cách rẻ và đúng chỗ hơn là chạy cổng **sau** `git add`. Tôi nộp phát
hiện, không tự quyết hộ thiết kế của cổng.

## Một điều tôi KHÔNG kết luận

Đường ghim cứng `chromium-1194` **vẫn tồn tại trên máy này** — tôi đã kiểm
(`/home/lakiet/.cache/ms-playwright/` có cả 1187, 1194, 1234). Nên bốn script đó
chạy được ở đây; khuyết tật của chúng đúng bằng cái cổng nói, không hơn: **không
chạy được ở máy khác**. Ba build chromium cùng nằm đó chính là dấu hiệu mà
docstring của #336 đã mô tả — không ai chọn con số 1194 một cách có chủ ý.

Đáng chú ý: `timTrinhDuyet()` trên máy này trả về **1234**, không phải 1194. Chỉ
dẫn `export PUPPETEER_EXECUTABLE_PATH=.../chromium-1194/...` đang lưu hành cũng
là một con số ghim cứng cùng loại.

## Bằng chứng

Cây sạch dựng riêng tại `origin/main` (`git worktree add --detach`, `git status`
0 dòng) để chắc rằng đỏ không đến từ file nháp trong worktree của tôi:

```
$ python3 -m pytest tests/test_qa_evidence_runs_on_another_machine.py -q   # tại ca72a53, cây sạch
1 failed, 22 passed
  tests/qa/qa-tt-0036/di-bo-hai-man-giua.mjs:16: /home/lakiet/
  tests/qa/qa-tt-0036/probe-hang-nguoi.mjs:2:   /home/lakiet/
  tests/qa/qa-tt-0036/probe-input.mjs:2:        /home/lakiet/
  tests/qa/qa-tt-0036/probe-tran.mjs:2:         /home/lakiet/
```

Đối chứng hai chiều trên bản vá (`git stash` chính bốn file đó):

```
fix REVERTED  → 1 failed, 22 passed
fix RESTORED  → 23 passed
```

Bốn file vẫn **nạp được** sau khi sửa — đây là phần `quet()` không nhìn thấy,
vì thay đường dẫn bằng lời gọi helper mà quên `import` sẽ ra `ReferenceError`
mà không phép quét văn bản nào bắt được. Bằng chứng dương, không phải vắng lỗi:

```
$ node -e 'import("./tim-trinh-duyet.mjs").then(m=>console.log(m.timTrinhDuyet()))'
/home/lakiet/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome

$ node qa-tt-0036/probe-input.mjs        # không truyền argv[2]
page.goto: Cannot navigate to invalid URL — navigating to "undefined/?man=nhan-dien"
```

Lỗi đó nằm ở dòng 6, **sau** `chromium.launch()`: import đã giải, helper đã trả
path thật, trình duyệt đã mở. Đó là điều cần chứng minh.

Cổng đầy đủ sau bản vá:

```
$ python3 -m pytest services/api/tests tests -q
2534 passed, 547 skipped, 4901 subtests passed in 224.76s

$ cd apps/mobile && npm test
# tests 757 · pass 757 · fail 0 · skipped 0
```

## Ô CHƯA quét

- **Tầng PostgreSQL chưa chạy lượt này.** 547 `skipped` ở trên phần lớn là tầng
  đó (thiếu `MOBILE_TEST_DATABASE_URL`). `skipped` không phải xanh — tôi không
  tuyên bố gì về JSONB, partial unique index, view hay trigger append-only.
- **Lát cắt dọc `npm run test:e2e` chưa chạy** (cần uvicorn + Postgres). Bản vá
  này chỉ chạm bốn file bằng chứng QA, không chạm code sản phẩm, nên tôi không
  dựng môi trường đó cho lượt này — nhưng nói rõ là chưa quét.
- **Mã QR vẫn chưa được quét bằng app ngân hàng thật.** Không agent nào làm được;
  chỉ leader, bằng một điện thoại thật.
- **Bốn script đã sửa chưa được chạy đầu-cuối trên một máy khác.** Cổng chứng
  minh chúng không còn ghim tên một máy; nó không chứng minh chúng chạy ở đó.
