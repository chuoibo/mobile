# Phán quyết QA — PR #333 lượt hai (cổng `server-routes`)

**FAIL**

**Lý do (đọc trước phần chi tiết):** tác giả đã làm **2 trong 3** tiêu chí gỡ chặn —
nhánh đã gộp `main`, `scripts/gate.sh` đã giải xung đột đúng bằng hợp, và cây gộp
giờ **sạch, không còn xung đột nào cho Lead**. Tiêu chí thứ ba **chưa làm**: commit
mới `4b052a5` chỉ sửa `scripts/gate.sh`, không đụng `.server-routes-uncalled.json`.
Nên hệ quả cũ còn nguyên và lần này tôi đo được **trên chính hiện vật tác giả đẩy**,
không phải cây tôi tự gộp: cổng `exit 1` với **đúng 6 route** của #133/#303. Lead bấm
merge bây giờ là `make gate` trên `main` đỏ cho **cả bốn lane**.

Bản thân cổng thì **tốt hơn nữa sau khi gộp**: 6/6 đột biến chạy lại trên cây gộp
đều đúng, có đối chứng dương. Đây không phải phán quyết về chất lượng cổng. Nó là
phán quyết về **6 dòng JSON còn thiếu**. Tiêu chí gỡ chặn ở mục 6 — một dòng lệnh.

```
đo tại   4b052a59efee7492c73c23fb6763b413d17116db   (head PR #333)
         99cea34 = origin/main@ce0fa80 ⊕ 4b052a5    (cây gộp tôi dựng, merge SẠCH)
sha này  nhánh CHƯA merge. main@ce0fa80 đứng trước nó 2 commit, cả hai chỉ chạm
         docs/qa/ + tests/qa/ — tập route của main KHÔNG đổi kể từ lượt đo trước.
```

