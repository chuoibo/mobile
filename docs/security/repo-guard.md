# W9a — Repo guard cho dữ liệu nghiên cứu

## 1. Quy tắc tuyệt đối và nơi lưu quy ước

Dữ liệu thật của người tham gia **không bao giờ được mở, nhập, export, giải nén, tạo file tạm, bind-mount hoặc symlink vào repository hay bất kỳ worktree nào**.

Root quy ước trên máy nghiên cứu được leader phê duyệt là:

```text
/srv/mobile-study-private/<protocol_version>/<study_id>/
```

Đây phải là storage được mount trên máy nghiên cứu dành riêng, không phải một thư mục do engineer tự tạo trên laptop. Leader phải xác minh trước FIELD-GATE:

- account cá nhân, không dùng chung mật khẩu;
- quyền tối thiểu theo vai; mặc định chỉ operator và data custodian của study được đọc;
- ACL hoặc owner/group được kiểm tra, root không world-readable; thư mục study mặc định `0700`, chỉ mở thêm quyền có chủ đích;
- mã hoá khi lưu và khi backup, backup có cùng hoặc chặt hơn quyền nguồn;
- có audit access, retention và deletion do W9 quy định;
- root không nằm trong clone, worktree, thư mục sync cá nhân, và không được symlink/bind-mount vào đó.

Biến môi trường trỏ tới root, nếu công cụ nghiên cứu cần, chỉ được cấu hình trong môi trường operator được kiểm soát. Không ghi biến đó vào `.env` trong repo.

Một thư mục bị `.gitignore` **không phải** nơi lưu an toàn. `.gitignore` chỉ giảm nguy cơ `git add` nhầm; `git add -f`, đổi tên, copy, archive, script export hoặc worktree khác vẫn vượt qua được. Nó cũng không tạo access control, mã hoá, audit, retention hay xoá an toàn. Dữ liệu đặt trong worktree đã vi phạm quy tắc ngay cả khi Git chưa track.

## 2. Các lớp guard và ranh giới của từng lớp

| Lớp | Chặn/giảm thiểu | Không đảm bảo |
|---|---|---|
| Quy ước storage ngoài repo | Tách dữ liệu thật khỏi máy và luồng Git của engineer | Cần leader thật sự provision và kiểm tra quyền |
| `.gitignore` | Các đường dẫn data/export quen thuộc và database local | Có thể bị `git add -f`; file ở worktree vẫn là vi phạm |
| `.githooks/pre-commit` | Quét phần thêm mới trong staged diff, path, tên export và artifact | Bị bỏ qua bằng `--no-verify`; hook phải được kích hoạt ở từng clone/worktree |
| CI `repo-guard` | Quét toàn tree và từng snapshot commit mới, kể cả nội dung đã thêm rồi xoá trong PR | Chỉ chặn merge khi leader bật required check; push lên feature branch đã đưa object lên remote |
| Allowlist theo digest | Buộc review lại khi artifact đổi một byte hoặc đổi path | Reviewer vẫn có thể duyệt nhầm một binary chứa PII |

Guard cố ý **fail closed** nếu không đọc được Git/config hoặc gặp binary lạ, file text quá 2 MiB, symlink hay gitlink mới mà chưa allowlist. Mốc 2 MiB là ngưỡng phân loại `controlled-artifact`, **không phải** cam kết rằng mọi nội dung nhỏ hơn ngưỡng đều sạch PII.

## 3. Bật hook local

Trong clone độc lập, chạy:

```bash
git config core.hooksPath .githooks
git config --get core.hooksPath
```

`core.hooksPath` là config dùng chung giữa các linked worktree. Không bật đơn phương nếu worktree khác chưa có `.githooks`; việc đó có thể làm commit của teammate lỗi. Trong giai đoạn chuyển tiếp, chạy hook cho đúng một commit bằng:

```bash
git -c core.hooksPath=.githooks commit
```

Có thể chạy guard trực tiếp:

