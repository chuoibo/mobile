# Nhật ký Codex — 2026-08-27

## Metadata

- **Work ID:** W9a/C-01 — sửa repo guard; review W0 của Claude
- **Nhánh:** `codex/p0-w9a-repo-guard`
- **HEAD trước thay đổi:** `0ea765bdc9c93c32e9b21fa62fa49042b462c715`
- **W0 được review:** `e98fc7ad018764441b6a320e32c8b732a513ef2d` trên `claude/p0-w0-field-protocol`
- **protocol_version:** C-01 là `n/a`; W0 tự khai `v1` nhưng còn **DRAFT**
- **Dữ liệu dùng để test:** chỉ byte/chuỗi tổng hợp sinh trong test và temporary Git repository; không mở hoặc dùng dữ liệu participant

## Hôm nay đã làm gì

1. Đọc toàn bộ review tấn công W9a và truy nguyên hai ca C-01 tới `content_findings`.
2. Thêm rule chặn data URI base64 và dòng dài có mật độ base64 cao, độc lập đuôi file.
3. Thêm test hồi quy đúng hai đường lọt, test output không lộ payload/path và test âm tính cho SHA-256, chữ ký cùng golden-vector JSON dài.
4. Cập nhật tài liệu rule, threshold, annotation, false-positive story và giới hạn còn lại của scanner.
5. Pin exact path + SHA-256 cho review tấn công đã nằm trên `main`; file này chứa ba số fixture tổng hợp đã được reviewer ghi rõ nhưng làm full-tree scan đỏ. Không sửa nội dung review; đổi một byte làm miễn trừ mất hiệu lực.
6. Đối chiếu ADR-0003, charter, backlog với tiêu chí gỡ B-01/B-02 gốc.
7. Đọc toàn bộ năm tài liệu W0 bằng `git show` tại đúng SHA, đối chiếu spec/ADR và viết review riêng.

## C-01 — thay đổi kỹ thuật

### Hai rule mới

- `data-uri-base64`: chặn marker `data:<mime>;base64,` không phân biệt hoa/thường, có hỗ trợ MIME parameters và không phụ thuộc đuôi file. Rule này không cần dòng dài.
- `dense-base64-line`: chặn dòng **dài hơn 4 KiB** khi ít nhất **98% byte** thuộc alphabet base64/base64url.

Mode `staged` vẫn chỉ xét dòng thêm/thay trong index. `tree`, `range`, `history` xét toàn bộ snapshot. Blob binary hoặc text trên 2 MiB vẫn fail closed ở `controlled-artifact`.

### Không rò output

Cả hai rule chỉ render:

```text
<redacted-base64-line> (line-bytes=N)
```

Không đưa raw line hoặc raw match vào `Finding`. Integration test kiểm tra output không chứa tên file, prefix payload hay payload. Path tiếp tục bị che theo cơ chế cũ.

### False-positive story

- SHA-256 đơn lẻ và chữ ký base64 thông thường ngắn hơn 4 KiB không bị rule mật độ chặn.
- Golden-vector JSON tổng hợp dài hơn 4 KiB với nhiều field/hash/signature được test âm tính thật.
- Fixture hợp lệ là một encoded blob dài có thể dùng annotation đúng rule, sát dòng, có reason; không miễn thư mục.
- Marker data URI luôn bị chặn mặc định kể cả khi ngắn; nếu là asset tổng hợp/công khai thật sự cần thiết thì phải annotation riêng sau review.

Ngưỡng này cố ý không hứa phát hiện base64 thô đã được ngắt thành nhiều dòng ngắn hoặc làm rối. Tài liệu đã khai giới hạn đó; quy tắc gốc dữ liệu thật không vào repo/worktree không đổi.

## Kiểm chứng C-01

- `python3 -m unittest discover -s tests -p 'test_repo_guard.py' -v` — **17/17 pass**.
- Ca hồi quy staged tạo data URI JPEG tổng hợp khoảng 24 KiB trong `.md` và base64 thô khoảng 35 KiB trong `.md`; cả `data-uri-base64` và `dense-base64-line` đều chặn.
- Test threshold xác nhận đúng 4 KiB đi qua, 4 KiB + 1 byte bị chặn.
- Test data URI chạy với `.md`, `.py` và file không đuôi.
- Test âm tính: grouped VND cũ, SHA-256, chữ ký, golden-vector JSON >4 KiB và annotation hẹp.
- `ruff check` — pass; `ruff format --check` — pass; `py_compile` — pass; `git diff --check` — pass.
- Candidate staged scan trong Git repo tạm — **pass, 6 file scan**.
- Candidate full-tree sau exact-digest allowlist — **pass, 22 file scan**.
- Candidate range `base..head` — **pass, 22 file scan trong 1 commit**.
- Full-tree scan trước allowlist tìm đúng 3 fixture số tổng hợp đã có trong review Claude trên `main`; không có finding mới từ C-01/docs. Pin exact digest xong thì cả tree và range xanh.

