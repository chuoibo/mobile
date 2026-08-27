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

---

## Bổ sung cùng ngày — C-02 và review ADR-0004

### Metadata lượt bổ sung

- **Work ID:** W9a/C-02; W6 contract review
- **Nhánh:** `codex/p0-w9a-repo-guard`
- **HEAD trước thay đổi:** `50a8491b1fca02e5743c89b589f5a6b718d4dc99`
- **C-01 đã được leader commit hộ:** `7330a3f006ba3ff089ecdecf0fac604b7f9d4b01`
- **Allocator contract được merge để review:** ADR `36fa45e716aa586454b29a70a4ae5645c6a4cd7f`, golden/self-check `bc08897ab5f1fa03cf984099d1738094ac83d582`
- **Dữ liệu dùng để test:** chỉ byte tổng hợp sinh runtime, JSON/golden đã track và Git repository tạm; không mở hoặc dùng dữ liệu participant
- **Commit:** không tạo theo yêu cầu của leader

### Tái tạo C-02 trước khi sửa

Bộ 17 test C-01 ban đầu xanh, nhưng năm probe độc lập xác nhận đúng lỗ hổng mới:

| Ca | Input tổng hợp | Trước C-02 |
|---|---|---|
| e1 | base64 của blob khoảng 22 KiB, wrap 76 | lọt |
| e2 | cùng blob, wrap 1000 | lọt |
| e5 | token base64 3000 byte trong JSON string | lọt |
| e6 | token base64 3000 byte trên một dòng | lọt |
| e7 | token base64 5000 byte trên một dòng | chặn bởi `dense-base64-line` |

Không in payload trong probe; chỉ in tên ca, rule và kích thước.

### Bản vá C-02

Thêm hai content rule, giữ nguyên các rule C-01:

- `dense-base64-block`: gom dãy ít nhất hai dòng không rỗng liên tiếp; từng dòng phải có mật độ alphabet base64/base64url ít nhất 98%; **tổng byte của các dòng phải lớn hơn 4 KiB**. Detector đọc toàn staged blob để thấy biên khối nhưng chỉ báo khi khối giao với dòng thêm/thay.
- `long-base64-token`: chặn token liên tục **lớn hơn 2 KiB** thuộc alphabet base64/base64url, có tối đa hai dấu padding `=`. Rule chạy bất kể tổng độ dài hay mật độ của dòng chứa token.

Tôi ban đầu cân nhắc sàn 64 byte cho từng dòng của khối để giảm false positive, rồi **bỏ sàn đó trước khi chốt**: nó tạo đường vòng hiển nhiên bằng wrap ngắn hơn 64. Regression test có thêm wrap 12 để chứng minh detector thật sự theo khối, không chỉ vá đúng hai width được báo.

Ưu tiên classification giữ hành vi cũ: một dòng đơn >4 KiB vẫn là `dense-base64-line` (e7); wrapped block là `dense-base64-block`; token 3000 byte là `long-base64-token`. Một khối được báo một finding thay vì một finding cho mỗi dòng.

Output mới chỉ chứa metadata đã che:

```text
<redacted-base64-block> (block-bytes=N, lines=N)
<redacted-base64-token> (token-bytes=N)
```

Raw path, raw dòng và raw token không đi vào `Finding`. Hai rule mới hỗ trợ allowlist ghim exact path+digest và annotation đúng rule, sát match; không tạo miễn trừ thư mục.

### Chọn ngưỡng và false positive

Ngưỡng token `> 2 KiB` được chọn ở đầu trên của khoảng 1,5–2 KiB được đề xuất để giữ khoảng cách lớn với nội dung hợp lệ hiện có. `git grep` không tìm thấy token thuộc alphabet này dài quá 300 ký tự trong tree trước thay đổi.

Các ca sau được khóa xanh bằng test:

- SHA-256 64 ký tự;
- chữ ký base64 ngắn;
- JSON golden tổng hợp dài;
- toàn bộ năm file thật trong `phase0/allocator/golden/`;
- chuỗi lặp 300 ký tự;
- đúng 2 KiB token và đúng 4 KiB khối (ngưỡng strict `>`).

Tài liệu khai thẳng false positive còn có thể xảy ra với một danh sách rất dài gồm hash thuần trên nhiều dòng liên tiếp. Payload nhỏ hơn threshold, hạ mật độ dưới 98%, chia thành đoạn không liên tiếp hoặc đổi encoding vẫn có thể lọt. Scanner vẫn chỉ là mitigation; quy tắc dữ liệu thật không vào repo/worktree không đổi.

### Kiểm chứng C-02

