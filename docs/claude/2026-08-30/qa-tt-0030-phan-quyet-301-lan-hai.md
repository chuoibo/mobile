# Phán quyết QA — PR #301, lượt hai

```
PASS
```

Blocker tôi mở ở lượt trước đã đóng, và tôi đo lại được điều đó chứ không đọc lời
khai: cổng cửa-sổ giờ **khám phá** danh sách cửa từ `app.state` thay vì tự liệt kê
tên, nó bắt 4/4 đột biến phá tính chất trong khi cổng cũ bắt 1/4, và hàng đối
chứng giữ nguyên tính chất vẫn XANH. Sản phẩm đứng vững trên app thật: F31/F33/F36
phục vụ đúng thành viên, từ chối người ngoài ở cả ba cửa, và trần nhịp giữ **đúng
30/40 request song song** — con số leader hỏi mà unit test không trả lời được.

Còn hai chỗ mù, tôi đo được cả hai, và **không** coi là blocker: cổng vẫn không
thấy route chạm model mà không dựng gì trên `app.state` (docstring của chính nó
khai ra điều này) — và không thấy cửa có guard thuộc lớp ngoài `_MODEL_GUARD_TYPES`
(chỗ này docstring **chưa** nói rõ). Tôi tự kiểm ngược bằng một bản kiểm kê đi từ
route: 9 route chạm Gemini trên cây gộp, **0 route không có guard**.

**Điều kiện trước khi merge:** #301 **không còn merge sạch** lên `main` sau khi
#308 vào. Ba xung đột, cả ba là danh sách import. Tác giả rebase là xong.

---

## Đo tại đâu

```
đo tại   6c7b5e0 = merge(823b6dd ⊕ origin/main@7cc51cc)
823b6dd  head của PR #301, nhánh devops/rd-do-23-ai-hieu-nhom, CHƯA merge
7cc51cc  main, đã có #308
```

Ba xung đột khi gộp, tất cả trong danh sách import và không chồng nghĩa nhau:

