# Protocol v1 — Tổng quan và định nghĩa hoạt động

- **protocol_version:** `v1`
- **Trạng thái:** 🟡 **DRAFT** — chưa đóng băng. Đóng băng khi Codex ra verdict và merge vào `main`.
- **Chủ sở hữu:** Claude (W0) · **Reviewer:** Codex
- **Chặn:** W1 (study instrument), W3 (experiment suite)

> Sau khi đóng băng, **không sửa file này tại chỗ**. Thay đổi → ADR → tạo `docs/protocol/v2/`. Dữ liệu mới trỏ `protocol_version: v2`. **Không gộp dữ liệu v1 và v2.**

## Phần bị chặn bởi ADR-0002

Các tham số sau **để trống** cho tới khi leader chọn biến thể:

| Tham số | Trạng thái |
|---|---|
| Số cohort (1 hay 2) | ⛔ chờ ADR-0002 |
| Danh tính operator | ⛔ chờ ADR-0002 |
| Có audit độc lập hay không | ⛔ chờ ADR-0002 |
| Phạm vi counsel review | ⛔ chờ ADR-0002 |
| Có giữ ảnh bill hay không (quyết định W2 có chạy được không) | ⛔ chờ ADR-0002 |

Mọi thứ khác trong protocol v1 **không** phụ thuộc biến thể và được chốt ngay.

---

## 1. Định nghĩa hoạt động

Đây là phần quan trọng nhất của W0. Mọi con số ở cổng 13.3 đều là hàm của những định nghĩa này. Định nghĩa mơ hồ → cổng có thể bị diễn giải theo hướng có lợi sau khi thấy kết quả.

**Quy tắc bao trùm:** mỗi định nghĩa phải phán quyết được bởi một người thứ hai chỉ đọc log, không cần hỏi lại operator.

### 1.1 `valid_cost_opportunity` — cơ hội chi phí hợp lệ

Đây là **mẫu số** của cổng 13.3. Nếu định nghĩa lỏng, "không có cơ hội" sẽ trở thành lời bào chữa cho mọi lần không quay lại.

Một cơ hội là hợp lệ khi **cả bốn** điều sau đúng:

1. Một khoản chi chung có thật đã phát sinh trong cửa sổ quan sát, giữa **≥3 người** thuộc nhóm đã tuyển.
2. Một người đã **ứng trước** toàn bộ hoặc phần lớn, tức có tồn tại nghĩa vụ thật giữa người với người.
3. Loại chi phí đó **thuộc tập mà chính nhóm này đã chia ở baseline**. Không dùng ngưỡng tiền tuyệt đối — 35k với nhóm này là đáng chia, với nhóm khác thì không. Baseline là chuẩn của chính họ.
4. Trạng thái cơ hội được xác định **độc lập với việc họ có dùng dịch vụ hay không**.

#### Xác định cơ hội — hai đường, ưu tiên đường A

**Đường A (ưu tiên) — đăng ký trước lúc thu nạp.**
Lúc intake hỏi: nhóm có chuyến đi / sự kiện / kỳ chi phí nào **đã lên lịch** trong cửa sổ không? Ghi ngày dự kiến vào hồ sơ nhóm **trước khi** chu kỳ bắt đầu. Cơ hội trở thành `confirmed` nếu sự kiện diễn ra, `did_not_occur` nếu không.
→ Không recall bias. Không cần liên hệ giữa chừng. Khớp với "rút ngắn hợp lệ" ở spec mục 13.6.

**Đường B (dự phòng) — check-in trung lập sau cửa sổ.**
Chỉ dùng khi nhóm không có sự kiện lên lịch. Gửi **sau khi cửa sổ đã đóng**, câu chữ cố định, **giống hệt nhau cho mọi nhóm**, và:
- ❌ không nhắc tên dịch vụ
- ❌ không hỏi họ có muốn dùng lại không
- ❌ không gợi ý chia tiền
- ✅ chỉ hỏi: trong khoảng thời gian X–Y, nhóm có phát sinh khoản chi chung nào mà một người trả trước không? Loại gì, khoảng bao nhiêu người?

> **Sửa theo blocker W0-04 của Codex.** Tôi lo sai chỗ. Tôi lo **priming**, và Codex chỉ ra rằng gửi sau khi cửa sổ đã đóng thì câu hỏi **không thể làm phát sinh ngược** một hành vi đã xảy ra trong chính cửa sổ đó.
> Rủi ro thật là **recall và demand bias trong việc PHÂN LOẠI mẫu số**: chỉ nhóm **không** có sự kiện đăng ký trước mới đi Đường B, và người trả lời **biết mình có dùng dịch vụ hay không**. Cùng một tập hành vi có thể thành `5/10` hay `6/10` chỉ vì một ca biên được nhớ và phán quyết **sau khi đã biết outcome**. Câu chữ giống hệt nhau không loại được sai lệch hệ thống này.

