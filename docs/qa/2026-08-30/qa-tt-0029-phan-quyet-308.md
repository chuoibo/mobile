# PASS cho #308 — F39 Post + F42 Privacy

**Bốn audience giữ đúng lời hứa trên app thật, và cổng của PR đỏ được ở đúng tầng bị đột biến —
kể cả khi chỉ đột biến một trong hai bản sao của luật.**

| | |
|---|---|
| protocol_version | v1 |
| PR | #308 · `frontend/rd-fe-36-post-va-privacy` |
| SHA của PR | `1b2260789ff10fcf2d5ef6e48b28d022143eb9c2` |
| **đo tại** | `463a52242283edfb7f92f37019aae0cd0a8d8f61` = merge `1b22607` ⊕ `origin/main@3e64ccf` |
| sha này | **là kết quả merge, chưa ở main.** Nhánh PR đứng sau main 3 commit; tôi gộp trước khi đo vì đó là cây sẽ ship |
| đối chứng | `origin/main@3e64ccf` chạy song song ở cổng 8141 |
| verdict | **PASS** |
| blocker còn mở | không có |
| kỹ năng | `e2e-testing`, `bug-reproduction` |

Alembic sau khi gộp: đúng **một** head (`a7d3f2b81c56`). Không xung đột head với ba commit main mới.

---

