# QA qa-tt-0021 — `FAIL` cho #283, và một sự cố đang mở trên `main`

**Phán quyết: `FAIL`.**

**Lý do, trước chi tiết:** #283 làm **API không khởi động được** trong ảnh Docker.
Route `DELETE .../reactions` mà nó thêm khai `status_code=204` trong một module có
`from __future__ import annotations`, và với **fastapi 0.115.6 — đúng bản
`requirements-dev.txt` ghim và ảnh Docker cài** — chuyện đó ném `AssertionError`
ngay lúc import. Máy tác giả và cây QA này có fastapi **0.135.3**, nơi lỗi đó
không tồn tại, nên 1852 ca pytest, `tests/postgres`, và 9 chặng cổng tác giả chạy
đều xanh thật lòng. Chặng `docker` là chặng duy nhất nạp app bằng bản đã ghim, và
nó **không nằm trong 9 chặng đó**.

Bốn tính chất nghiệm thu của PR thì **đều đúng** — tôi đo lại bằng hình dạng khác
và cả bốn đứng vững. Bản vá 422 cũng thật: nó bịt 5 hình dạng rò rỉ tôi tự viết.
Lỗi nằm ở một dòng decorator, không ở thiết kế.

> **#283 đã được merge lúc 04:37Z trong lúc tôi đang đo nó**, rồi #278 chồng lên.
> Nên đây không còn là phiếu chặn PR nữa mà là **sự cố trên `main`**, và
> **máy demo đã chết thật**: `mobile-local-api-1` ở trạng thái `Exited (1)`,
> `curl localhost:8099/healthz` không kết nối được. Đường hero đứt ở bước đầu tiên.

## Đo tại đâu

```
đo tại   2837a45   (origin/main hiện tại: #278 ⊕ #283 ⊕ main)
sha này  ĐÃ ở main
đối chứng 04c2992  (main ngay TRƯỚC #283)
cây gộp  66b0a3e   (main@04c2992 ⊕ PR@1ad971b, tôi tự gỡ xung đột để đo trước khi PR được merge)
```

Xung đột lúc đó nằm ở `services/api/app/api/service.py` và là **thuần cộng thêm** —
#282 và #283 cùng nối method vào sau `list_context_memories`. Tôi giữ cả hai khối;
cả 11 method của hai bên đều còn, và `alembic heads` ra **đúng một** head.

## Sự cố: API không khởi động được

```
$ bash scripts/gate.sh --strict docker        # tại 2837a45
container thoát trước khi healthy
AssertionError: Status code 204 must not have a response body
  File "/srv/app/api/routes/memories.py", line 143, in <module>
    @router.delete(
```

Máy demo, không phải chỉ cổng:

```
$ docker ps -a
mobile-local-api-1     Exited (1) 3 minutes ago
mobile-local-postgres-1  Up 33 hours (healthy)
$ curl -s -o /dev/null -w '%{http_code}' localhost:8099/healthz
000
$ docker logs mobile-local-api-1 | tail -1
AssertionError: Status code 204 must not have a response body
```

### Vì sao xanh ở máy dev, đỏ trong ảnh

`requirements-dev.txt` ghim `fastapi==0.115.6`; ảnh Docker cài đúng bản đó. Máy này
có `0.135.3` trên PATH. Trong 0.115.6:

```python
if self.response_model:
    assert is_body_allowed_for_status_code(status_code), ...
```

`memories.py:13` có `from __future__ import annotations`. Với annotation hoãn lại,
`-> None` được `get_type_hints` trả về **lớp `NoneType`**, không phải hằng `None`.
Lớp thì **truthy**, nên FastAPI tưởng route có response model và assert nổ ở 204.
Bản 0.135.3 đã sửa chỗ này — nên cùng một dòng code, một bản im lặng, một bản chết.

Đây đúng là hình dạng ["Công cụ trên PATH không phải bản repo ghim"]: cùng file,
một bản `exit 0`, một bản `exit 1`.

### Tái lập tối thiểu — 17 dòng

`tests/qa/qa-tt-0021/repro_204_response_model.py`, chạy trong **chính ảnh**:

```bash
docker run --rm -v .../repro_204_response_model.py:/t.py \
  --entrypoint /venv/bin/python mobile-api:gate /t.py
```

