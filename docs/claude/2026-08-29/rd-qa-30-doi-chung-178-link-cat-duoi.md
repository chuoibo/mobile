# rd-qa-30 · PASS #178 — link khách bị cắt đuôi

**PASS.** Bản sửa làm đúng điều nó nói: link bị cắt đuôi giờ trả trang tiếng Việt
404 `text/html` thay vì JSON tiếng Anh. Đối chứng đỏ-trước được (6 ca đỏ trên cây
chưa sửa, đỏ đúng bằng chuỗi JSON cũ), cổng đầy đủ xanh trên main, và trang mới
render sạch ở 320/390 với axe 0 vi phạm.

**Một điều Lead cần biết trước phần chi tiết: #178 đã được merge trong lúc tôi
đang test, 5 phút sau khi mở, chưa qua phán quyết QA.** Kết quả may mắn là đạt —
nhưng lần này cổng QA đã bị đi vòng qua, không phải được thoả mãn.

## Đo tại đâu

| | |
|---|---|
| head của PR | `47261e7f30f192f3b846d0c7a65b08d5e45d2558` |
| sha này | **đã vào main** — squash `32c9f53`, merged 2026-08-29T15:32:40Z |
| cây trước khi sửa | `ab458d9` (cha của PR) |
| main lúc chốt | `831429c` (main chạy tiếp tới `37f4068` trong lượt) |
| DB | container **riêng** `qa178-pg` cổng 5878, `alembic head = e3b8c1d5720f` — không đụng DB chung |
| máy chủ | uvicorn 127.0.0.1:8823 dựng từ chính cây đang đo, 44 route, `/healthz` 200 |

Link khách dùng để đi bộ là link **thật** do `tests/qa/rd-qa-21/tao-link-khach.mjs`
sinh ra qua đúng client của app (`dist-test/api.js`), có ghim
`EXPO_PUBLIC_API_URL` sang 8823 — mặc định của client là 8099, tức máy demo của
người khác.

## Đối chứng: lỗi cũ có thật

Bung **hai file test của PR** lên cây `ab458d9` chưa có bản sửa (đã xác nhận
`GUEST_LINK_NOT_FOUND` = 0 lần trong `errors.py`/`main.py`, template chưa tồn tại):

```
6 failed, 9 passed
assert 'Không mở được link này' in '{"code":"guest_link_not_found","detail":"Guest link does not exist"}'
```

Đỏ đúng chỗ, và đỏ bằng chính chuỗi JSON tiếng Anh mà phiếu mô tả. Sau khi sửa:
15 ca của hai file đều xanh.

## Cổng đã chạy

| Cổng | Kết quả |
|---|---|
| `pytest services/api/tests tests` trên head PR `47261e7` | **1240 passed**, 286 skipped, 4592 subtest |
| như trên, trên **kết quả merge** #178 ⊕ main@`894a2eb` | **1259 passed** — không có xung đột ngữ nghĩa |
| như trên, trên **main sạch** `831429c` | **1264 passed**, 285 skipped |
| `npm test` (apps/mobile) trên main sạch | **505/505 pass**, 0 fail |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **251 passed, 0 skipped** |

Ghi chú về một dấu đỏ **không phải lỗi của PR**: chạy `npm test` trên head PR và
trên cây merge của tôi thì `stacked-branch.test.mjs` đỏ một ca —
`6/6 file hiện trong diff mà nội dung y hệt origin/main`. Đó là vì #178 đã merge
rồi nên nhánh không còn mang gì mới; trên main sạch cổng này 2/2 xanh. Cổng đang
làm đúng việc của nó, không phải hồi quy.

## Đột biến — ca nào thật sự canh cái gì

| Đột biến | Kỳ vọng | Thực tế |
|---|---|---|
| thân 500 in ra exception (`Service unavailable: {exc}`) | chỉ ca mới của PR đỏ | **1 failed, 6 passed** — đúng như PR tự khai |
| literal `"guest_link_not_found"` trong `service.py` trôi khỏi hằng số | test bắt được | **6 failed** — chốt giữ hằng số ↔ literal có thật |
| bỏ điều kiện `is_guest_path` khỏi handler | ? | **976 passed, 0 đỏ** |

