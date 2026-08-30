# PASS — `main@4512290`, đã gồm #290 và #292

**Lý do (đọc dòng này trước, phần còn lại là bằng chứng):** ba cổng chống lỗi
"khai báo route làm app không import nổi dưới fastapi đã ghim" đều **có răng
thật** — tôi đo bằng bảng đột biến 4 hàng, và bằng một trình thông dịch có
fastapi 0.115.6 **thật** chứ không phải bản mô phỏng. Bảng 8 hình dạng của #290
**tương đương từng hàng** với 0.115.6 thật. Cổng đầy đủ trên `main` xanh:
`ĐẠT 12 · HỎNG 0 · BỎ QUA 2`, trong đó e2e chạy thật 7/7 và tầng postgres chạy
thật 368 + 89 ca. **Một phát hiện còn mở:** cổng của #288 báo nhầm đúng cái cách
sửa mà thông báo lỗi của #290 mách người ta dùng — chi tiết ở mục 4.

---

## 0. Đo tại đâu, và cái đó có ở main không

| | |
|---|---|
| đo tại | `4512290` (`origin/main` lúc 2026-08-30) |
| sha này | **ĐÃ ở main** |
| fastapi trên máy đo | 0.135.3 |
| fastapi trong ảnh / trong pin | 0.115.6 (`services/api/requirements-dev.txt`) |
| trình thông dịch đối chứng | venv riêng `/tmp/pin115`: fastapi 0.115.6 · starlette 0.41.3 · pydantic 2.13.5 |