Bỏ dòng `from __future__ import annotations` đi thì nó in `imported fine`. Giữ lại
thì nó nổ. Tôi đã thu nhỏ từng biến một: `-> None` một mình **không** nổ;
`responses=ERRORS` một mình **không** nổ; chỉ tổ hợp với annotation hoãn lại mới nổ.
(Giả thuyết đầu của tôi — `-> None` là đủ — **sai**, và bản thu nhỏ đã bác nó.)

### Đối chứng đỏ-trước / xanh-sau

| cây | chặng `docker` |
|---|---|
| `04c2992` — main trước #283 | **ĐẠT**, container healthy sau 6s |
| `2837a45` — main hiện tại | **HỎNG**, container thoát khi import |
| `2837a45` + 1 dòng `response_model=None` | **ĐẠT**, container healthy sau 6s |

### Phạm vi: đúng một route

Quét toàn bộ `app/api/routes/`:

| file | dòng | 204 | `__future__` | trả về |
|---|---|---|---|---|
| `contexts.py` | 76 | ✔ | ✔ | `Response` — an toàn |
| `contexts.py` | 86 | ✔ | ✔ | `MembershipListResponse` — an toàn |
| `memories.py` | **145** | ✔ | ✔ | **`None` — nổ** |

Hai route 204 có sẵn trả `Response`, mà `lenient_issubclass(..., Response)` làm
FastAPI đặt `response_model = None`. Nên chúng chưa bao giờ chạm assert. Không có
route thứ hai nào đang nợ cùng lỗi này.

### Tiêu chí gỡ chặn

Thêm `response_model=None` vào decorator ở `memories.py:143-147`, rồi
`bash scripts/gate.sh --strict docker` phải **ĐẠT** trên `main`.

**Phân loại blocker:** loại 1 — vi phạm cổng (chặng `docker` của `test.yml`), và
trên thực tế là mất môi trường dùng chung.

## Phần #283 làm ĐÚNG — đo lại bằng hình dạng khác

Tôi không chạy lại bộ test của PR. Tôi viết phép đo riêng, cố tình chọn hình dạng
khác với hình dạng PR đã chọn, rồi **đột biến chính phép đo của mình** để chứng
minh nó biết đỏ và đỏ đúng chỗ.

### Bản vá 422 là thật — 5 hình dạng, đỏ trước xanh sau

`tests/qa/qa-tt-0021/probe_422_leak.py` viết **cùng một vi phạm** — câu người ta gõ
đi ngược ra trong thân lỗi — bằng **bảy** hình dạng. PR đo đúng một (thân bình luận
5800 ký tự).

| # | hình dạng | `04c2992` trước | `2837a45` sau |
|---|---|---|---|
| 1 | `messages.body` quá `max_length=4000` | **LEAK** qua `input` | sạch |
| 2 | `body` gửi thành **object** chứa câu đó | **LEAK** qua `input` | sạch |
| 3 | `body` gửi thành **list** chứa câu đó | **LEAK** qua `input` | sạch |
| 4 | `extra=forbid`, câu đó là **TÊN TRƯỜNG** | **LEAK** qua `loc` | **vẫn LEAK** |
| 5 | JSON hỏng mang câu đó | sạch | sạch |
| 6 | `memories.caption` quá `max_length=2000` | **LEAK** qua `input` | sạch |
| 7 | `comments.body` (hình dạng PR đo) | 404 — route chưa có | sạch |

`5 rò rỉ → 1`. Bản vá làm đúng điều nó khai, và rộng hơn một route như tác giả nói.

**Hình dạng 4 còn hở, và tôi cố ý KHÔNG gọi nó là blocker.** Handler giữ lại `loc`,
mà `loc` mang tên trường client gửi lên. Để câu riêng tư chảy qua đường đó, client
phải tự đặt câu người dùng gõ làm **khoá JSON** — client của sản phẩm không làm thế,
và tôi đã kiểm: không có trường `dict[str, ...]` nào trong `schemas.py` để khoá
người dùng rơi vào `loc`. Kẻ tấn công chỉ đọc lại được chuỗi của chính mình. Đây là
**suggestion**, không phải một trong 5 loại blocker. Chỗ đáng sửa là **câu chữ
docstring** — nó viết "It does not repeat what was sent", mà tên trường cũng là thứ
được gửi.

Và bản vá **không làm gãy client**: không chỗ nào trong `apps/mobile/src/` đọc
`.input`, không test nào assert lên `input` của một 422.