## 1. Cổng đã thật sự chạy

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2221 passed, 434 skipped, 4829 subtests** (434 skip là tầng postgres, chạy riêng ở dòng dưới) |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1`, DB riêng `qa_tt_0029` | **382 passed, 0 skipped** |
| `make gate` (cây gộp) | **ĐẠT 14 · HỎNG 0 · BỎ QUA 0** — `guard guard-range ruff contract client-routes cors api migration pinned-import shared mobile docker postgres e2e` |
| `scripts/gate.sh ruff` trên 13 file Python của PR, ruff **0.9.2 đúng bản ghim** | `All checks passed` · `13 files already formatted` |
| `python3 scripts/repo_guard.py staged` | `Repo guard passed` |

Chặng `docker` và `pinned-import` đều ĐẠT. Đây là PR đổi khai báo route (+4), nên hai chặng đó
là điều kiện leader tự đặt cho chính mình — chúng xanh, không phải bỏ qua.

`434 skipped` không phải là xanh và tôi không đọc nó là xanh: tầng postgres được chạy riêng
bằng biến bắt buộc, ra **0 skipped**.

---

## 2. Đi bộ trên app THẬT — 59 phép kiểm, 0 thất bại

`tests/qa/qa-tt-0029/di-bo-f39-f42.py`. uvicorn thật ở `127.0.0.1:8129`, PostgreSQL thật,
HTTP thật. Đếm **bản ghi**, không đếm status — một feed rò một hàng vẫn trả 200.

Bốn người, bốn audience, ba bề mặt đọc. Ô = tập audience người đó nhìn thấy:

| người đọc | quan hệ với tác giả | `GET /posts` | `GET /people/{An}/posts` |
|---|---|---|---|
| An | tác giả | only_me · friends · group · public | như bên trái |
| Ban | bạn đã chấp nhận, **không** trong nhóm | friends · public | friends · public |
| Cuong | thành viên nhóm ACTIVE, **không** phải bạn | group · public | group · public |
| Duyên | người lạ, biết id | public | public |

`GET /posts/{id}` — 16 ô (4 người × 4 bài) đều đúng: 200 khi được phép, **404** khi không.

Những gì đã chứng minh thêm, mỗi cái một dòng đỏ được nếu sản phẩm sai:

- **404 của bài có thật giống hệt 404 của id bịa** — cùng status, cùng thân
  (`{"code":"post_not_found","detail":"Post does not exist"}`). Không có oracle xác nhận id tồn tại.
- **Header không mua được gì.** Duyên gửi `X-Actor-Contexts` khai đúng id nhóm → vẫn chỉ thấy
  `public`, vẫn 404 khi đọc bài group. Tự phong `X-Actor-Roles: group_admin` cũng vậy.
- **Tác giả LÀ actor.** Gửi kèm `author_id` → **422**, không phải bị bỏ qua im lặng.
- **`group` phân giải lúc ĐỌC.** Cuong rời nhóm → feed tụt về `{public}` và bài group thành 404,
  không cần đụng gì tới bài viết.
- Bài `group` của nhóm khác không lọt vào feed Cuong (đếm hàng = 0).

Ghi rõ hai lần **phép thử của tôi hỏng, không phải sản phẩm**: lượt đầu tôi thiếu
`POST /memberships/{id}/accept` nên Cuong mới ở trạng thái `INVITED`, và tôi gọi
`DELETE .../members/{id}` bằng tài khoản admin trong khi route đó đòi `is_self`. Sửa fixture
là hết đỏ; sản phẩm không đổi một dòng.

---

## 3. Cổng của PR có răng không — bảng đột biến, MỘT tầng một lúc

`tests/qa/qa-tt-0029/bang-dot-bien.py`. Đột biến cả hai bản sao cùng lúc thì tầng không có cổng
sẽ tàng hình sau tầng có cổng, nên mỗi hàng chỉ chạm đúng một chỗ.

Gốc trước khi đột biến: domain 19 passed · api 20 passed · postgres 14 passed.

| đột biến | muốn | domain | api | postgres | |
|---|---|---|---|---|---|
| **M0** đổi thứ tự các nhánh OR (**giữ nguyên nghĩa**) | GREEN | GREEN | GREEN | GREEN | ĐẠT |
| M1 domain: `only_me` rơi xuống `True` | RED | RED | RED | RED | ĐẠT |
| M2 sql: thêm `only_me` thành một nhánh OR (**chỉ tầng SQL**) | RED | GREEN | GREEN | **RED** | ĐẠT |
| M3 sql: bỏ `state == ACCEPTED` — lời mời chưa trả lời cũng là bạn | RED | GREEN | GREEN | **RED** | ĐẠT |
| M4 sql: bỏ `state == ACTIVE` + `left_at is NULL` | RED | GREEN | GREEN | **RED** | ĐẠT |
| M5 domain: audience `group` bỏ qua tư cách thành viên | RED | RED | RED | RED | ĐẠT |
| M6 domain: audience lạ thì cho đọc (fail **open**) | RED | RED | GREEN | GREEN | ĐẠT |
| M7a sql: `list_posts_visible_to` (feed) mất bộ lọc | RED | GREEN | GREEN | **RED** | ĐẠT |
| M7b sql: `list_person_posts_visible_to` (tường) mất bộ lọc | RED | GREEN | GREEN | **RED** | ĐẠT |
| M8 domain: bỏ chặn `only_me` mang theo `context_id` | RED | RED | RED | GREEN | ĐẠT |

**10 đột biến, 0 lọt.** Ba điều bảng này nói mà một bảng toàn đỏ không nói được:

1. **M0 XANH.** Bảng đang phản ứng với *tính chất*, không phải với "có ai sửa file".
   Không có hàng này thì mọi hàng đỏ còn lại vô nghĩa.
2. **M2/M3/M4/M7 chỉ đỏ ở cột postgres.** Đây là bằng chứng lời khai "hai bản sao, bên hẹp hơn
   thắng" là thật chứ không phải trang trí: `tests/api` chạy trên fake dict nên mù hoàn toàn với
   mệnh đề SQL, và `test_posts_postgres.py` gọi thẳng repository nên bắt được. Nếu cột postgres
   xanh ở bốn hàng này thì bản sao SQL là code không ai gác.
3. **M7a và M7b tách riêng.** `_readable_by` là một hàm, nhưng nó không phải một cổng —
   cổng chỉ rộng bằng tập chỗ gọi nó. Hai call site, hai hàng, cả hai đều đỏ được.

Sau mỗi hàng ba file nguồn được khôi phục từ bản sao trong RAM; `git status` sau khi chạy: sạch.

---

## 4. Thăm dò mép — 8 nhóm, không cái nào hở

| đâm vào | kết quả |
|---|---|
| tường của người **không tồn tại** | 200 rỗng (không phải 404 — không thành danh bạ ai có tài khoản) |
| tường người có thật, không chia sẻ gì | 200, 0 bài |
| thiếu `X-Actor-ID` | 401 cho cả GET và POST |
| `limit` = 0 / 101 / −1 / `abc` / 10²⁰ | 422 cả năm |
| `audience` = `"everyone"` / `null` / thiếu hẳn | 422 cả ba |
| `body` rỗng / 100 000 ký tự | 422 cả hai |
| `audience=group` trỏ vào nhóm **người khác** | 403 |
| `image_url` trỏ vào ảnh của nhóm mình không ở trong | 403 |

Và phép kiểm oracle: nhóm **có thật nhưng không phải của mình** với nhóm **bịa hoàn toàn**
trả lời **giống hệt nhau** ở cả hai đường ghi — cùng 403, cùng thân
`{"code":"permission_denied","detail":"is_group_member"}`. Không suy ra được nhóm nào tồn tại.

---

## 5. Một lỗi tìm được — KHÔNG do PR này, không chặn merge

**Đường ghi trả 2xx trước khi giao dịch commit.** Một lượt ghi trả `201 Created`, rồi lượt đọc
ngay sau đó không thấy hàng; hàng xuất hiện trong vòng 0.3 s.

Tái lập (`tests/qa/qa-tt-0029/repro-tra-loi-truoc-khi-commit.py`, `repro-post-doc-lai-ngay.py`):

```
cây gộp (8129)   PUT /people -> 201, rồi POST /friends/requests -> 404 person_not_found
                 3/120 vòng · cả 3 lần hàng ĐẾN MUỘN, 0 lần mất hẳn
