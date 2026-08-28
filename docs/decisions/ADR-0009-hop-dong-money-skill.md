# ADR-0009 — Hợp đồng `money_skill`

- **Trạng thái:** 🟡 **BẢN THẢO** 2026-08-28 — thêm quyết định 11–15 do corpus ép ra; vẫn chờ đóng băng
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

## Quyết định 11–15 — năm chỗ hở corpus tìm ra

Codex chạy hợp đồng này qua corpus 12 ca viết tay: **6 đạt, 6 trượt**. Nó phân
loại từng ca trượt, và **năm trong sáu là khoảng trống hợp đồng, không phải lỗi
code** — tức là chính ADR này chưa nói đủ. Đây là giá trị thật của việc viết
corpus trước khi viết code, và năm quyết định dưới đây là thứ corpus mua được.

Mỗi quyết định gắn với đúng một ca trượt. Không có ca nào, không có quyết định.

### Quyết định 11 — `excluded` là danh sách người **bị loại khỏi một khoản**, và bắt buộc khi có câu loại trừ

*Ca `05-loai-tru-nguoi`.* Validator cho phép trường `excluded`, nhưng ADR chưa
định nghĩa schema, ý nghĩa, hay khi nào bắt buộc phải có. Nên baseline bỏ qua nó
mà không sai hợp đồng nào cả.

`excluded: [tên]` nghĩa là **những người này không tham gia khoản chi này**, dù
họ có trong nhóm. Khi luồng chat có câu loại trừ ai đó khỏi một khoản cụ thể,
skill **phải** phát ra `excluded`, và phải trích dẫn tin nhắn chứa câu đó.

Skill **không** tự suy ra `shared_by` từ `excluded` — quyết định 2 vẫn nguyên.
Nó chỉ ghi lại điều đã được nói.

### Quyết định 12 — tin nhắn sửa sau vô hiệu hoá số trước, và cả hai đều phải trích dẫn

*Ca `07-sua-lai-so`.* Hợp đồng chỉ kiểm "con số có xuất hiện trong nguồn". Một
người nói 500k rồi nói lại "nhầm, 450k" thì **cả hai số đều xuất hiện**, nên giữ
số cũ là hợp lệ theo đúng chữ của ADR.

Nay: khi cùng một người sửa lại con số cho cùng một khoản, số **sau** thắng.
`source_message_ids` phải chứa **cả hai** tin nhắn — tin nêu số gốc và tin sửa
lại — để người duyệt thấy được vì sao con số là con số đó.

Không suy đoán quá một bước: nếu **người khác** đưa ra con số khác, đó không
phải sửa mà là bất đồng, và thuộc quyết định 13.

### Quyết định 13 — hai người kể cùng một khoản là **một** khoản, và cần hỏi

*Ca `08-hai-nguoi-ke-cung-mot-khoan`.* Chưa có khoá đồng nhất khoản chi, nên
baseline tạo hai khoản, mỗi khoản có số và nguồn hợp lệ, và validator không có
căn cứ nào để bác.

Hai lời kể **đồng nhất** khi trùng số tiền và nói về cùng một việc trong một
khoảng thời gian gần. Skill gộp thành một khoản, `source_message_ids` chứa cả
hai tin.

Nếu hai lời kể **khác số tiền** thì đó là bất đồng, không phải trùng lặp: skill
phát ra **một** khoản với con số của người trả tiền, và **bắt buộc** thêm một
câu vào `questions`. Nhân đôi một khoản chi là cách nhanh nhất để một nhóm đòi
tiền nhau gấp đôi.

### Quyết định 14 — `shared_by_hint` là **người hưởng**, không phải tập chia

*Ca `10-tra-ho-mot-nguoi`.* Trường này có trong allowlist của code nhưng không
có định nghĩa trong ADR: chưa rõ nó là người hưởng, tập chia dự kiến, hay chỉ
gợi ý giao diện.

`shared_by_hint: [tên]` nghĩa là **luồng chat nói rõ ai là người khoản này chi
cho**. Ví dụ "tao trả hộ vé của Linh" thì `shared_by_hint: ["Linh"]`.

Nó là **gợi ý cho người duyệt**, không phải đầu vào của allocator. Quyết định 2
vẫn cấm skill tự chế `shared_by`; cái này chỉ nói lại điều đã có trong tin nhắn,
và người duyệt vẫn phải xác nhận.

### Quyết định 15 — `must_ask` chấm theo **ý**, không theo chuỗi

*Ca `01-ro-rang`.* Oracle bắt câu "ai có mặt trong bữa ăn tối", baseline hỏi
"ai có mặt trong ăn tối". Cùng một câu hỏi, khác vài chữ, và ca dễ nhất trong
corpus trượt vì cách **chấm**, không vì cách **đọc**.

`must_ask` là **tập yêu cầu tối thiểu về ý**: mỗi mục mô tả một thông tin còn
thiếu, và một câu hỏi đạt nếu nó hỏi đúng thông tin đó. Câu hỏi thừa không làm
ca trượt — hỏi nhiều hơn cần thì tốn thời gian của người dùng, không tốn tiền
của họ.

Cách chấm cụ thể là việc của harness, không phải của ADR này. Cái ADR chốt là:
**chấm chuỗi tuyệt đối tạo âm tính giả**, và một hợp đồng bị đo bằng thước sai
thì không đo được gì.

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
5. **Năm quyết định 11–15 sinh từ đúng năm ca trượt.** Corpus có 12 ca, nên nếu
   nó thiếu một tình huống thì hợp đồng vẫn hở đúng chỗ đó và không ai biết.
   Codex đã nói thẳng: qua 12/12 ngay lần đầu thường nghĩa là corpus quá dễ, chứ
   không phải code quá tốt. Cần thêm ca trước khi đóng băng, không phải thêm
   quyết định.
6. Quyết định 13 gộp hai lời kể thành một khoản dựa trên "trùng số tiền và gần
   nhau về thời gian". Cả hai vế đều mờ. Hai bữa ăn 200k trong cùng một tối là
   hai khoản, và tôi chưa có cách phân biệt nào tốt hơn là hỏi.

## Cái không đổi

Mục 3 · ADR-0004 · 41 golden vector · mục 5.1 phần còn lại (không có primitive
nhắn tin tự do, không có bộ nhớ chung theo mặc định) · mục 8.3 cổng xác nhận.
