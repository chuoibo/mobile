# FAIL cho PR #411 — cổng định dạng đỏ vì chính file PR thêm; phần lập luận thì đứng vững

- task: `qa-tt-0053`
- protocol_version: v1
- verdict: **REQUEST_CHANGES** (một blocker, sửa bằng đúng một lệnh)
- skill: `e2e-testing`, `bug-reproduction`

## Lý do, viết trước chi tiết

Kết luận của #411 **đúng** và tôi tái lập được độc lập: ba con 403 là **(a)** —
phép đo nhắm vào một id không phải nhóm của ai cả, máy chủ trả lời đúng. Cả bốn
khẳng định của PR đều kiểm được.

Chặn là chuyện khác: **cây gộp `#411 ⊕ main` đỏ** ở
`tests/test_qa_scripts_are_ruff_formatted.py::test_no_new_unformatted_file_under_tests_qa`,
và file duy nhất bị nêu tên là **file của chính PR**. `main` đứng một mình thì
xanh. Đây là nợ do PR tạo ra, không phải nợ có sẵn.

Và một điều **không phải blocker** nhưng cần ghi vào PR trước khi ai đó trích dẫn
probe này về sau: probe cắn được 2 trong 4 đột biến. Hai đột biến sống sót in ra
**đúng cùng một câu** "San pham khong hong o quyen".

## Đo tại đâu

```
đo tại   d59e7b35ced9e83097e60a70c05f6b6bfac77eb5   (head #411 lúc nhận việc)
sha này  là nhánh CHƯA merge, SAU main 22 commit
cây gộp  ffad3cf = #411 ⊕ main@6def9a1   (gộp sạch, 0 xung đột)
gộp lại  51e7039 = #411 ⊕ main@d416de3   (gộp sạch, cổng đỏ Y HỆT)
```