cây gộp (8129)   POST /posts -> 201, rồi GET /posts/{id} -> 404
                 1/200 vòng
origin/main@3e64ccf (8141)   cùng hình dạng, 1/200 vòng
```

**Đo trên `origin/main` cũng đỏ, nên đây là lỗi có sẵn, không phải do #308.**
`#308` không chạm `app/api/deps.py`; `get_repository` là dependency `yield` và
`factory.begin()` commit ở phần teardown, chạy sau khi response đã đi.

Phân loại: **suggestion cho #308** (không thuộc 5 loại blocker đối với PR này), **phiếu lỗi
riêng cho backend**. Hậu quả thật: client tạo bài rồi điều hướng ngay sang bài đó sẽ thấy 404
chớp nhoáng, ~0.5 %.

## 6. Một điểm nhỏ, suggestion

`DEFAULT_AUDIENCE = "only_me"` trong `app/domain/post_audience.py` nằm trong `__all__` và có
hẳn một đoạn docstring giải thích ("What a client that says nothing gets… the cost of guessing
too wide cannot be taken back") — nhưng **không chỗ nào trong `app/` hay `tests/` dùng nó**.
`PostCreateRequest.audience` không có default; client không khai thì được **422 Field required**
(đã đo trên app thật).

Hành vi thật **hẹp hơn** cái docstring hứa, nên không có rò rỉ. Đột biến hằng số này sang
`"public"` ra XANH cả ba tầng — và đó là **đúng**, vì nó là code chết, không phải lỗ hổng cổng.
Đề nghị: hoặc cho `schemas.py` dùng hằng số này, hoặc xoá nó cùng đoạn docstring.

---

## 7. Ô CHƯA QUÉT — phần quan trọng nhất của báo cáo

- **Chưa màn hình nào gọi bốn route này.** `grep` trên `apps/mobile/src/` ra rỗng; PR đổi 0 file
  mobile. Đây là **thứ tự merge đúng** (máy chủ trước, client sau), không phải thiếu sót — nhưng
  nghĩa là F39/F42 **chưa dùng được từ app**, và không ai đã nhìn tính năng này bằng mắt.
- **Không có bề mặt UI để quét**: không ảnh chụp, không tương phản, không bàn phím, không trình
  đọc màn hình. Ma trận trang khách không áp dụng cho PR này.
- **Đồng thời và đua**: hai `POST /posts` cùng lúc, rời nhóm *trong lúc* một feed đang được đọc,
  huỷ kết bạn giữa hai request — chưa quét.
- **Tải**: chưa đo. Feed `limit=100` trên bảng lớn chưa có phép đo query plan; chưa có index nào
  được kiểm bằng `EXPLAIN`.
- **`GET /posts` không phân trang** (chỉ có `limit`, không cursor). Chưa quét hành vi khi một
  người có hơn 100 bài đọc được.
- **Mã QR VietQR vẫn chưa được quét bằng app ngân hàng thật.** Không liên quan PR này, nhưng nó
  vẫn là ô mở và tôi giữ nguyên câu này cho tới khi leader cầm điện thoại thật kiểm.
- **Repo chưa có bằng chứng hành vi nào** (ADR-0006). 2221 ca xanh nói code làm đúng điều tác giả
  nghĩ; nó không nói người thật hiểu bốn chữ "chỉ mình tôi / bạn bè / nhóm / công khai".

---

## 8. Vì sao PASS

Bốn audience giữ đúng lời hứa ở cả ba bề mặt đọc trên app thật, không phải trên fake. Luật được
viết hai lần và cả hai lần đều có cổng đỏ được **riêng lẻ** — đó là điều mà một bảng đột biến
toàn đỏ, hay một bảng không có hàng đối chứng, không chứng minh được. Không có oracle tồn tại,
không có đường nào để header của người gọi tự cấp quyền, và mọi mép tôi đâm vào đều trả 4xx đúng.

Lỗi duy nhất tìm được tái lập **trên chính `origin/main`**, nên nó không phải giá của việc merge
PR này.
