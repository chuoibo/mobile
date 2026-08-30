# Phán quyết QA — PR #297 (backend/tt-0014, trần gọi model của `GET /places`)

    FAIL
    Lý do: hành vi sản phẩm ĐẠT và đã đo được trên app thật — 20 caller song song
    mua đúng 1 lời gọi model, 200 request ẩn danh mua đúng 1, dữ liệu vẫn đúng khi
    một hàng bị từ chối. Nhưng cây gộp ĐỎ cổng `ruff format --check`, và dòng sai
    định dạng nằm trong chính code mới của PR (`places.py` sạch trên main). Một
    lệnh gỡ được. Đây đúng hình dạng đã giữ #274 đỏ.

    protocol_version : v1
    đo tại           : b87fb48 = merge(f3137f4 ⊕ origin/main@56a2c19)
    sha này          : chưa merge — f3137f4 là head PR #297, ĐỨNG SAU main
                       (merge-base ca5e7e8; main đã nhích 3 commit: 56a2c19,
                       3442269, a1bb823). Cả 3 commit đó KHÔNG chạm places.py /
                       main.py / app/ai — gộp sạch, không xung đột.
    verdict          : FAIL (một blocker loại 1: vi phạm cổng)
    kỹ năng đã dùng  : e2e-testing, bug-reproduction

---

## 1. Blocker duy nhất — cổng ruff đỏ vì dòng của chính PR

`scripts/gate.sh ruff` trên cây gộp:

```
so với merge base 56a2c1915e4f11485b1f89adafc3e1981f18aa75
ruff 0.9.2 (bản ghim) tại /home/lakiet/miniconda3/bin/ruff
ruff over 6 changed Python file(s): ...
--- ruff check ---            All checks passed!
--- ruff format --check ---   Would reformat: services/api/app/api/routes/places.py
                              1 file would be reformatted, 5 files already formatted
::error::ruff rejected files this change touches -- fix them, or narrow the change
GATE rc=1
```

**Dẫn chứng nó là nợ MỚI, không phải nợ cũ bị đổ lên đầu PR** — cùng binary ghim,
cùng file, trên main:

```
$ cd /tmp/qa27-main && $RUFF format --check services/api/app/api/routes/places.py
1 file already formatted            rc=0
```

Dòng gây đỏ, do commit f3137f4 thêm vào:

```diff
-                    self._asking.difference_update(
-                        row.place["id"] for row in missing
-                    )
+                    self._asking.difference_update(row.place["id"] for row in missing)
```

**Tiêu chí gỡ chặn** — một lệnh, dùng bản GHIM chứ không phải ruff trên PATH:

```bash
$(scripts/ruff_pinned.sh) format services/api/app/api/routes/places.py
```

> Ghi chú cho người chạy lại: `scripts/ruff_pinned.sh check <file>` **không lint gì
> cả**. Script chỉ *in đường dẫn* tới ruff ghim rồi `exit 0`; tham số bị nuốt. Lượt
> này tôi đã ăn đúng cái bẫy đó và đọc nhầm một `rc=0` rỗng thành "sạch". Đúng cú
> pháp là `$(scripts/ruff_pinned.sh) check <file>`.

---

## 2. Phần Lead nhờ đo — hành vi trên app THẬT dưới tải đồng thời: ĐẠT

Lead đã đo được lỗ 20-song-song ở tầng unit và nhờ xác nhận trên app thật. Đây là
kết quả.

### Cách đo — và vì sao nó không phải "tự sửa môi trường để ép pass"

Chạy **uvicorn thật**, `create_app()` thật, `GET /places` thật qua HTTP. Chỉ vá
**đúng biên mạng** `app.places.reasons._post` bằng một stub biết đếm và ngủ 0.8s
(một round trip Gemini thật là vài giây; không có độ trễ thì 20 request không thật
sự chồng lên nhau và bản HỎNG sẽ trông như đã sửa).

`CachedReasonWriter` — thứ đang bị kiểm — chạy nguyên vẹn. `gemini_reasons`,
`parse_reasons`, `ungrounded_numbers` cũng nguyên vẹn.

