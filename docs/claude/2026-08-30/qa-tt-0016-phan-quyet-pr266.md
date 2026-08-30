# PASS — #266 (`probe-xoa-nham-that.mjs`)

Probe đo đúng tính chất nó tuyên bố, và tôi không tìm được hình dạng nào của lỗi
cũ khiến nó in ĐẠT. Bảy đột biến của tôi: bốn hình dạng phá tính chất đều ra
**khác 0**, hai đột biến **giữ tính chất** đều ra **0**. Bỏ trần 12 chữ/màn thì
số ca đo tăng 90 → 146 mà kết quả không đổi (0/146 so với đối chứng 146/146) —
ô mà chính tác giả ghi là chưa quét, giờ đã quét.

- protocol_version: v1
- verdict: **PASS**
- đo tại `e2b0e97` (head PR lúc tôi nhận việc)
- **`#266` đã được merge lúc 02:13:46Z, GIỮA lượt đo của tôi** → `bffa667` trên main
- `sha256` của `probe-xoa-nham-that.mjs` và `che-chu.mjs`: head PR **y hệt** bản
  đã merge, nên phán quyết này áp cho `origin/main` chứ không chỉ cho nhánh
- blocker còn mở: **không có**

---

## 1. Tái lập con số của PR

Cây sạch, worktree detached riêng tại `e2b0e97`, `node_modules` chép bằng
`cp -al` (symlink làm `expo export` chết), `npm run build:check` dựng lại bundle
từ chính cây đó, `PUPPETEER_EXECUTABLE_PATH` ghim sang chromium của Playwright.

```
man          co the  thu  chon that   xoa(do)  xoa(doi chung)
kham-pha        22   12         11         0              11
len-plan        18   12         12         0              12
tin-nhan        14   12         11         0              11
ca-nhan         28   12         12         0              12
ky-niem         13   12         12         0              12
nhom             6    6          5         0               5
ban-be          18   12         11         0              11
dia-diem        27   12         12         0              12
dang-ky          5    5          4         0               4

chu bi chon that : 90   (56 vuot tran moi man, khong do)
bi xoa nham (do)         : 0/90 = 0.0%
bi xoa nham (doi chung)  : 90/90 = 100.0%
rc=0
```

Trùng khít bảng trong mô tả PR, tới từng ô của từng màn.

## 2. Đột biến — bốn hình dạng phá, hai hàng giữ tính chất

Tác giả đã có ba hàng. Tôi không chạy lại ba hàng đó rồi gật; tôi viết **cùng
một vi phạm bằng những hình dạng khác**, vì hàng đột biến của tác giả dùng
nguyên cả module pre-patch, và một cổng có thể đang phản ứng với "ai đó thay cả
file" chứ không phải với tính chất.

Đột biến trỏ vào module đang đo qua `CHE_CHU_MODULE`; mỗi bản được kiểm là neo
xuất hiện **đúng một lần** trước khi thay, nếu không thì thoát 9 chứ không lặng
lẽ vá nhầm bản sao.

| # | đột biến | mong | ra |
|---|---|---|---|
| M1 | tha bổng viết lại bằng `if/else` (khác chữ, cùng tính chất bị phá) | HỎNG `rc=1` | **`rc=1`**, xoá 90/90 |
| M2 | tha bổng **dời xuống tầng `laLoiThat`**, không đụng biểu thức verdict | HỎNG `rc=1` | **`rc=1`**, xoá 90/90 |
| M3 | đường tắt **dời lên hàm ĐẾM điểm mẫu** (`nhinThay++` khi selector khớp) | — | **`rc=3` CHƯA KẾT LUẬN** |
| M4 | **GIỮ TÍNH CHẤT:** dời 5 điểm mẫu `[.1 .3 .5 .7 .9]` → `[.15 .35 .5 .65 .85]` | ĐẠT `rc=0` | **`rc=0`** |
| M5 | **GIỮ TÍNH CHẤT:** ngưỡng `0.6` → `0.58` | ĐẠT `rc=0` | **`rc=0`** |
| M6 | đối chứng ghim vào sha **đã vá** `1fc37ae` | `rc=3` | **`rc=3`** |
| M7 | đối chứng ghim vào sha **không tồn tại** | `rc=3` | **`rc=3`** |
| — | hàng 1 của tác giả: module đo = pre-patch nguyên vẹn | HỎNG `rc=1` | **`rc=1`** |