```bash
python3 scripts/repo_guard.py staged
python3 scripts/repo_guard.py tree HEAD
python3 scripts/repo_guard.py range <base-sha> <head-sha>
python3 scripts/repo_guard.py history HEAD
```

Scanner đọc blob trong Git index ở mode `staged`, không đọc bản unstaged đang nằm trên disk. Điều này tránh cả bỏ sót lẫn báo nhầm khi một file có hai phiên bản.

## 4. Required CI — hành động bắt buộc của leader

Workflow `.github/workflows/repo-guard.yml` tạo status check có tên chính xác `repo-guard`. File workflow tồn tại **chưa làm check thành required**.

Trước FIELD-GATE, leader phải hoàn tất **W9a-E** trong `docs/team/backlog.md`: bật ruleset/branch protection cho `main` với bằng chứng tối thiểu:

1. bắt buộc đi qua pull request;
2. bắt buộc status check `repo-guard` thành công;
3. chặn direct push và giới hạn bypass;
4. chạy một PR dry-run tổng hợp để chứng minh check xuất hiện và merge bị khoá khi check đỏ;
5. lưu bằng chứng cấu hình không chứa PII trong gate packet.

GitHub Actions không phải pre-receive hook. Nó không thể thu hồi object nhạy cảm đã push lên feature branch. Vì vậy hook local và quy tắc storage ngoài repo vẫn là tuyến trước; required CI bảo vệ lịch sử được merge vào `main`.

## 5. Rule được quét

Scanner hiện có các rule:

- `forbidden-path`: các root data/export đã biết; **không allowlist được**;
- `controlled-artifact`: ảnh, PDF, archive, spreadsheet, database, CSV/TSV/JSONL, binary lạ, file text quá 2 MiB, symlink và gitlink;
- `export-filename`: tên giống export/dump/raw data hoặc dataset export;
- `vn-phone`: số di động và cố định Việt Nam ở dạng trong nước/quốc tế phổ biến;
- `email`;
- `long-number`: chuỗi từ 9 chữ số, có thể có dấu cách, chấm hoặc gạch nối.
- `data-uri-base64`: marker `data:<mime>;base64,` trên dòng được quét, không phụ thuộc đuôi file;
- `dense-base64-line`: dòng dài hơn 4 KiB có ít nhất 98% byte thuộc bảng chữ cái base64/base64url.

Ở mode `staged`, các content rule chỉ xét dòng được thêm hoặc thay trong index. Ở mode `tree`, `range` và `history`, scanner xét toàn bộ dòng của từng snapshot được quét. File text lớn hơn 2 MiB hoặc binary bị chặn ở cấp `controlled-artifact` trước khi content scanner đọc dòng.

Khi chặn, scanner chỉ in mã file như `F0001`, dòng/cột, path đã che và match đã che. Nó không in raw path, raw source line hay raw match ra stdout/stderr hoặc log CI. Muốn tìm file local, đối chiếu mã theo thứ tự path đã stage/track trong môi trường tin cậy; không paste danh sách path lên ticket hoặc chat.

## 6. False positive có chủ đích

Repo sẽ chứa số tiền VND và số liệu nghiên cứu tổng hợp. Không xử lý false positive bằng cách tắt hook hoặc miễn cả thư mục.

### Số tiền VND

Viết số tiền theo định dạng có phân nhóm và đơn vị, ví dụ `100.000.000 VND`. Scanner nhận dạng dạng này là tiền thay vì identifier. Số tiền viết thành một chuỗi chữ số trần vẫn bị chặn.

### Annotation cho text tổng hợp

Chỉ năm content rule `email`, `vn-phone`, `long-number`, `data-uri-base64`, `dense-base64-line` được miễn ở cùng dòng hoặc đúng dòng ngay sau annotation:

```text
# repo-guard: allow=long-number reason=synthetic-aggregate-id
Mã TỔNG HỢP GIẢ: 999999999999

# repo-guard: allow=email reason=synthetic-invalid-domain
Email TỔNG HỢP GIẢ: nguoi-gia@du-lieu.invalid

# repo-guard: allow=dense-base64-line reason=reviewed-synthetic-vector
<một dòng fixture base64 tổng hợp đã được review>
```

