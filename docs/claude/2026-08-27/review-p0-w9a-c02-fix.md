# Review C-02 fix — repo guard (Codex)

- **protocol_version:** `n/a`
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **1** (C-03)
- **Bằng chứng đã xem:** chạy lại **4 ca C-02** + **7 ca né tránh mới** + **6 ca false-positive** trên repo Git tạm độc lập, **mỗi ca một file, stage riêng**; `pytest tests/test_repo_guard.py` → 23/23

## C-02 đã đóng

| Ca | Kết quả |
|---|---|
| e1 — wrap **76 ký tự** (mặc định lệnh `base64`) | ✅ `dense-base64-block` |
| e2 — wrap 1000 ký tự | ✅ `dense-base64-block` |
| e5 — base64 3000 ký tự trong giá trị JSON | ✅ `long-base64-token` |
| e6 — base64 3000 ký tự một dòng | ✅ `long-base64-token` |
| f1 — wrap **12 ký tự** | ✅ `dense-base64-block` |
| f3 — chỉ 9000 ký tự, wrap 76 | ✅ `dense-base64-block` |

**Sáu ca false-positive đều đi qua đúng như phải thế:** hash SHA-256 · **golden vector JSON thật** ở `phase0/allocator/golden/` · chuỗi 300 ký tự lặp · file Python 60 dòng · bảng Markdown 3000 ký tự · **nguyên văn `ADR-0004`**.

Hai ca cuối tôi thêm vì chúng là loại file team này viết hằng ngày. Guard chặn nhầm tài liệu của chính mình sẽ bị tắt trong ba ngày.

## Blocker

### C-03 — chèn DÒNG TRỐNG reset bộ đếm khối

| Ca | Kết quả |
|---|---|
| f2 — wrap 40 ký tự, xen **1 dòng trống** | ❌ **LỌT** |
| f2b — wrap 76 ký tự, xen **1 dòng trống** | ❌ **LỌT** |
| f2d — wrap 200 ký tự, xen **1 dòng trống** | ❌ **LỌT** |
| f2c — wrap 76 ký tự, xen dòng `-` | ✅ chặn |

Chẩn đoán từ chính chênh lệch f2b ↔ f2c: bộ gộp khối **reset trên dòng rỗng**, nhưng chịu được dòng ngắn không rỗng. Cùng một ảnh bill 22KB, chỉ khác một ký tự xuống dòng, cho hai kết quả ngược nhau.

Ít tự nhiên hơn wrap-76 của C-02, nhưng **không hề khó**: dán ảnh theo từng đoạn vào một file Markdown là ra ngay dạng này.

**Tiêu chí gỡ chặn:** bộ gộp phải **chịu được một số dòng rỗng/không khớp có giới hạn** mà không reset bộ đếm — hoặc tính mật độ base64 trên một **cửa sổ trượt theo dòng**, thay vì đòi liên tiếp tuyệt đối. Kèm test âm tính cho cả ba biến thể f2, f2b, f2d.

## Ghi nhận

`long-base64-token` ở mức token là quyết định đúng và nó bịt được đúng hai ca (e5, e6) mà cách gộp theo dòng không bao giờ với tới. Ngưỡng 2 KB nằm xa mọi token hợp lệ tôi thử được — sáu ca false-positive xác nhận điều đó.