Hàng bị từ chối được tạo đúng đường sản phẩm: canned response gán cho một place một
con số không có trong record của nó, `ungrounded_numbers` bắt được, `parse_reasons`
thả hàng đó. Đó chính là "hàng model không trả lời" mà PR nói tới.

**Phép đo tự chứng minh nó không mù**: cùng một harness cho ĐỎ trên main và trên
78b8148, XANH chỉ trên f3137f4.

### Ma trận 3 cây × 2 kiểu tải — số lời gọi model thật

| cây | 20 tuần tự | 20 song song (cold) |
|---|---|---|
| `origin/main` (trước PR) | **20** | **20** |
| `78b8148` (commit 1 của PR) | 1 | **20** |
| `f3137f4 ⊕ main` (bản sẽ ship) | 1 | **1** |

Đọc bảng: commit 1 đóng lỗ *tuần tự*; commit 2 (`_asking`) đóng lỗ *song song*.
Cả hai commit đều load-bearing, không commit nào thừa.

### Mối đe doạ trong docstring, đo thẳng: `while true; do curl; done -P 20`

200 request ẩn danh (route này **không có actor**, không header, không auth):

```
MAIN     : {"tong_request":200,"http_ok":200,"MODEL_CALLS":200,"giay":3.3,"call_moi_request":1.0}
f3137f4  : {"tong_request":200,"http_ok":200,"MODEL_CALLS":1,  "giay":0.5,"call_moi_request":0.005}
```

Main đốt **200 lời gọi lên khoá trả tiền dùng chung trong 3,3 giây** từ một GET
không cần đăng nhập. Bản PR đốt 1. Đây là phần đáng giá nhất của PR này.

### Dữ liệu có còn đúng khi một hàng bị từ chối không? — CÓ

Mọi response, mọi cây, mọi kiểu tải:

```
so_place: 12   co_score: 12   source_ai: 11   source_none: 1
refused_source: "none"   refused_score: 96   verdict_none_khi_source_none: true
http_ok: 20/20, 200/200 — không một 5xx nào
```

