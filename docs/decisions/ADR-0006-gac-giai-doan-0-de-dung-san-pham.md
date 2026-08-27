# ADR-0006 — Gác Giai đoạn 0, dựng sản phẩm

- **Trạng thái:** ĐÃ CHẤP NHẬN
- **Ngày:** 2026-08-27
- **Người quyết:** **LEADER.** Engineer không quyết được việc này.
- **Thay thế:** `ADR-0002` (chọn biến thể Giai đoạn 0) — chuyển sang **HOÃN VÔ THỜI HẠN**, không phải bác bỏ

## Điều gì đã xảy ra

Leader hỏi một câu mà lẽ ra tôi phải tự hỏi trước: **"sao chưa bắt đầu code project dựng architecture đi mà làm gì vậy?"**

Câu đó đúng. Nhìn lại ba việc đang làm:

| Việc | Giá trị thật tại thời điểm đó |
|---|---|
| W9a repo guard | Chặn dữ liệu người tham gia vào Git — **nhưng chưa có người tham gia nào** |
| W0 giao thức thực địa | Giao thức cho một nghiên cứu **không có operator, không có nhóm, không có counsel** |
| W6 allocator | ✅ Thật. Sản phẩm nào cũng cần, không phụ thuộc nghiên cứu |

**Hai trong ba là hạ tầng cho một việc có thể không bao giờ diễn ra.**

## Giả định đã sai, và phát hiện muộn

Giai đoạn 0 ở mục 13 của spec được thiết kế cho một tổ chức **có ngân sách thuê operator, thuê luật sư, trả phí khuyến khích**. Leader đã trả lời thẳng: *"tất cả các nguồn lực đều là AI agent."*

Tôi ghi nhận điều đó, viết ba lựa chọn, rồi **vẫn tiếp tục xây dụng cụ cho phương án đắt nhất**. Đó là lỗi của tôi, không phải của leader. Đúng ra phải dừng và nói: *nghiên cứu này bạn không chạy được, nên đừng xây dụng cụ cho nó.*

## Lập luận

Câu hỏi hành vi — **nhóm có quay lại không** — thật sự không thể trả lời bằng cách xây. Nhưng nó cũng **không thể trả lời bằng một nghiên cứu không có người chạy**.

> Chờ đợi không phải là kiểm chứng. Nó chỉ là trì hoãn.

Và thứ duy nhất AI agent làm tốt mà **không cần ngân sách, không cần tuyển ai, không cần luật sư**: viết code.

## Quyết định

1. **Gác Giai đoạn 0.** Đi thẳng vào thứ tự xây ở mục 14.3 của spec.
2. **Lát cắt dọc đầu tiên:** lõi tiền → đợt thu → VietQR → trang cho khách không cần cài app. Đúng bước 2–4 của mục 14.3.
3. **W6 đổi thân phận:** từ *oracle nghiên cứu dùng một lần* → **code sản phẩm thật**.

## Cái giá — nói rõ để leader quyết có ý thức

**Xây khi chưa có bằng chứng hành vi là đúng rủi ro mục 13 của spec cảnh báo.** Hoàn toàn có thể ra một app chạy tốt mà không ai dùng lần thứ hai.

Điều này **không** được ghi lại thành "chúng tôi đã kiểm chứng rồi mới xây". Chúng tôi chưa. Đây là đánh cược có ý thức của leader trong điều kiện nguồn lực thật.

## Giữ lại gì

| Giữ | Vì sao |
|---|---|
| Bất biến tiền của mục 4 + 41 golden vector + property test | Sai số tiền là loại lỗi **không khôi phục được**. Rẻ để giữ, đắt để mất |
| `ADR-0004` hợp đồng allocator | Đã đóng băng sau 4 vòng. Trở thành đặc tả của code sản phẩm |
| Bảng phân quyền, ma trận hiển thị, máy trạng thái thu tiền (mục 9, 10, 8) | Bước 1 của chính mục 14.3 |
| `ADR-0005` đường đi review, taxonomy blocker, điều lệ team | Không tốn gì, và giữ được kỷ luật review chéo |
| W9a repo guard | Đã xong, chạy rồi. Tắt đi không tiết kiệm được gì |

## Gác lại gì — ĐÓNG BĂNG TẠI CHỖ, không xoá

`W0` giao thức thực địa · `W1` study instrument · `W2` cổng OCR · `W3` experiment suite · `W7` gate packet · `W8` pricing · `W9` chính sách dữ liệu · `W9a-E` bật enforcement.

**Không xoá file nào.** Khi nào có operator, counsel và kênh tuyển nhóm thì lấy ra dùng — chúng đã qua review và đã sửa 6 blocker.

## Bỏ luôn: hai bản allocator viết mù

Leader chọn phương án dựng sản phẩm, không chọn phương án giữ kỷ luật hai bản. Ghi lại lý do bỏ, để sau này không ai tưởng là quên:

- Bài tập viết mù có giá trị khi allocator là **oracle nghiên cứu** — nó đo xem hợp đồng có đủ chặt không.
- Khi nó là **code sản phẩm**, cùng ngân sách đó dùng vào 41 golden vector + property test + review của Codex cho ra nhiều hơn.
- Bốn vòng review hợp đồng **đã làm xong** phần việc mà differential test định làm: lôi ra 22 chỗ spec im lặng, trước khi có dòng code nào.

Đổi lại, **mọi thay đổi lên code allocator vẫn phải qua golden corpus và property test.** Đó là phần không thương lượng.

## Điều kiện quay lại

Có **operator được chỉ định** + **counsel review có phạm vi** + **kênh tuyển nhóm** → mở lại `ADR-0002`, dùng lại `docs/protocol/v1/` nguyên trạng.
