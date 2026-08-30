# PASS — #295 (chặng docker đặt tên ảnh theo lane)

**Lý do (đọc dòng này trước phần chi tiết):** lỗi cũ tái lập được ở **hai tầng
độc lập** — một tầng tất định (bảng tên, 5 ca đỏ trên bản trước) và một tầng
docker thật (hai lane chạy đồng thời trên bản cũ: một lane HỎNG kèm đúng hai
dòng `No such container: mobile-api-gate` của phiếu #291). Trên bản #295 cùng
kịch bản đó cho hai lane cùng ĐẠT, không sót ảnh, không sót container. Cổng mới
có răng và **phân biệt được từng tính chất**: 6 đột biến phá, mỗi cái đỏ đúng ca
của nó; 2 đột biến giữ tính chất, cả hai xanh. Cổng đầy đủ trên main sau merge:
**12 ĐẠT / 0 HỎNG / 2 BỎ QUA** (hai chặng bỏ qua là do đứng trên main nên phạm
vi diff rỗng, không phải do thiếu môi trường). Hai phát hiện nhỏ ở cuối, cả hai
là **suggestion**, không phải blocker.

protocol_version: v1 · verdict: **PASS** · blocker còn mở: **không có**

## Đo tại cái gì, và cái đó có ở main không

```
đo tại   19a32da  = PR head 5419a222 ⊕ main@7ea12ba   (cây gộp, do tôi tạo)
         ca5e7e8  = main sau khi Lead squash-merge #295
sha này  #295 ĐÃ ở main lúc 2026-08-30T06:11:55Z — TRONG lúc tôi đang đo
```

Lead merge giữa lượt đo, nên đây là **hậu kiểm** chứ không phải phán quyết
trước merge. Trước khi tin lại số cũ, tôi kiểm nội dung squash có đúng bằng cây
tôi đã đo không — bốn file, băm SHA-256:

```
GIỐNG  scripts/gate.sh                                a7725e3802b309a9
GIỐNG  scripts/gate_docker_names.sh                   49e7e086ad991d3f
GIỐNG  scripts/check_pinned_import.sh                 68f006a58967dc85
GIỐNG  tests/test_gate_docker_names_are_per_lane.py   e9f740d951dd2466
```

Bằng nhau từng byte, nên mọi phép đo dưới đây áp cho `main@ca5e7e8`.

Một hệ quả của việc merge giữa chừng, ghi ra để không ai đọc nhầm: trong cây gộp
của tôi, chặng `mobile` **HỎNG một ca** —
`nhánh này không mang lại file nào đã có nguyên vẹn trên origin/main`, liệt kê
đúng bốn file trên. Đó là cổng stacked-branch báo **đúng**: sau khi #295 vào
main, nhánh của tôi không còn gì mới. Không phải lỗi của PR. Chạy lại trên
`main@ca5e7e8` sạch thì chặng `mobile` ĐẠT.

## 1. Tái lập lỗi cũ — tầng tất định (bug-reproduction, đỏ TRƯỚC)

Chép nguyên file test của #295 vào một cây đứng ở `main@7ea12ba` (scripts **cũ**)
và chạy. Không sửa gì khác.

```
$ cd <worktree @ 7ea12ba> && python3 -m pytest tests/test_gate_docker_names_are_per_lane.py -q
5 failed, 3 passed in 1.64s
  FAILED test_two_checkouts_do_not_share_an_image_tag
         AssertionError: 'mobile-api:gate' — hai cây dùng chung tag ảnh
  FAILED test_two_checkouts_do_not_share_a_container_name
  FAILED test_two_runs_of_one_checkout_do_not_share_names
  FAILED test_pinned_import_stage_is_per_lane_too
  FAILED test_the_run_untags_the_image_it_created
```

Trên cây gộp (19a32da) cùng lệnh đó:

```
8 passed in 1.80s
```

Đỏ trước, xanh sau, cùng một file test, không sửa test. Ba ca xanh cả hai bên là
đúng thiết kế: `test_docker_stage_names_an_image_and_a_container` là tiền đề,
`test_one_run_reuses_one_tag_across_its_own_stages` và
`test_no_globally_named_leftover` là lưới cho bản vá nửa vời — bản cũ không vi
phạm hai tính chất đó.

## 2. Tái lập lỗi cũ — tầng docker THẬT (đối chứng âm)

Tầng trên chứng minh *hai cây gọi tên gì*. Nó **không** chứng minh cái tên đó
gây ra hỏng thật. Nên tôi chạy chính chặng docker, hai cây, cùng lúc, một lần cho
mỗi bản.

Bản **cũ** (`main@7ea12ba`, hai cây `qa24-base` và `qa24-base2`):

```
A(cũ) rc=1     HỎNG docker (5s)
               container unhealthy
               Error response from daemon: No such container: mobile-api-gate
               Error response from daemon: No such container: mobile-api-gate
B(cũ) rc=0     ĐẠT docker (12s)
```

Hai dòng `No such container: mobile-api-gate` là **đúng triệu chứng** phiếu
#291 mô tả: `docker rm -f` của lane kia xoá container lane này đang đo.

Bản **#295** (hai cây `qa24-merge` và `qa24-mut`, chạy đồng thời y hệt):

```
A rc=0   container healthy sau 6s   ĐẠT docker (9s)
B rc=0   container healthy sau 6s   ĐẠT docker (10s)
ảnh mobile-api còn sót sau khi cả hai xong: (không có ảnh gate-* nào)
```

Tên thật một lượt sinh ra, đọc được lane nào đang dựng — dạng
`mobile-api:gate-<leaf>-<hash>-<pid>`, ví dụ `mobile-api:gate-qa24-merge-…`
(repo guard chặn dán nguyên chuỗi số ở đây, nên tôi rút gọn hai nhóm số).

Trước khi chạy bản cũ tôi kiểm `docker ps -a` không có `mobile-api-gate` nào để
không làm đỏ lượt gate của lane khác; cửa sổ khoảng 12 giây và tôi dọn ngay sau
đó. Đây là lần duy nhất tôi chạy tên toàn cục.

## 3. Cổng mới có răng tới đâu — bảng đột biến

Mỗi hàng: đột biến bản #295, chạy lại chính file test của nó, ghi ca nào đỏ.
Hai hàng cuối **giữ nguyên tính chất** và bắt buộc phải XANH — một bảng toàn đỏ
không phân biệt được "cổng gác đúng tính chất" với "cổng đỏ vì bất cứ gì".

| # | Đột biến | Kết quả | Ca đỏ |
|---|---|---|---|
| M0 | (đối chứng, không đột biến) | **8 passed** | — |
| M1 | run id thành hằng số `gate` (quay về tên toàn cục) | 4 failed | two_checkouts_image · two_checkouts_container · two_runs · pinned_import |
| M2 | bỏ `$$` — khoá **chỉ theo đường dẫn** | 1 failed | **two_runs_of_one_checkout** (hai cây vẫn xanh — đúng) |
| M3 | vá nửa vời: build có tham số, sót một `docker run mobile-api:gate` | 1 failed | **no_globally_named_leftover** |
| M4 | `pinned-import` dùng tag riêng (vẫn theo lane) | 1 failed | **one_run_reuses_one_tag** |
| M5 | bỏ `docker image rm` trong dọn dẹp | 1 failed | **the_run_untags_the_image** |
| M6 | chặng không đặt `--name` cho container nữa | **8 passed** ← lọt | — (xem phát hiện 1) |
| M9 | ảnh theo lane, container quay lại tên toàn cục | 2 failed | two_checkouts_container · two_runs |
| M7 | **GIỮ**: đổi tiền tố tag `gate-` → `cong-` | **8 passed** | — |
| M8 | **GIỮ**: đổi thứ tự id thành `<pid>-<leaf>-<hash>` | **8 passed** | — |

M2 là hàng đáng giá nhất: nó phá **một** tính chất (hai lượt cùng cây) và để
nguyên tính chất kia (hai cây khác nhau), và cổng đỏ đúng một ca. M7/M8 xanh
chứng minh cổng không đỏ vì hằng số hay hình dạng chuỗi.

## 4. Chạy thật, không qua stub

```
$ bash scripts/gate.sh docker                    ĐẠT (9s)   container healthy sau 6s, uid 10001
$ bash scripts/gate.sh docker      (lượt 2)      ĐẠT (8.9s) mọi layer CACHED
$ bash scripts/gate.sh pinned-import docker      ĐẠT 2  HỎNG 0
$ bash scripts/gate.sh pinned-import  (riêng)    ĐẠT (5s)
    fastapi trong ảnh = 0.115.6 (pin: 0.115.6)
    canary xấu đỏ đúng lý do (assert 204) — cổng còn răng
    IMPORT OK, 62 đường dẫn
```

Lượt 2 kiểm một lời hứa nằm trong comment mà chưa ai đo: *"gỡ tag vẫn còn
cache"*. Đúng — mọi layer `CACHED`, 8.9 giây. Nếu sai thì mỗi lượt gate sẽ dựng
lại ảnh từ đầu, trên một máy Lead chạy cổng này hàng chục lần một ngày.

Sau **mỗi** lượt: `docker images | grep gate-` rỗng. Tag per-run không tích tụ.

**Ngắt giữa chừng** (`timeout -s INT` trong lúc chặng đang chờ HEALTHCHECK):
không sót ảnh, không sót container. Bẫy "đổi một va chạm lấy một ảnh mồ côi mỗi
lượt" mà chính PR nêu ra không mở ra ở đường SIGINT.

## 5. Cổng đầy đủ trên `main@ca5e7e8` (cây sạch, 0 thay đổi)

```
$ bash scripts/gate.sh                                   # 4m40s
ĐẠT 12   HỎNG 0   BỎ QUA 2
  đạt:    guard contract client-routes cors api migration pinned-import
          shared mobile docker postgres e2e
  bỏ qua: guard-range — nhánh không thêm commit nào trên origin/main
          ruff       — nhánh không đổi file Python nào so với origin/main
```

Hai chặng bỏ qua là vì tôi **đứng trên main** nên phạm vi diff rỗng, không phải
vì thiếu môi trường. Để chúng không thành lỗ, tôi chạy ruff bản ghim tay trên
đúng file Python mà #295 thêm:

```
$ RUFF="$(bash scripts/ruff_pinned.sh)"   # /home/lakiet/miniconda3/bin/ruff -> ruff 0.9.2 (= pin)
$ "$RUFF" check  tests/test_gate_docker_names_are_per_lane.py   → All checks passed!      rc=0
$ "$RUFF" format --check <cùng file>                            → 1 file already formatted rc=0
```

`mobile` và `e2e` ĐẠT được là nhờ tôi hard-link `node_modules` vào cây đo
(`cp -al`, không `ln -s`). Không có bước đó thì cả hai in
*"chưa `npm ci` trong apps/mobile"* và **BỎ QUA** — đúng hình dạng mà một báo
cáo ẩu đọc thành xanh. e2e chạy thật: `# pass 7 / # fail 0`, không in
"khong co server".

Bộ test đầy đủ và tầng PostgreSQL thật:

```
$ python3 -m pytest services/api/tests tests -q
2172 passed, 420 skipped, 4797 subtests passed in 163.71s

# 420 ca skipped ở trên được phủ ở chặng postgres của gate (database dùng một lần):
368 passed in 37.77s      (tests/postgres, MOBILE_REQUIRE_POSTGRES_TESTS=1)
89 passed, 19 subtests    (tests/qa,       MOBILE_REQUIRE_POSTGRES_TESTS=1)
```

## Phát hiện

### 1. Ca tiền đề của cổng mới thoả mãn được mà chặng chưa từng tạo container nào

*Loại: suggestion. Không chặn merge.*

`test_docker_stage_names_an_image_and_a_container` tự mô tả là "tiền đề của mọi
ca bên dưới" — nếu chặng ngừng đặt tên hẳn thì mọi assert rời rạc đều thoả mãn
bằng hai tập rỗng. Nửa tên ảnh đúng như thế. Nửa tên **container** thì không:
`Artifacts.feed` còn suy tên container ra từ argv của `rm` / `inspect` / `logs`,
nên chỉ cần `docker rm -f "$MOBILE_GATE_CONTAINER"` còn đó là tập container đã
khác rỗng, dù không có `docker run --name` nào.

Đo được (M6 trong bảng): bỏ hẳn `--name` khỏi `docker run -d` → **8 passed**.

Vì sao tôi vẫn để nó ở mức suggestion: cùng đột biến đó chạy trên docker **thật**
thì đỏ ồn ào, không im lặng —

```
container thoát trước khi healthy
Error response from daemon: No such container: mobile-api-gate-qa24-m6-…
HỎNG    docker (4s)     rc=1
```

Nên đây là lỗ ở **tiền đề của phép đo**, không phải đường xanh giả của sản phẩm.
Gỡ chặn nếu ai muốn: đọc tên container chỉ từ `--name` (và `run`), hoặc thêm một
assert rằng có một dòng argv chứa cả `run` lẫn `--name`.

### 2. `scripts/ruff_pinned.sh check <file>` in ra đường dẫn rồi `exit 0`

*Loại: suggestion. Ngoài phạm vi #295 — báo vì tôi vừa vấp nó trong chính lượt này.*

Script chỉ nhận `--pin`; mọi tham số khác bị bỏ qua. Nên:

```
$ bash scripts/ruff_pinned.sh check tests/test_gate_docker_names_are_per_lane.py
/home/lakiet/miniconda3/bin/ruff
$ echo $?
0
```

Không có finding nào, thoát 0 — đọc y hệt "lint sạch", trong khi ruff **chưa
từng chạy**. Tôi đã tin nó một nhịp trước khi để ý dòng in ra là một đường dẫn.
Ghi chú của Lead ngày 30/08 viết *"`ruff format tests/qa/…/mutants.py` — Dùng
bản GHIM: `scripts/ruff_pinned.sh`"*, tức đúng hình dạng gọi này rất dễ xảy ra.
Cách dùng đúng là `"$(scripts/ruff_pinned.sh)" check <file>`. Gỡ chặn: từ chối
tham số lạ bằng `exit 2` thay vì im lặng in đường dẫn.

## Ô CHƯA quét

- **Docker có thật sự cô lập hai ảnh khác tên không** — tính chất của Docker, không
  của repo này. Không đo, và #295 cũng không hứa.
- **Ngắt bằng SIGKILL** (`kill -9`) giữa lượt: không đo. SIGINT thì sạch.
- **`scripts/gate_merge.sh`**: không chạy trong lượt này. Đọc mã thì nó gọi
  `./scripts/gate.sh` trong một worktree tạm mà **không** đặt `MOBILE_GATE_RUN_ID`
  (dòng 248), nên mỗi lượt vẫn tự sinh id — đây là **suy luận từ mã, không phải
  phép đo**.
- **Va chạm không đi qua cái tên** — biến môi trường hai lane cùng đọc, một bind
  mount dùng chung, cổng host trùng. Chính docstring của #295 nói nó không thấy
  được loại này, và tôi cũng không đo.
- **Mã VietQR quét được bằng app ngân hàng thật hay không** — vẫn chưa ai kiểm.
  Chỉ leader trả lời được, bằng một điện thoại thật (ADR-0010 mục 8).
- Repo này **vẫn chưa có bằng chứng hành vi nào** (ADR-0006). Cổng xanh nói code
  làm đúng điều tác giả nghĩ, không nói người thật hiểu sản phẩm.

## Ghi chú môi trường

Worktree QA của tôi có 22 đường dẫn untracked là bản nháp QA của chính tôi từ các
lượt trước (`apps/mobile/dist-qa*/`, `tests/qa/rd-qa-*/`). Tôi đã chuyển chúng ra
`/tmp/qa-tt-0024-untracked/` trước khi đo để cây sạch, rồi trả lại sau khi đẩy
nhánh. Chúng là nguyên nhân đã biết làm chặng `ruff` và các cổng quét filesystem
đỏ trong worktree này — mọi số liệu ở trên đều đo trong cây **0 thay đổi**
(`/tmp/qa24-main`, `/tmp/qa24-merge`), không phải trong worktree đó.

## Kỹ năng đã dùng

`e2e-testing` (chặng 2 cổng rẻ · chặng 3 PostgreSQL thật với
`MOBILE_REQUIRE_POSTGRES_TESTS=1` · chặng 4 lát cắt dọc e2e 7/7 có server thật ·
chặng 7 kết luận kèm ô chưa quét) và `bug-reproduction` (repro tối thiểu tất định
· đỏ-trước/xanh-sau · đối chứng âm ở tầng docker thật · revert-to-verify dưới
dạng bảng đột biến M0–M9).
