# Protocol v1 — Bản khai thiên lệch

`protocol_version: v1` · **DRAFT** · DRI Claude · Reviewer Codex

> Khai trước khi thu dữ liệu. Mục đích là để **không** giải thích chúng đi sau khi thấy kết quả.
> Mọi báo cáo kết quả phải đính kèm file này.

## 1. Concierge thiên lệch theo TỪNG CHIỀU, không phải một cận trên duy nhất

| Chiều | Concierge là cận | Nghĩa là |
|---|---|---|
| Hiểu câu mơ hồ | **TRÊN** | Sản phẩm thật sẽ **tệ hơn** |
| Xử lý ngoại lệ | **TRÊN** | Sản phẩm thật sẽ **tệ hơn** |
| Độ chính xác phân bổ | **TRÊN** | Sản phẩm thật sẽ **tệ hơn** |
| Niềm tin và quyền riêng tư | **DƯỚI** | Có người lạ đọc chi tiêu → sản phẩm thật có thể **tốt hơn** |
| Tốc độ | **DƯỚI** | Phải chờ người → sản phẩm thật có thể **tốt hơn** |
| Nhất quán, khả dụng 24/7 | **DƯỚI** | Sản phẩm thật có thể **tốt hơn** |
| Mức sẵn lòng dùng | **DƯỚI** | Người dùng biết phía sau là con người |

→ **Không được** gộp thành một câu "concierge là cận trên". Sai theo cả hai hướng tuỳ chỉ số.

## 2. Concierge có thể đang bán lao động miễn phí

"Tự xin dùng lại" có thể nghĩa là **họ thích có người làm hộ**, không nghĩa là họ sẽ dùng app tự phục vụ.

Giảm thiểu: một chu kỳ sau phải ép giao diện gần sản phẩm thật hơn và giới hạn operator đúng các năng lực có thể tự động hoá.
**Nếu không chạy được chu kỳ đó, kết luận tích cực bị giới hạn tương ứng và phải ghi rõ.**

## 3. Tín hiệu "tự xin làm lần nữa": độ chính xác cao, độ bao phủ THẤP

Chỉ có nghĩa khi **cả bốn**: nhóm biết dịch vụ vẫn còn · thực sự phát sinh cơ hội hợp lệ · người tổ chức **chủ động** (không phải trả lời "có" khi được hỏi) · operator không chăm sóc vượt mức sản phẩm tương lai.

→ Vắng tín hiệu **không** chứng minh vắng nhu cầu.

## 4. Thiên lệch chọn mẫu

- Ta chọn về những nhóm **vốn dễ chịu với việc chia sẻ dữ liệu tài chính**. Nhóm ngại nhất — có thể là nhóm có pain lớn nhất — không xuất hiện trong mẫu.
- Nếu tuyển qua mạng lưới cá nhân của leader: thêm **thiên lệch nể nang**, mạnh theo hướng có lợi cho sản phẩm.
- Ưu tiên cohort nào để tuyển trước cũng là một thiên lệch. Ghi lại thứ tự và lý do.

## 5. Operator giỏi dần theo thời gian

Wave sau sẽ trơn tru hơn wave trước vì **operator giỏi lên**, không phải vì nhóm khác nhau.

Giảm thiểu: SOP + `protocol_version`. Không có hai thứ đó, cải thiện theo wave sẽ bị nhầm thành khác biệt cohort.

## 6. Hawthorne

Người tổ chức biết đang được quan sát → chủ động hơn bình thường ở **cả** baseline lẫn concierge. Hướng lệch không rõ, nhưng có ở cả hai phía nên so sánh trong-nhóm chịu được tốt hơn so sánh giữa-nhóm.

## 7. Founder tự làm operator *(chỉ áp dụng nếu ADR-0002 chọn P0-Gọn)*

Tổ hợp `founder làm operator + participant là người quen + không audit độc lập + founder tự phỏng vấn` **vô hiệu hoá mọi kết luận tích cực**.

Cơ chế: người tạo ra sản phẩm sẽ **vô thức cứu mọi phiên**, và `out_of_contract_rescue` sẽ không bao giờ được ghi trung thực.

Giảm thiểu đã thiết kế: Q1 và Q2 đứng đầu cây quyết định nhãn (`01-` mục 3) · gán nhãn ngay lúc thao tác · sửa nhãn tạo audit event · khảo sát người gửi ẩn danh · người độc lập gán lại ≥20% mẫu.

> **Không có bất kỳ audit độc lập nào → kết quả tích cực chỉ là hypothesis-generating.** Nó biện minh được cho một thí nghiệm tiếp theo, không đủ để tuyên bố đã vượt cổng hành vi.

## 8. Tự khai thời gian ngoài công cụ

`organizer_active_time` có phần tự khai. Social desirability bias đẩy theo hướng **báo ít giờ hơn ở chu kỳ concierge** — tức có lợi cho sản phẩm, đúng chiều ngưỡng giảm 30%.

Giảm thiểu: điền **cùng ngày** (mục không cùng ngày bị loại khỏi chỉ số chính) · cùng công cụ khai ở baseline và concierge · báo riêng phần trong-công-cụ (tin cậy cao) và phần tự khai.

## 9. "Chấp nhận không sửa" ≠ "đúng"

Chỉ số chất lượng AI đo **hành vi sửa**, không đo độ chính xác. Có thể chỉ nghĩa là người dùng **bấm nhanh**.

Giảm thiểu: mẫu kiểm toán có **chuẩn đúng độc lập** · kiểm tra ngẫu nhiên sau xác nhận · tách `accepted_without_edit` khỏi `verified_correct` · theo dõi lỗi phát hiện **sau** khi publish — đó mới là chấp nhận sai nguy hiểm.

## 10. Cỡ mẫu nhỏ

10–15 nhóm/cohort cho phép **so sánh mô tả** failure mode. **Không** cho phép tuyên bố cohort nào thắng. Spec ghi rõ ngay cả 30/cohort cũng chưa đủ cho tuyên bố đó.

Với tỉ lệ quanh 40–60%, khoảng bất định ở n=10 rộng tới mức `6/10` và `4/10` **không phân biệt được về mặt thống kê**.

→ Cổng 13.3 là **cổng quyết định vận hành**, không phải kết luận thống kê. Đối xử với nó đúng như vậy trong mọi báo cáo.
