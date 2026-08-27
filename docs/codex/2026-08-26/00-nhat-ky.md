# Nhật ký Codex — 2026-08-26

## Metadata

- **Work ID:** W9a — Repo guard
- **Nhánh:** `codex/p0-w9a-repo-guard`
- **Base SHA:** `1c9f18f3d45e6275235d7fbbe528b5aae0a9d643`
- **protocol_version:** `n/a` — W0 chưa có snapshot protocol; guard áp dụng trước mọi version
- **Dữ liệu dùng để build/test:** chỉ dữ liệu tổng hợp hiển nhiên giả, domain `.invalid` và byte giả; không mở hoặc dùng dữ liệu người tham gia

## Hôm nay đã làm gì

1. Đọc và đối chiếu `docs/team/charter.md`, `docs/team/backlog.md`, ADR-0001, ADR-0002 và các mục 13, 15, 16 của spec mà chúng viện dẫn.
2. Thêm quy ước storage thật ở ngoài repo/worktree: `/srv/mobile-study-private/<protocol_version>/<study_id>/`, kèm yêu cầu leader provision access control trước FIELD-GATE.
3. Mở rộng `.gitignore` cho các root data/export, file response/participant export, spreadsheet và database thường gặp.
4. Viết `scripts/repo_guard.py` dùng Python standard library, không phụ thuộc package ngoài.
5. Thêm hook `.githooks/pre-commit` quét staged diff và workflow `.github/workflows/repo-guard.yml` quét tree + từng commit mới.
6. Thêm allowlist exact `path + SHA-256 + rule + reason` cho artifact tổng hợp/công khai; forbidden data path không allowlist được.
7. Thêm test unit và integration chỉ sinh fixture giả trong temporary Git repository.
8. Viết hướng dẫn vận hành guard và runbook xử lý khi dữ liệu đã vào worktree, commit hoặc remote history.
9. Review thật bốn tài liệu của Claude tại `review-claude-2026-08-26.md`.

## Quyết định thiết kế

### Scanner đọc Git object, không đọc nhầm worktree

Mode `staged` lấy blob từ index và chỉ quét dòng thêm/thay trong staged diff. Path, binary/export và rename vẫn được kiểm tra ở cấp file. Một bản unstaged khác trên disk không thay đổi kết quả pre-commit.

Mode CI quét toàn bộ tree tại HEAD và toàn bộ tree của từng commit trong range. Vì vậy ca “commit PII rồi xoá ở commit sau trong cùng PR” vẫn đỏ và buộc rewrite history, không chỉ sửa tip.

### Output không mang raw PII

Finding chỉ chứa rule, mã file `Fxxxx`, dòng/cột, path đã che và match đã che. Scanner không giữ raw match trong object finding, không in source line, không chuyển tiếp stderr của Git, và suppress raw exception. Test integration xác nhận output không chứa email giả hoặc filename export giả đã dùng để kích hoạt rule.

### Binary/export fail closed và allowlist hẹp

Ảnh, PDF, archive, spreadsheet, database, CSV/TSV/JSONL, binary không UTF-8/NUL, file text quá 2 MiB, symlink và gitlink đều cần allowlist đúng path và digest. Đổi nội dung hoặc đổi path làm approval mất hiệu lực. `forbidden-path` không thể miễn.

### False-positive story

- Tiền VND có phân nhóm và đơn vị, như `100.000.000 VND`, không bị coi là identifier dài.
- Match tổng hợp hợp lệ dùng annotation ngay cạnh và đúng rule, có `reason`; không miễn cả file/thư mục.
- Artifact/export tổng hợp dùng allowlist theo digest; content rule chỉ miễn nếu entry nêu rõ rule tương ứng.
- Dữ liệu thật không bao giờ được annotation hoặc allowlist.

## Cái gì chặn cái gì

| Control | Chặn/giảm thiểu trực tiếp | Lỗ hổng còn lại |
|---|---|---|
| Storage boundary ngoài repo | Dữ liệu thật không đi qua Git/worktree | Leader chưa provision/kiểm chứng access control |
| `.gitignore` | `git add` vô ý ở path/export quen thuộc | `git add -f`, copy/rename và file ở path lạ |
| Pre-commit staged scan | Phản hồi trước commit; pattern + path + artifact | Bypass bằng `--no-verify`; hook cần kích hoạt |
| CI full-tree + commit-range | Chặn merge tree bẩn và commit trung gian bẩn | Chỉ có hiệu lực khi check là required; không ngăn object đã push lên feature branch |
| Exact-digest allowlist | Binary/export mới hoặc đổi byte phải review lại | Scanner không nhìn được nội dung binary; reviewer có thể phê duyệt sai |
| History runbook | Containment, rewrite, cache/fork/clone cleanup | Không thể hứa xoá khỏi bản sao ngoài quyền kiểm soát |