Phán quyết trước: FAIL tại `8241e24` (#340, đã vào main). Đây là lượt đo lại vì tác
giả đẩy commit mới, không phải xử lại chuyện cũ.

---

## 1. Ba tiêu chí gỡ chặn lượt trước — hai xong, một chưa

| # | Tiêu chí lượt trước | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Rebase/merge lên `main` | **XONG** | `git merge-base HEAD origin/main` = `267971e`, đúng mốc tôi yêu cầu |
| 2 | Giải `gate.sh`, giữ **cả hai** chặng | **XONG** | `STAGES=(... client-routes server-routes cors api migration pinned-import demo-watch shared ...)` |
| 3 | Xử lý 6 route đỏ | **CHƯA** | `.server-routes-uncalled.json` không đổi một byte, vẫn 17 dòng |

Tiêu chí 2 làm **đúng**, không phải làm cho xong. `4b052a5` mang nguyên khối
`do_demo-watch()`, `check_prereq` và `broken_why` của `main` sang, không cắt xén —
tôi đọc cả 54 dòng diff. Đây là chỗ dễ mất việc của lane khác nhất và nó không mất.

Và cây gộp giờ **merge sạch**: lượt trước tôi phải tự giải xung đột `gate.sh` và ghi
rõ "bản giải của tôi không phải bản để merge". Lần này không còn cảnh báo đó.

```
git merge 4b052a5 → exit 0, không xung đột
```

## 2. Tái lập lỗi cũ — lần này trên hiện vật của chính tác giả

Lượt trước tôi chỉ chứng minh được lỗi trên cây **tôi** gộp. Đó là điểm yếu của phán
quyết đó. Lần này `4b052a5` đã chứa `main@267971e`, nên chạy thẳng trên head PR:

```
$ python3 scripts/check_server_routes_called.py     # tại 4b052a5, cây sạch
Máy chủ khai 76 route. 48 có người gọi, 5 miễn, 17 đang nợ, 6 không ai gọi và chưa ghi nhận.
...
6 route không ai gọi.
exit=1

$ bash scripts/gate.sh server-routes                # chỗ nối truyền mã lỗi
exit=1
```

Và trên cây gộp với `main` **hiện tại** (`ce0fa80`), để loại khả năng main đã nhích:

```
$ python3 scripts/check_server_routes_called.py     # tại 99cea34
6 route không ai gọi.     exit=1
$ bash scripts/gate.sh server-routes                exit=1
```

Hai nền đo khác nhau, cùng một con số 6. Đây là **cùng một lỗi**, chưa được chạm tới.

## 3. Sáu route đó — kiểm bằng tay, KHÔNG qua script

Tôi không được tin công cụ của chính mình. `grep -rn` trực tiếp trên `apps/mobile/src`,
lọc bỏ dòng comment:

| Chuỗi | Tổng dòng khớp | Dòng **không phải** comment |
|---|---|---|
| `votes` | 4 | **0** |
| `ballots` | 2 | **0** |
| `face-boxes` | 0 | 0 |
| `my-items` | 0 | 0 |

Sáu route `/contexts/{context_id}/votes`, `/votes/{vote_id}`, `/votes/{vote_id}/ballots`,
`/votes/{vote_id}/close` (từ #133), `/contexts/{context_id}/photos/{photo_id}/face-boxes`,
`/bills/{bill_id}/my-items` (từ #303) đều **thật sự không có người gọi**. Cổng nói đúng.

Bốn dòng "votes" đều là comment tiếng Anh — đúng cái canary "xanh giả" mà PR mô tả,
đang xảy ra trên dữ liệu sống. Một bộ đọc khớp chuỗi con sẽ kết luận 4 route vote đã
có người gọi và bỏ lọt cả bốn.

Không nhánh remote nào đang mở trả nợ này (kiểm `git branch -r --sort=-committerdate`:
không có nhánh màn bình chọn hay màn face-box).

## 4. Đột biến chạy lại trên CÂY GỘP — 6/6, merge không làm cùn răng

Lượt trước bảng đột biến chạy trên cây tôi tự gộp. Một lần gộp có thể làm hỏng bộ đọc
mà không ai thấy, nên bảng được chạy lại trên hiện vật đã gộp thật.

Nền: cây gộp ĐỎ sẵn 6 route, nên tôi **ghim tạm** 6 route đó để có nền `exit 0` rồi
mới đột biến. Không có nền xanh thì mọi hàng đều "đỏ" và bảng không phân biệt được gì.
Mỗi đột biến khôi phục bằng `git checkout --` trước lượt sau; cây sạch khi xong.

```
M0 nền (6 route ghim tạm)              exit=0   0 route đỏ
```

| # | Đột biến | Mong đợi | Đo được | Kết |
|---|---|---|---|---|
| M1 | Thêm route máy chủ không ai gọi | ĐỎ + nêu tên | `exit 1`, nêu đúng tên | **BẮT** |
| M3 | **Cùng** route đó nhưng có literal gọi thật trong `api.ts` | XANH | `exit 0` | **ĐỐI CHỨNG DƯƠNG** |
| M4 | Phá bộ đọc client (`tokenize` → `[]`) | không được XANH | `exit 2`, in câu từ chối | **BẮT** |
| M5 | Phá mẫu số máy chủ (`load_openapi` → `{"paths":{}}`) | không được XANH | `exit 2`, in câu từ chối | **BẮT** |
| M7 | Gỡ người gọi thật của `/expenses` (cả **2** bản sao) | ĐỎ + nêu tên | `exit 1`, nêu `/expenses` **và** `/expenses/{expense_id}/confirm` | **BẮT** |
| M8 | Dòng nợ trỏ vào route máy chủ không hề khai | không được nuốt im lặng | `exit 0` + in `GHIM CŨ: ... máy chủ không còn khai route này` | **BẮT (không tử)** |

**M3 vẫn là hàng quan trọng nhất.** Một cổng luôn đỏ cũng cho 5/5 "BẮT" ở các hàng
kia. M3 chứng minh nó phân biệt được có/không có người gọi, nên các hàng đỏ mới có
nghĩa.

**M8 là hàng mới của lượt này.** Một danh sách ngoại lệ mà không ai kiểm được thì
theo thời gian sẽ đầy rác, và rác trong đó là chỗ giấu route chết. Script **có** phát
hiện dòng nợ trỏ vào hư không, in ra, và **cố ý không giết cổng** — comment trong code
giải thích vì sao (xoá một route chết là kết quả cổng này muốn, không phải lỗi). Tôi
đột biến để xem nó nổ thật chứ không đọc comment rồi tin.

**M7 dùng `replace` toàn bộ, không `count=1`** — hai bản sao `"/expenses"` trong
`api.ts`; vá một bản sao rồi đọc "đỏ" là đọc nhầm một cổng đang mù.

## 5. Cổng đầy đủ trên cây gộp

```
$ python3 -m pytest services/api/tests tests -q        # tại 99cea34
2515 passed, 548 skipped, 4887 subtests passed in 230.26s

$ python3 -m pytest tests/test_server_routes_called_gate.py \
    tests/test_gate_covers_every_inline_step.py \
    tests/test_gate_covers_every_workflow_job.py \
    tests/test_gate_stage_bodies_are_unique.py -q
46 passed, 86 subtests passed

$ python3 scripts/check_server_routes_called.py --selftest
6/6 ĐẠT (2 canary xấu ĐỎ, 3 đối chứng XANH, 1 canary route khách chưa ghi lý do)
exit=0
```

`46 passed, 86 subtests` **khớp đúng con số lượt đo trước** — lần gộp không nuốt ca
test nào. Đây là phép kiểm có chủ ý: gộp im lặng làm mất ca test là chuyện đã xảy ra
trong repo này.

548 skipped là tầng PostgreSQL (thiếu `MOBILE_TEST_DATABASE_URL`) + 1 ca cần
`apps/mobile/node_modules`. **skipped không phải xanh** — xem mục 7.

## 6. Blocker và tiêu chí gỡ chặn

**Loại 1 — vi phạm spec/cổng.** Gộp #333 lên `main@ce0fa80` làm `make gate` ĐỎ.

- **Dẫn chứng:** mục 2 (`exit 1` trên **hai** nền đo độc lập) và mục 3 (kiểm tay).
- **Hậu quả:** `server-routes` đứng thứ 6 trong `STAGES` mặc định, trước `api`. Mọi
  lane gõ `make gate` trên `main` đỏ trong vài giây, cho tới khi có người xử lý.
- **Gỡ chặn — một việc, 6 dòng JSON:** thêm 6 route ở mục 3 vào
  `.server-routes-uncalled.json` kèm `reason` **thật**.

Lý do thật ở đây rẻ và không phải nói dối: *"F17/F22 đã merge, máy chủ có route,
`apps/mobile/src` chưa có màn nào gọi — kiểm bằng grep, 0 literal"*. Đó là một sự
kiện ai cũng kiểm lại được trong 5 giây, không phải câu giữ chỗ.

**Một chuyện Lead cần quyết, không phải chuyện tác giả tự quyết được:** nợ này thuộc
về #133 (backend) và #303 (devops), không thuộc qa3. Ba đường đi, tôi xếp theo mức
rẻ:

1. **qa3 tự ghim 6 dòng** (rẻ nhất, không nói dối, mở khoá ngay) — ghim là *ghi nợ*,
   không phải *trả nợ*, và chính file đã viết ra sự phân biệt đó.
2. Lead merge #333 **kèm** một commit ghim trong cùng lượt.
3. Đợi frontend viết màn gọi 6 route — đúng nhất nhưng chặn cổng này lâu nhất, và nó
   để `main` tiếp tục không ai hỏi câu này.

Tôi không khuyến nghị hộ Lead giữa 1 và 2; cả hai đều gỡ được blocker.

**Không có blocker nào khác.** Chất lượng cổng: đo hai lượt trên hai cây khác nhau,
13 đột biến cộng lại, cả hai lượt đều có đối chứng dương. Nó gác cả hai mẫu số — chỗ
phần lớn cổng trong repo này đã chết. Và nó bắt được một lỗ hổng mà **phán quyết PASS
#303 của chính tôi đã bỏ sót** (`face-boxes` không màn nào gọi). Đây là lý do PR nên
vào, không phải lý do giữ nó lại.

## 7. Ô CHƯA quét

- `tests/postgres` tầng live (548 ca skip) — chưa chạy lượt này. PR không chạm
  `app/`, `db/`, `payments/` nên ngoài rủi ro của PR, nhưng **chưa quét** chứ không
  phải "không áp dụng".
- `cd apps/mobile && npm test` — **chưa chạy**. `git diff --name-only origin/main HEAD`
  cho **0 file** dưới `apps/mobile/`, nên kết quả sẽ bằng đúng kết quả của `main`;
  vẫn ghi là chưa quét vì tôi không đo.
- `npm run test:e2e` lát cắt dọc — chưa chạy.
- Chặng `demo-watch` mà `4b052a5` mang sang: tôi chỉ đọc diff, **không chạy** nó.
- Nhánh bỏ qua `if [ ! -d apps/mobile/src ]` trong bước CI: trên máy này thư mục tồn
  tại nên nhánh đó không kích hoạt — **chưa quét đường bỏ qua**. Nó là một đường xanh
  im lặng nếu ai đó đổi layout.
- Mã QR quét bằng app ngân hàng thật — vẫn chưa ai làm, ngoài phạm vi PR này.

---

### Lệnh tái lập

```bash
git worktree add --detach /tmp/qa34-pr333 4b052a59
cd /tmp/qa34-pr333
python3 scripts/check_server_routes_called.py ; echo "exit=$?"   # 1, sáu route
bash scripts/gate.sh server-routes ; echo "exit=$?"              # 1
python3 scripts/check_server_routes_called.py --selftest          # 0

git worktree add --detach /tmp/qa34-merge origin/main
cd /tmp/qa34-merge && git merge 4b052a59                          # sạch, không xung đột
python3 scripts/check_server_routes_called.py ; echo "exit=$?"   # 1, sáu route
python3 -m pytest services/api/tests tests -q                     # 2515 passed
```

Bảng đột biến ở `tests/qa/qa-tt-0034-333/dot-bien-lan-hai.sh` — chạy trên
`/tmp/qa34-merge`, tự dựng nền xanh, tự khôi phục sau mỗi lượt, in bảng ở mục 4.

skills dùng: `e2e-testing` (chặng 2 cổng rẻ, chặng 6 thăm dò, chặng 7 kết luận +
ô chưa quét), `bug-reproduction` (bước 2 vòng tái lập-thu nhỏ, bước 5 nền xanh trước
khi đột biến, bước 6 đối chứng dương M3 = revert-to-verify, bước 8 ghi bằng chứng
kèm SHA).
