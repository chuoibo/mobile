# PASS — #206, cổng cho các bước inline của workflow

**Lý do:** cổng làm đúng điều nó hứa, và tôi chứng minh được bằng đột biến chứ không
bằng dấu xanh. Bước inline mới bị bắt ở **6/6 hình dạng** tôi viết ra, kể cả file
workflow hoàn toàn mới ở cả hai đuôi `.yml`/`.yaml`. Cái lỗ PR nói nó vá là **lỗ
thật**: trên `main` xoá pin `ruff==` thì `scripts/gate.sh ruff` thoát 0 và toàn bộ
1362 ca vẫn xanh; có PR thì thoát 1. Hai chỗ mù tôi tìm được đều nằm ở tầng phòng
thủ chiều sâu, một trong hai đã được PR tự khai trong docstring — không cái nào đủ
để chặn merge.

    protocol_version  v1
    verdict           PASS
    đo tại            e229a35 (merge origin/main 15b0e5c ⊕ #206 464ec69)
    sha này           là kết quả merge #206 ⊕ main@15b0e5c, chưa vào main
    head PR khi đo    464ec69827d2375c7f6b257ba6dd750adf7b065d
    kỹ năng           e2e-testing · bug-reproduction

Nhánh PR đứng **sau main 3 commit**. Tôi kiểm trước khi đo: `main` không đụng
`.github/workflows` hay `scripts/gate.sh` kể từ merge-base, nên bảng `INLINE_STEPS`
không thể lệch vì main. Vẫn đo trên bản merge, không đo trên head trần.

---

## 1. Cổng trên bản merge

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **1370 passed**, 328 skipped, 3 xfailed, 4653 subtest |
| `cd apps/mobile && npm test` | **560 passed / 0 fail** |
| `python3 scripts/repo_guard.py tree HEAD` | passed, 692 file |
| `python3 scripts/repo_guard.py range origin/main HEAD` | passed, 2032 file / 3 commit |
| migration render ra DDL | exit 0 |

Bảng khớp chính xác: **31 bước** chạy shell parse được từ 3 file workflow,
**31 mục** trong `INLINE_STEPS` (26 GATE / 4 SETUP / 1 INFO), `gate.sh` có 11 stage.
Không mục thừa, không bước thiếu.

## 2. Đối chứng — lỗ này có thật không?

Đây là phần quan trọng nhất. PR nói: bước `Install the pinned ruff` của `test.yml`
khẳng định có dòng `ruff==` trong `requirements-dev.txt`, và không chỗ nào ngoài
workflow đó nhìn tới pin. Actions đang chết vì billing, nên khẳng định đó chạy ở
**không đâu cả**.

Tôi xoá dòng `ruff==0.9.2` ở cả hai bên:

| Cây | `scripts/gate.sh ruff` | `pytest services/api/tests tests` |
|---|---|---|
| **main 15b0e5c** (chưa có PR) | **exit 0** — "Tất cả chặng đã chạy đều ĐẠT" | **1362 passed, 0 fail** |
| **merge e229a35** (có PR) | **exit 1** — "không có dòng ruff== …" | — |

Bản trước PR thật sự hỏng ở đúng chỗ PR nói. Đỏ-trước / xanh-sau đạt.

## 3. Đột biến — cổng có đỏ được không?

Mỗi vi phạm tôi viết lại bằng nhiều hình dạng, vì một canary viết bằng hình dạng
dễ đọc sẽ tự xanh trong khi cổng vẫn mù.

**A · Thêm một bước chạy shell mới — 6/6 bị bắt**

| Hình dạng | Kết quả |
|---|---|
| bước có `name:` | bắt (exit 1) |
| bước trần không `name:` (nhãn rơi về dòng đầu) | bắt |
| `- run: echo …` một dòng ngay trên dấu gạch | bắt |
| chỉ có `id:` | bắt |
| file `.github/workflows/*.yml` hoàn toàn mới | bắt |
| file `.yaml` mới | bắt |

**B/D/F · Ba dạng trôi khác — bắt hết**

| Đột biến | Kết quả |
|---|---|
| sửa một dòng trong thân bước, bảng giữ nguyên (`body_sha` drift) | bắt |
| mục GATE trỏ stage bịa `stage-khong-ton-tai` | bắt |
| gỡ hẳn `ruff` khỏi mảng `STAGES` của gate.sh | bắt |

## 4. Hai chỗ mù — cả hai là suggestion, không phải blocker

### 4.1 `can_fail_on_purpose` mù với ba cách "nói không" khác

Docstring của `test_nothing_that_asserts_is_filed_as_setup_or_info` viết
*"The escape hatch, closed"*. Chính xác hơn là **hẹp lại**, chưa đóng.

Tôi cho bước INFO `test.yml::docker::Image size` mọc thêm khả năng từ chối, viết
bằng 6 hình dạng, rồi chỉ chạy đúng ca kiểm đó:

| Hình dạng chèn vào thân bước INFO | Kết quả |
|---|---|
| `if [ "$size" -gt 9 ]; then exit 1; fi` | bắt |
| `test -f … \|\| exit 1` (PR đã vá hình dạng này) | bắt |
| `echo "::error::image too big"` | bắt |
| `grep -q "fastapi" services/api/pyproject.toml` | **MÙ, exit 0** |
| `test -f … \|\| false` | **MÙ, exit 0** |
| `code=1; [ "$size" -gt 9 ] && exit $code` | **MÙ, exit 0** |

`run:` block mặc định chạy dưới `bash -e`, nên cả ba hình dạng mù đều làm bước đỏ
thật — chúng là gate, đúng theo định nghĩa PR tự đặt ("written to be able to say
no"). Đáng chú ý nhất là `|| false`: nó là anh em ruột của `|| exit 1` mà PR vừa vá
hôm 2026-08-30 sau một canary. Vá một hình dạng, hình dạng còn lại vẫn mở.

**Vì sao không chặn merge:** để khai thác được, phải có người vừa viết bước kiểu
gate vừa tự tay xếp nó vào SETUP/INFO. Đây là lớp phòng thủ cuối, không phải lớp
duy nhất — `test_every_inline_step_is_accounted_for` vẫn bắt bước mới ở 6/6 hình
dạng. Đề nghị: thêm `|| false`, `&& exit $var`, và cân nhắc nêu giới hạn thật
trong docstring thay vì "closed".

### 4.2 Giới hạn PR tự khai — tôi đo kích thước của nó

Docstring nói thẳng: *"It does not prove the stage runs the same shell."* Đúng, và
đây là kích thước:

```
do_ruff() { echo "khong lam gi"; return 0; }
→ pytest services/api/tests tests  =  1370 passed, 0 fail   (y hệt cây sạch)
→ xoá pin ruff rồi chạy gate.sh ruff  =  exit 0
```

Moi ruột một stage mà giữ nguyên tên thì **không cổng nào trong repo kêu** — kể cả
cổng mới này. Đây là khai báo trung thực, không phải giấu giếm; tôi ghi ra để Lead
biết hình dạng chính xác của ô chưa phủ, vì một comment giải thích loại trừ là bằng
chứng cho *ý định*, không phải cho *phạm vi*.

## 5. Ô CHƯA quét

- Bước inline có chạy đúng **cùng một shell** với stage local hay không — không
  kiểm được khi Actions còn chết; `body_sha` chỉ ghim văn bản đã review.
- Stage bị moi ruột mà giữ tên (4.2).
- Bản thân YAML có hợp lệ không — không parser nào ở đây trả lời.
- PR chạm 0 dòng `apps/mobile`, `services/api/app`; không có bề mặt người dùng nào
  để đi bộ. Tầng `tests/postgres` không liên quan tới thay đổi này, tôi không chạy.
- Cảnh báo lệch phiên bản ruff (máy 0.15.15 vs pin 0.9.2) cố ý **không** làm đỏ.
  Lựa chọn có chủ ý, có ghi lý do; tôi đồng ý — cổng đỏ trên mọi máy là cổng bị tắt
  trong một ngày.

## 6. Một cảnh báo giả tôi loại được

`npm test` trong worktree QA của tôi ra **1 fail** — `stacked-branch.test.mjs`, "nhánh
này không mang lại file nào đã có nguyên vẹn trên origin/main", 13/13 file. Đó là
di chứng squash merge của #207, không phải main đỏ và không liên quan tới #206:
trên `main` sạch và trên bản merge, chính ca đó **pass 2/2**. Ghi lại để không ai
đọc nhầm nó thành sự cố.
