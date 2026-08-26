# Protocol v1 — Giao thức thực địa

`protocol_version: v1` · **DRAFT** · DRI Claude · Reviewer Codex

## 1. Baseline — trước concierge

**Quan sát trực tiếp một chu kỳ chi phí thật theo cách nhóm đang làm.** Không hỏi hồi tưởng về quy trình.

Thu thập:
- Thời gian chủ động của người tổ chức (mục 1.5 của `00-`), theo cùng cách sẽ dùng ở chu kỳ concierge
- Số thao tác thủ công mỗi nghĩa vụ · số lần chia sẻ · số lời nhắc người tổ chức phải tự gửi
- Tỉ lệ nghĩa vụ được thanh toán trong 7 ngày — **đây là comparator bắt buộc.** Thu tiền đạt 50% là vô nghĩa nếu nhóm đó đang đạt 70% bằng Zalo
- Loại chi phí nào nhóm **có** chia và loại nào **không** — định nghĩa `valid_cost_opportunity` cho chính nhóm này
- Công cụ họ đang dùng, và chỗ nào họ tự chế cách làm

### Quy tắc tương đương baseline ↔ concierge

Hai chu kỳ phải tương đương về: **số người · số tiền · độ phức tạp phân bổ · số người nhận tiền.**

Nếu lệch, ghi vào hồ sơ nhóm và **báo cáo riêng**. Không so trực tiếp một baseline chia đều 4 người với một chu kỳ concierge chia theo món cho 9 người rồi kết luận sản phẩm nhanh hơn.

## 2. Chu kỳ concierge

Người vận hành đứng **sau một giao diện giả lập**. Người tổ chức vẫn phải **tự làm** đúng những thao tác mà v1 sẽ đòi hỏi: nhập dữ liệu, chia sẻ, chủ động gửi lời nhắc.

### 2.1 Danh sách CẤM của operator — vi phạm là `out_of_contract_rescue`, luôn luôn

- ❌ Liên hệ trực tiếp bất kỳ participant nào **không phải người tổ chức**. *App tương lai không có kênh push tới khách vô danh — nếu operator làm được thì đang đo một sản phẩm không tồn tại.*
- ❌ Gửi lời nhắc thay người tổ chức
- ❌ Tự chia sẻ link / QR thay người tổ chức
- ❌ Sửa dữ liệu mà trong sản phẩm thật người dùng phải tự sửa
- ❌ Làm việc ngoài khung giờ SLA
- ❌ Cung cấp thông tin không được hỏi
- ❌ **Dùng hiểu biết cá nhân về participant** không có trong dữ liệu phiên

Vi phạm **không được làm im lặng**. Nếu operator thấy buộc phải cứu, vẫn cứu được — nhưng phải ghi log kèm lý do, và nó tính vào intervention rate.

### 2.2 Đóng băng trước khi ra thực địa

Bốn thứ sau đóng băng **trước** field, không sửa giữa chừng:
1. **Script** — câu chữ chính xác cho mọi phản hồi chuẩn
2. **SLA** — khung giờ trực và thời gian phản hồi tối đa
3. **Lịch nhắc** — thời điểm và **số lần** tối đa
4. **Action allowlist** — thao tác operator được phép làm

Muốn đổi bất kỳ thứ nào → ADR → `protocol_version` mới → **dữ liệu cũ không gộp**.

### 2.3 Hai lane tách biệt

| Lane | Nội dung | Dữ liệu dùng vào đâu |
|---|---|---|
| **Lane V1** | Bot chỉ làm tiền. Yêu cầu ngoài phạm vi bị **từ chối** và ghi `unsupported_intent` | Tính vào hiệu quả v1 |
| **Lane khám phá** | Chốt quán, lên lịch trình, kỉ niệm… có chấp thuận riêng | ⛔ **KHÔNG** tính vào hiệu quả v1 |

Lời từ chối ở Lane V1 phải theo script cố định. Cách từ chối là một biến sản phẩm, không phải chỗ để operator tuỳ hứng.

## 3. Bốn nhãn thao tác — cây quyết định

Gán nhãn **ngay lúc thao tác**, không gán sau. Sửa nhãn sau đó tạo **audit event**, không ghi đè.

Hỏi theo đúng thứ tự này. Dừng ở câu đầu tiên trả lời được:

```
Q1. Hợp đồng của sản phẩm tương lai có CHO PHÉP hành động này không?
    (kênh liên lạc có tồn tại? quyền có sẵn? trong SLA?)
    KHÔNG ─────────────────────────────> out_of_contract_rescue

Q2. Operator có dùng thông tin KHÔNG nằm trong dữ liệu phiên đã ghi lại không?
    (biết người đó ngoài đời, nhớ từ nhóm khác, đoán từ quan hệ cá nhân)
    CÓ, và sản phẩm không thể có thông tin đó ──> out_of_contract_rescue
    CÓ, nhưng sản phẩm có thể có ─────────────> human_judgment_required

Q3. Một QUY TẮC CỐ ĐỊNH, không cần hiểu ngôn ngữ hay hình ảnh, có sinh ra
    đúng output này từ dữ liệu đã có trong hệ thống không?
    CÓ ────────────────────────────────> deterministic_automatable

Q4. Một model ngôn ngữ/thị giác hiện nay có KHẢ NĂNG HỢP LÝ sinh ra output này
    từ đúng những input người dùng đã cung cấp, với người dùng xác nhận sau đó?
    CÓ ────────────────────────────────> model_plausible

Q5. Còn lại ──────────────────────────> human_judgment_required
```

