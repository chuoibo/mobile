# FAIL cho PR #397 tại `3795c80` — hai blocker cũ đã gỡ thật, còn một cổng đỏ cách PASS đúng một lệnh

- protocol_version: v1
- task_id: qa-tt-0051
- verdict: **FAIL**
- PR: #397 `frontend/api-actor-id-bat-buoc`
- phán quyết trước: FAIL tại `9df1c82` (#412, đã ở main)

## Lý do, viết trước chi tiết

Hai blocker tôi mở ở `9df1c82` **đã được gỡ thật**, và tôi kiểm bằng đột biến chứ
không bằng lời tác giả. Không cần tranh luận lại chúng.

Nhưng PR làm **đỏ một cổng thứ ba mà bản trước không đỏ**: `scripts/ruff_changed.sh`
thoát 1 vì `scripts/check_api_contract.py` không đúng định dạng ruff. File này **sạch
trên main** và **bẩn trên PR** — nghĩa là chính PR tạo ra nó, không phải nợ có sẵn.
Phần chưa format đúng là hai khối trong vòng lặp sinh canary mà bản vá blocker A thêm vào.

Sửa mất một lệnh:

```bash
$(scripts/ruff_pinned.sh) format scripts/check_api_contract.py
```

Tôi đã chạy thử lệnh đó trong cây của mình rồi hoàn nguyên: sau khi format, cổng ruff
xanh, bộ đọc vẫn ra **67 đường dẫn**, `--selftest` ĐẠT, 31/31 ca liên quan xanh.
Không có tác dụng phụ. Đây là FAIL cơ học, không phải FAIL thiết kế.

## Đo tại đâu

```
đo tại   3795c80  (head #397, khớp head trên GitHub lúc tôi đo)
sha này  là nhánh CHƯA merge
cây gộp  5aa7d33 = 3795c80 ⊕ origin/main@880cd6d, gộp KHÔNG xung đột một dòng nào
```

`origin/main` nhích **hai lần** trong lượt đo của tôi: `b9362d5` → `880cd6d` (#415 vào
giữa chừng). Tôi đo lại toàn bộ cây gộp trên `880cd6d`; số dưới đây là của lần đo sau.

## Blocker A — bộ đọc route mù đi mà vẫn thoát 0: ĐÃ GỠ, VÀ ĐÃ CÓ CỔNG GÁC

| | đường dẫn đọc được | mã thoát |
|---|---|---|
| `9df1c82` (bản tôi FAIL) ⊕ main | **13** / 19 lời gọi | 0 |
| `3795c80` ⊕ main `880cd6d` | **67** / 79 lời gọi | 0 |

Bản vá đẩy bốn tên `callAsActor` / `callAnonymous` / `translatedAsActor` /
`translatedAnonymous` vào `REQUEST_FUNCTIONS`, và — quan trọng hơn — thêm
`test_every_wrapper_it_reads_is_still_declared_in_api_ts`.

**Đột biến 1 — đúng kiểu hỏng tôi đã báo.** Đổi tên khai báo `callAsActor` trong
`api.ts` thành `callAsActorRenamed`:

```
FAILED tests/test_api_contract.py::ReaderDoesNotGoBlind::
       test_every_wrapper_it_reads_is_still_declared_in_api_ts
1 failed, 12 passed
```

**BỊ GIẾT**, kèm thông điệp chỉ đúng chỗ phải sửa. Nền trước đột biến: 13/13 xanh.
Cổng này cắn thật, không phải cọc canh trang trí.

## Blocker B — cây gộp không biên dịch: ĐÃ GỠ

Đối chứng, đo trên chính `origin/main@880cd6d`:

```
9df1c82 ⊕ main  →  src/api.ts(1013,20): error TS2304: Cannot find name 'call'.
                   src/api.ts(2386,24): error TS2304: Cannot find name 'call'.
                   TSC_EXIT=2          (gộp KHÔNG xung đột — lỗi ngữ nghĩa)

3795c80 ⊕ main  →  TSC_EXIT=0
```

Lỗi cũ tái lập được, bản mới sạch. Hai chỗ đó là `GET /bank-recipients/{id}` và
`POST /bills/{id}/split` — đường hero, nên đây là chỗ đáng gác.

## Cổng đã chạy trên cây gộp `5aa7d33`

| cổng | kết quả |
|---|---|
| `pytest services/api/tests tests -q` | **2677 passed, 0 failed**, 580 skipped, 4901 subtests |
| `npm test` (apps/mobile) | **933 pass, 0 fail** |
| `npx tsc --noEmit` | **EXIT 0** |
| `check_api_contract.py` | 67 đường dẫn / 79 lời gọi, EXIT 0 |
| `check_api_contract.py --selftest` | ĐẠT |
| `check_actor_headers.py` | ĐẠT, 138 lời gọi đều gửi `X-Actor-ID` |
| `scripts/ruff_changed.sh` | **EXIT 1 ← blocker duy nhất còn lại** |
| `ruff check` (3 file đã sửa) | All checks passed |

## Phát hiện kèm theo — KHÔNG phải blocker của #397

Bộ đọc hợp đồng vẫn mù được theo **hướng cộng thêm**, và lỗ này **có sẵn trên main**,
không do #397 tạo ra. Tôi đo cả hai bên để khỏi đổ oan:

Thêm một wrapper mới hợp kiểu rồi chuyển các lời gọi qua nó, không báo cho bộ đọc:

| cây | trước | sau đột biến | cổng | test |
|---|---|---|---|---|
| main `b9362d5` (chưa có #397) | 67 đường dẫn | **53** | vẫn in "khớp hợp đồng", EXIT 0 | 12/12 xanh |
| #397 `3795c80` | 67 đường dẫn | **53** | vẫn in "khớp hợp đồng", EXIT 0 | 13/13 xanh |

`tsc` xanh ở cả hai vì mã hoàn toàn hợp lệ. 14 đường dẫn thôi được đọc mà không cổng
nào kêu.

Ca mới của #397 gác hướng **xoá/đổi tên** (tên bộ đọc biết mà `api.ts` không còn khai
báo). Nó không gác được hướng **thêm** (tên `api.ts` khai báo mà bộ đọc chưa biết) —
vì `REQUEST_FUNCTIONS` là danh sách viết tay, và một danh sách viết tay không tự biết
mình thiếu.

Vì lỗ này có trước #397 và #397 làm nó **hẹp lại** chứ không rộng ra, đây là
**suggestion + việc nối tiếp**, không phải blocker. Đề nghị mở phiếu riêng: đối chiếu
hai chiều giữa `REQUEST_FUNCTIONS` và các hàm trong `api.ts` thực sự gọi `send()`.

## Ô CHƯA quét

- `tests/postgres` — **580 skipped**, không có `MOBILE_TEST_DATABASE_URL`. Skip không phải xanh.
- `npm run test:e2e` — chưa chạy, không dựng uvicorn + Postgres trong lượt này.
- Trang khách, ma trận trạng thái × sáng/tối × 320/390/1440 — chưa quét.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, cần leader và một điện thoại thật.
- `make gate` / `make gate-merge` đầy đủ — chưa chạy; tôi chạy từng cổng lẻ như bảng trên.
- Đường bấm thật của người dùng trên #397 — chưa đi bộ; PR này là thay đổi tầng kiểu.

## Tiêu chí gỡ chặn

Chạy `$(scripts/ruff_pinned.sh) format scripts/check_api_contract.py`, commit, đẩy.
Tôi chỉ cần đo lại đúng một cổng (`scripts/ruff_changed.sh`) là chuyển PASS —
hai blocker cũ đã đóng, không mở lại.
