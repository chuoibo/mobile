# Protocol v1 — Preregistration

`protocol_version: v1` · **DRAFT** · DRI Claude · Reviewer Codex

> Đăng ký **trước khi** thu dữ liệu: mẫu số, ngưỡng, khung thời gian, cách gán cohort, cỡ mẫu, lịch xem interim.
> Sau khi đóng băng, đổi bất kỳ mục nào ở đây → ADR → `protocol_version` mới → **dữ liệu cũ không gộp.**

## 1. Kết quả CHÍNH

**Tỉ lệ nhóm evaluable có `valid_cost_opportunity = confirmed` mà người tổ chức tự khởi tạo lần dùng tiếp theo.**

| Kết quả | Hành động — quyết định TRƯỚC, không diễn giải lại sau |
|---|---|
| `< 4/10` | **Dừng wedge** hoặc đổi wedge |
| `4–5/10` | **Chưa được xây.** Chẩn đoán lại |
| `≥ 6/10` | Được xây **prototype tự phục vụ rẻ nhất** |
| `≥ 7/10` **và** ≤20% phiên cần can thiệp "chỉ người mới làm được" | Tín hiệu mạnh |

Cửa sổ đo: cohort đi chơi — cơ hội chi chung kế tiếp, hoặc 60 ngày. Mốc 30 ngày chỉ là chỉ báo sớm. Cohort ở trọ — chu kỳ kế tiếp.

## 2. Kết quả PHỤ — đều phải đạt, không bù trừ cho nhau

| Chỉ số | Ngưỡng |
|---|---|
| Median `organizer_active_time` | Giảm **≥30%** so với baseline **của chính nhóm đó** |
| Đường nhập | Ít nhất một đường nhanh hơn form cấu trúc về **thời gian tới phân bổ ĐÚNG**, không tăng lỗi vật chất |
| Hiểu đúng năng lực sau onboarding | **≥80%**. Không đạt → sửa lời hứa ra mắt, không sửa ngưỡng |
| Tỉ lệ nghĩa vụ `receiver_confirmed` trong 7 ngày | **≥ baseline của chính nhóm đó.** Sàn tuyệt đối 50% là vô nghĩa nếu Zalo đang cho họ 70% |

⚠️ **Thời gian tới phân bổ ĐÚNG**, không phải thời gian tới lúc có kết quả. Một đường nhập cho ra kết quả trong 5 giây rồi cần 3 phút sửa thì chậm hơn form.

## 3. Guardrail — có quyền PHỦ QUYẾT, không đánh đổi được

| Guardrail | Ngưỡng |
|---|---|
| `serious_error` | **0.** Đạt mọi chỉ số khác mà có một lần chuyển sai người vẫn là **THẤT BẠI** |
| Trải nghiệm người gửi | Không xấu đi rõ rệt so với baseline |
| Tổn hại quan hệ | 0 ca quy được về nghiên cứu |

Guardrail thất bại → **không có kết quả PASS**, bất kể chỉ số chính bao nhiêu.

## 4. Kế hoạch phân tích — viết trước, chạy được lại

- Mọi bảng kết quả sinh ra từ **script tái lập được** trên input đã khoá. Không có số nào chép tay.
- Codex **tái lập độc lập toàn bộ số liệu từ input đã khoá** — không chỉ đọc narrative của Claude.
- Phân tầng theo `protocol_version`. **Dữ liệu trước và sau một thay đổi lớn không được gộp.**
- Phân tầng theo cohort. Báo **mô tả**, không xếp hạng.
- Báo `N` và `N_missing` ở mọi chỉ số.
- Báo `attrited` và `indeterminate` riêng.
- Nhãn operator: báo kèm Cohen's kappa. `kappa < 0.6` → chỉ mô tả, không mở cổng.

## 5. Lịch xem interim — cố định trước

Chỉ xem tại **ranh giới block**. Không xem hằng tuần.

Mỗi lần xem ghi lại: xem lúc nào · số liệu lúc đó · có đổi gì không · nếu đổi thì ADR nào.

Xem ngoài lịch = `protocol_deviation`, phải log.

## 6. Ma trận chẩn đoán — chốt trước để không kết luận vội

| Thu tiền | Quay lại | Chẩn đoán |
|---|---|---|
| Cao | Thấp | Nhu cầu theo sự kiện, hoặc sai định vị — **KHÔNG** phải wedge sai |
| Thấp | Cao | Sổ có giá trị nhưng **UX thanh toán hỏng** |
| Thấp | Thấp | Lúc này mới thực sự nghi ngờ wedge |

Cả hai thấp → **dừng mở rộng phạm vi, chẩn đoán, chạy một vòng sửa có kiểm soát rồi đo lại.**
Chỉ kết luận wedge sai nếu **sau vòng sửa**, sản phẩm vẫn không cải thiện thời gian hoặc tỉ lệ thu tiền so với cách làm hiện tại, ở những nhóm thực sự có cơ hội dùng lại.

## 7. Điều gì sẽ bác bỏ luận đề

Ghi ra trước để không hợp lý hoá sau:

- **Luận đề "thu tiền mới là pain".** Bị bác nếu `organizer_active_time` giảm ≥30% nhưng tỉ lệ tự khởi tạo vẫn `<4/10` — nghĩa là tiết kiệm thời gian không đủ để họ quay lại.
- **Luận đề "tiếng Việt tự nhiên nhanh hơn form".** Bị bác nếu form cấu trúc thắng hoặc hoà về thời gian tới phân bổ đúng. Khi đó wedge là **form tốt**, không phải AI.
- **Luận đề "đây là phần mềm".** Bị bác nếu phần lớn giá trị đến từ `human_judgment_required` + `out_of_contract_rescue`. Kết luận đúng khi đó là **dịch vụ vận hành, không phải phần mềm**.
- **Luận đề biên lợi nhuận.** Bị bác nếu concierge được yêu thích nhưng tốn ~15 phút lao động mỗi đợt. Điều đó **chứng minh pain và đồng thời bác bỏ mô hình phần mềm biên lợi nhuận cao**.

## 8. Sửa đổi

Bất kỳ thay đổi nào ở tài liệu này sau khi đóng băng:
1. ADR mô tả thay đổi và **lý do, viết trước khi xem dữ liệu mới**
2. `protocol_version` mới
3. Dữ liệu cũ **không gộp**

**Leader không được** đổi ngưỡng sau khi đã thấy kết quả. Đây là ràng buộc lên leader và nó cố ý.
