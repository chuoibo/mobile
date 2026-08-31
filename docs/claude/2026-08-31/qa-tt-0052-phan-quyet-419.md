# FAIL — PR #419 tại `827b918`

Ý tưởng của PR đúng và vẫn cần thiết. Bản vá thì **không gộp được**: nó ghim hai
cái tên wrapper mà client không còn khai báo từ khi #397 lên main, nên cây gộp
làm chính cổng này chết — `exit 2`, "KHÔNG CHẠY ĐƯỢC", trong khi `--selftest`
vẫn báo ĐẠT.

```
protocol_version : v1
verdict          : REQUEST_CHANGES (FAIL)
đo tại           : 827b918452c63214d34f47325afdf79d0771a825  (head #419)
sha này          : nhánh chưa merge, dựng trên a6fdbe4
đối chứng        : origin/main adca3ae, rồi kiểm lại tại 2fcd723
blocker          : 1 (loại "vi phạm spec/cổng")
suggestion       : 1
```

Main nhích hai lần trong lúc tôi đo (`adca3ae` → `2fcd723`, tức #422 rồi #423).
Ba file quyết định kết luận này — `scripts/check_api_contract.py`,
`tests/test_api_contract.py`, `apps/mobile/src/api.ts` — **không đổi** giữa hai
mốc đó, và tôi đã chạy lại phép gộp ở mốc mới: cùng kết quả.

---

## Blocker — cây gộp làm cổng chết, và `--selftest` không thấy

Nhánh #419 dựng trên `a6fdbe4`, **trước** khi #397 (`8312042`) lên main. #397 đã
tách `call`/`translated` thành bốn tên: `callAsActor`, `callAnonymous`,
`translatedAsActor`, `translatedAnonymous`.

#419 thêm một danh sách neo **viết tay thứ hai**:

```python
CLIENT_WRAPPERS = ("call", "translated")     # scripts/check_api_contract.py:471
```

Hai cái tên đó không còn được khai báo ở đâu trong `apps/mobile/src`.

Khi gộp, git **chỉ báo một xung đột duy nhất**, và nó nằm ở dòng
`wrapper=name in ...` chứ không nằm ở danh sách. Vùng
`REQUEST_FUNCTIONS` / `CLIENT_WRAPPERS` được **tự động nhập, im lặng**, ra một
file có `REQUEST_FUNCTIONS` bốn tên mới của main đứng cạnh `CLIENT_WRAPPERS` hai
tên đã chết:

```
$ git checkout 827b918 && git merge origin/main
CONFLICT (content): Merge conflict in scripts/check_api_contract.py
Auto-merging tests/test_api_contract.py          <-- không xung đột, và đó là vấn đề

$ python3 scripts/check_api_contract.py
KHÔNG CHẠY ĐƯỢC: bộ đọc mất dấu wrapper của client, nên con số bên dưới không nói lên điều gì:
  - `call` không còn được khai báo ở đâu trong apps/mobile/src ...
  - `translated` không còn được khai báo ở đâu trong apps/mobile/src ...
EXIT=2
```

**Cả hai cách gỡ xung đột đều chết y hệt** — tôi thử cả hai để kết luận này không
phụ thuộc vào việc tôi gỡ xung đột kiểu nào:

| gỡ xung đột | gate |
|---|---|
| giữ `wrapper=name in WRAPPERS` (bản main) | `EXIT=2` |
| giữ `wrapper=name in CLIENT_WRAPPERS` (bản #419) | `EXIT=2` |

Lý do cả hai đều chết: `lost_wrappers()` được gọi trong `check()` **trước** mọi
thứ khác, nên cách gỡ dòng `CallSite.wrapper` không cứu được gì.

`scripts/gate.sh:338` chạy script trần, nên `exit 2` = `make gate` đỏ trên main.

### Điều làm blocker này nặng hơn: thông điệp lỗi nói sai

Cổng in "bộ đọc mất dấu wrapper của client... mọi lời gọi qua nó giờ vô hình".
Trên cây gộp, câu đó **sai**. Bộ đọc đọc client tốt — 67 đường dẫn qua bốn tên
mới. Cái lệch là `CLIENT_WRAPPERS`, một bản sao thứ hai của danh sách. Người nhận
báo lỗi này sẽ đi tìm bug ở `api.ts` chứ không ở cổng.

Đúng cái docstring của chính PR đã cảnh báo, hai dòng ngay phía trên:

> *"Read from the one list, not spelled a second time here: two copies of the
> same names is how a rename updates one of them."*

### Và `--selftest` báo ĐẠT ở đúng khoảnh khắc đó

Trên cây gộp, cùng một lúc:

```
python3 scripts/check_api_contract.py            -> EXIT=2   (chết)
python3 scripts/check_api_contract.py --selftest -> EXIT=0   "Tự kiểm ĐẠT" (18/18)
```

Canary tự viết nguồn của nó, nên nó chấm bộ đọc chứ không chạm client thật. Một
cổng mà tầng tự kiểm không nhìn thấy được cái chết của tầng chạy thật thì tầng tự
kiểm không bảo lãnh được gì cho tầng kia — ghi lại để lần sau không ai đọc
`--selftest` xanh thành "cổng khoẻ".

### Tiêu chí gỡ chặn

1. Rebase lên main hiện tại.
2. Đừng thêm danh sách tên thứ ba. Main đã có
   `WRAPPERS = tuple(name for name in REQUEST_FUNCTIONS if name not in DIRECT_FETCH)`
   — **suy ra**, không chép. Cho `lost_wrappers()` đọc `WRAPPERS`, bỏ hẳn
   `CLIENT_WRAPPERS`.
3. Chứng minh lại bằng: `python3 scripts/check_api_contract.py` thoát 0 trên cây
   gộp, và probe kèm dưới đây báo "Đã bịt" cho cả bốn tên.

---

## Phần đúng của PR — đừng đóng nó, khoảng trống vẫn mở

Tôi kiểm giả thuyết "#397 đã bịt rồi, #419 thừa". **Không thừa.**

Trên `main` sạch, đổi tên một wrapper trong client rồi chạy cổng:

```
$ python3 tests/qa/qa-tt-0052-neo-wrapper/probe_neo_wrapper.py

NỀN            : 67 đường dẫn / 79 lần gọi, 0 finding
Đổi tên callAnonymous       : 67 đường dẫn / 77 lần gọi, 0 finding, mất 0 đường dẫn
Đổi tên callAsActor         : 52 đường dẫn / 62 lần gọi, 0 finding, mất 15 đường dẫn   <-- MÙ, vẫn thoát 0
Đổi tên translatedAnonymous : 64 đường dẫn / 75 lần gọi, 0 finding, mất 3 đường dẫn    <-- MÙ, vẫn thoát 0
Đổi tên translatedAsActor   : 29 đường dẫn / 40 lần gọi, 0 finding, mất 38 đường dẫn   <-- MÙ, vẫn thoát 0
```

Đổi tên `translatedAsActor` làm rơi **38/67 đường dẫn (57%)** và
`scripts/check_api_contract.py` vẫn in "Client và máy chủ khớp hợp đồng", thoát
0. Cái bắt được nó là `tests/test_api_contract.py`, chứ không phải cổng:

```
$ # tren main, doi ten callAsActor -> callAsActorV2 trong apps/mobile/src
$ python3 scripts/check_api_contract.py       -> EXIT=0  "khớp hợp đồng"  (67 -> 52 duong dan)
$ python3 -m pytest tests/test_api_contract.py -q
FAILED ReaderDoesNotGoBlind::test_every_wrapper_it_reads_is_still_declared_in_api_ts
AssertionError: Lists differ: ['callAsActor'] != []
1 failed, 12 passed
$ # khoi phuc cay, cung ca test do:
13 passed
```

Nên vị trí #419 chọn — kiểm **bên trong `check()`**, để mã thoát của chính script
biết mình mù — là đúng và main chưa có. Đây là lý do phán quyết là
`REQUEST_CHANGES` chứ không phải `REJECT`.

Một thứ tôi ngờ mà hoá ra **không** thủng: wrapper **mới thêm** (chứ không phải
đổi tên). Thêm `postJson` gọi route không tồn tại vào `api.ts` trên main → cổng
`EXIT=2` với ba finding "có chỗ mới", vì bộ đếm ghim bắt được. Không phải lỗ hổng.

---

## Bảng đột biến — commit trước, rồi mới đột biến

Chạy trên `827b918` (chưa gộp), nền: `22 passed`, `--selftest` exit 0.

| # | đột biến | `tests/test_api_contract.py` | `--selftest` | kết |
|---|---|---|---|---|
| M1 | `lost_wrappers()` luôn trả `[]` | 3 failed | exit 1 | **giết** |
| M2 | `CLIENT_WRAPPERS = ("call",)` | 2 failed | exit 1 | **giết** |
| M3 | thêm `import` vào từ khoá khai báo | 22 passed | exit 0 | *tương đương* |
| M3' | bỏ hẳn từ khoá khai báo (tên trần) | 1 failed | exit 1 | **giết** |
| M4 | gỡ `lost_wrappers()` ra khỏi `check()` | 1 failed | exit 0 | **giết** |

M3 **sống nhưng là đột biến tương đương**, không phải lỗ hổng: regex thành
`(?:function|const|let|var|import)\s+call`, mà văn bản thật là `import { call` —
có dấu `{` chen giữa nên không khớp. M3' là bản không-tương-đương của cùng câu
hỏi và nó bị giết. Ghi cả hai dòng vì một bảng chỉ có M3 sẽ bị đọc thành "nhánh
loại trừ import không được gác", và đó là kết luận sai.

M4 đáng chú ý theo hướng khác: dây nối `lost_wrappers` → `check()` chỉ có **đúng
một** ca gác, và `--selftest` xanh khi cắt dây. Không phải blocker, nhưng đó là
điểm mỏng nhất của bản vá.

**4/4 đột biến không-tương-đương bị giết.** Bộ test của #419 là thật.

---

## Suggestion (không chặn) — dây nối chỉ có một ca gác

M4 cho thấy gỡ lời gọi `lost_wrappers()` khỏi `check()` chỉ làm đỏ một ca, và
`--selftest` không thấy gì. Khi rebase, cân nhắc để `--selftest` chạm được cả
đường `check()` chứ không chỉ `findings_for_source`, vì đó là nửa thật sự sẽ mục.

---

## Đã chạy

| lệnh | ở đâu | kết quả |
|---|---|---|
| `python3 -m pytest services/api/tests tests -q` | 827b918 | **2680 passed, 580 skipped, 4891 subtests** |
| `python3 scripts/check_api_contract.py` | 827b918 | exit 0, 67 đường dẫn / 76 lần gọi |
| `python3 scripts/check_api_contract.py --selftest` | 827b918 | exit 0, 10/10 canary ĐẠT |
| `$(scripts/ruff_pinned.sh) format --check` + `check` (2 file PR sửa) | 827b918 | `2 files already formatted`, `All checks passed!` (ruff 0.9.2 ghim) |
| `git merge origin/main` + gate | 827b918 ⊕ adca3ae | **exit 2**, cả hai cách gỡ xung đột |
| lặp lại phép gộp | 827b918 ⊕ 2fcd723 | **exit 2**, y hệt |
| `probe_neo_wrapper.py` | main | mù ở **3/4** wrapper |
| bảng đột biến M1–M4 + M3' | 827b918 | 4/4 không-tương-đương bị giết |

## Ô CHƯA quét

- `tests/postgres` — không chạy. PR không chạm persistence, nhưng đây là ô trống.
- `apps/mobile && npm test` — chưa chạy ở lượt này; PR chỉ sửa hai file Python.
- `npm run test:e2e` / lát cắt dọc trên server sống — chưa chạy.
- Trang khách, ma trận thiết bị/theme — không liên quan PR này, chưa quét.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, vẫn cần leader.