**Vì sao Q1 đứng trước Q3:** một hành động có thể vừa tất định vừa ngoài hợp đồng. Tự động nhắc khách vô danh là tất định — nhưng sản phẩm không có quyền đó. Xếp nó vào `deterministic_automatable` là tự lừa mình rằng phần mềm làm được.

**Vì sao Q2 đứng thứ hai:** đây là chế độ hỏng chính khi **chủ sản phẩm tự làm operator**. Founder biết participant ngoài đời và sẽ vô thức dùng hiểu biết đó. Nếu không hỏi Q2 sớm, mọi thao tác sẽ được gắn nhãn `model_plausible` và kết luận "AI làm được phần lớn" là giả.

### Kiểm định độ tin cậy của nhãn

Một người **độc lập** gán lại nhãn cho **≥20% mẫu ngẫu nhiên**. Báo cả tỉ lệ đồng thuận thô **và** Cohen's kappa.

> **kappa < 0.6 → nhãn KHÔNG dùng được** để kết luận "giá trị đến từ loại nào". Khi đó chỉ được báo cáo mô tả, và phải sửa cây quyết định trước wave sau.

Không có bất kỳ người gán lại độc lập nào → kết luận từ nhãn chỉ là **hypothesis-generating**, ghi rõ như vậy ở mọi nơi con số xuất hiện.

## 4. Lấy mẫu tuần tự

```
Wave A: 6 nhóm/cohort  →  sửa giao thức (có thể lên protocol v2, dữ liệu KHÔNG gộp)
   ↓
Block: +3 nhóm/cohort, lặp lại
   ↓
Mở cổng 13.3 khi: ≥10 nhóm evaluable trong MỘT cohort có valid_cost_opportunity = confirmed
   ↓
Dừng tuyển khi: hai block liên tiếp không sinh failure mode mới
                VÀ hướng kết quả không còn đảo ngược
```

**"Failure mode mới"** = một thất bại không khớp mục nào trong `failure-mode register`. Register là **append-only**, mỗi mục có: mô tả, lần đầu quan sát, nhóm, `protocol_version`.

⚠️ Hai điều kiện dừng là **độc lập**. Chạm `/10` không cho phép dừng tuyển nếu block vẫn đang sinh failure mode mới.

⚠️ Theo lịch `6 + 3 + 3`, điểm sớm nhất có thể vừa đủ là **~12 nhóm/cohort** — và chỉ khi gần như tất cả thực sự có cơ hội tiếp theo. Thiếu opportunity hoặc attrition → 15, 18…

### Interim look

Chỉ được xem số **tại ranh giới block**, theo lịch đã đăng ký trước. Cấm nhìn số hằng tuần rồi chỉnh protocol cho đẹp.

## 5. Phỏng vấn và guardrail người gửi

Người gửi tiền là bên **không** chọn dùng sản phẩm. Trải nghiệm của họ có **quyền phủ quyết** (spec mục 12.4, 13.3).

- Khảo sát **riêng và ẩn danh**. Người tổ chức không thấy câu trả lời cá nhân.
- Nếu operator là founder: founder **không** trực tiếp hỏi người gửi có thích không. Dùng kênh ẩn danh hoặc người thứ ba.
- Đo trước và sau, cùng bộ câu hỏi, để so được với baseline.

### Stop rule về tổn hại quan hệ — dừng ngay, không chờ block

Dừng cohort ngay khi bất kỳ điều nào xảy ra:
- Có báo cáo tổn hại quan hệ quy được về nghiên cứu
- Một participant xin rút và nêu lý do là **áp lực** hoặc **xấu hổ**
- Khảo sát ẩn danh cho thấy mức khó chịu **xấu hơn baseline** rõ rệt

Dừng rồi mới chẩn đoán. Không "chạy nốt block cho đủ mẫu".

## 6. An toàn tiền — bắt buộc ở CẢ HAI biến thể

- **Không ai trong team giữ hoặc chuyển tiền hộ.** Participant tự chuyển trực tiếp cho nhau.
- **Nghĩa vụ phải là thật.** Không có nghĩa vụ thật → rơi vào bẫy "tạo khoản nợ giả" mà spec mục 13.6 cấm.
- **Đối chiếu hai bước** trước khi bất kỳ thông tin nhận tiền nào tới tay participant: người nhận · số tài khoản · số tiền · tên ngân hàng. Hai bước = hai lần kiểm tra tách biệt về thời gian, không phải đọc lại một lần.
- **Kế hoạch hoàn trả** phải viết sẵn **trước** field, không soạn lúc đang có sự cố.
- VietQR do operator tạo **vẫn có thể chuyển sai người**. Đây là rủi ro thật, không phải giả định.

## 7. Đạo đức

- Mọi người bị quan sát phải biết và đồng ý — **kể cả việc có người thật đọc dữ liệu chi tiêu của họ** trong Wizard-of-Oz. Đây là điểm dễ bị bỏ qua nhất vì nó làm lời mời khó nghe hơn.
- Consent phải có **trước** khi thu bất kỳ dữ liệu nào, không phải trước khi phân tích.
- Người gửi tiền cũng là subject nghiên cứu, không chỉ người tổ chức.
- Ghi nhận thiên lệch chọn mẫu: ta đang chọn về những nhóm vốn dễ chịu với việc chia sẻ dữ liệu tài chính.