### Bốn ràng buộc nghiệm thu — 16/16, bằng đường đâm khác

`tests/qa/qa-tt-0021/walk_f40_f41.py`, PostgreSQL thật, HTTP thật, **hai nhóm** để
"tường nhóm khác" là một chỗ có thật chứ không phải một id bịa:

```
A. Leo chéo context -- context CỦA MÌNH trong path, memory của nhóm KHÁC
  PASS  thả tim lên memory nhóm B qua path nhóm A -> 404
  PASS  bình luận  -> 404      PASS  đọc bình luận -> 404
  PASS  không có gì được ghi vào tường B (reactions=0, comments=0)
B. Oracle 403/404 -- bốn tổ hợp id phải không phân biệt được
  PASS  người ngoài nhận đúng MỘT mã cho cả bốn: {403}
  PASS  và đúng MỘT thân trả lời
  PASS  khai X-Actor-Contexts trỏ đúng nhóm A vẫn 403  (lỗ #253)
  PASS  LEFT -> 403        PASS  INVITED -> 403
C. Quyền tác giả -- đâm qua QUERY STRING, không qua field đã bị forbid
  PASS  ?person_id=<người khác> bị bỏ qua, tim thuộc về người gọi
  PASS  ?author_id=<người khác> bị bỏ qua, bình luận thuộc về người gọi
D. Một người một tim -- 8 lần chạm ĐỒNG THỜI
  PASS  còn đúng 1 hàng; mã trả về [201, 409 x7]
E. Tim và bình luận không nhân nhau
  PASS  2 tim x 2 bình luận đọc ra 2/2, không phải 4/4
16/16 checks passed
```

Mọi lời gọi — kể cả của người ngoài — được phát **bộ role mạnh nhất**
(`member,group_admin`). Nếu vẫn bị từ chối thì nó bị từ chối vì **hàng membership
trong database**, không phải vì thiếu header.

Điểm A là đường đâm PR không viết: người gọi là thành viên **thật** của nhóm mình,
nên `_require_permission` **đi qua** — chỉ còn phép thu hẹp theo `context_id` trong
`get_context_memory` đứng giữa họ và tường nhóm khác. Nó đứng vững.

### Bảng đột biến của tôi, đánh lên chính phép đo của tôi

`walk_f40_f41.py` xanh 16/16 ngay lần chạy thật đầu tiên. **Một cổng mới chỉ từng
xanh thì chưa phải bằng chứng.** Nên tôi phá từng tính chất một và nói TRƯỚC ca nào
của tôi phải đỏ — so **tên ca**, không so số lượng, vì đỏ vì lý do khác đọc y hệt
một cổng tốt.

```
CONTROL: cây sạch -> 16/16 (nếu control đỏ thì mọi màu bên dưới vô nghĩa)

OK  [BREAKS] 1. tra memory TRƯỚC khi kiểm quyền -- mở lại oracle 403/404
OK  [BREAKS] 2. tra memory bỏ qua context -- với tới tường nhóm khác
OK  [BREAKS] 3. membership đọc từ HEADER thay vì database (#253)
OK  [BREAKS] 4. đếm tim bằng cách join thêm bảng bình luận -- 2x2 đọc ra 4
OK  [BREAKS] 5. bình luận ghi tên chủ ảnh thay vì người gọi
OK  [KEEPS]  6. count(id) -> count()          (phải XANH)
OK  [KEEPS]  7. đổi câu chữ lời từ chối 409   (phải XANH)
OK  [KEEPS]  8. đổi câu chữ lời từ chối 404   (phải XANH)
8/8 rows behaved as predicted
```

Ba hàng **GIỮ TÍNH CHẤT** không phải cho đủ số: không có chúng thì bảng không phân
biệt được "gác đúng tính chất" với "đỏ khi có ai đụng vào file", và một cổng đỏ vì
đổi tên biến sẽ bị tắt trong một tuần.

**Bảng này bắt hai lỗi của chính tôi**, và đó là lý do nó tồn tại:

1. Hàng 5 lúc đầu viết `author_id=memory.author_id` trong khi `memory` **không tồn
   tại** ở scope đó — `NameError`, đỏ vì crash chứ không vì tính chất. Đúng cái bẫy
   "đột biến với biến ngoài scope đọc nhầm là bắt được".