Việc này khởi đầu là phán quyết cho hai PR đang mở, **#290** (oracle khai báo
route) và **#292** (chặng `pinned-import`). Trong lúc tôi đo, cả hai được merge
(`fa9a81f` cho #292, và #290 vào cùng đợt), cùng với #285 và #291. Nên đây là
**hậu kiểm trên `main`**, không phải cổng chặn merge — và tôi giữ nguyên phép đo
thay vì bỏ, vì hai PR đó vào `main` mà chưa ai chạy bảng đột biến cho chúng.

Một phép đo trung gian tôi đã làm trên cây gộp `16cdc802` (= `main@65319b5` ⊕
#290 ⊕ #292) cho kết quả **giống hệt**; con số dưới đây là bản chạy lại trên
`main` hiện tại.

## 1. Bảng của #290 có tả đúng fastapi 0.115.6 không

`test_route_declarations_under_pinned_fastapi.py` quyết định "bản ghim sẽ nói
gì" bằng cách **vá một hàm phân giải** trên fastapi của máy này. Đó là một **mô
hình** của 0.115.6. Mô hình sai ở đây là kiểu sai tệ nhất: nó sinh ra dấu xanh
cho đúng khai báo làm container chết.

Nên tôi dựng venv có 0.115.6 thật và chạy **chính bảng đã commit** — đọc bằng
`ast.literal_eval` để đo đúng corpus mà cổng dùng, không đo một bản sao:

```
$ python3 tests/qa/qa-tt-0023/tuong_duong_voi_fastapi_ghim.py /tmp/pin115/bin/python
trình thông dịch đối chứng: /tmp/pin115/bin/python — fastapi 0.115.6
đọc 8 hình dạng từ services/api/tests/api/test_route_declarations_under_pinned_fastapi.py

hình dạng                               bảng khai    đo được  kết luận
deferred_model_204                        từ chối    từ chối  khớp
deferred_none_200                            nhận       nhận  khớp
deferred_none_204                         từ chối    từ chối  khớp
deferred_none_204_explicit_model             nhận       nhận  khớp
deferred_none_304                         từ chối    từ chối  khớp
deferred_response_204                        nhận       nhận  khớp
deferred_unannotated_204                     nhận       nhận  khớp
plain_none_204                               nhận       nhận  khớp

KẾT LUẬN: TƯƠNG ĐƯƠNG — mọi hàng khớp với fastapi thật
```

8/8 khớp, và "từ chối" được kiểm theo **chuỗi lỗi của chính fastapi**
(`must not have a response body`), không theo mã thoát trần — đỏ vì gõ sai tên
module cũng là đỏ.

Hàng gánh nặng nhất là `plain_none_204`. #290 dùng chính hàng này để **nới**
cổng của #288 (bỏ một ca báo nhầm). Nới cổng là hướng nguy hiểm, nên nó là hàng
tôi kiểm kỹ nhất: 0.115.6 **thật** nhận nó. Việc nới là **đúng**, không phải hạ
chuẩn cho xanh.

## 2. Ba cổng có đỏ được không, và có xanh được không

Bảng đột biến sửa cây làm việc rồi chạy cổng, rồi trả cây về. Ba hàng **phá**
bất biến phải ĐỎ; một hàng **giữ** bất biến (khai báo hợp lệ, 0.115.6 nạp được)
phải XANH — hàng giữ tính chất là thứ phân biệt "đo đúng luật của bản ghim" với
"dị ứng với mấy ký tự `-> None`".

| đột biến | #290 oracle | #292 `check_pinned_import.sh` (0.115.6 **thật**) | #288 in-process |
|---|---|---|---|
| M1 `memories` 204 trở lại `-> None` — **đúng lỗi đã ship** | ĐỎ | ĐỎ | ĐỎ |
| M2 `contexts.leave_context` 204 với `-> None` — **file khác** | ĐỎ | ĐỎ | ĐỎ |
| M3 `-> None` **+ `response_model=None`** — **GIỮ tính chất** | XANH | XANH | **ĐỎ — báo nhầm** |
| M4 204 → **304**, vẫn `-> None` — **mã khác, cùng lớp lỗi** | ĐỎ | ĐỎ | ĐỎ |

Hai điều đọc ra được từ bảng này mà từng cổng riêng lẻ không nói:

- **Mô phỏng của #290 khớp với 0.115.6 thật trên app thật**, không chỉ trên 8
  hình dạng tổng hợp. Cột 1 và cột 2 giống nhau cả 4 hàng, mà cột 2 là fastapi
  thật trong ảnh sẽ ship.
- M2 và M4 chứng minh cổng không neo vào một file hay một con số: nó bắt được lỗi
  ở `contexts.py` và bắt được 304 chứ không chỉ 204.

Lệnh tái lập, cả ba đều nằm trong repo:

```bash
python3 tests/qa/qa-tt-0023/dot_bien_khai_bao_route.py bash -o pipefail -c \
  "cd services/api && python3 -m pytest tests/api/test_route_declarations_under_pinned_fastapi.py -q"
python3 tests/qa/qa-tt-0023/dot_bien_khai_bao_route.py bash -o pipefail -c \
  "cd services/api && python3 -m pytest tests/api/test_bodyless_status_declarations.py -q"
python3 tests/qa/qa-tt-0023/dot_bien_khai_bao_route.py bash scripts/check_pinned_import.sh
```

`-o pipefail` không phải trang trí. Lượt chạy đầu tiên của tôi nối pytest vào
`tail`, nên mã thoát nhận được là của `tail` — **bốn cổng đỏ thật bị đọc thành
bốn cổng xanh**. Tôi phát hiện vì dòng tóm tắt in "1 failed" ngay cạnh "rc=0".
Đó là phép đo của tôi hỏng, không phải sản phẩm hỏng.

## 3. Cổng của #292 có tự khai khi nó mù không

Đây là chỗ đáng khen nhất và cũng là chỗ tôi nghi nhất: canary của
`check_pinned_import.sh` chỉ có nghĩa nếu nó **đỏ được**, và cả cổng chỉ có nghĩa
nếu nó **tự báo khi mất răng**. Nâng pin lên bản không còn lỗi rồi chạy lại:

```
$ sed -i 's/^fastapi==0.115.6/fastapi==0.135.3/' services/api/requirements-dev.txt
$ MOBILE_PINNED_IMAGE=mobile-api:qa23-blind bash scripts/check_pinned_import.sh
fastapi trong ảnh = 0.135.3 (pin: 0.135.3)
canary xấu IMPORT ĐƯỢC với fastapi 0.135.3 — bản này không còn bắt hình dạng
'204 + annotation hoãn lại', nên chặng pinned-import không còn thấy lỗi nó sinh ra
để bắt. Coi như ĐỎ.
rc=1
```

Đúng hình dạng ba trạng thái mà Lead đòi: nó **không** nhập "không biết" vào
"đạt". Ảnh trong lượt thử này dùng tag riêng `mobile-api:qa23-blind` để không
đầu độc tag chung của lane khác; `requirements-dev.txt` đã trả về nguyên trạng
ngay sau đó (`git diff --stat` rỗng).

Lượt chạy bình thường trên `main`: `IMPORT OK, 62 đường dẫn`, 7 giây với cache.

## 4. PHÁT HIỆN CÒN MỞ — hai cổng mách hai đường ngược nhau

Cổng của #290, khi đỏ, in ra:

> `Fix: pass response_model=None in the decorator of the route named in the traceback, or annotate it -> Response.`

Làm theo **vế thứ nhất** — cũng chính là cách tài liệu FastAPI khuyên — thì cổng
của #288 đỏ, với một lời chẩn đoán **sai sự thật**:

```
AssertionError: These routes promise a response body under a status code that
forbids one. FastAPI 0.115.6 -- pinned in requirements-dev.txt, installed in the
image -- raises AssertionError while registering them, so `app.api.main` does not
import and the container never answers /healthz:
assert not ["['DELETE'] /contexts/{context_id}/memories/{memory_id}/reactions
            status_code=204 declares a body: <class 'NoneType'>"]
```

Câu "the container never answers /healthz" **không đúng cho hình dạng này**. Cùng
lúc đó, trên cùng cây:

- 0.115.6 thật nhận nó (`deferred_none_204_explicit_model` → **nhận**, mục 1)
- `check_pinned_import.sh` với 0.115.6 thật trong ảnh: `IMPORT OK, 62 đường dẫn`
- oracle của #290: XANH

**Hậu quả:** người tiếp theo sửa một route 204 theo đúng cách tài liệu khuyên —
và theo đúng câu cổng vừa mách họ — sẽ làm `main` đỏ, và thông báo sẽ nói với họ
rằng container không boot được, trong khi container boot bình thường. Đó là
đường ngắn nhất để một cổng bị tắt đi.

**Phân loại:** không phải blocker (không còn gì để chặn — cả hai đã ở `main`), và
**không phải lỗi của #290**: #290 kế thừa chỗ này từ #288, viết thẳng ra rằng nó
"knowingly over-reports", và thêm hẳn file có thẩm quyền để phân xử. Đây là việc
còn nợ, tôi nộp cho Lead định tuyến chứ không tự vá — vá xong tự nghiệm thu là
mất tính độc lập.

**Hai đường gỡ, rẻ hơn thì trước:**

1. Sửa **câu chữ**, không sửa logic: đổi thứ tự gợi ý thành `-> Response` trước,
   và nói rõ `response_model=None` sẽ làm cổng anh em đỏ. Một dòng, không đụng
   hành vi.
2. Sửa **vị từ**: #290 lập luận rằng in-process không thấy được
   `response_model` khai tường minh, vì trên route đã dựng cả hai đều thành
   `None`. Đúng ở tầng route — nhưng `inspect.getsource(route.endpoint)` **có
   kèm cả dòng decorator**, nên vẫn phân biệt được. Thô, và cần chính họ cân
   nhắc; tôi nêu ra để "không sửa được" không bị chốt sớm.

## 5. PHÁT HIỆN — `scripts/ruff_pinned.sh` thoát 0 khi bị gọi như một wrapper

Script này **in ra đường dẫn** tới ruff đúng bản ghim; nó **không chạy** ruff.
Mọi tham số ngoài `--pin` bị bỏ qua âm thầm. Ghi chú Lead để lại cho tôi viết
"Dùng bản GHIM: `scripts/ruff_pinned.sh`, không phải ruff trên PATH", và tôi đã
đọc thành wrapper — rồi báo cáo cho mình một dấu xanh không đo gì cả.

Cùng một file, cùng một ruff ghim:

```
$ scripts/ruff_pinned.sh check tests/qa/rd-qa-36/di-bo-ban-be.py
/home/lakiet/miniconda3/bin/ruff
rc=0                                   # ← không lint gì, vẫn xanh

$ "$(scripts/ruff_pinned.sh)" check tests/qa/rd-qa-36/di-bo-ban-be.py
Found 3 errors.
rc=1                                   # ← cách gọi đúng
```

Chi phí gỡ: bốn dòng ở cuối script, từ chối tham số lạ và thoát 2. Cùng họ với
"cổng in ra bằng chứng mình đang mù" — script này thậm chí đã cẩn thận **rất**
kỹ về việc dùng đúng bản ruff, rồi để ngỏ đúng cái cửa khiến nó không chấm gì.

## 6. Cổng đầy đủ trên `main`

```
$ bash scripts/gate.sh          # main@4512290, 4m57s
ĐẠT 12   HỎNG 0   BỎ QUA 2
  đạt:     guard contract client-routes cors api migration pinned-import
           shared mobile docker postgres e2e
  bỏ qua:
    guard-range: nhánh không thêm commit nào trên origin/main
    ruff:        nhánh không đổi file Python nào so với origin/main
```

Hai chặng bỏ qua là do **tôi đang đứng trên `main`** nên phạm vi diff rỗng, không
phải do thiếu môi trường. Số của từng chặng đáng đọc:

| chặng | đo được |
|---|---|
| `api` | 2146 passed · 420 skipped · 4797 subtests (chạy riêng, 2m35s) |
| `postgres` | database dùng một lần, **368 passed** + **89 passed / 19 subtests** — 420 ca `skipped` ở trên được phủ ở đây |
| `e2e` | 7/7 pass, **0 skipped** — có server thật, không in "khong co server" |
| `docker` | container healthy sau 6s, uid 10001 |
| `pinned-import` | `IMPORT OK, 62 đường dẫn` với fastapi 0.115.6 |
| `guard` | `Repo guard passed tracked tree: 862 file scan(s)` |

**Một cảnh báo về phép đo của chính tôi:** lượt chạy `gate.sh ruff` đầu tiên của
tôi ĐỎ với 3 lỗi — và cả ba nằm trong `tests/qa/rd-qa-36/di-bo-ban-be.py`, một
**bản nháp untracked của chính tôi** từ lượt trước, không thuộc PR nào. Cổng ruff
quét cả file untracked. Chuyển bản nháp ra ngoài rồi chạy lại: 4/4 chặng ĐẠT.
Nếu tôi dừng ở lần đo đầu, tôi đã nộp một phiếu lỗi cho lane khác về rác của
mình.

## 7. Ô CHƯA QUÉT

- **`check_pinned_import.sh` khi không có docker / daemon chết** (đường thoát 2).
  Không mô phỏng được ở đây; đọc code thì đúng, nhưng đọc code không phải phép đo.
- **Hai lane chạy đồng thời trên cùng tag ảnh.** Script mặc định
  `mobile-api:gate` — đúng tag toàn cục tôi đã báo cho chặng `docker` ở #291. Nó
  **luôn build lại từ cây của người gọi** nên cửa sổ hẹp, và canary sẽ bắt được
  nếu ảnh lệch bản. Nhưng khe giữa `docker build -t` và `docker run` thì tôi
  **không** đo. Gợi ý: mặc định tag theo cây thay vì hằng số toàn cục.
- **`gate.sh mobile` và `e2e` không được chạy riêng cho hai PR** — chúng chỉ chạy
  trong lượt `gate.sh` đầy đủ trên `main`. Cả hai PR không chạm `apps/mobile/`.
- **#285 (đã merge, `4512290`) chưa từng có phán quyết QA của tôi.** Nó vào `main`
  trong lúc tôi đo. Cổng đầy đủ ở mục 6 chạy **sau** khi nó đã ở `main`, nên
  "main xanh" có bao nó — nhưng đó không phải là đã test nó.
- **#274 (của tôi) vẫn kẹt** ở cổng ratchet vì định dạng
  `tests/qa/qa-tt-0017/mutants.py`, và Lead lưu ý #280 có thể đã xử phát hiện của
  nó theo đường khác. Cần rebase lên `main` mới rồi **đo lại**, không chỉ chạy
  `ruff format`.
- **Mã VietQR quét bằng app ngân hàng thật** — vẫn chưa ai làm. Không agent nào
  quét được mã QR.

## 8. Kỹ năng đã dùng

- `e2e-testing` — dựng thứ tự chặng (cổng rẻ trước, docker/postgres/e2e sau) và
  luật "`skipped` không phải xanh", chính nó đẩy tôi chạy tầng postgres thay vì
  đọc 420 ca bỏ qua thành xanh.
- `bug-reproduction` — bảng đột biến ở mục 2 là "đỏ trước, xanh sau" áp cho một
  **cổng** thay vì cho một bản vá: neo phải duy nhất (`text.count(old) != 1` thì
  báo *không đo được*, không âm thầm vá nhầm bản sao), khôi phục nằm trong
  `finally`, và mỗi hàng phải đỏ **đúng lý do** chứ không chỉ đỏ.
