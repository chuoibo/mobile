# Báo cáo chạy corpus `money_skill` bằng baseline độc lập

## Kết luận

Kết quả lần chạy đầu: **6 đạt, 6 trượt trên 12 ca**.

Baseline là extractor giả tất định chỉ nhận `context` mà `run_money_skill`
truyền vào. Nó không nhận `case_id`, `expected`, `must_ask` hay
`must_not_extract`. Vì vậy kết quả này loại được vòng lặp cũ
`FAKE_RESPONSES[case_id] -> oracle -> so lại chính oracle`.

Kết quả vẫn **không chứng minh khả năng đọc tiếng Việt đời thường**. Baseline
được viết sau khi corpus đã tồn tại và dùng một từ điển luật nhỏ. Sáu ca đạt chỉ
là baseline trên đúng 12 câu tổng hợp, không phải độ chính xác của model hay của
một extractor production.

Lệnh chạy:

```text
cd services/api
python3 tools/run_money_skill_corpus.py
```

Runner in đủ 12 kết quả rồi mới trả mã khác không. Tóm tắt quan sát được:

```text
SUMMARY passed=6 failed=6 total=12
```

Các ca đạt: `03`, `04`, `06`, `09`, `11`, `12`.

Các ca trượt: `01`, `02`, `05`, `07`, `08`, `10`.

## Phân loại từng ca trượt

| Ca | Phân loại chính | Bằng chứng và hậu quả |
|---|---|---|
| `01-ro-rang` | **khoảng trống hợp đồng ADR-0009** | Baseline hỏi `ai co mat trong an toi`; oracle bắt `ai co mat trong bua an toi`. Hai câu cùng yêu cầu xác nhận người tham gia, nhưng ADR không định nghĩa so khớp ngữ nghĩa hay câu chữ chuẩn. Chấm bằng chuỗi tuyệt đối tạo âm tính giả. Tôi không sửa câu baseline để lấy điểm. |
| `02-so-tien-o-tin-nhan-sau` | **lỗi code — extractor giả** | Baseline không nối phát biểu “đã trả khách sạn” với số tiền ở tin nhắn trả lời sau, nên không tạo khoản chi. `run_money_skill` không thể chứng minh tính đầy đủ của output; lỗi quan sát được nằm ở extractor, không phải phép kiểm grounding. |
| `05-loai-tru-nguoi` | **khoảng trống hợp đồng ADR-0009** | Oracle yêu cầu `excluded=[Linh]` và trích cả hai tin, còn baseline chỉ tạo khoản lẩu từ tin có số tiền. Validator cho phép trường `excluded`, nhưng ADR chưa định nghĩa schema, ý nghĩa bắt buộc hay cách xử lý một câu loại trừ. Chưa đủ căn cứ gọi output thiếu trường này là vi phạm hợp đồng máy đọc được. |
| `07-sua-lai-so` | **khoảng trống hợp đồng ADR-0009** | Baseline giữ số cũ; validator chấp nhận vì số đó thật sự có trong nguồn. ADR chỉ kiểm “số xuất hiện”, chưa có luật tin sửa sau vô hiệu hoá số trước. `must_not_extract` chỉ nói không tạo hai khoản, chưa nói bằng predicate cấu trúc rằng số cũ phải bị loại. |
| `08-hai-nguoi-ke-cung-mot-khoan` | **khoảng trống hợp đồng ADR-0009** | Baseline tạo hai khoản đều có số và nguồn hợp lệ. ADR chưa định nghĩa khoá đồng nhất khoản chi, quy tắc gộp lời kể lại, hoặc nguồn nào quyết định `paid_by`; validator vì thế không thể bác việc nhân đôi. |
| `10-tra-ho-mot-nguoi` | **khoảng trống hợp đồng ADR-0009** | Baseline tạo khoản vé chung, không có `shared_by_hint=[Linh]`. Trường này có trong allowlist của code nhưng không có định nghĩa chuẩn trong ADR: chưa rõ đây là người hưởng, tập chia dự kiến hay chỉ gợi ý giao diện. |

Không có ca trượt nào đủ bằng chứng để kết luận **corpus sai**. Ca `01` có lỗi ở
hợp đồng chấm, không phải ở ý định oracle. Với `05`, `07`, `08`, `10`, oracle
nêu hành vi an toàn hợp lý nhưng ADR chưa biến hành vi đó thành quy tắc chuẩn có
thể kiểm bằng máy.

## `must_ask` và `must_not_extract`

Harness mới hiểu `must_ask` là **tập yêu cầu tối thiểu**, đúng nghĩa tên trường:
câu hỏi thừa không làm ca trượt. Tuy vậy, câu bắt buộc hiện vẫn được so theo
chuỗi tuyệt đối; ca `01` chứng minh cách đó chưa đủ.

`must_not_extract` hiện là văn bản tự do. Harness không giả vờ hiểu ngữ nghĩa
của văn bản này. Nó luôn mang các ghi chú đó vào báo cáo, còn phản ví dụ quan
sát được bị bắt bằng so sánh chính xác toàn bộ danh sách `expenses`. Bốn mutant
thêm khoản ngoài oracle ở các ca `04`, `07`, `09`, `12` đều làm harness đỏ.
Điều này bắt đúng bốn phản ví dụ hiện tại, nhưng chưa biến câu chữ tự do thành
predicate tái sử dụng cho corpus mới.

## Cổng tiếp theo

Chưa được gọi corpus này là `PASS` hành vi. Trước khi dùng nó làm cổng cho một
extractor thật, ADR-0009 cần chốt ít nhất:

1. schema chuẩn và semantics của `excluded` cùng `shared_by_hint`;
2. quy tắc sửa số và gộp lời kể trùng;
3. cách chấm câu hỏi theo intent thay vì chuỗi, hoặc một tập câu hỏi chuẩn;
4. dạng predicate có cấu trúc cho `must_not_extract`.

Sau đó mới đóng băng evaluator, chạy một extractor không được viết vừa khít với
12 ca này, và giữ nguyên báo cáo tất cả ca trượt.
