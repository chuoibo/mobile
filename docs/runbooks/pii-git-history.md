# Runbook — khi PII hoặc dữ liệu người tham gia lọt vào Git

Runbook này áp dụng cả khi dữ liệu chỉ mới nằm trong worktree. “Chưa push” làm giảm phạm vi phát tán, không biến sự cố thành vô hại.

## 1. Dừng và cô lập

1. **Dừng commit, push, CI rerun, PR update và mọi script đang đọc file.** Không dùng `--no-verify`.
2. Không paste raw match, raw filename, screenshot, `git diff`, `git status` hoặc log chứa dữ liệu lên issue/chat/email. Chỉ dùng incident ID và loại dữ liệu ở mức khái quát.
3. Báo ngay leader và chủ sở hữu W9 qua kênh sự cố đã được phê duyệt. Nếu có credential/token thì revoke hoặc rotate trước; rewrite Git không vô hiệu hoá credential.
4. Leader tạm hạn chế quyền repo và yêu cầu mọi collaborator ngừng push. Nếu đã lên remote, coi dữ liệu đã bị lộ cho mọi account, runner, mirror, fork và cache có quyền ở thời điểm đó.
5. Đưa máy/worktree bị ảnh hưởng vào diện xử lý sự cố. Không tự copy “backup để phòng” sang thư mục khác.

## 2. Xác định mức sự cố mà không làm rò thêm

| Mức | Trạng thái | Hành động tiếp theo |
|---|---|---|
| A | File thật ở worktree nhưng chưa stage | Đã vi phạm storage boundary; operator được uỷ quyền chuyển/xoá theo W9 |
| B | Đã stage, chưa commit | Unstage trong môi trường local, rồi xử lý file như mức A |
| C | Đã commit, chưa push | Không push; object đã nằm trong object database/reflog local |
| D | Đã push hoặc không chắc | Freeze remote, rewrite phối hợp và xử lý cache/fork/clone |

Chạy scanner chỉ cho triage đã che:

```bash
python3 scripts/repo_guard.py staged
python3 scripts/repo_guard.py history HEAD
```

Scanner không thấy mọi PII, đặc biệt tên người Việt và nội dung trong binary. Người xử lý được uỷ quyền phải xác định thêm: mọi path/rename cũ, commit/ref/tag/PR liên quan, Git LFS, Actions artifact/cache, package/release, fork, mirror, backup và clone của collaborator. Việc kiểm tra raw chỉ diễn ra trong môi trường incident access-controlled; không redirect kết quả vào repo.

## 3. Mức A/B — chưa commit

1. Ở mức B, unstage file mà không xoá bản worktree. Tránh ghi raw path có PII vào shell history; dùng công cụ local được phê duyệt hoặc pathspec file đặt ở storage sự cố ngoài repo.
2. Operator/data custodian chuyển dữ liệu cần giữ về `/srv/mobile-study-private/<protocol_version>/<study_id>/` và xác minh quyền trước khi mở lại.
3. Xoá bản worktree, temp file, editor backup, notebook checkpoint và trash theo chính sách W9. Engineer không tự suy diễn rằng `rm` là xoá an toàn trên SSD/snapshot/sync storage.
4. Chạy lại `staged` và kiểm tra worktree bằng quy trình local không tạo log raw.
5. Tạo regression test mới chỉ bằng dữ liệu tổng hợp hiển nhiên giả.

## 4. Mức C — commit local, chưa push

`git commit --amend`, xoá branch hoặc reset ref **không đủ**: blob có thể còn trong reflog và object database.

1. Không push bất kỳ ref nào từ repository bị nhiễm.
2. Nếu đây là clone cô lập, đường an toàn ưu tiên là bỏ clone bị nhiễm theo quy trình xoá của W9, clone sạch lại, rồi tái tạo duy nhất thay đổi không nhạy cảm.
3. Nếu là linked worktree, object database dùng chung; coi tất cả worktree của clone đó bị ảnh hưởng. Leader phải freeze cả clone và chọn quy trình rewrite/garbage-collection có phối hợp. Không xoá một worktree rồi tuyên bố đã sạch.
4. Xác minh blob/ref/reflog bị loại trong môi trường hạn chế trước khi cho phép push lại.

## 5. Mức D — đã lên remote