**Điều kiện bắt buộc cho Đường B:**

| | |
|---|---|
| Đóng băng trước field | Nguyên văn script · ai là người trả lời · thời điểm · **số lần hỏi tối đa** · rubric bằng chứng |
| Người phán quyết | **Độc lập và mù với usage outcome** khi khả thi. Không khả thi → ghi rõ, và kết quả bị giới hạn tương ứng |
| Bằng chứng không đủ cho **cả bốn** điều kiện ở mục 1.1 | **BẮT BUỘC** `indeterminate`. Không được suy đoán theo hướng có lợi |
| Phân tích | Đăng ký trước việc **tách riêng Đường A và Đường B**, và quy tắc gate khi hai đường cho kết quả khác nhau |
| Sức bền | Đường B **một mình không tạo được GO** nếu kết quả không bền dưới cách phân loại **bảo thủ nhất** (mọi ca biên → không có cơ hội hoặc không repeat) |
| Phơi nhiễm | Mọi dữ liệu **sau** check-in phải ghi `checkin_exposed = true`, kèm quy tắc loại hoặc washout đã đăng ký — check-in **có thể** prime các cửa sổ tương lai nếu nhóm còn được theo dõi |

Ghi rõ nhóm nào dùng đường nào. Kết quả đảo chiều giữa hai đường là **phát hiện**, và khi đó **gate đóng** cho tới khi giải thích được — không phải nhiễu để bỏ qua.

### 1.2 Hai chỉ số khác nhau — KHÔNG được gộp

> **Sửa theo blocker W0-01 của Codex.** Bản đầu tính tử số gate ngay khi người tổ chức đưa một khoản chi vào công cụ. Spec mục 15 đòi nhiều hơn hẳn: *"Chỉ tính repeat khi người dùng **xác nhận VÀ publish** một đợt thu có **ít nhất một nghĩa vụ hợp lệ**."*
> Hậu quả nếu giữ định nghĩa cũ: một bản nháp nhập rồi bỏ, không xác nhận, không chia sẻ, không sinh nghĩa vụ nào **vẫn đẩy được kết quả từ `5/10` lên `6/10`** và mở quyền xây prototype. Đó là tự cho điểm.

#### `voluntary_start` — tín hiệu CHẨN ĐOÁN, không phải tử số gate

Người tổ chức tự đưa một khoản chi mới vào công cụ, không do nhắc.

Dùng để: chẩn đoán chỗ rơi rụng giữa "bắt đầu" và "hoàn tất". **Không bao giờ** dùng để mở cổng.

#### `qualifying_repeat` — TỬ SỐ CỔNG 13.3

Suy ra từ một **chuỗi sự kiện quan sát được**, đủ cả bốn mắt xích, đúng thứ tự, trong cùng một cơ hội:

```
voluntary_start            người tổ chức tự bắt đầu, không do nhắc
   → organizer_confirmed   xác nhận đề xuất
   → organizer_shared      tự chia sẻ / phát đợt thu
   → obligation_declared   ≥1 nghĩa vụ THẬT hợp lệ tới tay ít nhất một người gửi
```

Thiếu bất kỳ mắt xích nào → **không** phải `qualifying_repeat`. Ghi lại mắt xích cuối cùng đạt được, để phân tích rơi rụng.

#### "Không do nhắc" — định nghĩa kiểm tra được, bỏ mốc 48 giờ

Bản đầu dùng "48 giờ trước đó". Codex đúng khi nói mốc đó **không có căn cứ và không có event nào để kiểm tra** — một lời nhắc ở giờ thứ 49 vẫn được tính là tự khởi tạo.

Thay bằng quy tắc **theo cửa sổ, nhị phân, không có con số tuỳ ý**:

> Một `voluntary_start` là **không do nhắc** khi trong cửa sổ cơ hội đang xét, **không tồn tại** `research_contact` nào có `mentions_service = true` xảy ra **trước** nó.

Event `research_contact` là **bắt buộc**: mọi liên hệ từ phía nghiên cứu tới nhóm đều phải log, kèm `mentions_service: bool`. Check-in trung lập ở mục 1.1 Đường B có `mentions_service = false` **theo thiết kế** — và điều đó phải kiểm chứng được bằng script đã đóng băng, không bằng trí nhớ.

Không log `research_contact` ⇒ **không thể** kết luận "không do nhắc" ⇒ ca đó là `indeterminate`.