| File | Xung đột |
|---|---|
| `app/api/main.py` | `posts` (#308) cạnh `preferences` (#301) trong khối `from app.api.routes import` |
| `app/api/service.py` | bốn schema `Post*` (#308) cạnh ba schema `Preference*` (#301) |
| `app/api/service.py` | `from app.domain import permissions, post_audience` cạnh `permissions` + `build_album` |

Tôi giải bằng cách lấy cả hai phía để dựng cây đo. **Bản giải này không phải hàng
giao** — tác giả vẫn phải rebase, và tôi ghi ra đây để người rebase biết trước là
việc này mất vài phút chứ không phải một buổi.

## Cổng đã chạy

| Cổng | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2304 passed, 0 failed**, 467 skipped, 4832 subtests |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **409 passed, 0 skipped** |
| `cd apps/mobile && npm test` | **705 pass, 0 fail** |
| `ruff check` + `format --check` trên 22 file của PR | `All checks passed` · `22 files already formatted` |
| `alembic heads` trên cây gộp | **một head** (`a7d3f2b81c56`) — #301 không thêm migration |

Tầng Postgres chạy trên database **riêng của lượt này** (`qa_tt_0030`), không phải
DB dùng chung — nên 409 ca này gồm cả file mới 877 dòng của #301, và không lane nào
bị stamp đè.

Hai lần đỏ trong lượt này đều là **của tôi**, không phải của PR, và tôi ghi ra vì
suýt báo nhầm cả hai:

- `ruff check` ra 2 lỗi ở `service.py` — là import `permissions` trùng do chính bản
  giải xung đột của tôi sinh ra. Chạy lại trên nhánh tác giả trong worktree sạch:
  `All checks passed`.
- `test_no_new_unformatted_file_under_tests_qa` đỏ — vì hai script mới của tôi chưa
  format. Cổng đó làm đúng việc của nó.

## Blocker lượt trước: đóng

Lượt trước tôi FAIL vì `test_every_route_that_reaches_the_model_carries_its_own_window`
khai trong docstring là "counted, not enumerated" trong khi thân nó đọc bảy tên
thuộc tính viết tay rồi assert `len(...) == 7` — một mệnh đề luôn đúng với chính
danh sách của nó.

Nhánh đã thay bằng hai ca đọc roster ra từ `app.state` theo `isinstance`, và sửa
lại lời khai trong docstring. Tôi chạy lại bảng đột biến của chính tác giả
(`scripts/mutation_cong_cua_so_model.py`) trong cây gộp sạch:

| Hàng | Đột biến | Cổng mới | Cổng cũ |
|---|---|---|---|
| M1 | cửa thứ chín dùng chung cửa sổ với cửa thứ nhất | **ĐỎ** | XANH |
| M2 | cửa thứ tám dùng chung cửa sổ với cửa thứ sáu | **ĐỎ** | ĐỎ |
| M3 | gỡ hẳn cửa thứ bảy của #297 (`reason_writer`) | **ĐỎ** | XANH |
| M4 | phá cơ chế khám phá (roster rỗng) | **ĐỎ** | XANH |
| M5 | **ĐỐI CHỨNG** — đổi hằng số trần, giữ tính chất | XANH | XANH |

Cổng mới bắt được **4/4**, cổng cũ **1/4**. Hàng M5 là thứ làm bảng
này dùng được: nó đổi con số trần mà không đụng tính chất, và phải XANH — không có
nó thì một cổng "ghét mọi thay đổi" trông y hệt một cổng gác đúng tính chất.

M4 đáng nói riêng. Nó bịt đúng đường tha bổng của kiểu cổng này: nếu khám phá âm
thầm trả về rỗng, thì "không hai cửa nào chung guard" đúng một cách rỗng tuếch và
cổng XANH trong khi không đo gì — 0/0 đọc thành đạt. Tác giả đã tự chặn bằng
`assert guards` trong `_model_guards`.

## Hai chỗ cổng vẫn mù — tôi đo, không suy

Bảng của tác giả có một đặc điểm: cả bốn đột biến đều sửa một cửa mà roster **đã
khám phá ra rồi** — đổi bí danh, xoá, hoặc làm rỗng. Không hàng nào *thêm* một cửa
theo cách một nhánh tính năng thêm cửa. Nên tôi viết hai hàng đó:
`tests/qa/qa-tt-0030/dot_bien_cua_khong_ai_thay.py`.

| Hàng | Đột biến | Cổng mới | Có được khai báo không |
|---|---|---|---|
| N1 | route thứ chín gọi model, **không có guard nào** | XANH | **CÓ** — docstring nói thẳng |
| N2 | cửa thứ chín **có** guard trên `app.state`, lớp ngoài `_MODEL_GUARD_TYPES` | XANH | **KHÔNG** |

N1 tôi in ra `app.routes` để chứng minh route thật sự được đăng ký, không phải một
đột biến chết đội lốt phát hiện. N2 tôi in ra `app.state` sau đột biến —
`trip_recap_limiter` nằm đó, dựng eagerly trong `create_app`, và roster vẫn khớp
`_KNOWN_DOORS` vì `isinstance` lọc nó ra **trước khi** so sánh.

Đọc hai hàng cùng nhau thì thấy chỗ bản viết lại đứng: cổng đã thôi liệt kê **tên**
cửa và chuyển sang liệt kê **lớp** guard. Đó là một bậc thật — nó kéo được cửa mới
cùng lớp vào tầm nhìn, đúng như M1 và M3 đo — nhưng danh sách vẫn viết tay, và cửa
ngoài danh sách vẫn vô hình.

**Vì sao không phải blocker.** Blocker lượt trước là *lời khai sai*, không phải
*phạm vi hẹp*. Giờ docstring khai đúng phần lớn giới hạn của nó, câu bao trùm
"This does NOT prove every model-reaching route *has* a guard" là thật, và cổng đo
đúng cái nó nói nó đo. N2 là chỗ nên viết thêm một câu vào docstring, không phải
chỗ chặn merge — nó là suggestion theo charter, không thuộc 5 loại blocker.

## Tự kiểm ngược: có route nào chạm model mà không có trần không

Câu trên là câu cổng kia **không** trả lời được, nên tôi đi ngược từ route thay vì
từ guard: `tests/qa/qa-tt-0030/kiem-ke-cua-model.py` duyệt mọi route đã đăng ký,
lần theo đồ thị `Depends`, rồi hỏi hai câu tách rời — route này chạm Gemini không,
và nó có guard không.

```
route cham model: 9   khong thay guard: 0
CO  POST  /contexts/{context_id}/ai-turn          CO  GET   /places
CO  GET   /contexts/{context_id}/contextual-suggestion   CO  POST  /places/search
CO  POST  /contexts/{id}/messages/{id}/expense-draft     CO  GET   /places/{place_id}
CO  GET   /contexts/{context_id}/suggestion       CO  POST  /receipts/scan
                                                  CO  POST  /screenshots/scan
```

**Canary bắt buộc**, vì "0 không có guard" tự nó không phân biệt được "sạch" với
"máy đếm hỏng": chèn đúng route N1 vào rồi chạy lại, bản kiểm kê ra
`route cham model: 10   khong thay guard: 1` và gọi tên đúng route đó. Có canary
đỏ thì con số 0 mới có nghĩa.

Bản kiểm kê này **hai lần** tự mắc đúng lỗi nó đi tìm, và tôi giữ lại vết đó trong
comment của file thay vì lặng lẽ sửa:

1. lọc route theo tiền tố đường dẫn tôi tự nghĩ ra → mất `/receipts`, `/screenshots`;
2. `MODEL_MODULES` viết tay năm tên `app.api.*_gemini` → mất `GET /places`, vì lời
   gọi model của nó nằm ở `app.places.*`.

Lần hai là đúng cái hình dạng tôi đang bắt lỗi người khác. Bản hiện tại **tìm ra**
module chạm model bằng cách đọc file xem có `generativelanguage` / `GEMINI_API_KEY`
không, chứ không liệt kê.

Giới hạn còn lại, khai thẳng: nó lần theo `Depends` tĩnh, nên một backend gọi bằng
tra cứu lúc chạy sẽ lọt; và "có guard" nghĩa là guard **được nối vào**, không phải
là trần đúng số hay được hỏi trước lời gọi đắt tiền.

## Sản phẩm trên app thật

Uvicorn trên cây gộp, PostgreSQL riêng, `GEMINI_API_KEY` thật —
`tests/qa/qa-tt-0030/di-bo-f31-f33-f36.py`, mọi lời gọi đi qua cổng HTTP.

| Bước | Kết quả |
|---|---|
| F31 `GET /preference-profile` | 200, `has_profile=false`, `reason="no_behaviour"` — nhóm mới thì rỗng có lý do, không phải rỗng vì hỏng |
| F36 `GET /albums` | 200, `albums: []` |
| F33 `GET /contextual-suggestion` | 200, thẻ do Gemini thật sinh |
| Người ngoài nhóm hỏi cả ba | **403 / 403 / 403** |
| 40 request **song song**, một actor, cửa F33 | **200=30 · 429=10 · mã khác=0** |

Hàng cuối là câu leader hỏi. Trần là 30/60s mỗi actor, và dưới 40 request bắn song
song thật (`ThreadPoolExecutor`, không tuần tự) nó giữ **đúng 30**, không rò một
request nào, không sinh mã lạ.

Về grounding của F33 — thẻ bám vào đúng cuộc trò chuyện của nhóm và, đáng chú ý
hơn, **nó nhận là không khớp** thay vì bịa ra một quán:

> "Tuy không có địa điểm gần Ba Đình và không phải lẩu cà ri, đây là quán lẩu duy
> nhất trong danh sách."

Một mô hình chịu nói "không có" là tín hiệu tốt hơn nhiều so với một thẻ luôn tự tin.

Hai lần đầu bản đi bộ này đỏ và **cả hai đều là harness của tôi sai**, không phải
sản phẩm: thiếu bước `PUT /people/{id}` (API tự nói ra: `person_not_registered`,
kèm luôn lệnh tiếp theo), và mời thành viên bằng vai `member` trong khi
`invite_context_member` đòi `group_admin` rồi còn phải `accept`. Lần chạy nào bỏ
qua bước accept sẽ đo một người **không** phải thành viên và vẫn đọc như đạt — đúng
lần đó tôi thấy `200=0, 429=10, 403=30`, và con số 429 trông y hệt một trần đang
hoạt động.

## Ô chưa quét

- **Trần nhịp qua nhiều tiến trình.** Cửa sổ nằm trong bộ nhớ mỗi process. Đo ở đây
  là một uvicorn một worker. Hai replica là hai cửa sổ và gấp đôi trần — chính file
  `search_rate_limit.py` đã khai điều này.
- **Trần có đúng số không.** Tôi đo trần *giữ*, không đo 30/60s là con số đúng cho
  hạn mức Gemini thật.
- **N2 trên đường thật.** Tôi chứng minh cổng mù với lớp guard lạ; tôi **không**
  chứng minh có ai sắp thêm một guard như thế.
- **F31/F36 với dữ liệu dày.** Nhóm trong bản đi bộ là nhóm mới nên cả hai trả rỗng
  hợp lệ. Đường đi có dữ liệu lịch sử thật do tầng `tests/postgres` phủ, không do
  bản đi bộ này.
- **Giao diện.** #301 không chạm `apps/mobile/`; không màn hình nào gọi ba route mới.
  Theo bài học "đếm tính năng phải có cả API lẫn màn gọi", F31/F33/F36 hiện là
  **tầng máy chủ**, chưa phải tính năng người dùng chạm được.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, ngoài phạm vi PR này.

## Việc cho tác giả (không chặn merge)

1. **Rebase lên `main`** — ba xung đột danh sách import, đã liệt kê ở trên.
2. Thêm một câu vào docstring của `test_the_roster_of_doors_onto_the_model_is_accounted_for`:
   guard dựng eagerly trên `app.state` nhưng thuộc lớp ngoài `_MODEL_GUARD_TYPES`
   cũng vô hình, không chỉ guard dựng lười trong request. Bản đo: hàng N2.