`reason` là token ASCII ít nhất 8 ký tự. Annotation phải cụ thể theo rule và nằm ngay cạnh match để reviewer thấy. Không dùng annotation cho dữ liệu thật. Nếu cùng một file cần nhiều miễn trừ, từng vị trí phải có annotation riêng.

SHA-256 đơn lẻ dài 64 ký tự và chữ ký base64 thông thường ngắn hơn ngưỡng dòng nên không kích hoạt `dense-base64-line`. Golden-vector JSON dài chỉ bị rule này chặn khi cả dòng vượt 4 KiB **và** đạt mật độ 98%; JSON có nhiều field, dấu phân cách, hash và chữ ký riêng rẽ không mặc nhiên bị chặn. Nếu một fixture hợp lệ thực sự là một blob mã hoá dài, ưu tiên format lại thành nhiều dòng khi định dạng cho phép; nếu không, dùng annotation hẹp sau review. `data:` URI vẫn phải được annotation riêng vì marker này bị chặn bất kể độ dài.

### Allowlist cho artifact/export hợp lệ

Chỉ allowlist asset công khai hoặc fixture tổng hợp đã được người khác review. Entry trong `.repo-guard-allowlist.json` phải pin đồng thời path, SHA-256, rule và lý do. Ví dụ minh hoạ:

```json
{
  "path": "docs/assets/synthetic-flow.png",
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "rules": ["controlled-artifact"],
  "reason": "Public synthetic documentation asset"
}
```

Digest trong ví dụ là placeholder; entry thật phải lấy từ đúng staged blob. Một CSV tổng hợp có tên giống export có thể cần cả `controlled-artifact`, `export-filename` và content rule liên quan. Đổi path hoặc một byte làm allowlist mất hiệu lực.

Binary là opaque đối với scanner. Reviewer phải kiểm tra nguồn tạo, xác nhận không dùng dữ liệu người tham gia, kiểm tra metadata/EXIF nếu có, rồi mới allowlist. **Không bao giờ allowlist binary thật chỉ vì scanner không đọc được nó.**

## 7. Khi guard đỏ

- Nếu là fixture/test: thay bằng dữ liệu tổng hợp hiển nhiên giả, hoặc dùng annotation/allowlist hẹp như trên.
- Nếu là số tiền: dùng định dạng VND có phân nhóm và đơn vị.
- Nếu nghi là dữ liệu thật: dừng commit/push, không paste match vào log, issue hoặc chat, và làm theo `docs/runbooks/pii-git-history.md`.
- Không dùng `--no-verify` để “thử cho qua”. CI sẽ quét lại lịch sử commit trung gian.

## 8. Giới hạn đã biết — không được diễn giải quá mức

Không scanner nào nhận ra mọi tên người Việt, biệt danh, địa chỉ, nội dung chat hay định danh theo ngữ cảnh. Ví dụ, một dòng chỉ có tên thật và số tiền viết hoàn toàn bằng chữ có thể đi qua. Regex này cũng có thể bỏ sót email/điện thoại bị làm rối hoặc format chưa biết.

Scanner chặn marker data URI base64 và dòng dài có mật độ base64 cao, nhưng không giải mã base64 để phân loại nội dung. Base64 thô được ngắt thành nhiều dòng ngắn hoặc làm rối có thể không bị hai rule này nhận ra. Scanner cũng không OCR ảnh, không giải nén archive, không đọc PDF, spreadsheet/database theo schema và không thấy PII nằm trong ảnh nén hoặc archive mã hoá. Allowlist binary là quyết định của con người, không phải bằng chứng file sạch.

Scanner không cung cấp consent, access control, encryption, retention, deletion hay incident response. Hook bị bypass được; CI chạy sau push; reviewer có thể dùng annotation/allowlist sai. Đây là lớp giảm thiểu. Quy tắc gốc vẫn là: **dữ liệu thật không đi vào repository hoặc worktree ngay từ đầu.**
