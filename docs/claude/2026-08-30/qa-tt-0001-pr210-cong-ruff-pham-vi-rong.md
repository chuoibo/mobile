# qa-tt-0001 — PASS #210, và một lỗ mới do #206 ⊕ #210 hợp lại

    protocol_version  v1
    verdict           PASS  (#210)
    đo tại            16a8955  (head #210)  →  đã merge squash thành 7e1ed4b trên main
    đối chứng tại     15b0e5c (trước sửa) · 23455e7 (main trước #210) · 7e1ed4b (main sau #210)
    blocker còn mở    0 cho #210 · 1 phát hiện mới trên main (loại "vi phạm spec/cổng")
    kỹ năng           e2e-testing · bug-reproduction

## Lý do, trước phần chi tiết

**#210 ĐẠT.** Lỗi nó mô tả là thật, tái lập được, và bản sửa xử đúng chỗ:
đứng trên main, chặng `ruff` đổi từ **ĐẠT/thoát 0** thành **BỎ QUA/thoát 2**, và
`--strict` biến nó thành **HỎNG/thoát 1**. Bộ test kèm theo không phải trang trí —
đột biến theo cả hai chiều đều bị bắt.

**Nhưng bản đã merge không phải bản tôi test.** `scripts/gate.sh` ở `7e1ed4b`
**khác** `scripts/gate.sh` ở `16a8955`: #206 cũng sửa `do_ruff` và thêm một phép
kiểm pin `ruff==`. Hai PR không xung đột văn bản, nhưng hợp lại thì phần bỏ qua
của #210 chạy **trước** thân chặng và **nuốt luôn** phép kiểm của #206. Xoá pin
`ruff==` là sửa một file `.txt` — không đổi file Python nào — nên chặng bỏ qua và
phép kiểm sinh ra để bắt đúng việc đó không bao giờ chạy.

## 1. Lỗi #210 mô tả: tái lập được, và vẫn sống trên main

Chạy `scripts/gate.sh ruff` trong cây sạch đứng ngay trên main:

| cây | gate.sh | kết quả |
|---|---|---|
| `15b0e5c` (main lúc PR viết) | bản cũ | `ĐẠT ruff (0s)` · `Tất cả chặng đã chạy đều ĐẠT` · thoát **0** |
| `23455e7` (main lúc tôi test) | bản cũ | `ĐẠT ruff (0s)` · thoát **0** |

Cả hai lần: `merge-base(origin/main, HEAD) == HEAD` → phạm vi rỗng → `ruff_changed.sh`
in `no Python files changed` và thoát 0 → `gate.sh` dịch thành ĐẠT.

Nửa sau của lời tố cáo cũng đúng. Lấy thẳng từ `origin/main`, `ruff format --check`:

```
Would reformat: tests/qa/rd-qa-37/doc-wire.py
Would reformat: tests/qa/rd-qa-37/tao-anh-bill.py
Would reformat: tests/qa/rd-qa-37/test_exif_duong_bill.py
3 files would be reformatted, 2 files already formatted
```

Ba file này thuộc lane QA, do chính commit `15b0e5c` của tôi đưa lên.
**Không sửa trong lượt này** — PR #211 đã mở sẵn cho đúng ba file đó cộng một cổng
độc lập phạm vi (`tests/test_qa_scripts_are_ruff_formatted.py`). Kiểm trước khi làm,
đúng như luật; làm lại là phí.

## 2. Bản sửa: đỏ trước / xanh sau, ở cả hai tầng

**Tầng test** — lấy file test mới của #210 đặt vào cây `15b0e5c` (script cũ):

```
trước sửa   4 failed, 4 passed
sau sửa     8 passed
```

**Tầng hành vi** — cùng một cây đứng trên main, chỉ thay hai script:

| | kết quả |
|---|---|
| main + script cũ | `ĐẠT ruff (0s)` · thoát **0** |
| main + script #210 | `BỎ QUA ruff -- nhánh không đổi file Python nào` · `BỎ QUA KHÔNG PHẢI ĐẠT` · thoát **2** |
| main + script #210, `--strict` | `HỎNG ruff` · thoát **1** |

## 3. Đột biến: cổng của #210 có đỏ được không

Đột biến `scripts/gate.sh` / `ruff_changed.sh`, mỗi lần chạy lại `pytest tests -q`
(nền sạch: 305 passed):

| # | đột biến | kết quả |
|---|---|---|
| A | prereq **không bao giờ** bỏ qua (= hành vi cũ) | **BỊ BẮT** — 4 failed |
| B | prereq **luôn luôn** bỏ qua | **BỊ BẮT** — 3 failed (canary) |
| C | không có merge base → bỏ qua thay vì chạy thân | **SỐNG SÓT** |
| D | `--list` lỗi → bỏ qua thay vì chạy thân | **SỐNG SÓT** |
| E | `do_ruff` dùng base khác với prereq | **SỐNG SÓT — nhưng tương đương, đã loại** |
| F | `--list` giấu file chưa track | **BỊ BẮT** — 1 failed |

A và B là phần quan trọng: cổng đỏ được **cả hai chiều**, nên nó không phải một
dòng bỏ qua vô điều kiện đọc ra giống cổng đang chạy.

**E đã bị loại chứ không nộp thành phát hiện.** `ruff_changed.sh` dạng một tham số
tự tính `git merge-base "$base" HEAD` bên trong, nên truyền đỉnh `origin/main` hay
truyền chính SHA merge-base đều cho **cùng một danh sách file** — kiểm bằng cách so
hai lần `--list`, giống hệt nhau. Đột biến tương đương sống sót **không** chứng minh
cổng mù; nộp nó thành "chỗ mù" là báo sai.

**C và D là chỗ mù thật**, và cả hai đều tới được:

```
repo git không có origin/main   → HỎNG ruff · "không tìm được merge base" · thoát 1
ruff không có trên PATH         → HỎNG ruff · "ruff is not installed"     · thoát 1
```

Bản đã ship xử **đúng** ở cả hai (chạy thân chặng, đỏ to). Nhưng đổi chúng thành
"bỏ qua" thì **305 passed vẫn nguyên** — tức là đúng cái ý định mà comment trong
`check_prereq` viết ra ("Only a confident empty answer skips") **không có test nào giữ**.
Đây là *suggestion*, không phải blocker: hành vi hiện tại đúng, chỉ là không được ghim.

## 4. Phát hiện mới: #206 ⊕ #210 mở một lỗ mà riêng từng cái không mở

`scripts/gate.sh` ở bản **đã merge** khác bản tôi test — #206 thêm vào đầu `do_ruff`
một phép kiểm: `services/api/requirements-dev.txt` phải có dòng `ruff==`, vì
`test.yml` cài đúng bản đó. Comment của chính #206 nói vì sao nó đáng thêm: xoá pin
thì "CI là thứ duy nhất nhận ra — mà trong lúc Actions không khởi động được job nào,
nghĩa là không gì nhận ra".

`check_prereq` chạy **trước** thân chặng. Nó bỏ qua → `do_ruff` không chạy → phép
kiểm pin không chạy.

Cùng một sửa đổi: **xoá dòng `ruff==`, không đụng file `.py` nào.**

| main | kết quả |
|---|---|
| `23455e7` — có #206, chưa có #210 | `không có dòng ruff== trong services/api/requirements-dev.txt` · **HỎNG** · thoát **1** |
| `7e1ed4b` — có cả hai (main hiện tại) | `BỎ QUA ruff -- nhánh không đổi file Python nào` · thoát **2** |

Lần thứ hai không chỉ im hơn — **lý do nó đưa ra là sai**: nhánh *có* đổi thứ chặng
ruff quan tâm, và cổng báo là không. Dưới `--strict` vẫn đỏ, nhưng đỏ kèm một chẩn
đoán chỉ người đọc sang nhầm file.

Phân loại: **vi phạm spec/cổng** (loại 1 trong 5 loại của charter).
Hậu quả: phép kiểm pin của #206 chết đúng trong hình dạng thay đổi mà nó sinh ra để
bắt, một ngày sau khi được thêm, trong lúc Actions không chạy.
Tiêu chí gỡ chặn: `check_prereq` không được biến một chặng "có việc để làm" thành bỏ
qua — kiểm pin trước khi quyết định bỏ qua, hoặc thu hẹp điều kiện bỏ qua. Chọn cách
nào là của lane devops.

### Ghim bằng test, không bằng lời

`tests/test_gate_ruff_skip_hides_pin_check.py` — `xfail(strict=True)` theo đúng lệ
`rd-qa-37`, kèm hai canary để bản vá không thể là "gỡ luôn phần bỏ qua của #210".
Marker được chứng minh là cổng thật chứ không phải một dòng đỏ trang trí:

```
2 passed, 1 xfailed          # main @ 7e1ed4b, chưa đụng
1 failed  (XPASS strict)     # + kiểm pin trước khi quyết định bỏ qua
2 passed, 1 xfailed          # gỡ bản vá, cây sạch lại
```

## 5. Cổng đã chạy

Trên nhánh này (main `7e1ed4b` + một file test mới), cây sạch:

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **1400 passed, 328 skipped, 1 xfailed, 4653 subtests** |
| `cd apps/mobile && npm test` | **560/560 pass, 0 fail** (chạy tại `16a8955`; PR đụng 0 file mobile) |
| `python3 scripts/repo_guard.py tree HEAD` | `Repo guard passed tracked tree: 691 file scan(s)` |
| migration render ra DDL, không cần DB | thoát **0** |

## 6. Ô CHƯA quét

- **Tầng `tests/postgres`** — không chạy trong lượt này. #210 đụng 0 dòng persistence,
  nhưng nói "đã phủ" là nói dối; nó chưa chạy.
- **`npm test` tại đúng SHA đã merge** — chạy tại `16a8955`, không phải `7e1ed4b`.
  PR đụng 0 file dưới `apps/mobile/`, nên rủi ro thấp, nhưng đây không phải phép đo
  trên bản đã ship.
- **`gate.sh --strict` đủ 11 chặng** — tôi chỉ chạy chặng `ruff`. Con số
  `ĐẠT 11 HỎNG 0 BỎ QUA 0` trong mô tả #210 là của tác giả, tôi **không** dựng lại.
- **Hệ quả `--strict` trên main** — sau #210, cây sạch đứng trên main chạy
  `--strict ruff` là **HỎNG** (`ĐẠT 0 HỎNG 1`). Đó là *thành thật* chứ không phải hỏng:
  chặng không trả lời được thì không được báo đã trả lời. Nhưng nó nghĩa là
  "chạy `--strict` trên main" không còn là phép kiểm dùng được, và thứ **thật sự** trả
  lời "main có sạch không" là cổng độc lập phạm vi của #211 —
  `tests/test_qa_scripts_are_ruff_formatted.py`. **#210 chặn lời nói dối; #211 cung cấp
  câu trả lời.** Thiếu một trong hai thì main vẫn không kiểm được.
- **Mã QR quét bằng app ngân hàng thật** — chưa, và không liên quan PR này. Vẫn ghi ra
  vì nó chưa từng được đóng.

## 7. Một ghi chú về quy trình

#210 được merge lúc `2026-08-29T19:26:26Z` với comment `APPROVE`, **trước** khi có
phán quyết của tôi. Theo luật Lead tự chốt ngày 2026-08-29, đây là **loại 2** —
0 dòng code sản phẩm, chỉ `scripts/` và `tests/` — nên Lead được merge sau khi tự đột
biến. Tôi không nêu đây là vi phạm.

Nhưng nó minh hoạ vì sao loại 2 vẫn cần người chạy lại: lỗ ở mục 4 **không** lộ ra từ
việc đột biến #210 một mình, và cũng không lộ ra từ việc đột biến #206 một mình. Nó
chỉ lộ khi so `scripts/gate.sh` **đã merge** với bản **đã test** và thấy chúng khác
nhau. Head PR lúc nhận việc không phải bản đã ship.
