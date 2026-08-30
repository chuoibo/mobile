# FAIL cho #359 — cổng persona demo

**Verdict: `FAIL`**

**Lý do (đọc trước phần chi tiết):** hai điều, cả hai đều sửa nhỏ.

1. **Nhánh không gộp được vào `main`.** `Makefile` xung đột ở dòng `.PHONY`:
   #359 thêm `demo-persona-check`, còn `#350` (đã vào main) thêm `demo-reset`.
   Tái lập độc lập bằng `git merge-tree` trên hai ref sạch, không cần cây local.
2. **Cổng báo `SẠCH` khi nó đo ĐÚNG KHÔNG NGƯỜI NÀO.** Cho danh sách persona rỗng
   thì nó in `SẠCH — cả 0 persona demo...` và thoát **0**. Không có dòng nào
   khẳng định "tôi vừa đo bảy người". Mẫu số không được gác.

Ô (2) không phải giả định: cổng đọc `PEOPLE` từ `scripts/seed_demo_data.py`, và
`main` vừa sửa đúng file đó hôm nay ở `09559ec` (#350). File làm mẫu số đang
được sửa dưới chân cổng.

**Phần còn lại của PR thì đúng, và đo lại được.** Số trong mô tả PR tái lập
chính xác trên máy tôi, và đối chứng dương xanh thật — nên cái đỏ không phải do
môi trường chết.

---

## Đo tại đâu

```
nhánh PR   : devops/cong-persona-demo-sach @ 393aff7cba42
cây đã đo  : CÂY GỘP 393aff7 ⊕ origin/main@159694b  (Makefile gỡ xung đột tại chỗ, KHÔNG đẩy)
sha này    : nhánh CHƯA merge — đi sau main; `git merge-tree` trả CONFLICT
```

`main` nhích 4 commit giữa lượt đo (`2ca428c` #361, `44c1912` #348, `f752ba7`
README, `159694b` #362). Tôi **đã dựng lại cây gộp và chạy lại cổng backend trên
`main` mới** chứ không giữ số cũ — số dưới đây là của `main@159694b`.

## Bảng hai chiều — cái làm cho phán quyết này có nghĩa

Cùng một script, cùng bảy id, hai thế giới:

| thế giới | kỳ vọng | đo được |
|---|---|---|
| máy demo 8099 (dùng chung, bẩn) | exit 1 | **exit 1**, 16 vi phạm, cả 7 persona BẨN |
| stack sạch `dopersona2` (8489/5479) | exit 0 | **exit 0**, cả 7 persona sạch |

Dòng thứ hai là dòng chịu lực. Một bảng toàn đỏ không phân biệt được "cổng có
răng" với "môi trường chết" — chính lỗi đã làm hỏng lượt đo #354 hôm nay. Ở đây
cổng **xanh được**, nên cái đỏ ở dòng trên là phát hiện thật.

Số tái lập khớp mô tả PR đến từng đồng:

```
Minh   API spend=3.613.333đ/21 chi   riêng nhóm demo 1.603.666đ/9 chi
Trang  API spend=3.690.336đ/22 chi   riêng nhóm demo 1.593.666đ/9 chi
Hải    API spend=3.463.334đ/20 chi   riêng nhóm demo 1.603.668đ/9 chi
```

Và `D` bắt được đúng cái mà `JOIN` sẽ đánh rơi im lặng — một context mồ côi:

```
'<context 1aa00000-aaaa-4aaa-8aaa-0000a0000001 không có trong contexts>' 329.667đ/1 chi
```

`LEFT JOIN` ở đây là quyết định đúng, và tôi xác nhận nó có hậu quả đo được chứ
không phải phòng thủ trang trí.

## Blocker 1 — không gộp được

```
$ git merge-tree --write-tree origin/main origin/devops/cong-persona-demo-sach
EXIT=1
CONFLICT (content): Merge conflict in Makefile
```

Xung đột nằm ở dòng `.PHONY`: hai nhánh cùng thêm một target vào cùng một dòng.

| bên | phần đuôi dòng `.PHONY` |
|---|---|
| nhánh #359 | `... demo-check demo-data-check demo-persona-check demo-watch ...` |
| `origin/main` | `... demo-check demo-data-check demo-watch ... demo-reset` |

Gỡ bằng cách lấy hợp của hai danh sách (giữ cả `demo-persona-check` lẫn
`demo-reset`).

(Báo cáo này cố ý **không** dán dấu xung đột nguyên văn: `repo_guard` chặn đúng
chuỗi đó, và nó đã chặn commit đầu của tôi — cổng làm đúng việc.) Tôi đã gỡ tại chỗ **chỉ để đo**, không
đẩy — người sở hữu nhánh gộp và đẩy.

**Tiêu chí gỡ chặn:** `git merge-tree --write-tree origin/main <nhánh>` thoát 0.

## Blocker 2 — mẫu số không được gác

Loại: **hỏng tính hợp lệ thí nghiệm**.

Đột biến tại chỗ, chạy trên **stack sạch** (nơi nền là exit 0, nên mọi thay đổi
đều đọc được):

```python
-    return list(seed.PEOPLE), seed.GROUP_NAME
+    return [], seed.GROUP_NAME
```

```
SẠCH — cả 0 persona demo chỉ có lịch sử trong 'Team Đà Lạt'.
H1 EXIT=0
```

Nền chưa đột biến cũng exit 0 → **cổng mù hoàn toàn với đột biến này**. Nó không
đổi màu, không đổi mã thoát, và câu nó in ra (`cả 0 persona`) là câu duy nhất tố
cáo nó — mà không ai đọc stdout của một cổng đã xanh.

Điều làm nó đáng chặn chứ không phải đáng ghi chú: docstring của chính cổng nói
lý do nó đọc `PEOPLE` từ builder là *"A hand-written list here would keep passing
on the day somebody adds an eighth demo person"*. Tức tác giả đã gác **người thứ
tám**, nhưng chưa gác **người thứ không**. Và `seed_demo_data.py` vừa bị #350 sửa
sáng nay — đây là file đang chuyển động, không phải hằng số.

**Tiêu chí gỡ chặn:** cổng từ chối kết luận khi không đọc được đủ người. Một dòng
là đủ, ví dụ:

```python
if len(people) < 7:
    return die(f"chỉ đọc được {len(people)} persona từ seed_demo_data.py, cần 7")
```

Xanh lại khi: chạy lại đúng đột biến trên và cổng thoát **2**, còn bản thường vẫn
thoát 0 trên stack sạch và 1 trên 8099.

## Suggestion (KHÔNG chặn) — phép đo chết đang đọc thành sản phẩm bẩn

Đổi tên một trường mà API trả về (mô phỏng API đổi hình dạng):

```python
-  if m["context_id"] != str(keeper)
+  if m["ctx_id_DOI_TEN"] != str(keeper)
```

```
KeyError: 'ctx_id_DOI_TEN'
EXIT=1
```

`1` là `EXIT_DIRTY` theo chính hợp đồng của cổng. Ai đọc mã thoát mà không đọc
traceback sẽ kết luận "persona bẩn" trong khi thật ra là "cổng gãy".

Đây đúng là điều docstring của cổng đã tự dặn: *"gộp một phép đo chết vào một sản
phẩm hỏng là đúng cái kiểu sai repo này vẫn tìm."* Trường hợp "số đổi giữa lúc
đo" đã được gác cẩn thận thành exit 2; trường hợp "API đổi hình dạng" thì chưa.
Bọc thân `main()` để mọi `KeyError`/`TypeError` từ thân JSON rơi về `die()` là
khép kín được.

Tôi để đây là suggestion vì traceback vẫn hiện ra và người chạy tay sẽ thấy —
khác với blocker 2 vốn im lặng.

## Suggestion (KHÔNG chặn) — chưa ai gọi cổng này định kỳ

`demo-persona-check` chỉ xuất hiện đúng hai chỗ trong cả cây: dòng `.PHONY` và
chính định nghĩa target. Không test, không `make gate`, không CI, và **không nằm
trong `demo_watch.py`** — watcher định kỳ chạy `check_demo_matches_main.py`
(`GATE_RELPATH`), không chạy cổng này.

Nói thẳng vì sao tôi vẫn không chặn: chính Makefile của PR ghi rõ mục nào là
"gọi TAY" và mục nào là "gọi ĐỊNH KỲ", và tác giả đặt nó vào nhóm tay một cách có
ý thức. Nhưng lý do PR tự nêu để viết cổng là *"sửa xong một lần rồi nhìn bằng
mắt thì hôm sau nó bẩn lại mà không ai biết"* — mà một target không ai gọi thì
hỏng theo đúng kiểu đó. Cắm nó vào `demo_watch` là việc chạm hạ tầng canh của
devops, nên để tác giả quyết.

## Cổng đã chạy (cây gộp `393aff7 ⊕ main@159694b`)

```
python3 -m pytest services/api/tests tests -q
  -> 2591 passed, 552 skipped, 4902 subtests passed in 305.18s

ruff check scripts/cong_persona_demo_sach.py         -> All checks passed!
ruff format --check scripts/cong_persona_demo_sach.py -> 1 file already formatted
python3 scripts/repo_guard.py tree HEAD              -> passed, 1051 file scan(s)
```

## Ô CHƯA quét — đọc phần này trước khi tin phần trên

- **`cd apps/mobile && npm test` — CHƯA CHẠY.** `node_modules` chưa cài trong cây
  gộp tạm (`tests/test_phone_path.py:398` skip đúng vì lý do đó). PR không chạm
  file frontend nào — diff là `Makefile` + `scripts/cong_persona_demo_sach.py` —
  nhưng tôi không đọc điều đó thành "đã xanh".
- **`tests/postgres` — CHƯA CHẠY** với `MOBILE_REQUIRE_POSTGRES_TESTS=1`. 552
  skipped ở trên có phần lớn là tầng này. PR không thêm hành vi persistence nào.
- **Đối chứng CẮN bằng cách ghi dữ liệu bẩn thật** — tôi **cố ý không làm**.
  `confirmed_allocations` là append-only, trigger chặn DELETE; ghi vào stack sạch
  là phá vĩnh viễn chính cái đối chứng dương mà phán quyết này dựa vào. Tác giả
  đã làm phép thử đó (777.000đ cho Minh qua route thật) và tôi **không tái lập
  độc lập** — ô này ghi là chưa quét, không ghi là đã xác nhận.
- **Cổng có bắt được persona thứ 8 không** — chưa quét. Tôi gác được đầu "không
  người", chưa đo đầu "thêm người".
- Repo này **chưa có bằng chứng hành vi nào** (ADR-0006). Xanh nghĩa là code làm
  đúng điều tác giả nghĩ.

## Đánh giá chung

Đây là cổng được viết cẩn thận, và hai chỗ tôi định bắt thì tự nó đã gác sẵn:
đọc id từ builder chứ không chép tay, và tách exit 2 khỏi exit 1. Tôi còn ngờ
`BEGIN ISOLATION LEVEL REPEATABLE READ` bị psycopg nuốt vì lệnh `SET` phía trước
đã mở giao dịch — **đo ra thì đúng là `repeatable read`**, ngờ sai, không phải
phát hiện.

Cái sót lại đúng một loại: gác được đầu trên của mẫu số, chưa gác đầu dưới.

---

đo tại `393aff7cba42` ⊕ `origin/main@159694b` · protocol_version v1 · verdict `FAIL`
· blocker còn mở: 2 (xung đột Makefile · mẫu số rỗng đọc thành SẠCH)
