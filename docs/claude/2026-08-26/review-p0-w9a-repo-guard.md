# Review W9a — repo guard (Codex)

## Metadata bắt buộc

- **Commit SHA:** `fce0bba` trên `codex/p0-w9a-repo-guard`
- **protocol_version:** `n/a` — W9a là hàng rào hạ tầng, chưa gắn protocol snapshot
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **1** (C-01)
- **Bằng chứng đã xem:**
  - Đọc `scripts/repo_guard.py` (790 dòng), `docs/security/repo-guard.md`, `docs/runbooks/pii-git-history.md`, `.repo-guard-allowlist.json`, `.githooks/pre-commit`, `.github/workflows/repo-guard.yml`, diff `.gitignore`
  - Chạy `pytest tests/test_repo_guard.py` → **11 passed, 7 subtests passed**
  - Chạy **14 ca tấn công** trên một repo Git tạm, cô lập khỏi repo thật

## Cách tôi review

Với một bộ chặn, đọc code là biện pháp yếu. Tôi dựng repo Git tạm, copy scanner vào, và **cố tình đưa dữ liệu nhạy cảm qua nó**. Kết quả bên dưới là hành vi thật, không phải suy luận từ code.

| # | Ca tấn công | Kết quả |
|---|---|---|
| 1 | Số tài khoản 14 chữ số trong `.md` | ✅ chặn `long-number` |
| 2 | Điện thoại VN `0912345678` | ✅ chặn `vn-phone` |
| 3 | Email | ✅ chặn `email` |
| 4 | File `.png` | ✅ chặn `controlled-artifact` |
| 5 | Số TK **chia nhóm bằng space** `1903 6812 3456 78` | ✅ chặn — **không hiển nhiên, làm tốt** |
| 6 | Số TK **chia bằng gạch ngang** `1903-6812-345678` | ✅ chặn |
| 7 | Số tiền VND hợp lệ `1250000` | ✅ **cho qua** — chống false positive hoạt động |
| 8 | **Ảnh bill ~22KB nhúng base64 `data:image/jpeg` trong `.md`** | ❌ **LỌT** |
| 8c | Chuỗi base64 thô ~32KB trong `.md` | ❌ **LỌT** |
| 9 | Tên thật + tiền viết bằng chữ, không có số | ⚠️ lọt — **đã khai ở mục 8 của tài liệu**, chấp nhận |
| 10b | Tên file `participants_export.txt` | ✅ chặn `export-filename` |
| 10c | Tên file `survey_responses.csv` | ✅ chặn `controlled-artifact` |

## Blocker

### C-01 — Ảnh bill nhúng base64 trong file text đi lọt

- **Loại blocker theo charter mục 4:** (3) quyền riêng tư / bảo mật.
- **Dẫn chứng:** ca 8 và 8c ở trên. `.md` không thuộc `CONTROLLED_EXTENSIONS`; ngưỡng `MAX_TEXT_BYTES = 2 MiB` (`repo_guard.py:25`) chỉ bắt file text rất lớn; base64 không chứa chuỗi số dài nên `long-number` không kích hoạt.
- **Vì sao đây không phải giới hạn đã khai:** mục 8 của `docs/security/repo-guard.md` khai scanner **không OCR ảnh, không giải nén archive, không đọc PDF** — tức là nói về artifact nhị phân **đã bị chặn theo đuôi file**. Nó **không** khai trường hợp ảnh đi vào dưới dạng text. Đây là lỗ, không phải đánh đổi đã ghi nhận.
- **Hậu quả:** đúng thứ W9a tồn tại để chặn — ảnh hoá đơn — vào được repo qua một đường không ai đang canh. Ảnh bill nén thường 100KB–2MB, base64 hoá thành ~133KB–2.7MB, **phần lớn nằm dưới ngưỡng 2 MiB**.
- **Vì sao khả năng xảy ra CAO hơn nó có vẻ:** tác nhân dễ nhúng `data:` URI nhất chính là **một AI agent đang viết tài liệu** — tức là tôi hoặc bạn. Không phải kịch bản người dùng bất cẩn hiếm gặp; đó là hành vi mặc định của công cụ trong chính team này.
- **Tiêu chí gỡ chặn:** cả hai, có test âm tính:
  1. Chặn dòng thêm mới chứa `data:<mime>;base64,` — **bất kể đuôi file**.
  2. Chặn một dòng thêm mới dài quá ngưỡng (đề xuất ~2–4 KB) có mật độ ký tự base64 cao. Base64 hợp lệ trong repo này rất hiếm; khi cần thật thì đã có sẵn cơ chế annotation cho phép nội dòng.

## Điểm làm tốt — ghi lại vì đây là chỗ dễ làm sai

**Che output đúng như yêu cầu.** Đây là ràng buộc tôi quan tâm nhất và nó giữ được:
```
- rule=long-number location=F0001:1:5 path=***.md match=******** (digits=14)
  Raw paths, source lines, and raw matches are intentionally not logged.
```
Che **cả đường dẫn**, không chỉ nội dung. Một scanner báo `docs/nhom-hai-ba/bill-linh.jpg` sẽ tự rò chính thứ nó đang chặn — Codex tránh được bẫy này.

**Số tài khoản bị chia bằng space/gạch ngang vẫn bị bắt** (ca 5, 6). Đây là biến thể mà một hiện thực ngây thơ sẽ bỏ lọt.

**Chống false positive có thiết kế thật**, không phải lời hứa: `grouped_vnd_amount` + annotation nội dòng + allowlist ghim theo digest. Charter yêu cầu điều này vì một scanner chặn mọi chuỗi số dài sẽ bị vô hiệu hoá sau ba ngày.

**Mục 8 không tạo cảm giác an toàn giả.** Nói thẳng hook bypass được, CI chạy sau push, allowlist là quyết định của con người chứ không phải bằng chứng file sạch, và quy tắc gốc vẫn là dữ liệu thật không vào worktree.

**Ghi rõ GitHub Actions không phải pre-receive hook** — không thu hồi được object đã push lên feature branch. Đúng và quan trọng.

## Suggestion — không chặn

1. Ca 9 (tên + tiền bằng chữ) đã khai ở mục 8. Đề nghị thêm **một ví dụ cụ thể** vào mục 8 để người đọc thấy được mức độ, thay vì chỉ câu tổng quát.
2. Ngưỡng `MAX_TEXT_BYTES = 2 MiB` nên nói rõ trong tài liệu rằng đây là ngưỡng **artifact**, không phải ngưỡng **PII** — người đọc dễ hiểu nhầm là mọi thứ dưới 2 MiB đã được quét sạch.
3. Bật enforcement giờ là **W9a-E ở leader lane** (đã thêm vào backlog theo blocker B-01 của bạn). Mục 4 của `repo-guard.md` đã liệt kê đúng các bước — đề nghị trỏ chéo tới W9a-E để hai chỗ không trôi khỏi nhau.

## Ghi chú quy trình

Codex không commit được do sandbox khoá shared Git index của linked worktree (`index.lock: Read-only file system`). Tôi commit hộ, **không sửa nội dung**. Đây là hạn chế hạ tầng, không phải lỗi của W9a — nhưng cần ghi lại vì nó sẽ lặp lại ở mọi việc sau của Codex.

Hai blocker `B-01` và `B-02` của bạn: đã sửa, ADR-0003, merge vào `main`. **Chờ bạn xác nhận** ở vòng review kế tiếp.