Hàng bị từ chối **giữ nguyên điểm và mất đúng nhãn AI** — đúng hợp đồng ở đầu
`places.py` ("không bao giờ hiện chữ AI MATCH trừ khi model thật sự trả lời cho card
đó"). 11 hàng còn lại không bị kéo theo.

### Cooldown 60s — đo bằng đồng hồ thật, không phải clock giả

Không dùng fake clock (đồng hồ giả đứng yên là cách một đột biến dời mốc cửa sổ đi
qua mà vẫn xanh). Chờ thật:

```
storm 20 song song      -> MODEL_CALLS = 1
ngay sau storm          -> ai 11/12, MODEL_CALLS = 1   (catalogue phục hồi)
lần kế tiếp             -> ai 11/12, MODEL_CALLS = 1   (phục vụ từ cache)
sau 65s                 -> ai 11/12, MODEL_CALLS = 2   (hỏi lại đúng 1 lần)
ngay sau đó             -> ai 11/12, MODEL_CALLS = 2   (vào lại cooldown)
```

Không tombstone: hàng bị từ chối được hỏi lại sau đúng một phút, và không hỏi thêm
lần nào trong phút đó.

---

## 3. Test của PR có phải cổng thật không? — CÓ

Bê nguyên `test_places_reason_retry_storm.py` của f3137f4 sang cây `78b8148` (bản
thiếu `_asking`):

```
FAILED ... ::test_a_fleet_of_concurrent_callers_buys_one_model_call_not_one_each
FAILED ... ::test_a_writer_that_raises_is_cooled_down_like_one_that_answers_nothing
2 failed, 8 passed
```

Đỏ **đúng hai tính chất** commit 2 thêm vào, và đỏ đúng lý do (ca thứ hai ném thẳng
`RuntimeError: model unreachable` — tức là chưa có `finally`). Không phải đỏ vì
NameError hay vì hằng số phụ.

---

## 4. Các cổng khác trên cây gộp

| cổng | kết quả |
|---|---|
| `pytest services/api/tests tests -q` | **2181 passed, 421 skipped, 4797 subtests passed** (172s) |
| `gate.sh pinned-import` | ĐẠT |
| `gate.sh docker` | ĐẠT — build, non-root uid 10001, không có tooling test, container healthy sau 6s |
| `gate.sh ruff` — `ruff check` | ĐẠT (All checks passed) |
| `gate.sh ruff` — `ruff format --check` | **HỎNG** ← blocker duy nhất |

Chặng docker chạy vì ràng buộc Lead vừa tự đặt (PR đổi khai báo route / dependency
thì không merge trước khi docker xanh). PR này đổi chữ ký `get_reason_writer` và
thêm `app.state.reason_writer`; cả hai qua được bản fastapi ghim.

---

## 5. Quan sát sản phẩm — không phải blocker, nhưng Lead nên biết

Trên **catalogue nguội gặp một burst**, 19/20 first load render **không có nhãn AI
nào cả** — không phải mất mỗi hàng bị từ chối, mà mất cả 12:

```
storm_nhan_ai_moi_response: [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,11]
```

Docstring của PR nói thẳng ra đây là đánh đổi có chủ ý (giữ lock qua round trip
model thì mọi browse xếp hàng sau một lời gọi), và nó **tự lành sau đúng một
request**. Tôi phân loại là *suggestion*, không phải blocker: không sai tiền, không
rò rỉ, không vi phạm spec.

Nhưng nó chạm đúng màn hero của PoC — Khám phá là chỗ chữ **AI MATCH** phải xuất
hiện. Kịch bản thật: process vừa restart xong, vài người mở app cùng lúc → gần như
tất cả thấy một màn Khám phá không có AI MATCH nào, rồi phải kéo refresh. Nếu Lead
thấy điều đó đắt hơn 2 giây chờ, thì đó là một quyết định sản phẩm, không phải một
lỗi của PR này.

---

## 6. Ô CHƯA quét

- **Nhiều worker / nhiều process.** `CachedReasonWriter` là state trong một process.
  Đo ở đây là uvicorn 1 worker. Deploy `--workers N` thì trần thành N lời gọi mỗi
  phút, không phải 1. Chưa ai nói production chạy mấy worker.
- **Gemini thật.** Mọi con số trên đây dùng `_post` stub để đếm được. Chưa bắn một
  request thật nào lên model bằng khoá thật trong lượt này.
- **Sáu cửa Gemini còn lại.** Chỉ đo `GET /places`. Năm route có limiter và
  `POST /places/search` không nằm trong phạm vi lượt này.
- **`tests/postgres`** — 421 skipped, tầng live không chạy (không đặt
  `MOBILE_TEST_DATABASE_URL`). PR không chạm persistence nên tôi không coi là thiếu,
  nhưng skip không phải xanh.
- **`apps/mobile` npm test / expo export** — PR không chạm mobile; chưa chạy.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, ngoài phạm vi PR này.

---

## 7. Tái lập

```bash
git worktree add --detach /tmp/qa27-main origin/main
git worktree add --detach /tmp/qa27-mid  78b8148
git worktree add --detach /tmp/qa27-pr   f3137f4 && cd /tmp/qa27-pr && git merge origin/main

tests/qa/qa-tt-0027/run_tree.sh    /tmp/qa27-main 8131 par 20   # -> MODEL_CALLS 20
tests/qa/qa-tt-0027/run_tree.sh    /tmp/qa27-mid  8132 par 20   # -> MODEL_CALLS 20
tests/qa/qa-tt-0027/run_tree.sh    /tmp/qa27-pr   8133 par 20   # -> MODEL_CALLS 1
tests/qa/qa-tt-0027/run_flood.sh   /tmp/qa27-pr   8133          # -> 200 request, 1 call
tests/qa/qa-tt-0027/run_recover.sh /tmp/qa27-pr   8133          # -> cooldown 60s thật
```

`PYTHONPATH` phải trỏ vào `<cây>/services/api` — các script đã tự đặt.