M1 và M2 là câu trả lời cho "cổng đo tính chất hay đo việc có ai đụng file":
M2 không sửa một ký tự nào trong `doTrongTrang`, nó tha bổng ở tầng dưới, và
probe vẫn đỏ 90/90. M4 và M5 đổi thật hành vi của dụng cụ mà không đổi tính
chất, và probe im lặng đúng như phải thế.

### M3 là hàng đáng đọc nhất, và nó không phải lỗ hổng

Tôi đoán `rc=1`, ra `rc=3`. Đoán của tôi sai, probe đúng.

M3 tái lập sự tha bổng **mà không đụng biểu thức verdict**: nó thổi `nhinThay`
lên bằng cách đếm luôn phần tử khớp selector là "đọc được". Chữ bị chôn thật
khi đó đọc ra `5/5 điểm đọc được` → verdict `cuon-khuat` → bị xoá.

Hệ quả: mẫu số của probe (`chỉ đếm lần chôn đã ăn`, tức `diemNhinThay === 0`)
rơi về **0**. Một cổng hai trạng thái sẽ in `0/0 = 0.0%` và thoát 0 — **một dấu
xanh giả hoàn hảo**. Chốt `tChon === 0` biến nó thành "không biết".

Tôi không tin suy luận đó, tôi đo riêng bằng một trang HTML **tự dựng, không
dùng một dòng nào của probe** (lớp phủ là anh em của chữ, mang đúng class của
tổ tiên — va chạm atomic class của rnw, dựng bằng tay):

```
snippet: div.r-card.r-bg.r-pad "Tong cong nhom" is 92% covered by an opaque element (div.r-card.r-bg.r-pad)

module                        verdict      doc duoc  laLoiThat
ban dang do (post-#261)       that         0/5       GIU canh bao
M3 duong tat trong ham dem    to-cha       5/5       XOA canh bao
doi chung pre-patch           to-cha       0/5       XOA canh bao
```

Ba điều đọc ra được từ đây:

1. M3 **thật sự xoá** cảnh báo, và cơ chế đúng là bộ đếm bị thổi (`5/5`), không
   phải một exception làm probe chết nhầm.
2. `rc=3` là trạng thái thứ ba bắn đúng chỗ — đúng hình dạng Lead yêu cầu ở ghi
   chú 08:21.
3. **Không hình dạng nào trong bốn hình dạng phá tính chất cho ra `rc=0`.** Đó
   mới là câu kết luận, chứ không phải "M3 lọt".

## 3. Đối chứng đỏ-trước / xanh-sau cho chính bản vá #261

Cùng trang tự dựng ở trên, không qua probe:

- `c9532cf` (pre-patch): chữ bị chôn thật, ghi nhận `0/5 điểm đọc được`, verdict
  `to-cha` → **XOÁ cảnh báo**. Lỗi cũ tái lập được.
- bản đang chạy (post-`#261`): cùng trang, verdict `that` → **GIỮ cảnh báo**.

Đối chứng của probe cũng ghim theo commit chứ không theo ref di động, và **kiểm
chuỗi đường tắt trong nguồn trích ra** trước khi tin. M6 chứng minh chốt đó
sống: ghim vào sha đã vá thì nó từ chối kết luận thay vì in cột đối chứng trấn
an. Đây đúng là bài học "đối chứng neo vào `origin/main` hết hiệu lực".

## 4. Trần 12 chữ/màn không giấu gì

Tác giả tự khai 56 chữ vượt trần nên không được đo. Tôi bỏ trần (`12 → 1000`):

```
chu bi chon that : 146   (0 vuot tran moi man, khong do)
bi xoa nham (do)         : 0/146 = 0.0%
bi xoa nham (doi chung)  : 146/146 = 100.0%
rc=0
```

Số ca tăng 90 → 146, kết quả không nhúc nhích. Ô này khép lại.

## 5. Cổng đã chạy

Cây sạch tại `e2b0e97`:

```
python3 -m pytest services/api/tests tests -q
  -> 1616 passed, 358 skipped, 2 xfailed, 4736 subtests passed  (129.00s)
     2 xfail la marker rd-qa-40 cua viec khac, khong lien quan PR nay

python3 scripts/repo_guard.py tree HEAD
  -> Repo guard passed tracked tree: 791 file scan(s).

cd apps/mobile && npm test
  -> tests 667 · pass 666 · fail 1
```

