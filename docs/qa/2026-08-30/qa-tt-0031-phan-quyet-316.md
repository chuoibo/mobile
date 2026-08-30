# Phán quyết QA — PR #316 (bug-160855, commit trước khi trả lời)

**PASS**

**Lý do:** bản vá đúng và không gây hồi quy ở *cả hai* bản fastapi (2183 ca cổng rẻ,
370 ca `tests/postgres` xanh ở bản máy **và** bản ghim), cổng wiring của nó đỏ được
khi gỡ bản vá ở cả hai bản, và nhánh cuộn-lại mà PR viết tay tôi đã tự đo là đúng.
Hai điều phải sửa **trước khi merge**, cả hai đều không phải lỗi hành vi:
(1) bảng bằng chứng trong mô tả PR đo trên `fastapi 0.135.3` — **không phải** bản
`0.115.6` mà ảnh docker và CI thật sự cài — và ở bản ghim thì lỗi *không tồn tại*,
nên hai ca postgres của PR **không thể đỏ** ở nơi CI chạy; (2) `get_repository` bị
viết lại từ context manager thành try/except/else/finally thủ công mà **không ca nào**
gác nhánh `rollback`.

- protocol_version: v1
- SHA đã test: `6384bf24b64b4af02be1ea00d28a80117ada10c9` (head của #316 lúc đo)
- SHA này **là nhánh chưa merge**, đứng sau `origin/main` (`2862154`) 1 commit, trước 10
- Nhánh nền khi đo: `3e64ccf` (merge-base với main)
- DB đo: `qatt31` riêng trên `qa22-postgres-1:5722`, migrate tới head của chính nhánh
  này (39 bảng) — không đụng DB chung

---

## 1. Phát hiện chính: bằng chứng của PR đo trên bản fastapi không được ship

`services/api/Dockerfile` cài phụ thuộc với `--constraint` sinh từ
`requirements-dev.txt`, trong đó `fastapi==0.115.6`. Đo thẳng trên container đang
chạy, không suy luận:

```console
$ docker exec mobile-local-api-1 python -c "import fastapi,starlette,fastapi.routing as r,inspect; ..."
ANH DOCKER: fastapi 0.115.6 starlette 0.41.3
request_response dinh nghia trong fastapi.routing: False
thuc su den tu: starlette.routing
```

Trên PATH của máy này thì là `fastapi 0.135.3`. Hai bản đặt exit stack của dependency
dạng `yield` — và do đó đặt COMMIT — ở **hai phía đối nhau** của
`await response(scope, receive, send)`:

| | `fastapi.routing.request_response` | exit stack của yield-dependency | COMMIT xảy ra |
|---|---|---|---|
| `0.115.6` (GHIM, ảnh docker + CI) | **không tự định nghĩa** — `from starlette.routing import (...)` dòng 65–72 | nằm **trong** `get_request_handler`, đóng trước khi trả `Response` | **trước** khi gửi body |
| `0.135.3` (máy này) | tự định nghĩa, hai stack | `request_stack` đóng **sau** `await response(...)` | **sau** khi gửi body ← lỗi |

Hệ quả là docstring của `app/api/unit_of_work.py` sai ở đúng cận dưới dải nó tự khai:

> Dùng `fastapi.routing.request_response`, **không phải** bản của Starlette. […]
> stable across the supported `fastapi>=0.115,<1` range.

Ở `0.115.6` thì `fastapi.routing.request_response` **chính là** bản của Starlette.
Điều này vô hại — fastapi 0.115.6 tự nó cũng gọi đúng hàm đó ở dòng 569 — nhưng câu
văn đang bảo lãnh một điều không đúng ở bản đang ship.

### Ma trận 2×2, chạy lại được

`tests/qa/qa-tt-0031/ma-tran-fastapi.sh` dựng lại toàn bộ bảng dưới đây và tự khôi
phục cây (trap EXIT). Đột biến = bỏ lời gọi `install_commit_before_response(application)`,
tức tương đương hành vi của `main` trước PR.

```console
$ tests/qa/qa-tt-0031/ma-tran-fastapi.sh /tmp/venv_pin/bin/python 'postgresql+psycopg://…/qatt31'
=== ban vá CÓ ===
--- fastapi may   (0.135.3)                  4 passed in 1.34s
--- fastapi GHIM  (0.115.6)                  4 passed in 1.30s

=== ban vá GO (tuong duong main truoc PR) ===
--- fastapi may   — mong doi DO              3 failed, 1 passed in 1.44s
--- fastapi GHIM  — day la o quyet dinh      1 failed, 3 passed in 1.27s
```

| | fastapi 0.135.3 (máy) | fastapi 0.115.6 (**GHIM — CI + ảnh**) |
|---|---|---|
| bản vá **có** | 4 passed | 4 passed |
| bản vá **gỡ** | **3 failed** — 2 ca postgres + cổng wiring | **1 failed** — chỉ cổng wiring; **2 ca postgres XANH** |

Ô dưới-phải là phát hiện. Hai ca `tests/postgres/test_commit_before_response_postgres.py`
— đúng hai ca PR trưng ra làm bằng chứng đỏ-trước/xanh-sau — **xanh ngay cả khi gỡ bản
vá**, ở bản đang ship. Chúng xanh vì ở `0.115.6` hàng đã commit và đã nhìn thấy được từ
kết nối khác *vào đúng lúc* `http.response.body` đi ra; ca assert
`another connection counted 1 row at the moment the body went out` và nó đếm được 1.

**Đọc đúng:** lỗi `1/200 → 404` mà qa-tt-0029 đo trên `main@3e64ccf` là thật, nhưng nó
là lỗi của cây chạy `fastapi 0.135.3` (cài không ràng buộc, tức mọi máy dev), **không
phải** của ảnh docker. Bản vá vẫn đáng giữ: `pyproject.toml` cho phép `fastapi>=0.115,<1`,
nên ngày nào ghim được nâng là lỗi có thật trong ảnh. Nhưng câu trong mô tả PR — "trên
đường hero đây là 404 người dùng nhìn thấy" — chưa đúng cho bản đang ship, và bảng
"trước bản vá 2/2 FAILED" cần nói rõ nó đo ở bản nào.

**Không phải blocker** vì hành vi ở cả hai bản đều đúng và không có hồi quy. Là việc
phải sửa vì Lead chỉ đọc mô tả PR, và mô tả hiện tại làm người đọc tin rằng hai ca
postgres kia đang gác cửa ở CI — chúng không.

Cổng wiring thì **có** đỏ ở cả hai bản (ô dưới, cột phải: `1 failed`), nên việc ai đó
gỡ hẳn `install_commit_before_response` vẫn bị bắt. Đó là phần chắc chắn của PR này.

---

## 2. Phát hiện hai: nhánh `rollback` viết tay không có ca nào gác

PR thay `with factory.begin() as session:` — context manager mà SQLAlchemy bảo đảm
rollback — bằng `try/except BaseException: session.rollback() / else: commit / finally: close`
viết tay. Không ca nào trong PR đi vào nhánh `except`.

`tests/qa/qa-tt-0031/probe-cuon-lai-khi-loi.py` đâm thẳng vào đó trên PostgreSQL thật:
một route ghi một hàng rồi ném, hàng không được sống sót.

```console
# PR head, cả hai bản fastapi
  DAT  HTTPException 409 sau khi ghi: status=409 hang con lai=0 (mong doi 0)
  DAT  RuntimeError 500 sau khi ghi:  status=500 hang con lai=0 (mong doi 0)
  DAT  duong hanh phuc:               status=200 hang con lai=1 (mong doi 1)
KET QUA: DAT
```

Hành vi **đúng**. Nhưng probe phải chứng minh mình đỏ được, nếu không nó chỉ là trang
trí. Đột biến `session.rollback()` → `session.commit()` trong nhánh `except`:

```console
# probe                             -> HONG 2/3
  HONG  HTTPException 409 sau khi ghi: status=409 hang con lai=1 (mong doi 0)
  HONG  RuntimeError 500 sau khi ghi:  status=500 hang con lai=1 (mong doi 0)

# bộ test của chính PR trên cùng đột biến  -> 4 passed
```

Bộ test của PR **mù hoàn toàn** với việc mất rollback. Nếu nhánh đó hỏng, hàng bị ghi
trong một request kết thúc bằng lỗi sẽ được commit, và không cổng nào kêu. Trên đường
tiền — route ghi sổ rồi ném — đó là hàng sổ cái không được phép tồn tại.

Probe đã có sẵn và chạy được; đề nghị backend nhận nó thành một ca trong `tests/postgres`.

---

## 3. Cổng đã chạy (SHA `6384bf2`, cây sạch)

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2183 passed, 422 skipped, 4797 subtests** |
| `tests/postgres`, `MOBILE_REQUIRE_POSTGRES_TESTS=1`, fastapi máy | **370 passed, 0 skipped** |
| `tests/postgres`, cùng cờ, **fastapi 0.115.6 ghim** | **370 passed, 0 skipped** |
| Đột biến gỡ `install_commit_before_response` | 3 failed (máy) · 1 failed (ghim) |
| Đột biến `rollback`→`commit` | probe HONG 2/3 · test của PR 4 passed |

Một dòng đỏ duy nhất trong lượt đầu — `test_no_new_unformatted_file_under_tests_qa` —
là **file nháp chưa commit của chính tôi**, không phải của PR: cổng đó quét filesystem
chứ không quét cây git. Đã format bằng `$(scripts/ruff_pinned.sh) format`, sau đó
4 passed.

Bản ghim dựng bằng venv cách ly, **không** vá gì vào interpreter của máy:

```bash
python3 -m venv --system-site-packages /tmp/venv_pin
/tmp/venv_pin/bin/pip install "fastapi==0.115.6"     # kéo theo starlette 0.41.3
```

## 4. Ô CHƯA quét

- **`npm test` / `npm run test:e2e` của `apps/mobile`** — chưa chạy lượt này. PR chỉ
  chạm `services/api/app/api/`, không đổi hợp đồng HTTP nào, nhưng tôi không đo nên
  không khai là đã phủ.
- **Lát cắt dọc thật qua uvicorn** — chưa dựng server lượt này; ca ordering của PR đo
  ở tầng ASGI, chặt hơn một vòng lặp săn race, nhưng không thay thế được một lượt đi bộ.
- **Route ghi ngoài `get_repository`** — `sqlalchemy_store_factory` (idempotency,
  `main.py:78`) cố ý là giao dịch ngắn riêng và commit trước khi handler chạy; tôi đọc
  chứ chưa đâm nó bằng ca riêng.
- **Trang khách, ma trận trạng thái × chủ đề × khung nhìn** — không liên quan diff này,
  không quét.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, vẫn cần leader và một
  điện thoại thật.
- **`scripts/check_pinned_import.sh` / chặng docker** — chưa chạy; tôi lấy bản ghim
  bằng venv và bằng cách hỏi thẳng container đang chạy.

## 5. Việc phải làm trước khi merge

1. Sửa bảng bằng chứng trong mô tả #316: nói rõ `2/2 FAILED` đo ở `fastapi 0.135.3`,
   và ở bản ghim `0.115.6` thì hai ca đó xanh cả trước lẫn sau. Sửa luôn docstring
   `unit_of_work.py` — ở `0.115.6`, `fastapi.routing.request_response` *là* bản Starlette.
2. Nhận `probe-cuon-lai-khi-loi.py` thành ca `tests/postgres` cho nhánh rollback.
3. Rebase lên `origin/main` (`2862154`) — nhánh đang sau main 1 commit.
4. Quyết định riêng, không chặn PR này: có nên chạy `tests/postgres` ở bản ghim trong
   CI không. Hiện mọi tầng test chạy ở `0.135.3` còn ảnh chạy `0.115.6`; ma trận trên
   là ví dụ đo được của khoảng cách đó.