2. Viết lại cho đúng thì nó lộ **chỗ mù trong phép đo của tôi**: ca của tôi để
   **Amy bình luận dưới ảnh của chính Amy**, nên "ghi tên người gọi" và "ghi tên chủ
   ảnh" cho ra **cùng một hàng** — bản đúng và bản sai không phân biệt được. Đã sửa
   để **Ben** bình luận dưới ảnh của Amy. Đây đúng là chỗ mù tác giả PR cũng tự tìm
   ra và sửa trong một commit riêng; tôi vấp lại nó một cách độc lập.

Cả hai đều được **guard của chính script** chặn trước khi thành kết luận: neo khớp
sai số lần thì **dừng** chứ không chạy (hai hàng đã ABORT ở lượt đầu vì khớp 20 và 4
lần — vá nhầm bản sao rồi báo XANH là bẫy đã có thật), khôi phục bằng **bytes giữ
trong bộ nhớ** chứ không `git checkout` (nó xoá luôn việc chưa commit), và xoá
`__pycache__` sau mỗi lần khôi phục.

Sau toàn bộ đột biến, `git status --porcelain -- services/` **rỗng**.

## Các tầng đã thật sự chạy

| lệnh | kết quả |
|---|---|
| `pytest services/api/tests tests -q` (cây gộp) | **1922 passed**, 0 failed, 418 skipped |
| `tests/postgres` + `MOBILE_REQUIRE_POSTGRES_TESTS=1`, DB `qatt21` thật | **365 passed, 0 skipped** |
| `tests/qa` trên Postgres thật | **89 passed**, 19 subtests |
| `alembic upgrade head` trên DB sạch | rc=0, đúng **1** head |
| `scripts/gate.sh --strict` (13 chặng) | **ĐẠT 10 · HỎNG 3 · BỎ QUA 0** |
| `apps/mobile` (chặng `mobile`) | 673/674 — xem ghi chú dưới |

DB `qatt21` là **DB riêng tôi tạo**, không stamp lại DB dùng chung.

`ruff` **ĐẠT**. Lượt chạy đầu nó đỏ, và thủ phạm là **file nháp của chính tôi** nằm
ở gốc worktree, không phải file của PR. Tôi đã dọn rồi đo lại trước khi viết dòng
nào — suýt nữa thì báo nhầm một lỗi ruff cho tác giả. 28 dòng format tác giả tự khai
là nợ thừa kế thì đúng như họ mô tả.

Ca `mobile` duy nhất đỏ là `stacked-branch.test.mjs` — *"10/10 file trong diff có
nội dung y hệt origin/main"*. Đó **không** phải lỗi sản phẩm: nó là chữ ký của việc
**#283 vừa được merge trong lúc tôi đo**, đúng như cổng đó được dựng để nói. Chính
nó là thứ báo cho tôi biết main đã dịch dưới chân.

## Ô CHƯA quét — phần quan trọng nhất

- **Mã VietQR chưa từng được quét bằng app ngân hàng thật.** Không agent nào làm
  được; cần leader, một điện thoại, 15 phút.
- **Không quét được giao diện F40/F41 sau bản dựng này.** Máy demo đang chết, nên
  không có bundle nào truy được về `2837a45` để quét. Phán quyết của tôi cho #278
  (PR trước) vẫn đứng ở phạm vi nó đã đo, **không** mở rộng sang bản dựng này.
- **Chặng `e2e` chưa chạy trên cây gộp** — nó cần API sống, mà API không khởi động
  được. Đây chính là chặng duy nhất có cả client lẫn server thật, nên đây là ô trống
  đắt nhất trong báo cáo này.
- **Không đo tải, không đo truy cập đồng thời nhiều nhóm.** Phép đo đồng thời của
  tôi là 8 luồng trên **một** memory, đủ để chứng minh index giữ luật, không đủ để
  nói gì về hành vi dưới tải.
- **Không kiểm nội dung bình luận trong log.** PR khai "không vào log"; tôi kiểm
  được đường 422 và trang khách, **chưa** kiểm đường ghi log.

## Còn lại, không phải blocker

1. **Hình dạng 4 của bảng 422** (tên trường vào `loc`) — suggestion, đã lập luận ở trên.
2. **Chưa có route sửa/xoá bình luận** — tác giả đã nói rõ là vỏ chưa có, không giấu.