Ca thứ ba **không phải lỗ hổng**: tôi đã truy `guest_link_not_found` chỉ được ném
từ `guest_view` và `_objection_envelope`, mà `guest_view` chỉ có router `/g` gọi.
Nên hôm nay đó là **đột biến tương đương** — bỏ `is_guest_path` không đổi hành vi
quan sát được. Nó chỉ trở thành lỗ thật vào ngày có route ngoài `/g` gọi
`guest_view`, và lúc đó sẽ không có ca nào kêu.

## Đi bộ như người dùng thật

Cắt 4 ký tự đuôi của một link đang chạy được — đúng cái ứng dụng chat làm:

| | link đầy đủ | cắt 4 ký tự |
|---|---|---|
| status | 200 | **404** |
| content-type | `text/html` | **`text/html`** |
| chuỗi `guest_link_not_found` trong thân | 0 | **0** |
| câu tiếng Việt | — | **có** |
| echo lại token | 3 (trang đang chạy, form trỏ về chính nó) | **0** |
| `cache-control` / `referrer-policy` / `x-robots-tag` | đủ 3 | **đủ 3** |

Đối chứng âm: `/contexts/khong-co-that` vẫn `401 application/json` — đường ngoài
`/g` không bị đổi. `is_guest_path` khớp `/g` và `/g/...`, không khớp `/goals`.

Hợp đồng client: `grep` toàn `apps/` + `packages/` — **không client nào đọc**
`guest_link_not_found`. Đổi content-type không giết màn nào.

## Giao diện — trang mới chưa ai nhìn

Quét URL có **ghim Chrome** (`PUPPETEER_EXECUTABLE_PATH` → chromium-1194) và
**hai canary mỗi lượt**:

- `imp detect` canary **xấu**: 1 finding, **exit 2** · canary **sạch**: 0, **exit 0** → máy quét sống
- axe canary **xấu**: **4 vi phạm** (contrast, html-has-lang, image-alt, label) → máy quét sống

Số đo trên trang thật, sau khi canary đã đỏ:

- **axe: 0 vi phạm** (wcag2a + wcag2aa + wcag22aa)
- tràn ngang **0px** ở cả 390 và 320; ảnh chụp đọc được, dấu tiếng Việt rõ
- không có tên người, không có số tiền, không có token trên trang
- `imp detect`: 2 finding — `cream-palette` là **có sẵn** (`--ground: #feeee0` của
  `guest.css` dùng chung, trang khách đang chạy cũng dính y hệt), còn
  `flat-type-hierarchy` (12/13/18px) là **riêng trang này**

## Còn lại — suggestion, không phải blocker

1. `flat-type-hierarchy`: 12px và 13px quá sát nhau trên trang mới. Thẩm mỹ.
2. `POST /g/{token}/da-chuyen` với token không tồn tại **vẫn trả JSON tiếng Anh**
   (`guest_obligation_not_found`), vì nó ném mã khác. **Có sẵn từ trước, #178
   không làm tệ đi**, và đường tới nó là một tab mở sẵn rồi bấm — không phải
   đường của link bị cắt. Nêu ra vì nguyên tắc của PR ("dưới `/g` là người đọc")
   chưa phủ hết mã lỗi.
3. Docstring của `test_every_route_that_can_refuse_an_unknown_token...` nói "mọi
   route", nhưng parametrize 4 trong 8 tổ hợp method+path dưới `/g`. Bốn tổ hợp
   còn lại hôm nay không ném mã này nên không sai kết quả — chỉ là câu chữ hứa
   rộng hơn ca đang chạy.

## Ô CHƯA quét

- **Mã QR quét bằng app ngân hàng thật** — chưa, và không agent nào làm được.
  Vẫn là việc 15 phút của leader.
- Chủ đề tối và các trạng thái khách khác (`expired`/`revoked`/...) — không quét
  lại lượt này; #178 không chạm chúng.
- Trình duyệt điện thoại thật — mới chỉ chromium ở 320/390.
- Trang mới ở khung 1440 — chưa quét.

## Điều đáng lo hơn cả bản sửa

#178 mở 15:27:49Z, merge 15:32:40Z — **4 phút 51 giây**, không có phán quyết QA
nào trên PR (0 comment lúc tôi bắt đầu). Bản sửa này đạt, nên lần này không mất
gì. Nhưng luật "mọi PR phải qua QA" vừa được chứng minh là **kỷ luật chứ không
phải cưỡng chế** — đúng như `CLAUDE.md` đã ghi về branch protection. Nếu Lead
muốn cổng QA có thật, chỗ hở nằm ở đây, không nằm trong code.
