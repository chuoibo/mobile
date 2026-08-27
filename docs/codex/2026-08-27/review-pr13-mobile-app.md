# Review PR #13 — app Expo và thay đổi repo guard

## Metadata bắt buộc

- **Nhánh:** `origin/claude/mobile-app`
- **Commit SHA:** `0051e4bc774d6eb349ee0c9211c5496d7a6d467f`
- **Base đối chiếu:** `origin/main@4acac3319f3369270a226e6fc3b818979b330d4f`
- **protocol_version:** `n/a` — PR đổi prototype sản phẩm và scanner, không đổi
  snapshot `docs/protocol/v1/`
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **4**

## Kết luận ngắn

Bốn màn hình có hướng đúng ở nhiều chỗ: không có bulk share, đếm lượt chuyển
trước, hiển thị rounding, dữ liệu offline được gắn nhãn giả, typecheck hiện xanh.
Nhưng không thể merge: exemption lockfile vẫn là cửa lọt dữ liệu, client tự tạo
một allocator thứ hai bằng JS Number, identity đổi theo vị trí khi sửa danh sách,
và state machine cho phép đi từ xác nhận proposal tới publish mà không có hai
cổng payer acknowledgement và bank recipient readiness.

## Blocker còn mở

### PR13-01 — Chỉ cần marker lockfile là được miễn toàn bộ long-number/base64

- **Loại blocker theo charter mục 4:** (3) quyền riêng tư/bảo mật.
- **Dẫn chứng:** `is_generated_lockfile` chỉ tìm một substring như
  `"lockfileVersion"` trong 8 KiB đầu (`scripts/repo_guard.py:210–226`). Nếu có,
  scanner bỏ aggregate rule cho toàn file (`:681–687`) và loại mọi finding
  `long-number`/base64 trên mọi dòng (`:776–777`). Test chỉ chứng minh file **thiếu**
  marker không được miễn (`tests/test_repo_guard.py:654–692`); nó không đặt dữ
  liệu nhạy cảm tổng hợp vào một lockfile vốn hợp lệ. Phản ví dụ thực chạy: JSON
  có `name`, `lockfileVersion: 3`, `packages`, thêm một identifier 14 chữ số tổng
  hợp và một blob base64 tổng hợp; kết quả
  `generated_lockfile=True`, `rules=[]`.
- **Hậu quả:** một `package-lock.json` thật vẫn có thể chứa field lạ do merge,
  tool lỗi hoặc paste nhầm; chính marker hợp lệ làm số tài khoản và bill base64
  trong phần còn lại trở nên vô hình. Đổi “tin tên file” thành “tin một substring”
  chưa đóng cửa sau.
- **Tiêu chí gỡ chặn:** không miễn `long-number` hoặc payload rule trên **toàn
  file**. Nếu cần giảm false positive, parse đúng format/version và chỉ miễn các
  value ở field sinh máy có schema rõ như integrity/resolved; field ngoài schema
  vẫn phải quét. Thêm regression: một lockfile hợp lệ có marker và dependency
  bình thường nhưng chứa riêng identifier dài/blob tổng hợp phải bị chặn, output
  chỉ ghi match/vị trí đã che. Một phương án an toàn hơn là allowlist path + digest
  có review, chấp nhận cập nhật digest khi dependency đổi.

### PR13-02 — Chế độ offline tạo allocator TypeScript thứ hai và dùng số thực trung gian

- **Loại blocker theo charter mục 4:** (1) vi phạm Shared Team Invariants/ADR;
  (2) sai tiền.
- **Dẫn chứng:** đầu `api.ts:8–10` nói “Nothing here computes money” và cấm một
  implementation TypeScript thứ hai, nhưng `fixtureProposal` ngay dưới lại chia
  bằng `Math.floor(draft.totalVnd / n)`, tự tính deficit, tie-break và allocations
  (`api.ts:32–56`). Phép `/` tạo số thực trung gian, trái luật “integer dong; no
  float even in intermediate values”. Input lại parse bằng
  `Number(amount.replace(/\D/g, ""))` mà không khóa cận `10**12`
  (`NhapKhoanChi.tsx:32–39`). Phản ví dụ tổng hợp: chuỗi
  <!-- repo-guard: allow=long-number reason=synthetic-js-safe-integer-boundary-example -->
  `9007199254740993` bị parse thành `9007199254740992` nhưng
  `Number.isInteger` vẫn là true.
- **Hậu quả:** banner “dữ liệu giả” không biến phép chia sai contract thành an
  toàn. Demo có thể hiển thị, tạo obligation và chia sẻ một phân bổ do client tự
  suy ra, khác server/golden corpus; input ngoài miền có thể bị đổi số âm thầm.
- **Tiêu chí gỡ chặn:** xóa logic allocator khỏi client. Fake tất định phải nằm
  sau cùng interface API và trả **response fixture đã tính trước** từ corpus tổng
  hợp, không tính theo input bằng JS. Khi nối thật, server là nơi duy nhất phân
  bổ. Parse/validate amount từ chuỗi, từ chối ngoài `0..10**12` trước khi đổi
  sang `number`; thêm test biên và test client không chứa arithmetic phân bổ.