### Một ca đỏ, và nó KHÔNG phải lỗi của PR

```
not ok 499 - nhánh này không mang lại file nào đã có nguyên vẹn trên origin/main
  tests/stacked-branch.test.mjs:247
  1/1 file hien trong diff ma noi dung y het origin/main.
  actual: [ 'apps/mobile/tools/probe-xoa-nham-that.mjs' ]
```

Nguyên nhân: `#266` được squash-merge vào main lúc `02:13:46Z`, **trong lúc tôi
đang đo**. Ca này bắt đúng chữ ký "việc của nhánh đã nằm trên main", và chính
thông điệp của nó nói "Không phải lỗi". Ghi ra đây vì một người đọc lướt sẽ thấy
`fail 1` và tưởng PR hỏng.

Tôi đối chiếu `sha256` để chắc phán quyết vẫn áp được cho bản đã ship:

```
probe-xoa-nham-that.mjs  head PR = 6c6411bc…1536c
                         main    = 6c6411bc…1536c   trùng
che-chu.mjs              head PR = af74db54…25a4
                         main    = af74db54…25a4   trùng
```

## 6. Ô CHƯA QUÉT — phần quan trọng nhất

- **Tổ tiên thật đè lên chính con nó.** Trong `doTrongTrang`, một điểm mẫu được
  tính là **đọc được** khi phần tử trên cùng là tổ tiên (`tren.contains(el)`).
  Lớp phủ của probe là **anh em** được `appendChild` vào `body`, chỉ *mặc* class
  của tổ tiên — nên trường hợp một cha có nền đục vẽ đè lên chữ con của chính
  nó **chưa từng được probe dựng**. Nếu tình huống đó xảy ra thật, bộ lọc sẽ
  đọc là đọc-được → `cuon-khuat` → xoá. Đây là tính chất **có sẵn trong bộ lọc,
  không do PR này sinh ra**, và cũng không được PR này đo. Đáng một việc riêng.
- **Ngưỡng `0.6` đặt đúng chỗ hay không** — không file nào trong PR đụng tới.
- **Probe không được nối vào cổng nào.** Không `Makefile`, `gate.sh`, workflow
  hay test nào gọi `probe-xoa-nham-that.mjs`; nó là dụng cụ chạy tay. Không phải
  lỗ hổng — `che-chu.mjs` vẫn có `tests/che-chu.test.mjs` và
  `tests/che-chu-lo-to-cha.test.mjs` chạy trong `npm test` — nhưng nghĩa là con
  số 0/146 này sẽ **không tự chạy lại** ở lần hồi quy sau.
- **Cặp canary của `imp detect`**: tôi **không** chạy lại, dùng lại kết quả tác
  giả dán. Phần đó chưa được tôi kiểm chứng độc lập.
- **Các màn ngoài 9 tab** — Chụp bill, gán món, trang khách — như tác giả đã khai.
- **Mã QR quét bằng app ngân hàng thật**: vẫn chưa ai làm. Không liên quan PR
  này, nhưng chưa được gỡ khỏi danh sách.

## 7. Ghi cho Lead

`#266` được merge trước khi có phán quyết của tôi. Lần này kết quả là PASS nên
không mất gì, nhưng tôi ghi lại để con số đếm đúng: đây là PR thứ hai trong hai
ngày đi qua cổng QA theo hướng ngược.

Và một ghi nhận cho tác giả: trạng thái `CHƯA KẾT LUẬN ĐƯỢC` không phải trang
trí. Nó là thứ duy nhất chặn M3 — hình dạng lỗi khó thấy nhất trong bảy hình
dạng tôi thử — khỏi in ra một dấu xanh hoàn hảo.

## Lệnh tái lập

```bash
git worktree add --detach /tmp/qa16-pr266 e2b0e97
cd /home/lakiet/agent-harness/wt/qa/apps/mobile && cp -al node_modules /tmp/qa16-pr266/apps/mobile/node_modules
cd /tmp/qa16-pr266/apps/mobile && npm run build:check
export PUPPETEER_EXECUTABLE_PATH=/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome
node tools/probe-xoa-nham-that.mjs                      # 0/90 vs 90/90, rc=0
CHE_CHU_SHA_DOI_CHUNG=1fc37ae node tools/probe-xoa-nham-that.mjs   # rc=3
```

Kịch bản đột biến và phép đo độc lập: `tests/qa/qa-tt-0016/`.