- `python3 -m unittest discover -s tests -v` — **23/23 pass**.
- Unit regression: e1 wrap 76 và e2 wrap 1000 bị `dense-base64-block` chặn; thêm wrap 12 cũng đỏ.
- Unit regression: e5 JSON token 3000 và e6 raw token 3000 bị `long-base64-token` chặn.
- Hồi quy C-01: e7 5000 vẫn bị `dense-base64-line` chặn.
- Integration staged tạo wrapped blob và JSON token trong repo tạm; cả hai bị chặn, output không chứa path hay prefix payload.
- Integration staged còn chứng minh detector đọc 53 dòng không đổi cạnh dòng mới thứ 54: khối chỉ vượt 4 KiB sau đúng một dòng append vẫn bị chặn.
- Annotation hẹp của cả hai rule mới được test.
- `ruff check` — pass; `ruff format --check` — pass sau khi format test; `py_compile` — pass; `git diff --check` — pass ở thời điểm kiểm tra kỹ thuật C-02.
- `python3 scripts/repo_guard.py tree HEAD` — pass, 30 file scan.
- Dùng Git index/object tạm trong `/tmp`, không sửa index dùng chung: candidate staged scan **pass, 5 file**; candidate full-tree **pass, 31 file**; candidate range `HEAD..candidate` **pass, 31 file trong 1 commit**.

### Review ADR-0004

- **Verdict:** `REQUEST_CHANGES`
- **Blocker:** 5
- **Review:** `docs/codex/2026-08-27/review-claude-adr0004-2026-08-27.md`
- **Golden đã xem:** 29 vector = 18 success + 11 error; self-check **12 test, 220 subtest pass**.
- **Kết quả số học:** tính lại toàn bộ 18 success, không tìm thấy expected output sai.

Tôi xác nhận các quyết định chính:

- #16 advancer nhận **THÊM** 1đ khi remainder bằng nhau;
- #17 byte UTF-8, G16 đúng;
- #1 mismatch bị từ chối, không co giãn;
- #3 exact share 0 hợp lệ, nhưng output/consumer phải giữ dòng participant 0đ.

Năm blocker còn lại:

1. validation và error precedence chưa gán hành vi cho amount 0, invalid/duplicate entity ID, duplicate `shared_by`, discount scope-target mismatch;
2. API hai tầng làm mất warning fallback và không định nghĩa failure của tiền đề `apportion`;
3. miền generator thiếu ràng buộc quan hệ và chưa tách success/invalid lane;
4. chín invariant cho qua một allocation trao +1đ cho remainder nhỏ hơn;
5. golden self-check hiện không khóa advancer/UTF-8/largest-remainder ranking hoặc warning fallback, và corpus thiếu một vector composition.

Vì contract chưa đóng băng, **không viết `impl_a`, không mở W6a/W6b**. Giữ blindness; chỉ bắt đầu sau một vòng ADR sửa và verdict `APPROVE`.

### File thay đổi trong lượt bổ sung

- `scripts/repo_guard.py`
- `tests/test_repo_guard.py`
- `docs/security/repo-guard.md`
- `docs/codex/2026-08-27/review-claude-adr0004-2026-08-27.md`
- `docs/codex/2026-08-27/00-nhat-ky.md`

Không commit, không sửa nhánh allocator, không viết allocator và không chạm `/home/lakiet/mobile`.

---

## Bổ sung cùng ngày — C-03 và review ADR-0004 v2

### Metadata lượt bổ sung

- **Work ID:** W9a/C-03; W6 contract review v2
- **Nhánh:** `codex/p0-w9a-repo-guard`
- **HEAD trước thay đổi:** `fb7d89d6b65f9a40453d0330b0f31c72f9759c94`
- **C-02 đã được leader commit hộ:** `a9d51ed`
- **ADR v2:** commit sửa `5cfafbe`, merge `fb7d89d`
- **Dữ liệu test:** chỉ payload tổng hợp sinh runtime, golden/doc đã track và Git repository tạm; không dùng dữ liệu participant
- **Cách ly W6:** không đọc hoặc quét nội dung `phase0/allocator/impl_b/`
- **Commit:** không tạo theo yêu cầu của leader

### C-03 — tái hiện và bản vá

Tái hiện đúng hình dạng né tránh bằng cách xen **một dòng rỗng giữa mỗi hai dòng wrap**. Trước bản vá, cả ba ca đều không có finding:

| Ca | Width | Trước C-03 | Sau C-03 |
|---|---:|---|---|
| f2 | 40 | lọt | `dense-base64-block` |
| f2b | 76 | lọt | `dense-base64-block` |
| f2d | 200 | lọt | `dense-base64-block` |

`dense_base64_blocks` giờ cho phép tối đa **một dòng rỗng/không khớp liên tiếp** giữa các dòng dense. Giới hạn là theo số gap liên tiếp, nên một dòng rỗng xen lặp lại không reset khối; hai gap liên tiếp kết thúc khối thay vì nối qua một khoảng phân cách dài.

Test mới phủ:

- f2/f2b/f2d với dòng rỗng xen lặp lại;
- f2c với dòng `-` xen lặp lại;
- cùng ba width với một dòng text không khớp xen lặp lại;
- hai gap liên tiếp phải reset, để chứng minh cửa sổ có giới hạn;
- staged integration với wrap-76 xen dòng rỗng;
- output vẫn chỉ có match/path đã che.

Tài liệu security được cập nhật đúng semantics gap và false-positive story. Scanner vẫn là mitigation; quy tắc dữ liệu thật không vào repo/worktree không đổi.

### Kiểm chứng C-03

- `python3 -m pytest tests/test_repo_guard.py -q` — **25 passed, 42 subtests passed**.
- `ruff check` — pass; `ruff format --check` — pass.
- Chạy gộp repo guard + allocator self-check — **42 passed, 361 subtests passed**; `py_compile` và `git diff --check` đều pass.
- Ma trận độc lập f2/f2b/f2d đều trả `dense-base64-block`.
- Sáu lớp false-positive tiếp tục không có finding: SHA-256/chữ ký ngắn; golden JSON thật; chuỗi lặp 300; Python 60 dòng; bảng Markdown trên 3000 byte; nguyên văn ADR-0004.
- Quét trực tiếp năm candidate file bằng chính `scan_entry` — **0 finding**; không stage và không sửa Git index dùng chung.

### Review ADR-0004 v2

- **Verdict:** `REQUEST_CHANGES`
- **Blocker:** 5
- **Review:** `docs/codex/2026-08-27/review-claude-adr0004-v2.md`
- **Baseline:** **17 test, 319 subtest pass** trên 41 golden vector.

Các sửa v2 đã đóng đúng phần lớn blocker cũ, nhưng chưa đủ đóng băng:

1. ADR còn hai danh sách precedence cùng tự nhận là đầy đủ nhưng khác nhau; câu #16 cũ cũng chưa được thay.
2. Chưa chốt `INVALID_PARTICIPANT_ID`/`INVALID_ENTITY_ID` áp vào declaration hay cả reference/advancer.
3. Chưa có concrete input/output boundary chung; `exact_shares: Fraction` xung đột với `impl_a` không dùng Fraction.
4. Valid generator thiếu cận số discount và lịch bắt buộc sát biên trên.
5. Một mutant G22 sai composition nhưng tự nhất quán vẫn làm self-check xanh **15 test, 313 subtest**; mutant hiện tại chỉ phá tổng.

Vì verdict chưa phải `APPROVE`, **không tạo `phase0/allocator/impl_a/` và không tạo `phase0/allocator/harness/`**. Blindness được giữ nguyên.

### File thay đổi trong lượt bổ sung

- `scripts/repo_guard.py`
- `tests/test_repo_guard.py`
- `docs/security/repo-guard.md`
- `docs/codex/2026-08-27/review-claude-adr0004-v2.md`
- `docs/codex/2026-08-27/00-nhat-ky.md`

Không commit, không sửa Git index dùng chung, không đọc `impl_b` và không chạm `/home/lakiet/mobile`.

---

## Bổ sung cùng ngày — C-04 và review ADR-0004 v3

### Metadata lượt bổ sung

- **Work ID:** W9a/C-04; W6 contract review v3
- **Nhánh:** `codex/p0-w9a-repo-guard`
- **HEAD trước thay đổi:** `41a63c7` (`merge: ADR-0004 v3`)
- **C-03 đã được leader commit hộ:** `1832fd2`
- **Dữ liệu test:** chỉ payload tổng hợp sinh runtime, golden/doc đã track và Git repository tạm; không dùng dữ liệu participant
- **Cách ly W6:** không đọc, import, quét hoặc chạy `phase0/allocator/impl_b/`
- **Commit:** không tạo theo yêu cầu của leader

### C-04 — bỏ hẳn khái niệm dòng liên tiếp

Xoá detector `dense_base64_blocks`, hằng gap-line và toàn bộ state nối/reset khối. Rule mới `aggregate-base64-fragments` làm đúng một phép tính trên phạm vi dòng đang quét của mỗi file:

1. tìm token dài ít nhất **8 byte** chỉ thuộc alphabet base64/base64url, kể cả tối đa hai byte padding `=`;
2. cộng tổng byte của mọi token đó, bất kể token nằm ở đâu và giữa chúng có gì;
3. chặn khi tổng **lớn hơn 16 KiB**.

Ở `staged`, phạm vi là toàn bộ dòng thêm/thay của file, không chia theo hunk. Ở `tree`, `range`, `history`, phạm vi là toàn snapshot. Số dòng trống/văn xuôi chen giữa không đi vào quyết định nên không còn hằng `N` để tấn công bằng `N+1` dòng.

Đo trước khi chọn ngưỡng:

| Nội dung | Tổng byte token với sàn 8 |
|---|---:|
| Bill tổng hợp wrap | 30040 |
| `scripts/repo_guard.py` | 9372 |
| `tests/test_repo_guard.py` trước C-04 | 8085 |
| Markdown team dài khoảng 89 KiB | 6406 |
| ADR-0004 v3 | 4455 |
| Golden JSON tổng hợp lặp hash/chữ ký | 6960 |

Ngưỡng 16 KiB giữ khoảng cách với corpus hợp lệ hiện tại nhưng vẫn chặn bill. Đây là heuristic có giới hạn được ghi thẳng: tổng không quá ngưỡng, token bị chẻ dưới 8 byte, phá bằng ký tự ngoài alphabet hoặc encoding khác vẫn có thể lọt. Scanner vẫn chỉ là mitigation.

Test biên bắt một lỗi triển khai trong lượt: token cuối có 6 byte dữ liệu + `==` phải được tính là token 8 byte. Regex đầu tiên đòi 8 byte trước padding và hụt đúng 8 byte; đã sửa để ngưỡng tính cả padding, test sau sửa báo đúng 30040 byte.

Annotation `aggregate-base64-fragments` chỉ loại token trên cùng dòng hoặc dòng ngay sau annotation khỏi tổng; không miễn toàn file. Allowlist vẫn pin exact path + digest + rule. Finding chỉ in path/match đã che cùng `aggregate-bytes` và số token.

### Kiểm chứng black-box C-04

Mỗi ca dưới đây được stage riêng trong Git repository tạm độc lập, chạy thật `python3 scripts/repo_guard.py staged`; output bị kiểm không chứa raw path hay prefix payload:

| Ca | Kết quả |
|---|---|
| h1 — xen hai dòng trống giữa mọi fragment | `aggregate-base64-fragments` |
| h2 — xen ba dòng trống | `aggregate-base64-fragments` |
| h3 — xen văn xuôi tiếng Việt | `aggregate-base64-fragments` |
| hN — xen 250 dòng trống | `aggregate-base64-fragments` |
| SHA-256 | xanh |
| nguyên văn ADR-0004 v3 | xanh |
| Python 200 dòng | xanh |
| Markdown team dài khoảng 89 KiB | xanh |
| cả sáu file golden JSON | xanh |

Unit/integration còn khóa ngưỡng strict, width 8/40/76/200, annotation theo dòng, masked output và phép cộng qua **hai hunk thêm mới cách nhau 500 dòng không đổi**; mỗi hunk riêng dưới 16 KiB nhưng tổng file vượt ngưỡng. Tài liệu security được cập nhật đúng semantics mới.

- Chạy gộp repo guard + allocator self-check: **42 passed, 378 subtests passed**.
- `ruff check`, `ruff format --check`, `py_compile` và `git diff --check`: pass.
- Quét đúng năm candidate file bằng semantics added-lines và full-file, không stage: **0 finding / 0 finding**.

### Review ADR-0004 v3

- **Verdict:** `REQUEST_CHANGES`
- **Blocker:** 2
- **Review:** `docs/codex/2026-08-27/review-claude-adr0004-v3.md`
- **Baseline:** `18 passed, 343 subtests passed`
- **Corpus thực tế:** 23 success + 18 error = 41 vector

Các sửa đúng đã được công nhận:

- V2-01 đóng: một precedence chuẩn; câu #16 đúng.
- V2-02 đóng cho bốn field occurrence được nêu.
- V2-04 đóng ở mức hợp đồng generator.
- Lõi V2-05 đóng thật: G22 tự nhất quán đỏ với pipeline check và xanh khi ablate đúng check đó; phép tính tay độc lập xác nhận golden G22 hiện tại đúng.

Hai blocker còn lại:

1. ADR vẫn đồng thời khai public `ExpenseInput -> ApportionResult` với `Fraction`/tuple và public `dict -> dict` với rational string/list. Missing key/sai wire type cũng chưa được phân loại là precondition/harness bug hay lỗi public.
2. README nói tám mutant nhưng `MUTANTS` chỉ có bảy. G11 hiện không tự nhất quán vì bỏ warning mà chính docstring nói phải có; khi sửa warning và tắt pipeline check, mutant mới đi qua như kỳ vọng.

Vì verdict chưa phải `APPROVE`, **không tạo `phase0/allocator/impl_a/` và không tạo `phase0/allocator/harness/`**.

### File thay đổi trong lượt bổ sung

- `scripts/repo_guard.py`
- `tests/test_repo_guard.py`
- `docs/security/repo-guard.md`
- `docs/codex/2026-08-27/review-claude-adr0004-v3.md`
- `docs/codex/2026-08-27/00-nhat-ky.md`

Không commit, không sửa Git index dùng chung, không đọc `impl_b` và không chạm `/home/lakiet/mobile`.