## Kiểm chứng đã chạy

- `python3 -m unittest discover -s tests -p 'test_repo_guard.py' -v` — **11/11 pass**.
- `python3 scripts/repo_guard.py tree HEAD` trên base trước thay đổi — **pass, 9 file scan**.
- Index tạm biệt lập chứa toàn bộ diff: scanner trực tiếp và hook thật — **đều pass, 10 file scan**.
- Candidate commit dựng bằng Git plumbing trên index tạm: full tree — **pass, 18 file scan**; range `base..candidate` — **pass, 18 file scan trong 1 commit**.
- `ruff check` và `ruff format --check` sau format — **pass**; `py_compile`, `sh -n`, `git diff --check` và parse YAML workflow — **pass**.
- Test bao phủ: email, nhiều format điện thoại Việt Nam, số dài, VND grouped, annotation, exact digest, đủ nhóm ảnh/PDF/archive/spreadsheet/database, forbidden path, tên export, index khác worktree, log không lộ raw match/path, và PII giả chỉ tồn tại ở commit trung gian.

## Giới hạn đã biết

- Không scanner nào nhận ra mọi tên người Việt, biệt danh, địa chỉ hoặc PII theo ngữ cảnh.
- Scanner không OCR ảnh, không giải nén archive, không hiểu PDF/spreadsheet/database và không thấy PII trong ảnh nén/archive mã hoá.
- Regex bỏ sót được format lạ/obfuscation và tạo false positive; annotation/allowlist có thể bị con người lạm dụng.
- Masked log giảm phát tán qua CI nhưng không biến máy chạy scanner thành môi trường được phép chứa dữ liệu thật.
- Local hook luôn bypass được. GitHub Actions chạy sau push và chỉ bảo vệ merge nếu branch rule yêu cầu nó.
- `.gitignore` không phải access control và dữ liệu ignored trong worktree vẫn là vi phạm.

Do các giới hạn này, W9a là **lớp giảm thiểu**, không phải bằng chứng dữ liệu thật an toàn trong worktree.

## Việc còn mở ngoài engineer lane

Leader phải, trước FIELD-GATE:

1. provision và xác minh access control cho `/srv/mobile-study-private/`;
2. bật ruleset/branch protection bắt buộc PR và required check chính xác `repo-guard` trên `main`;
3. chặn direct push, giới hạn bypass và chạy PR dry-run chứng minh merge bị khoá khi check đỏ;
4. ghi bằng chứng không chứa PII vào gate packet.

Workflow file tồn tại **không** hoàn thành các bước này. Đây là leader lane. Review bốn tài liệu cũng chỉ ra rằng trách nhiệm kích hoạt required check hiện chưa sống trong ADR/backlog/charter; nhật ký này không thể thay nguồn quyết định theo chính charter mục 5.

## Trạng thái gate

- **Engineering artifact W9a:** đã implement và kiểm chứng local, đang chờ review Claude.
- **MERGE-GATE:** chưa qua; chưa có verdict artifact của Claude.
- **FIELD-GATE:** đóng; ngoài review/merge còn thiếu W9 + counsel, W4a, W0 frozen protocol, leader storage/incident readiness và required CI activation; W6 nếu phiên có công cụ tính/đề xuất tiền.

## Hạn chế môi trường bàn giao

Linked-worktree index thật nằm trong shared Git metadata dưới worktree gốc và bị sandbox của phiên này mount read-only. `git add` dừng ở bước tạo `index.lock`; tôi không đổi quyền, không sửa shared Git metadata và không đụng nội dung worktree `/home/lakiet/mobile`.

Để vẫn kiểm chứng đúng artifact sẽ commit, tôi copy index gốc sang thư mục tạm, dùng object directory tạm với object store gốc ở chế độ read-only, stage toàn diff, chạy hook, dựng candidate tree/commit và quét staged/tree/range như ghi trên. Working tree hiện chứa đầy đủ diff nhưng phiên này chưa thể tạo commit/ref thật. Đây là blocker hạ tầng cho sản phẩm “commit trên nhánh”, không phải lý do coi MERGE-GATE đã qua.