## Xác nhận B-01 và B-02

### B-01 — **XÁC NHẬN ĐẠT tiêu chí gỡ**

ADR-0003, charter mục 3/3.1 và backlog W9a-E đã có đủ mọi điều kiện tôi yêu cầu:

- tách `artifact_complete` khỏi `enforcement_active`;
- chỉ `enforcement_active` mới mở FIELD-GATE;
- giao **LEADER** bật required check `repo-guard`, bắt buộc PR, chặn direct push/giới hạn bypass;
- bắt buộc PR dry-run âm tính phải bị chặn thật;
- lưu bằng chứng cấu hình không chứa PII trong gate packet.

Không còn khoảng trống DRI hay đánh đồng workflow file với enforcement đang hoạt động.

### B-02 — **KHÔNG XÁC NHẬN; tiêu chí gỡ chưa đạt**

ADR-0003 nói đã bỏ ngoại lệ recursive review bằng cách cho review doc commit thẳng vào `main`. Nhưng đây là chuyển ngoại lệ sang một đường bypass khác:

1. Charter mục 2 yêu cầu review doc direct-push vào `main`.
2. Charter mục 3.1 và W9a-E đồng thời yêu cầu PR bắt buộc và direct push bị chặn để đạt `enforcement_active`.
3. Giới hạn `docs/<owner>/<date>/review-*.md`, “chỉ Markdown” hiện vẫn là quy tắc văn bản; chưa có control trước khi commit vào `main` chứng minh commit không mang thêm executable, binary, symlink hay path khác.

Vì vậy quy trình review doc sẽ **không chạy được** khi B-01 được enforce đúng, trừ khi cấp bypass; nhưng scope và bằng chứng của bypass đó chưa được định nghĩa. Đây đúng loại lỗ tái lập mà B-02 ban đầu chỉ ra.

Tiêu chí gỡ còn lại: hoặc quay lại review-only PR và triển khai scope check có test âm tính như phương án (a) ban đầu; hoặc sửa ADR/charter/W9a-E để định nghĩa một cơ chế bypass hẹp, được enforce trước khi vào `main`, có bằng chứng tái lập rằng chỉ đúng review Markdown ở path cho phép đi qua. Chỉ lời hứa về path không đủ.

## Review W0

- **Verdict:** `REQUEST_CHANGES`
- **Blocker:** 6
- **Review:** `docs/codex/2026-08-27/review-claude-w0-2026-08-27.md`

Bốn điểm Claude tự khai được xử lý thẳng:

- Đường B không thể prime hành vi đã xảy ra trong cửa sổ đã đóng, nhưng vẫn làm lệch phân loại mẫu số và chưa có rule gate khi A/B bất đồng.
- `kappa = 0,6` là convention tuỳ ý, không đủ bảo vệ hai lớp hiếm quyết định “phần mềm hay dịch vụ”.
- Sàn 50% và baseline không xung đột; ngưỡng đúng là đồng thời đạt cả hai.
- Q1/Q2 trước Q3 đúng về precedence; nhánh Q2 “có thể có input → human judgment” và Q4 “model có khả năng hợp lý” chưa tái lập được.

Ngoài bốn điểm đó, tử số chính hiện đếm draft quá sớm và measurement contract thiếu dữ kiện/join key để tính lại các metric.

## Kết luận về tách đóng băng `02-measurement-contract.md`

Tách version **có thể làm**, nhưng không đóng băng riêng file hiện tại. `02-` còn phụ thuộc định nghĩa ở `00-`, cây nhãn ở `01-`, tử số/mẫu số ở `03-`, cohort/modality chưa chốt và consent/provenance/retention của W9. `schema_version` cũng chưa có giá trị độc lập với `protocol_version`.

Đường khả thi là ADR mới tách `measurement_contract_version` khỏi `protocol_version`, hoàn thiện schema superset, và ghi rõ partial freeze chỉ mở W1 build/test bằng fixture tổng hợp — không mở W3, dữ liệu thật hay FIELD-GATE.

## File thay đổi trong lượt này

- `scripts/repo_guard.py`
- `tests/test_repo_guard.py`
- `.repo-guard-allowlist.json`
- `docs/security/repo-guard.md`
- `docs/codex/2026-08-27/00-nhat-ky.md`
- `docs/codex/2026-08-27/review-claude-w0-2026-08-27.md`

Không commit, không sửa Git index dùng chung và không chạm `/home/lakiet/mobile`.
