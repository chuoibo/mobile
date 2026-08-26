# ADR-0002 — Chọn biến thể Giai đoạn 0

- **Trạng thái:** ĐỀ XUẤT — **chờ leader quyết**
- **Ngày:** 2026-08-26
- **Người quyết:** LEADER. Engineer không quyết được việc này.

## Đính chính quan trọng về cỡ mẫu

Bản trình bày trước cho leader hiểu Giai đoạn 0 đắt **gấp đôi** thực tế. Ba mốc là ba cổng khác nhau:

| Mốc | Ý nghĩa đúng |
|---|---|
| 6 nhóm/cohort | Wave A để sửa giao thức. **Chưa đủ mở gate** |
| Block +3/cohort | Tuyển tuần tự, kiểm tra failure-mode saturation |
| **≥10 nhóm trong một cohort có cơ hội lặp THẬT** | Đủ mở cổng prototype 13.3 cho cohort đó |
| Hai block liên tiếp ổn định | Điều kiện dừng tuyển — độc lập với việc vừa chạm `/10` |
| ≥30 nhóm đã kích hoạt/cohort | **Sàn pilot với sản phẩm thật, SAU prototype** — không thuộc Giai đoạn 0 |

Theo lịch block `6 + 3 + 3`, điểm sớm nhất vừa có hai block sau Wave A vừa có thể đạt ≥10 eligible là khoảng **12 nhóm/cohort** — và chỉ khi gần như tất cả thật sự có cơ hội tiếp theo. Thiếu opportunity, attrition, hoặc còn failure mode mới → phải lên 15, 18…

- ✅ Leader **không** cần ngân sách 60 nhóm cho Giai đoạn 0.
- ✅ Mục tiêu danh nghĩa: ~10–15 nhóm **đánh giá được** mỗi cohort.
- ❌ **Sai** nếu hiểu "tuyển 20–30 là chắc chắn đủ". Công thức thật là tuyển theo block **cho đến khi** vừa có ≥10 eligible **vừa** đạt stopping rule.

⚠️ 10–15/cohort cho phép **so sánh mô tả** failure mode giữa hai cohort. Nó **không** cho phép tuyên bố cohort nào thắng. Spec ghi rõ ngay cả 30/cohort cũng chưa đủ cho tuyên bố đó.

## Hai biến thể

### P0-Đầy đủ
2 cohort (ở trọ + đi chơi) · ~12–15 nhóm đánh giá được mỗi cohort · operator được thuê · counsel review trước khi chạm dữ liệu tài chính thật · có ngân sách khuyến khích. **4–6 tháng.**

### P0-Gọn — *controlled deviation*, không phải "đã làm đúng spec"
1 cohort duy nhất là beachhead (sinh viên đi chơi) · leader tự làm operator · kế hoạch ≥12 nhóm cộng buffer · không lưu ảnh bill quá phiên làm việc · consent bằng văn bản. **6–10 tuần**, và chỉ khả thi khi tuyển sát những buổi đi chơi **đã được lên lịch** — không được ép phát sinh lần đi chơi tiếp theo.

Điều kiện bắt buộc nếu chọn:
- Chỉ kết luận về cohort đi chơi. **Không** suy diễn sang cohort ở trọ.
- 6 nhóm chỉ đủ sửa protocol hoặc tạo tín hiệu **DỪNG**. Không tạo được GO — chưa có mẫu số `/10`.
- GO yếu cần ≥10 nhóm **có cơ hội lặp hợp lệ**, không phải 10 nhóm đã tuyển.
- Nhóm đủ điều kiện xác định theo **thứ tự đã đăng ký trước**, không chọn 10 nhóm đẹp nhất sau khi xem kết quả.
- Phải có ADR ghi rõ đây là controlled deviation. **Không** được diễn giải rằng spec vốn chỉ đòi một cohort.

## Rủi ro chí mạng của P0-Gọn: leader tự làm operator

Tổ hợp này **vô hiệu hoá mọi kết luận tích cực**:

```
founder làm operator  +  participant là người quen  +  không audit độc lập  +  founder tự phỏng vấn
```

Người tạo ra sản phẩm sẽ vô thức cứu mọi phiên, và nhãn `out_of_contract_rescue` sẽ không bao giờ được ghi trung thực.

Giảm thiểu **tối thiểu bắt buộc**:
- Script, SLA, số lượt hỏi, action allowlist **đóng băng trước** field.
- Operator ghi action + nhãn + lý do rescue **ngay lúc thao tác**. Sửa nhãn sau đó tạo audit event, **không ghi đè**.
- Mọi rescue tính vào chi phí và intervention rate, **kể cả rescue thành công**.
- Công cụ **không cho** operator tự gửi nhắc trực tiếp hoặc làm thay organizer.
- Thay đổi tool/protocol chỉ có hiệu lực ở version tiếp theo.
- Self-initiation đo bằng **hành vi**, không bằng câu trả lời phỏng vấn.
- Feedback người gửi qua khảo sát riêng/ẩn danh. Founder **không** đứng trước mặt hỏi họ có thích không.
- Tuyển người cách founder **ít nhất một bậc quan hệ**, không phải bạn thân.
- **Một người độc lập** audit mẫu log có cấu trúc và thực hiện hoặc kiểm tra phần phỏng vấn guardrail. Không cần thuê operator toàn thời gian — chỉ cần audit.

> Không có bất kỳ audit độc lập nào → kết quả tích cực chỉ là **hypothesis-generating**. Nó biện minh được cho một thí nghiệm tiếp theo, **không** đủ sạch để tuyên bố đã vượt behavioral gate.

## Ràng buộc không thương lượng ở CẢ HAI biến thể

1. **Consent tự soạn không thay được counsel review có phạm vi.** Spec mục 16.1 cấm tự kết luận pháp lý. P0-Gọn giảm được *phạm vi* review nhờ không lưu ảnh và không giữ tiền — nhưng founder vẫn đọc dữ liệu chi tiêu thật. **Hoàn toàn không có counsel → chỉ được chạy usability trên dữ liệu tổng hợp, và không được gọi đó là behavioral gate.**
2. **Không ai giữ hoặc chuyển tiền hộ.** Participant tự chuyển trực tiếp cho nhau.
3. **Nghĩa vụ phải là thật.** Không có nghĩa vụ thật → rơi vào bẫy "tạo khoản nợ giả" mà mục 13.6 cấm.
4. Mọi người bị quan sát phải biết và đồng ý — **kể cả việc có người thật đọc dữ liệu** trong Wizard-of-Oz.

## Cần leader trả lời

1. Chọn **P0-Đầy đủ** hay **P0-Gọn**?
2. Có ngân sách cho **counsel review có phạm vi** không? Nếu không → chỉ chạy usability trên dữ liệu tổng hợp.
3. Có tìm được **một người audit độc lập** không? Không cần toàn thời gian.
4. Ai là operator? Nếu là leader → chấp nhận toàn bộ danh sách giảm thiểu ở trên.
5. Kênh tuyển nhóm là gì, và có buổi đi chơi nào **đã lên lịch** trong 4–6 tuần tới không?