### PR13-03 — ID theo vị trí không ổn định; sửa danh sách có thể đổi người ứng tiền

- **Loại blocker theo charter mục 4:** (2) sai tiền; (1) vi phạm ranh giới định
  danh.
- **Dẫn chứng:** mỗi render tái sinh ID `p${index + 1}` từ chuỗi tên
  (`NhapKhoanChi.tsx:29–36`) trong khi `advancerId` được giữ ở state riêng
  (`:27`). Sau khi chọn `p2`, chèn/xóa/đổi thứ tự một tên ở trước vẫn để
  `chosen=true` nếu còn `p2`, nhưng `p2` giờ là người khác. Comment nói “position
  is the identity”; vị trí chỉ là index hiện thời, không phải identity ổn định.
- **Hậu quả:** người dùng có thể chọn đúng người trả trước, sửa danh sách, rồi
  bấm “Chia tiền” với một người ứng khác mà UI không buộc xác nhận lại. Tie-break,
  recipient và nghĩa vụ sau đó đều chạy theo sai ID.
- **Tiêu chí gỡ chặn:** participant phải là object state có ID ổn định, sinh một
  lần khi thêm người và không phụ thuộc thứ tự/display name. Nếu vẫn dùng parser
  chuỗi tạm, mọi thay đổi membership/order phải xóa lựa chọn advancer và bắt chọn
  lại. Thêm test insert/delete/reorder/duplicate-name sau khi đã chọn, chứng minh
  không đổi identity âm thầm.

### PR13-04 — State machine bỏ qua hai cổng bắt buộc trước publish

- **Loại blocker theo charter mục 4:** (1) vi phạm spec/cổng; (3) authorization.
- **Dẫn chứng:** spec mục 8.3 yêu cầu trước publish phải có payer acknowledgement
  và `BankRecipientSnapshot` hợp lệ (`docs/superpowers/specs/
  2026-08-25-group-hangout-ai-design.md:390–400`). Trong `App.tsx:60–80`, bấm
  xác nhận proposal gọi `openBatch`, rồi màn đợt thu gọi thẳng `publishBatch`;
  không có state/action nào cho hai cổng. Offline implementation cũng tạo
  obligations và envelopes trực tiếp (`api.ts:70–98`), sau đó `ChiaSe` mở share
  sheet thật.
- **Hậu quả:** prototype dạy và cố định một flow cho phép phát thu dưới danh
  nghĩa người ứng tiền trước khi họ xác nhận, đồng thời không có nơi thiết lập /
  kiểm tra người nhận. Khi tắt `OFFLINE`, backend đúng sẽ chỉ trả lỗi mà app không
  có đường khắc phục; backend yếu hơn sẽ thành lỗi authorization vật chất.
- **Tiêu chí gỡ chặn:** biểu diễn rõ trạng thái payer acknowledgement và bank
  recipient readiness từ backend; nút publish phải disabled/không được gọi cho
  tới khi cả hai cổng qua, với đường hành động để hoàn tất hoặc tách nghĩa vụ bị
  chặn theo spec. Thêm test state-machine dương/âm và test không mở Share sheet
  trước publish hợp lệ.

## Bằng chứng kiểm tra

- `node packages/shared/money.test.mjs` → **10 golden cases + 6 refusals** xanh;
  đây chỉ chứng minh formatter, không chứng minh phép chia trong `fixtureProposal`.
- Trên snapshot merge với `origin/main`, `python3 -m pytest services/api/tests
  tests -q` → **228 passed, 7 skipped, 4242 subtests passed**; bảy ca skip đều
  là PostgreSQL live do không có URL test.
- `python3 scripts/repo_guard.py tree HEAD` → xanh trên 148 file, nhưng phản ví
  dụ PR13-01 vẫn trả `rules=[]`; tree xanh không chứng minh exemption an toàn.
- `npm ci` → **467 package được cài thành công**; sau đó
  `npx tsc --noEmit` → exit 0. Typecheck vì vậy đã tái lập được từ
  install sạch trong worktree tạm.
- `git diff --check` → xanh.
- Chưa bật app trên emulator/thiết bị trong sandbox; chưa có bằng chứng về layout,
  thao tác Share sheet hoặc accessibility runtime. Đây là bất định cần QA, không
  được dùng để thay bốn blocker từ code path ở trên.

## Suggestion — không chặn

- Đưa `LockfileExemptionTests` lên trước khối `if __name__ == "__main__"`; hiện
  chạy file bằng `python tests/test_repo_guard.py` sẽ gọi `unittest.main()` trước
  khi class này được định nghĩa. Pytest vẫn discover được, nên không nâng thành
  blocker.

## Verdict cuối

**`REQUEST_CHANGES`.** Không có bất đồng thiết kế đủ để `REJECT`; các hướng UI
chính có thể giữ. Nhưng guard bypass, money path và authorization gate phải sửa
trước khi merge.
