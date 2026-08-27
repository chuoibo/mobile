# Review C-01 fix — repo guard (Codex)

## Metadata bắt buộc

- **Commit SHA:** `7330a3f` trên `codex/p0-w9a-repo-guard`
- **protocol_version:** `n/a`
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **1** (C-02)
- **Bằng chứng đã xem:** đọc `scripts/repo_guard.py:136–157, 275–279`; chạy `pytest tests/test_repo_guard.py` → **17 passed, 16 subtests**; chạy lại **toàn bộ 13 ca tấn công cũ** + **3 ca false-positive mới** + **7 ca né tránh mới** trên repo Git tạm độc lập

## C-01 đã đóng — xác nhận độc lập, không dựa vào test của người sửa

| Ca | Trước | Sau |
|---|---|---|
| 8 — ảnh base64 nhỏ trong `.md` | LỌT | ✅ `data-uri-base64` |
| 8b — ảnh bill ~22KB base64 trong `.md` | LỌT | ✅ `data-uri-base64` |
| 8c — base64 thô ~32KB một dòng | LỌT | ✅ `dense-base64-line` |

Mọi ca chặn cũ giữ nguyên. Ca 7 (`1250000 VND` hợp lệ) vẫn đi qua.

**Ba ca false-positive mới tôi thêm, cả ba đi qua đúng như phải thế:** hash SHA-256 64 ký tự hex · golden vector JSON ở `phase0/allocator/golden/` · chuỗi 300 ký tự lặp. Đây là điều kiện sống còn — một guard chặn nhầm sẽ bị vô hiệu hoá trong ba ngày.

## Blocker

### C-02 — ngưỡng THEO DÒNG bị vượt qua bằng cách ngắt dòng chuẩn

- **Loại blocker theo charter mục 4:** (3) quyền riêng tư / bảo mật.
- **Dẫn chứng:** 7 ca né tránh, mỗi ca một file riêng, stage riêng:

| Ca | Nội dung | Kết quả |
|---|---|---|
| e1 | ảnh bill 22KB, base64 wrap **76 ký tự/dòng**, không `data:` | ❌ **LỌT** |
| e2 | cùng ảnh, wrap 1000 ký tự/dòng | ❌ **LỌT** |
| e5 | base64 3000 ký tự trong **giá trị chuỗi JSON** | ❌ **LỌT** |
| e6 | base64 3000 ký tự, một dòng, không `data:` | ❌ **LỌT** |
| e3 | `data:` URI **ngắt dòng** giữa chừng | ✅ chặn |
| e4 | `DATA:...;BASE64,` **viết HOA** | ✅ chặn |
| e7 | base64 5000 ký tự một dòng | ✅ `dense-base64-line` |

- **Nguyên nhân:** `dense-base64-line` có ngưỡng **theo từng dòng** là 4 KiB (`repo_guard.py:25`). Mọi blob base64 ngắt dòng dưới 4 KiB đều thoát.
- **Vì sao nghiêm trọng hơn nó có vẻ:** wrap 76 ký tự **không phải kỹ thuật né tránh**. Đó là **mặc định của `base64` trên Linux (GNU coreutils)** và là chuẩn ngắt dòng của MIME/PEM. Nghĩa là **cách tự nhiên nhất để một ảnh bill lọt vào file text lại chính là cách thoát được guard.** Kẻ "tấn công" ở đây không phải người xấu — là một AI agent chạy `base64 bill.jpg >> notes.md`.
- **Tiêu chí gỡ chặn, cần cả hai, kèm test âm tính:**
  1. **Gộp theo khối, không theo dòng** — dãy dòng liên tiếp mật độ base64 cao mà **tổng** vượt ngưỡng thì chặn. Bịt e1, e2.
  2. **Rule ở mức token** — một chuỗi liên tục thuộc bảng chữ base64 dài hơn ~1.5–2 KB thì chặn, bất kể độ dài dòng. Bịt e5, e6.

## Ghi chú về phương pháp

Vòng đầu tôi tự tạo **harness bug**: tạo cả 5 file cùng lúc rồi `git add -A`, nên ca e1/e2 hiện "CHẶN" bởi rule của e3/e4 nằm chung staging area. Chạy lại từng file một mới ra kết quả thật.

Ghi lại vì đúng đây là loại nhầm mà taxonomy 5 loại của W6 tồn tại để bắt: **`harness_bug`, không phải `impl_bug`**. Nếu tôi tin kết quả vòng đầu thì đã kết luận sai rằng C-01 đã đóng hoàn toàn.
