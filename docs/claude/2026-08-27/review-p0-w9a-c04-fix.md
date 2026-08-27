# Review C-04 fix — repo guard (Codex)

- **Verdict:** **`APPROVE`**
- **Blocker còn mở:** **0**
- **Bằng chứng:** 5 ca né tránh + 4 ca false-positive, mỗi ca một file, stage riêng, repo Git tạm độc lập

## Cuộc chạy đua đã kết thúc đúng cách

`aggregate-base64-fragments` **bỏ hẳn khái niệm dòng liên tiếp** — đúng thứ tôi yêu cầu ở C-04. Số dòng chèn giờ vô nghĩa:

| 2 dòng trống · 5 dòng trống · **50 dòng trống** · xen văn xuôi dài | ✅ chặn |
|---|---|

Ba vòng trước, mỗi vòng tôi chỉ cần thêm một dòng trống. Vòng này thêm **năm mươi** dòng vẫn đỏ. Đó là khác biệt giữa vá ngưỡng và vá cấu trúc.

## False-positive: sạch, kể cả trên tài liệu lớn nhất của team

hash SHA-256 · nguyên văn `ADR-0004` · **toàn bộ spec 957 dòng** · **20 hash SHA-256 liên tiếp** — tất cả đi qua.

Ca cuối tôi thêm vì nó là tình huống thật sắp xảy ra: một file ghi digest của nhiều artifact. Nếu guard chặn nhầm nó thì team sẽ tắt guard.

## Giới hạn còn lại — CHẤP NHẬN, ghi lại, không phải blocker

**base64 wrap 4 ký tự mỗi dòng vẫn lọt.** Token 4 ký tự nằm dưới ngưỡng token nhỏ nhất.

Tôi **không** mở blocker cho ca này:
- Không ai wrap base64 ở 4 ký tự một cách tự nhiên. Đây là **né tránh có chủ đích**, không phải tai nạn.
- Threat model của W9a, ghi ở mục 8 của `docs/security/repo-guard.md`, là **người bất cẩn hoặc một AI agent chạy `base64 bill.jpg >> notes.md`** — không phải kẻ tấn công quyết tâm.
- Chính tài liệu đã nói guard là **lớp giảm thiểu, không phải bộ phân loại PII**, và quy tắc gốc vẫn là dữ liệu thật không vào worktree.

Hạ ngưỡng token xuống 4 sẽ chặn nhầm mọi thứ. Đây là điểm dừng đúng: **vá cấu trúc xong, hố còn lại nằm ngoài threat model đã tuyên bố.**

Đề nghị thêm một dòng vào mục 8 nói rõ điều này, để vòng sau không ai mở lại nó như blocker.

## W9a — tổng kết bốn vòng

| Vòng | Tôi tìm ra | Cách vá |
|---|---|---|
| C-01 | ảnh base64 trong `.md` | `data-uri-base64` + `dense-base64-line` |
| C-02 | wrap 76 ký tự — **mặc định của lệnh `base64`** | `dense-base64-block` + `long-base64-token` |
| C-03 | chèn 1 dòng trống | khoan dung 1 dòng ← *vá ngưỡng* |
| C-04 | chèn 2, 3 dòng trống | `aggregate-base64-fragments` ← **vá cấu trúc** |

Ba vòng đầu là ngưỡng, vòng cuối là cấu trúc. Đáng ghi lại: **bản vá đúng chỉ xuất hiện khi review chuyển từ "ca này lọt" sang "cách tiếp cận này không có điểm dừng".**
