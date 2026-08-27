# Review C-03 fix — repo guard (Codex)

- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **1** (C-04)
- **Bằng chứng đã xem:** 3 ca C-03 + 3 ca né tránh mới + 3 ca false-positive, mỗi ca một file, stage riêng, repo Git tạm độc lập

## C-03 đã đóng

| f2 wrap 40 · f2b wrap 76 · f2d wrap 200, xen **1 dòng trống** | ✅ `dense-base64-block` |
|---|---|
| h3 — xen **dòng văn xuôi tiếng Việt** giữa các dòng base64 | ✅ `dense-base64-block` |

False-positive giữ nguyên xanh: hash SHA-256 · nguyên văn `ADR-0004` · file test Python 200 dòng.

## Blocker

### C-04 — đây là cuộc chạy đua, không phải bản vá

| Ca | Kết quả |
|---|---|
| h1 — xen **HAI** dòng trống | ❌ **LỌT** |
| h2 — xen **BA** dòng trống | ❌ **LỌT** |

Bản vá chịu được **đúng một** dòng không khớp liên tiếp. Vòng sau tôi thêm một dòng trống nữa, bạn nâng ngưỡng lên hai, tôi thêm ba. **Vòng lặp này không có điểm dừng** — mỗi vòng chỉ dịch ngưỡng thêm một bậc.

> Đây là blocker về **cấu trúc của cách tiếp cận**, không phải về hằng số. Nâng ngưỡng khoan dung lên `N` sẽ bị bác ngay ở vòng review sau bằng `N+1` dòng trống.

**Tiêu chí gỡ chặn:** bỏ hẳn khái niệm "dòng liên tiếp". Một hướng khả dĩ:

> Cộng dồn **tổng số byte nằm trong các token thuộc bảng chữ base64 có độ dài ≥ ngưỡng token nhỏ** trên **toàn bộ các dòng thêm mới của một file**, bất kể chúng nằm cách nhau bao xa. Vượt ngưỡng tổng thì chặn.

Ảnh bill wrap 76 sinh ~380 token, mỗi token 76 byte, tổng ~29 KB → đỏ **bất kể chèn bao nhiêu dòng trống**. Văn xuôi và code sinh token ngắn nên tổng gần 0.

Tôi đưa hướng, **không áp đặt thiết kế** — bạn là DRI của W9a. Nhưng bản vá tiếp theo phải làm cho **số lượng dòng chèn trở nên vô nghĩa**, chứ không phải chịu được nhiều hơn một chút.

Ràng buộc giữ nguyên: 3 ca false-positive ở trên phải tiếp tục đi qua, cộng golden vector JSON và file Markdown dài của chính team.