History rewrite là thao tác phá huỷ, đổi commit SHA, có thể làm mất chữ ký, hỏng PR diff và làm mất thay đổi mới. Chỉ incident commander do leader chỉ định mới được mở khoá force-push và thực hiện.

### 5.1 Chuẩn bị

- Freeze mọi push; chốt mốc ref và danh sách người có clone/fork/mirror.
- Revoke/rotate credential trước nếu có.
- Tạo fresh clone riêng trong storage sự cố access-controlled. Không rewrite trực tiếp trên worktree đang phát triển.
- Cài và kiểm tra `git-filter-repo` có hỗ trợ `--sensitive-data-removal`.
- Lập manifest path cũ/mới hoặc blob ID ở ngoài repo. Filename cũng có thể là PII; manifest có cùng access control với dữ liệu thật.

### 5.2 Rewrite trong fresh clone

Nếu phải xoá toàn bộ file ở mọi path đã biết:

```bash
git filter-repo --sensitive-data-removal --invert-paths --paths-from-file <restricted-path-manifest>
```

Nếu chỉ một path, dùng `--path <git-path>`; nếu file từng đổi tên, phải liệt kê **mọi** path. Nếu PII nằm trong text cần giữ lại, dùng `--replace-text` với manifest restricted và kiểm tra kỹ binary/encoding; không dùng leaked value làm fixture trong repo.

Đọc toàn bộ báo cáo `git-filter-repo`, đặc biệt first changed commits, changed refs và orphaned LFS objects. Chạy kiểm chứng ở mục 6 trước khi đẩy.

### 5.3 Thay lịch sử remote

Sau khi leader xác nhận freeze và bản rewrite:

```bash
git push --force --mirror origin
```

Lệnh này có thể ghi đè thay đổi của người khác và thường không sửa được ref PR do forge quản lý. Leader chỉ tạm nới branch protection trong cửa sổ sự cố, rồi phải bật lại ngay required PR/check và hạn chế bypass.

Với GitHub, mở ticket Support để xử lý PR refs, cached views, server garbage collection và LFS orphan theo báo cáo rewrite. GitHub không thể xoá dữ liệu khỏi clone của người khác; fork còn ref nhiễm phải được chủ fork phối hợp xoá.

### 5.4 Làm sạch các bản sao

- Yêu cầu collaborator bỏ clone cũ và clone lại là mặc định an toàn.
- Không cho phép `git pull` rồi merge lịch sử cũ; một merge có thể tái nhiễm toàn bộ remote.
- Xử lý riêng fork, mirror, CI workspace/cache/artifact, release/package, backup và máy operator.
- Nếu không chứng minh xoá được một bản sao, tiếp tục coi dữ liệu đã bị tiết lộ ở đó.

## 6. Xác minh trước khi mở freeze

Từ fresh clone của remote đã rewrite:

1. `python3 scripts/repo_guard.py history HEAD` phải xanh; đây chỉ là kiểm tra pattern/loại file scanner biết.
2. Kiểm tra từng ref/tag/branch và từng path cũ/đổi tên trong môi trường restricted.
3. Kiểm tra object ID đã biết không còn reachable; phối hợp host để xử lý object unreachable/cache thay vì coi “không reachable” là đã bị xoá vật lý.
4. Kiểm tra LFS, PR refs, Actions artifacts/cache, release/package, fork, mirror và backup.
5. Một người thứ hai tái lập kết quả từ fresh clone và ký checklist sự cố.

Chỉ leader cùng chủ sở hữu W9/counsel, theo mức ảnh hưởng, mới quyết định nghĩa vụ thông báo, retention/deletion và thời điểm mở lại FIELD-GATE.

## 7. Đóng sự cố và ngăn tái diễn

- Lưu incident record ngoài repo theo W9; artifact trong repo chỉ được chứa ID, timeline đã khử định danh, root cause và control change.
- Cập nhật `.gitignore`, pattern hoặc allowlist policy bằng regression fixture tổng hợp hiển nhiên giả.
- Xác minh lại hook ở clone/worktree và required check `repo-guard` trên branch protection.
- Không ghi “đã xoá hoàn toàn” nếu fork/cache/clone hoặc binary chưa được xác minh.

## 8. Tài liệu kỹ thuật tham chiếu

- [GitHub Docs — Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [git-filter-repo manual — Sensitive Data Removal](https://github.com/newren/git-filter-repo/blob/main/Documentation/git-filter-repo.txt)