`main` **nhích hai lần giữa lượt đo**: `eda412d` → `6def9a1` (#428) → `d416de3`
(#429, #430). Tôi gộp lại ở cả hai mốc và chạy lại cổng định dạng — đỏ ở đúng một
file, cùng một file, ở cả hai mốc. Con số dưới đây vì thế không phải là ảnh của
một `main` đã hết hạn.

Stack đo: dùng-một-lần từ `scripts/e2e_slice.sh --keep`, API `127.0.0.1:45069`,
Postgres `127.0.0.1:44965`, uvicorn pid `4026003`. Kiểm **trước** khi tin số:
`readlink /proc/4026003/cwd` trỏ đúng worktree này, và `MOBILE_DATABASE_URL` của
nó trỏ đúng container trên. Máy đang có hơn 10 stack của lane khác nghe trên
loopback, nên một `curl 200` không tự nói nó trả lời từ cây nào.

## BLOCKER — cây gộp đỏ, và lỗi thuộc về PR

```
$ python3 -m pytest services/api/tests tests -q          (trên cây gộp)
1 failed, 2704 passed, 580 skipped, 4901 subtests passed in 306.52s

FAILED tests/test_qa_scripts_are_ruff_formatted.py::...::test_no_new_unformatted_file_under_tests_qa
  AssertionError: Lists differ:
    ['tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py'] != []
```

Đối chứng — cùng cổng đó, trên `main` đứng một mình:

```
$ git checkout origin/main        # 6def9a1
$ python3 -m pytest tests/test_qa_scripts_are_ruff_formatted.py -q
4 passed in 1.24s
```

Xanh trên `main`, đỏ trên cây gộp, và cổng tự in ra tên đúng một file — file của
PR. Không phải nợ có sẵn.

Xác nhận trực tiếp bằng ruff bản ghim (0.9.2, không phải bản trên PATH):

```
$ $(scripts/ruff_pinned.sh) check  tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py
All checks passed!                     <- `ruff check` XANH, nên dễ tưởng là sạch
$ $(scripts/ruff_pinned.sh) format --check tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py
Would reformat: ...                    <- thủ phạm là `format`, không phải `check`
```

**Tiêu chí gỡ chặn** — một lệnh:

```bash
$(scripts/ruff_pinned.sh) format tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py
```

Phải dùng bản **ghim**; format bằng ruff khác để lại cổng đỏ trên file mà tác giả
vừa được báo là sạch — chính cổng đó nói ra điều này trong thông điệp lỗi của nó.

## Phần lập luận của PR: kiểm được, và đúng

### 1. Kết luận (a) tái lập nguyên vẹn trên stack của tôi

```
[D] ID GHIM 1aa00000-...   GET /contexts/{id} -> 403   contexts 0 dòng · memberships 0 dòng
    NHÓM THẬT eb2d167f     GET /contexts/{id} -> 200   contexts 1 dòng · memberships 7 dòng
[A] thành viên × ID GHIM     403 · 403 · 403
[B] CÙNG actor × nhóm thật   200 · 200 · 200
[C] người lạ  × nhóm thật    403 · 403 · 403
=> (a) PHÉP ĐO CHỌN NHẦM NHÓM. Sản phẩm không hỏng ở quyền.        exit 0
```

Nhóm khác id với báo cáo gốc (seed mới), hình dạng giống hệt.

### 2. Khẳng định "client ghim nhóm" — đúng

`apps/mobile/src/screens/kham-pha/places.ts:53` export thẳng
`CONTEXT_ID = "1aa00000-aaaa-4aaa-8aaa-0000a0000001"`. Hai chỗ còn lại nhắc tới id
này đều là comment kể lại lịch sử của nó. Nên đây là **một** lỗi client, đúng như
PR nói, không phải ba tính năng hỏng.

### 3. Khẳng định "heatmap rỗng là DỮ LIỆU, không phải quyền" — đúng

Chạy chặng `--ghi` (chặng duy nhất có ghi) trên stack dùng-một-lần:

```
truoc  GET /heatmap -> 200  khu=0 scanned=0
ghi    POST /contexts/{id}/checkins p-tiem-nuong-xom-lao -> 201
ghi    POST /contexts/{id}/checkins p-lung-chung-cafe    -> 201
sau    GET /heatmap -> 200  khu=1 scanned=2  [('da-lat', 2)]
```

### 4. Các cổng còn lại trên cây gộp

```
scripts/e2e_slice.sh (lát cắt dọc)   7 pass · 0 fail · 0 skipped
cd apps/mobile && npm test           964 pass · 0 fail · 0 skipped   (18 suites)
python3 -m pytest ... tests -q        2704 pass · 1 fail · 580 skipped
```

## KHÔNG phải blocker — nhưng probe chỉ cắn được một nửa

PR viết **"Chiều C không phải thủ tục"**, và đúng. Nhưng chiều C chứng minh cổng
cắn được ở *một* trong ba điều kiện mà `is_member` hỏi. Tôi đo bằng đột biến —
harness ở `tests/qa/qa-tt-0053-dot-bien-411/dot_bien_cong_thanh_vien.py`:

| đột biến | exit | probe nói gì |
|---|---|---|
| M0 nền, không đổi gì | 0 | (a) không hỏng — **tái lập PR** |
| M1 cổng mở toang (`return True`) | 1 | **GIẾT** — "C KHÔNG đỏ, mọi kết luận từ B vô nghĩa" |
| M2 cổng đóng sập (`return False`) | 1 | **GIẾT** — "(b) lỗi quyền thật" |
| M3 chỉ ADMIN vào được | 0 | **SỐNG** — "(a) Sản phẩm không hỏng ở quyền" |
| M4 người đã RỜI nhóm vẫn vào được | 0 | **SỐNG** — "(a) Sản phẩm không hỏng ở quyền" |

Hai dòng cuối in ra **đúng cùng một câu** như dòng M0. Vì sao:

- **M3:** chiều [B] chọn actor bằng `order by c.created_at desc, m.role limit 1`,
  rơi đúng vào **admin duy nhất** của nhóm. Nhóm seed có 1 admin + 6 member. Siết
  thành admin-only khoá **6/7 người** khỏi cả ba route, và probe vẫn thoát 0.
- **M4:** người lạ ở chiều [C] là uuid **chưa bao giờ** là thành viên. Không chiều
  nào dùng một membership `state != active`. Nên "thu hồi tư cách thành viên có
  được tôn trọng không" là câu probe không hỏi — dù `is_member` có hẳn hai dòng
  code cho nó (`state == ACTIVE`, `left_at IS NULL`).

**Vì sao đây là suggestion chứ không phải blocker:** câu hỏi PR đặt ra là "403 này
là (a) hay (b)", và hai chiều trả lời câu đó (B và C) **thật sự cắn được** — M1 và
M2 chứng minh. Kết luận của PR không sai. Cái cần siết là **phạm vi được phép
trích dẫn** probe về sau: nó chứng minh cổng tôn trọng *tư cách thành viên*, không
chứng minh nó tôn trọng *thu hồi*, cũng không chứng minh member và admin ngang nhau.

Probe này **không có cổng nào chạy** — không có tiền tố `test_` nên pytest không
thu, và không script nào trong `scripts/` gọi tên nó. Nên exit code của nó do
người đọc, không phải CI. Đó là lý do câu "nó có cắn không" phải có người trả lời
bằng tay một lần, và đây là lần đó.

Đề xuất (không chặn merge): thêm một chiều `[C2] thành viên đã RỜI × nhóm thật`,
và cho chiều [B] chạy trên một actor `role='member'` thay vì để `order by` rơi vào
admin. Hai dòng SQL, và M3 + M4 sẽ bị giết.

## Ô CHƯA quét

- `tests/postgres` **chưa chạy** trong lượt này (`580 skipped` gồm cả tầng đó).
  Không cần cho phán quyết này: PR không đổi một dòng persistence nào.
- Không quét trang khách, không quét ảnh, không quét a11y — PR không chạm `app/web/`.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Vẫn nguyên trong ô chưa quét,
  không lượt QA nào đóng được câu này.
- M3/M4 là **đột biến giả định**, không phải lỗi đang tồn tại: `is_member` trên
  `main` hiện kiểm đúng cả `state` lẫn `left_at`. Tôi không báo lỗi quyền nào.
