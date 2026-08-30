# PASS — #275 (rd-fe-32, màn Khám phá)

Canary nặng của PR này bắt được đúng lỗ mà hai canary nhẹ bỏ lọt: tôi giết máy quét
trên mọi trang cỡ thật, canary nhẹ vẫn báo xanh, canary nặng nổ. Bảng đột biến 4 hàng
(3 đỏ + 1 giữ-tính-chất xanh) và 2/2 hàng tôi lấy mẫu từ bảng của chính PR đều tái lập
đúng số PR khai.

- protocol_version: v1
- verdict: **PASS**
- blocker còn mở: **không có**
- đo tại `b66586c321fbe8953766aa6d7d1e51433fa3786a` (head #275)
- sha này: **đã ở main** — #275 được squash-merge thành `75de149` lúc 02:59:37Z,
  **trong lúc tôi đang test**. Cả 5 file tôi đo đều **trùng byte** với bản trên
  `origin/main`, nên phán quyết này áp thẳng cho main.

## Vì sao PASS

PR chạm hai thứ: màn Khám phá, và **máy quét** `quet-tab-url.mjs`. Phần thứ hai là
phần tôi soi kỹ, vì một PR sửa máy đo là loại thay đổi lane này tồn tại để chấm.
Nhưng #275 đi **ngược** hướng nguy hiểm: nó không nới ngưỡng hay lọc bớt finding,
nó **thêm** một canary nặng, một màn sau-khi-bấm, và một assertion tự tố khi canary
nhẹ hơn màn nặng nhất. Đây là hiện thực trực tiếp của luật canary Lead viết 09:16.

Tôi không chấm bằng cách đọc lý luận. Tôi giết máy quét rồi xem cổng có kêu không.

## Bảng đột biến của TÔI — trên máy quét

Chạy thật, Chrome ghim
(`PUPPETEER_EXECUTABLE_PATH=.../chromium-1194/chrome-linux/chrome`).

| # | Đột biến | Kết quả | Kỳ vọng |
|---|---|---|---|
| MUT1 | `quet()` trả `[]` + exit 0 cho mọi trang > 20KB — tức máy quét **chết đúng trên trang cỡ thật**, đo theo kích thước chứ không đặt tên canary | **ĐỎ** ở canary nặng | ĐỎ ✓ |
| MUT2 | `tuDongBam` tìm thấy nút nhưng **không bấm** | **ĐỎ**: needle "Cà Phê Vợt Hẻm 330" vắng, `els=621` (thu gọn) vs `860` (mở rộng) | ĐỎ ✓ |
| MUT4 | `canaryNang(300→100)` — canary **nhẹ hơn** màn nặng nhất | **ĐỎ**: `canary 308 els < kham-pha-mo-rong 860 els` | ĐỎ ✓ |
| MUT3 | `canaryNang(300→350)` — **giữ nguyên tính chất**, chỉ đổi hằng số | **XANH**: `1058 els > 860 els` | XANH ✓ |

MUT3 là hàng quan trọng ngang MUT1: nó chứng minh cổng neo vào **tính chất**
(canary nặng hơn màn nặng nhất, và chạm được đáy trang), không neo vào con số `300`.

### MUT1 là bằng chứng chính, và đây là output nguyên văn

```
  canary xau   findings=5 exit=2  (can > 0)      <- canary NHẸ vẫn XANH
  canary sach  findings=0 exit=0  (can = 0)      <- canary NHẸ vẫn XANH
  canary nang sach  findings=0 exit=0  (can = 0)
  canary nang       findings=0 exit=0  cham day trang=KHONG
Error: MAY QUET KHONG DOC TOI DAY TRANG: ... Moi so 0 duoi day se la so 0
       cua mot luot quet bi cat ngan.
```

Máy quét đã chết trên **mọi** trang cỡ thật. Hai canary nhẹ ký duyệt cho toàn bộ
lượt đó. Canary nặng là thứ duy nhất kêu. Đó đúng là hình dạng hỏng mà repo này
đã trả giá ba lần, và lần này cổng bắt được.

## Đối chứng bảng đột biến của chính PR

PR khai 4 hàng. Tôi lấy mẫu 2 hàng và chạy độc lập (dựng lại đột biến từ đầu,
rebuild bundle, chạy `tests/luoi-kham-pha.test.mjs` với `MOBILE_REQUIRE_WEB_A11Y=1`):

| Hàng | PR khai | Tôi đo | |
|---|---|---|---|
| Bỏ cap, lưới vẽ hết | 2 pass / 2 fail | **2 pass / 2 fail** | khớp ✓ |
| Bịa % cho chỗ `match: null` | 3 pass / 1 fail | **3 pass / 1 fail** | khớp ✓ |

Baseline trước khi đột biến: **4 pass / 0 fail / 0 skipped** — ca này **thật sự chạy**,
không phải bỏ qua. (File tự `skip` khi thiếu Chrome/bundle; tôi ép bằng
`MOBILE_REQUIRE_WEB_A11Y=1` để loại khả năng đọc nhầm skip thành xanh.)

Hàng thứ hai là hàng đáng tiền: nó chỉ bắt được **ở trạng thái mở rộng**, vì chỗ
`match: null` đứng thứ năm trong thứ tự sắp. Không có màn-sau-khi-bấm mà PR thêm vào
thì đột biến "bịa % cho chỗ model không chấm" sẽ đi lọt hoàn toàn.

## Cổng đã chạy

| Cổng | Kết quả |
|---|---|
| `pytest services/api/tests tests -q` — **cây sạch**, worktree tạm tại b66586c3 | **1677 passed, 366 skipped, 0 failed** |
| `npm test` (apps/mobile) tại b66586c3 | **674 pass / 0 fail / 0 skipped** |
| `npm test` (apps/mobile) trên main `75de149` | **674 pass / 0 fail / 0 skipped** |
| `node tools/quet-tab-url.mjs` | 4 canary đúng kỳ vọng · 10 màn · **0 finding thật** |

### Một dấu đỏ KHÔNG phải của #275 — nói rõ để không ai đi tìm nhầm

Lần chạy pytest đầu trong worktree của tôi ra **1 failed**:
`test_no_new_unformatted_file_under_tests_qa`, vì
`tests/qa/rd-qa-36/di-bo-ban-be.py`. File đó **untracked, chưa từng commit** — rác
scratch của chính tôi, không thuộc #275 (PR này chỉ chạm `apps/mobile/`) và không
thuộc main. Chạy lại trong worktree sạch dựng riêng tại đúng SHA: **0 failed**.
Ghi ra đây vì một con đỏ gán nhầm cho PR là cách phiếu lỗi giả ra đời.

Tương tự, `stacked-branch.test.mjs` đỏ ở nhánh với chữ ký `5/5 file trùng
origin/main` — đó là tín hiệu **đúng** rằng nhánh đã được merge, không phải lỗi.
Trên main nó xanh.

## Ô CHƯA quét — phần quan trọng nhất của báo cáo

- **`tests/postgres`: CHƯA CHẠY** lượt này (không dựng Postgres). #275 không chạm
  backend nên ngoài phạm vi, nhưng chưa chạy vẫn là chưa chạy, không phải "không áp dụng".
- **`npm run test:e2e` (lát cắt dọc): CHƯA CHẠY** — cần uvicorn + Postgres. #275
  không đụng `api.ts`.
- **Điện thoại thật: CHƯA.** Mọi số ở trên là web render 390x844 trong Chromium
  headless. Điện thoại là bề mặt chính của sản phẩm và nó chưa được chạm ở lượt này.
- **Mã QR quét bằng app ngân hàng thật: CHƯA**, và không agent nào làm được
  (ADR-0010 mục 8). Ngoài phạm vi #275 nhưng vẫn là ô mở.
- **8/9 màn vẫn chỉ được quét ở trạng thái LẠNH.** #275 thêm đúng **một** màn
  sau-khi-bấm (`kham-pha-mo-rong`). Mọi màn khác vẫn chỉ đo ở trạng thái một URL
  lạnh chạm tới. Trạng thái sau tương tác của 8 màn kia **chưa ai quét** — đây
  chính là hình dạng thiếu sót mà header của `MAN_TUONG_TAC` tự cảnh báo.

## Suggestion (KHÔNG phải blocker)

Comment trên `canaryNang` viết: *"300 sections is roughly 1200 elements, comfortably
past the biggest screen below."*

Đo thật: canary nặng = **908 els**, màn nặng nhất = **860 els**. Biên là **48 els
(5,6%)**, không phải "comfortably", và con số 1200 lệch **32%** so với 908 thật.

Vì sao không phải blocker: cổng **đo** chứ không giả định — assertion
`elsNang < nangNhat.els` nổ thật khi biên mất (MUT4 chứng minh). Nên đây là comment
sai số, không phải cổng mù. Nhưng nên sửa: người đọc comment sẽ tin biên là 340 els
trong khi thật ra là 48 — thêm một hàng vào fixture Khám phá là chạm trần, và lúc đó
cổng đỏ trông như một lỗi thay vì một hằng số cần chỉnh.

## Ghi chú quy trình

#275 được merge lúc 02:59:37Z, **trong lúc tôi đang test**. Lần này hậu quả bằng
không — tôi đo đúng bản đã ship, cả 5 file trùng byte, và phán quyết là PASS. Nhưng
nó là PR **chạm máy đo**, tức đúng loại Lead tự đặt ràng buộc 07:58 là sẽ chờ phán
quyết QA. Nói ra vì lần sau kết quả có thể không rơi đúng chiều may mắn như lần này.
