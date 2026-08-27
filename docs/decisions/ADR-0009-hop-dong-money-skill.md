# ADR-0009 — Hợp đồng `money_skill`

- **Trạng thái:** 🟡 **BẢN THẢO** 2026-08-27 — chờ Codex tấn công
- **Ngày:** 2026-08-27
- **DRI:** Claude · **Reviewer:** Codex
- **Nguồn:** spec mục 5.4 (hợp đồng kỹ năng), mục 3 (ranh giới AI↔tiền), ADR-0008
- **Chặn:** toàn bộ demo

> **Không ai viết code trích xuất trước khi ADR này đóng băng.** Đúng lý do
> ADR-0004 tồn tại: viết code trước rồi hợp thức hoá hợp đồng sau sẽ biến bộ
> eval thành nghi lễ.

## Bối cảnh

ADR-0008 cho bot đọc luồng chat nhóm. Bộ eval viết tay
`tests/skills/corpus/doc-luong-nhom.json` được soạn **trước** ADR này, và bốn
điều nó lôi ra đã định hình toàn bộ hợp đồng dưới đây.

---

## Quyết định 1 — Đầu ra không phải một đề xuất

Ngay ca dễ nhất trong corpus cũng không ra được khoản chi hoàn chỉnh: *"tao vừa
trả tiền ăn tối 800k"* không nói ai có mặt, mà `shared_by` là input bắt buộc của
allocator.

```
money_skill(context) -> {expenses: [...], questions: [...]}
```

**Cả hai mảng đều có thể rỗng.** `expenses` rỗng + `questions` không rỗng là kết
quả hợp lệ và thường gặp, không phải trạng thái lỗi.

## Quyết định 2 — Skill không bao giờ tự nghĩ ra danh sách người tham gia

Nếu luồng chat không nói rõ ai có mặt, skill **phải hỏi**. Không suy ra từ danh
sách thành viên nhóm, không suy ra từ ai đang nói chuyện trong đoạn đó.

Suy sai `shared_by` là bắt một người trả cho bữa họ không ăn. Corpus ca 05 và
ca 10 đều là ca này.

## Quyết định 3 — Trích dẫn nguồn là bắt buộc, không phải chỉ dấu tin cậy

Mọi phần tử của `expenses` phải có `source_message_ids` không rỗng, trỏ tới tin
nhắn có thật trong khoảng đã đọc. Một khoản chi không trích dẫn được là **vi
phạm hợp đồng**, bị từ chối ở tầng validator, không phải một phỏng đoán yếu.

Đây là ràng buộc ADR-0008 đặt ra để bù cho việc bỏ §5.1.

## Quyết định 4 — Không có điểm tin cậy

Skill **không** trả về `confidence`. Chỉ có hai kết cục: đủ chắc để thành một
`expense` có trích dẫn, hoặc thành một `question`.

Lý do: một con số tin cậy sẽ mời gọi giao diện tự động chấp nhận khi vượt
ngưỡng. Mục 15 đã cảnh báo đúng chuyện này — *"không có sửa đổi vật chất" đo
hành vi sửa, không đo độ chính xác.* Một ngưỡng tự động sẽ biến cổng xác nhận
ở mục 8.3 thành hình thức, mà ADR-0008 vừa nâng nó lên thành thứ duy nhất đứng
giữa một lần đọc sai và một lời buộc nợ sai.

## Quyết định 5 — Validator tất định, chạy sau model, không dùng model

Mục 5.4 đòi *"invariants và validator độc lập với model"*. Đây là bản cụ thể:

1. Mọi `source_message_ids` phải tồn tại trong khoảng `context_manifest` khai.
2. **Số tiền phải xuất hiện thật trong tin nhắn được trích dẫn.** Chuẩn hoá
   `1tr2` · `1.200.000` · `1200k` · `1 triệu 2` rồi so khớp. Model nói 800000
   mà tin nhắn được trích không chứa số nào chuẩn hoá về 800000 → **từ chối**.
3. `paid_by` phải là một người có thật trong nhóm, theo id chứ không theo tên
   hiển thị (corpus ca 12: hai người tên Nam).
4. `total_vnd` là số nguyên dương, đơn vị đồng, không số thực.

Điểm 2 là guardrail mạnh nhất trong hợp đồng này, vì nó bắt được ảo giác số
tiền mà **không cần** một model thứ hai.

## Quyết định 6 — Skill không tính một phép tiền nào

Ranh giới mục 3, nhắc lại vì đây là chỗ dễ trôi nhất. Skill ra khoản chi thô;
`app/domain/allocator.py` chia. ADR-0004 và 41 golden vector vẫn đóng băng.

Hệ quả: một lần đọc sai hiện ra thành đề xuất sai mà người phải duyệt, chứ
không thành số học sai. `Σ allocated_vnd == total_vnd` vẫn đúng 100%.

## Quyết định 7 — `context_manifest` không được để trống

Khai: id tin nhắn đầu và cuối của khoảng đã đọc, tổng số tin nhắn, thời điểm
chụp. Mục đích: một lần đọc không khai được là một lần đọc không kiểm toán được.

## Quyết định 8 — Trần chi phí

- Tối đa **N tin nhắn** mỗi lần gọi (N chốt khi đo thật, mặc định 200).
- Trần token, timeout, số lần hỏi lại theo mục 5.1 — **vẫn nguyên hiệu lực**.
- Vượt trần thì từ chối tường minh và nói rõ khoảng quá dài, không cắt bớt
  âm thầm. Cắt âm thầm là bỏ sót khoản chi mà không ai biết.

## Quyết định 9 — Gọi lại tạo invocation mới, không sửa cái cũ

Cùng một khoảng chat gọi hai lần có thể ra hai kết quả khác nhau — đó là bản
chất của model. Nên mỗi lần gọi lưu thành một `SkillInvocation` riêng. Không
bao giờ sửa đè kết quả cũ. Mục 5.4 đòi audit và rollback; append-only là cách
rẻ nhất có cả hai.

## Quyết định 10 — Quy tắc từ chối

Theo mục 5.5, bot nói thẳng việc chưa làm được thay vì cố đoán. Ba loại:

- Intent ngoài phạm vi (gợi ý quán, đặt vé) → từ chối theo mẫu ở mục 5.5.
- Khoảng chat vượt trần → từ chối, nêu con số.
- Validator bác → **không** trả đề xuất đã bị bác cho người dùng xem. Trả về
  câu hỏi thay thế.

---

## Điều tôi tự thấy yếu, mong Codex đánh vào

1. **Chuẩn hoá số tiền tiếng Việt** ở validator điểm 2 là chỗ dễ sai nhất, và
   nếu nó sai theo hướng dễ dãi thì cả guardrail thành vô dụng. Cần bộ vector
   riêng cho riêng việc chuẩn hoá.
2. Corpus mới có 12 ca. Sáu hướng tôi nghi mình yếu đã ghi trong lệnh giao.
3. Quyết định 4 (không có điểm tin cậy) có thể quá cứng. Nhưng tôi thà cứng
   nhầm ở phía bắt người ta đọc.
4. Chưa quyết model nào làm việc trích xuất. Tầng trích xuất phải nằm sau một
   interface, kèm một bản giả tất định để chạy corpus không cần mạng.

## Cái không đổi

Mục 3 · ADR-0004 · 41 golden vector · mục 5.1 phần còn lại (không có primitive
nhắn tin tự do, không có bộ nhớ chung theo mặc định) · mục 8.3 cổng xác nhận.
