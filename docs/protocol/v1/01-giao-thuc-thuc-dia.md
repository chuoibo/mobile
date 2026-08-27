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
    CÓ, và sản phẩm KHÔNG THỂ có thông tin đó ─> out_of_contract_rescue
    CÓ, nhưng sản phẩm CÓ THỂ có ─────────────> missing_input_deviation
                                                (protocol deviation, KHÔNG phải
                                                 bằng chứng cần phán đoán người)

Q3. Một QUY TẮC CỐ ĐỊNH, không cần hiểu ngôn ngữ hay hình ảnh, có sinh ra
    đúng output này từ dữ liệu đã có trong hệ thống không?
    CÓ ────────────────────────────────> deterministic_automatable

Q4. Model đã NEO TRONG capability_snapshot (có tên model + version + ngày)
    có sinh ra output này từ đúng input người dùng đã cung cấp không?
    Phán quyết bằng REPLAY TEST đã version, KHÔNG bằng cảm giác
    CÓ ────────────────────────────────> model_plausible

Q5. Còn lại ──────────────────────────> human_judgment_required
```

**Vì sao Q1 đứng trước Q3:** một hành động có thể vừa tất định vừa ngoài hợp đồng. Tự động nhắc khách vô danh là tất định — nhưng sản phẩm không có quyền đó. Xếp nó vào `deterministic_automatable` là tự lừa mình rằng phần mềm làm được.

**Vì sao Q2 đứng thứ hai:** đây là chế độ hỏng chính khi **chủ sản phẩm tự làm operator**. Founder biết participant ngoài đời và sẽ vô thức dùng hiểu biết đó. Nếu không hỏi Q2 sớm, mọi thao tác sẽ được gắn nhãn `model_plausible` và kết luận "AI làm được phần lớn" là giả.

### Kiểm định độ tin cậy của nhãn

Một người **độc lập** gán lại nhãn cho **≥20% mẫu ngẫu nhiên**. Báo cả tỉ lệ đồng thuận thô **và** Cohen's kappa.

> **Sửa theo blocker W0-05 của Codex.** Ba sai lầm trong bản đầu:
> 1. `"sản phẩm có thể có input này"` → `human_judgment_required` là **phi logic**. Thiếu input trong phiên **không chứng minh** cần phán đoán con người. Đó là **protocol deviation**, giờ có nhãn riêng `missing_input_deviation`.
> 2. `"model hiện nay có khả năng hợp lý"` — model nào? phiên bản nào? Người thứ hai **không tái lập được**. Giờ neo vào `capability_snapshot` có version và phán quyết bằng **replay test**.
> 3. **Một con số kappa toàn cục che được lỗi ở đúng hai lớp quyết định luận đề.** Với bốn lớp lệch mạnh, `kappa ≥ 0.6` vẫn đi cùng đồng thuận rất tệ riêng ở `human_judgment_required` và `out_of_contract_rescue` — mà chính hai lớp đó quyết định "đây là phần mềm hay dịch vụ vận hành".

**Ba trục, ghi riêng, không gộp thành một nhãn rồi mất thông tin:**

| Trục | Câu hỏi | Giá trị |
|---|---|---|
| `contract_authority` | Sản phẩm có QUYỀN làm việc này không? | `permitted` · `not_permitted` |
| `input_provenance` | Thông tin đến từ đâu? | `in_session` · `outside_session_obtainable` · `outside_session_impossible` |
| `generation_mechanism` | Cơ chế nào sinh ra output? | `deterministic_rule` · `model_replayable` · `human_judgment` |

Bốn nhãn cũ vẫn suy ra được từ ba trục theo precedence Q1→Q5. Nhưng **dữ liệu thô là ba trục**, để phân tích lại được khi taxonomy sai.

**Đo độ tin cậy — đóng băng trước field:**
- Đơn vị lấy mẫu · **seed** · độ phủ **lớp hiếm** (lấy mẫu phân tầng, không lấy ngẫu nhiên thuần)
- Báo **confusion matrix** và **đồng thuận theo từng lớp**, không chỉ một con số
- Quy trình adjudication cho mọi bất đồng, đã đăng ký trước
- **Rule gate riêng cho nhóm `human_judgment_required` + `out_of_contract_rescue`** — đây là nhóm quyết định luận đề

> Báo kappa, nhưng **kappa KHÔNG phải công tắc duy nhất**. Đồng thuận theo lớp ở hai lớp gate-critical mới là điều kiện.

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
                VÀ "hướng" đã ổn định (định nghĩa bên dưới)
```

> **Sửa theo blocker W0-06 của Codex.** "Hướng kết quả không còn đảo ngược" là **câu tự do, không phải preregistration**. Hai analyst đọc cùng dữ liệu có thể ra hai quyết định khác nhau; và sau khi xem block, team có thể **gộp hoặc tách failure mode** cho vừa ý.

**`failure-mode register`** — tạo và **version TRƯỚC dữ liệu đầu tiên**, không phải khi gặp lỗi đầu tiên. Append-only. Mỗi mục có: mô tả · lần đầu quan sát · nhóm · `protocol_version` · `register_version`.

**"Mới hay không mới"** do một người adjudicate theo rule đã đăng ký, **không do người đang muốn dừng tuyển**. Gộp hai mục hoặc tách một mục đều là thay đổi `register_version`, và phải ghi lý do **trước khi** xem block tiếp theo.

**"Hướng" được định nghĩa bằng VỊ TRÍ SO VỚI NGƯỠNG**, không bằng cảm nhận xu hướng:

> "Hướng đã ổn định" = qua **hai block liên tiếp**, ước lượng điểm của chỉ số chính **không đổi khoang** trong bốn khoang đã đăng ký: `<4/10` · `4–5/10` · `≥6/10` · `≥7/10 kèm ≤20% can thiệp`.

Đổi khoang giữa hai block ⇒ **chưa ổn định**, tiếp tục tuyển.

**Đổi `protocol_version` RESET chuỗi hai block.** Dữ liệu trước và sau không gộp được thì cũng không tính chung vào điều kiện dừng.

**Trần và dừng sớm — đăng ký trước:**

| Rule | Ngưỡng |
|---|---|
| Trần tuyển | `N_max` nhóm mỗi cohort, và `T_max` tuần theo lịch. Chạm trần → dừng, báo cáo với mẫu hiện có, **không gia hạn** |
| `stop-futility` | Ước lượng điểm nằm ở khoang `<4/10` qua **hai block liên tiếp** |
| `stop-harm` | Bất kỳ điều kiện nào ở mục 5 — **có hiệu lực ngay, không chờ ranh giới block** |
| `stop-saturation` | Hai block không có failure mode mới **VÀ** hướng đã ổn định |

`N_max` và `T_max` chốt cùng lúc với ADR-0002 — chúng phụ thuộc biến thể.

**Golden block sequence** phải viết trước, dạng chuỗi tổng hợp, cho cả bốn kết cục `continue` · `stop-futility` · `stop-harm` · `stop-saturation`. Hai analyst chạy rule trên cùng chuỗi phải ra cùng quyết định — nếu không thì rule chưa đủ chặt.

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