**KHÔNG tính là `voluntary_start`:**
- ❌ Trả lời "có" cho câu hỏi "bạn có muốn dùng lại không?"
- ❌ Nói trong phỏng vấn rằng sẽ dùng lại
- ❌ Nháp do quy tắc định kỳ tự sinh
- ❌ Bất kỳ hành động nào sau một `research_contact` có `mentions_service = true` trong cùng cửa sổ

**Điều kiện tiên quyết để vào tử số** (spec mục 13.3): nhóm biết dịch vụ vẫn còn · thực sự có `valid_cost_opportunity` · operator không chăm sóc vượt mức sản phẩm tương lai.
→ Nhóm không thoả cả ba **không nằm ở tử số cũng không nằm ở mẫu số**. Báo cáo riêng, **không xoá im lặng**.

### 1.3 `serious_error` — lỗi nghiêm trọng. Phải bằng 0.

Xảy ra khi **thông tin sai đã đến tay participant** (đã publish / đã chia sẻ), bất kể có sửa sau đó hay không:
- sai người nhận tiền
- sai số tiền theo hướng vật chất
- một người bị yêu cầu trả khoản họ không nợ
- nghĩa vụ bị gán cho sai người

Sửa sau **không xoá** lỗi. Đã tới tay là đã xảy ra.

`near_miss` — bắt được **trước** khi tới tay participant. **Không** tính vào `serious_error`, nhưng **bắt buộc ghi log** với nguyên nhân. Tỉ lệ near-miss cao mà serious error = 0 nghĩa là hàng rào đang hoạt động, **không** nghĩa là hệ thống đúng.

### 1.4 `evaluable_group` — nhóm đánh giá được

Chỉ nhóm evaluable mới vào mẫu số `/10` của cổng 13.3. Điều kiện:
1. Hoàn tất baseline.
2. Hoàn tất **≥1** chu kỳ concierge.
3. Đã tới cuối cửa sổ cơ hội với trạng thái **xác định**: `confirmed` hoặc `did_not_occur`.

Nhóm rời giữa chừng → `attrited`, có `attrition_reason`, **báo cáo riêng, không bao giờ xoá im lặng**.

⚠️ Nhóm evaluable được xác định theo **thứ tự thu nạp đã đăng ký trước**. Cấm chọn 10 nhóm đẹp nhất sau khi đã xem kết quả.

### 1.5 `organizer_active_time` — thời gian chủ động của người tổ chức

Tổng thời gian người tổ chức bỏ ra cho việc chia và thu tiền, gồm hai nguồn:

| Nguồn | Cách đo | Độ tin cậy |
|---|---|---|
| Trong công cụ | Timestamp của instrument | Cao |
| Ngoài công cụ (đi đòi trong Zalo, nhắn riêng, đối chiếu) | Nhật ký tự khai có cấu trúc, điền **cùng ngày** | **Thấp — khai báo thẳng** |

Chỉ số chính là **median**, không phải trung bình — một nhóm hỗn loạn sẽ kéo lệch trung bình.

Baseline và concierge phải đo **cùng cách**, nếu không mức giảm 30% ở cổng 13.3 là giả tạo.

⚠️ Tự khai có social desirability bias theo hướng **có lợi cho sản phẩm** (người tổ chức biết đang được quan sát và có xu hướng báo ít giờ hơn ở chu kỳ concierge). Ghi vào bản khai thiên lệch.

### 1.6 `collection_batch_completed` — đợt thu hoàn tất

Định nghĩa **trước** khi pilot bắt đầu, gồm cách xử lý ba trường hợp ngoại lệ:
- **Tranh chấp:** nghĩa vụ đang tranh chấp **vẫn nằm ở mẫu số**.
- **Miễn nợ:** ghi nhận là `waived`, loại khỏi mẫu số, nhưng đếm riêng — tỉ lệ waive cao là tín hiệu xấu về quan hệ.
- **Huỷ hợp lệ:** loại khỏi mẫu số.

Hoàn tất = mọi nghĩa vụ không bị loại đều đạt `receiver_confirmed`.

⚠️ `receiver_confirmed` **không phải bằng chứng ngân hàng**. Người nhận quên bấm → thất bại giả. Bấm nhầm → thành công giả. Báo cáo phải ghi kèm cảnh báo này ở mọi nơi con số xuất hiện.

### 1.7 `operator_intervention` — can thiệp của người vận hành

Mọi thao tác của operator ngoài `deterministic_automatable` và `model_plausible`.

**Mọi rescue đều tính vào chi phí và intervention rate, kể cả rescue thành công.** Không có "linh hoạt giúp thêm miễn phí". Spec mục 13.1 nói rõ điều này và nó là chỗ dễ gian lận nhất với chính mình.
