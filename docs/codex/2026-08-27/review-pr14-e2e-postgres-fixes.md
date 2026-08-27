# Review PR #14 — tên ngân hàng trên trang khách

## Metadata bắt buộc

- **Nhánh:** `origin/claude/e2e-postgres-fixes`
- **Commit SHA:** `ae06a4764467176fdf09a0560c63e56fa309bab2`
- **Base đối chiếu:** `origin/main@4acac3319f3369270a226e6fc3b818979b330d4f`
- **protocol_version:** `n/a` — PR đổi projection hiển thị, không đổi snapshot
  `docs/protocol/v1/`
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **1**

## Kết luận ngắn

Mapper BIN → tên có fallback trung thực cho mã chưa biết, nhưng nó là dead path
trên chính đường PostgreSQL mà PR nói đã sửa. `SqlAlchemyApiRepository` luôn
đưa một `bank_name` truthy dạng `Ngân hàng <BIN>`; toán tử `or` trong view giữ
nguyên chuỗi đó và không gọi mapper. Các test mới chỉ gọi hàm rời nên vẫn xanh.

## Blocker còn mở

### PR14-01 — Fix không chạy trên projection PostgreSQL thật

- **Loại blocker theo charter mục 4:** (1) không đạt hành vi PR/spec; (5) kết
  quả/test không tái lập được end-to-end.
- **Dẫn chứng:** `SqlAlchemyApiRepository.get_guest_envelope()` tạo
  `"bank_name": f"Ngân hàng {snapshot.bank_bin}"`
  (`services/api/app/api/repository.py:900–910`). PR đổi view thành
  `obligation.get("bank_name") or bank_display_name(obligation["bank_bin"])`
  (`services/api/app/web/guest_view.py:113–123`). Chuỗi từ repository luôn
  truthy, nên vế sau không chạy. Thực nghiệm với envelope tổng hợp đúng shape
  của projection, BIN `970407` và `bank_name="Ngân hàng 970407"` cho output vẫn
  là **`Ngân hàng 970407`**, không phải `Techcombank`. Bốn test mới ở
  `test_banks.py:18–39` chỉ test hàm `bank_display_name` và tính nội tại của dict;
  không test `build_guest_view` với shape thật, càng không test HTTP/PostgreSQL.
- **Hậu quả:** merge PR không thay đổi điều khách nhìn thấy trên đường production;
  bug được mô tả trong commit vẫn nguyên. Dấu xanh tạo bằng chứng sai phạm vi:
  mapper đúng khi gọi trực tiếp không chứng minh mapper được gọi.
- **Tiêu chí gỡ chặn:** hoặc projection backend trả tên canonical/để trống field
  derived, hoặc web view chủ động derive từ `bank_bin` thay vì ưu tiên placeholder
  `Ngân hàng <BIN>`. Bắt buộc có regression đi qua `build_guest_view` với đúng
  envelope của `SqlAlchemyApiRepository`, và một ca PostgreSQL + HTTP sau Alembic
  assert trang chứa `Techcombank` đồng thời không chứa `Ngân hàng 970407`.

## Bằng chứng kiểm tra

- Targeted `test_banks.py` + `test_guest_page.py` → **27 passed, 14 subtests
  passed**; blocker vẫn tái hiện vì các test không đi qua projection thật.
- Suite chuẩn → **225 passed, 7 skipped, 4214 subtests passed**; 7 skip là tầng
  PostgreSQL vì thiếu URL test.
- `ruff check` ba file đổi → xanh; `ruff format --check` muốn format lại
  `guest_view.py`. Đây là suggestion style, không phải blocker.
- Không thể tự chạy Docker/PostgreSQL do sandbox từ chối Docker socket. Commit
  mô tả một lần chạy live của tác giả, nhưng không có test artifact trong diff
  để reviewer tái lập chính assertion tên ngân hàng.

## Suggestion — không chặn

- `BANKS` là dữ liệu định tuyến có thể thay đổi nhưng file không ghi nguồn hay
  `verified_at`. Khi sửa blocker, nên gắn nguồn chính thức/version và giữ fallback
  cho mã chưa biết; review này không suy đoán mapping hiện tại đúng hay sai.

## Verdict cuối

**`REQUEST_CHANGES`.** Hướng sửa cục bộ là hợp lý nên không `REJECT`, nhưng PR
chưa sửa được hành vi production mà nó tuyên bố sửa.
