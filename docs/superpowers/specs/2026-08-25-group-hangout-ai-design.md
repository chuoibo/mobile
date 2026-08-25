# Spec: Trợ lý nhóm đi chơi — v1 là kỹ năng chia & thu tiền

Ngày: 2026-08-26
Trạng thái: **ĐÃ HỘI TỤ** sau 19 vòng tranh luận đối kháng Claude ↔ Codex.
Mức độ: đủ để lập kế hoạch triển khai. **Chưa** phải giấy phép bắt đầu viết code sản phẩm — xem mục 13.

---

## 0. Tóm tắt điều hành

Tầm nhìn của chủ sản phẩm: một nền tảng tích hợp cho nhóm bạn trẻ Việt Nam đi chơi — gợi ý địa điểm, lên kế hoạch, chia sẻ kỉ niệm — với **một trợ lý AI được triệu hồi vào luồng của nhóm** làm chìa khoá.

V1 hiện thực hoá đúng **một** kỹ năng của trợ lý đó: **chia tiền và thu tiền**.

Hai phát hiện định hình toàn bộ thiết kế:

**① Phép chia không phải phần đau nhất. Việc đi thu tiền mới là.**
Tính ra *"Hà 82k, Nam 104k"* chỉ là nửa đầu. Nửa sau — nhắn riêng từng đứa, gửi số tài khoản, nhớ ai đã chuyển ai chưa, nhắc mà không mất lòng — mới là phần mệt và ngại. Nếu app tính nhanh hơn nhưng việc thu tiền vẫn diễn ra thủ công trong Zalo thì không có lý do để ở lại.
→ Màn hình trung tâm của kỹ năng tiền là **bảng thu tiền**, không phải màn chia tiền.

**② Đây là luồng giao việc, không phải app nhắn tin.**
Bot ngồi im cho tới khi được gọi. Trong luồng đó **không có nhắn tin tự do giữa người với người** — mọi thứ đăng lên là một lệnh gọi bot hoặc câu trả lời cho lệnh đang mở. Ràng buộc này là điều kiện sống còn: cho phép chat tự do thì mọi lý do khiến các app "chat + tính năng X" thất bại sẽ quay lại.

**Lưu ý về mức độ chắc chắn:** phát hiện ① vẫn là **luận đề chưa có bằng chứng hành vi**, và nó là giả định số 1 của cả sản phẩm. Mục 12 tồn tại để kiểm chứng nó *trước khi* viết code.

---

## 1. Định vị và phân khúc

### 1.1 Ba tầng thông điệp (bắt buộc tách bạch)

| Tầng | Nội dung |
|---|---|
| **Tầm nhìn** | Nền tảng tích hợp cho nhóm bạn đi chơi, trợ lý là chìa khoá |
| **Lời hứa lúc ra mắt** | *"Một trợ lý chung cho mọi cuộc đi chơi. Bắt đầu với chia bill và thu tiền."* |
| **Năng lực tại thời điểm dùng** | Bot tự khai chính xác kỹ năng nào đang hoạt động |

**Cấm tuyệt đối ở v1:** dùng cụm "gợi ý bất cứ điều gì" trên cửa hàng ứng dụng hoặc trong onboarding · hiện tab quán/chuyến đi/kỉ niệm đang trống hoặc gắn nhãn "sắp có" · dùng ảnh mô phỏng kỹ năng chưa tồn tại · gọi là "nền tảng tích hợp" rồi để lần dùng đầu chỉ thấy một ô chia tiền.

"Platform" là **tầm nhìn và kiến trúc mở rộng**; lời hứa thu hút người dùng vẫn phải là một việc cụ thể.

### 1.2 Phân khúc

- **Beachhead marketing:** nhóm bạn trẻ Việt Nam 18–24 đi chơi.
- **Cohort nghiên cứu (KHÔNG dùng để định vị):** sinh viên ở trọ chung — tuyển riêng qua ký túc xá/cộng đồng, dùng cho kiểm thử khả dụng, kiểm tra máy trạng thái và cơ chế định kỳ.
- **Không được gộp chỉ số hai cohort.** Nhóm ở trọ được tuyển chủ đích có quan hệ ổn định và nghĩa vụ bắt buộc hàng tháng → gần như chắc chắn ước lượng vống retention. Không dùng dữ liệu này để dự báo retention tự nhiên, chi phí thu nạp, hay định vị của thị trường đi chơi.
- Đo riêng trong cohort đi chơi: bao nhiêu nhóm thực sự có chi phí lặp lại ngoài các buổi đi chơi.

### 1.3 Đối thủ và lợi thế

Đối thủ thật **không phải Splitwise** (đã có sổ, chia theo món, quét hoá đơn, rút gọn nợ, và bản trả phí) mà là **máy tính bỏ túi + tin nhắn Zalo/Messenger + ảnh chụp màn hình chuyển khoản**.

Lợi thế **giả thuyết** (chưa chứng minh, phải đo): hiểu tiếng Việt đời thường và biệt danh · khách thao tác được không cần cài app · vòng thu tiền hoàn chỉnh hợp tập quán Việt · VietQR · phân phối qua chính nhóm chat sẵn có.

**Không phải lợi thế:** nhãn "có AI". Những thứ trên đều **sao chép được** và không tạo hiệu ứng mạng. Thứ có thể trở thành lợi thế thật là niềm tin, thói quen của người tổ chức, và dữ liệu vận hành có nhãn — cả ba **chưa tồn tại**.

### 1.4 Kiếm tiền

V1 miễn phí. Organizer Pro chỉ là **giả thuyết**. Không bán thứ hạng địa điểm cho quán.

Nhưng **không hoãn việc kiểm chứng đến sau retention** — chạy song song trong giai đoạn 0: phỏng vấn giá, cửa giả cho tính năng nâng cao, đo mức sẵn lòng trả theo cohort. Retention không tự biến thành mô hình kinh doanh.

### 1.5 Ràng buộc của chủ sản phẩm

**RB-1 — App native là ràng buộc cứng.** Không có cổng kiểm chứng kênh.
- Quyết định do chủ sản phẩm đưa ra, **không được dữ liệu giai đoạn 0 chứng minh**.
- Chi phí cài đặt và kích hoạt mạng lưới là **rủi ro đã được chấp nhận có ý thức**.
- Nếu dữ liệu cho thấy web vượt trội, kết cục hợp lệ dưới ràng buộc này là **dừng sản phẩm**, không phải âm thầm quay lại web.
- Vẫn phải đo "thuế native": tỉ lệ cài, hoàn tất đăng ký, claim membership, số thành viên thực sự tham gia luồng — để **chẩn đoán**, không phải để lật quyết định.

**RB-2 — Định vị nền tảng** (mục 1.1).

---

## 2. Phạm vi v1

### 2.1 CÓ

- Luồng triệu hồi tác vụ theo nhóm, với **đúng một kỹ năng AI: tiền**.
- Session-first: chia tiền ngay, không cần tạo nhóm trước.
- Ba đường vào (**không ngang hàng**): text tiếng Việt là đường cho người thạo · ảnh bill là *attachment* của lệnh gọi · nhập tay có cấu trúc là đường lui bắt buộc, phải chạy khi AI lỗi hoặc mất mạng.
- Một người ứng tiền cho mỗi khoản chi. Nhiều người ứng → nhiều khoản chi.
- AI sinh **đề xuất**; người có thẩm quyền xác nhận thì mới vào sổ.
- UI mặc định hiện **số tiền theo từng người**; drill-down *"Vì sao tôi trả 82k?"* là tuỳ chọn.
- **Đợt thu tiền** gom nhiều khoản chi, **nhiều người nhận trong một đợt**.
- Bảng thu tiền + hộp thư việc cần làm.
- **Chỉ có link cá nhân hoá cho từng người.**
- VietQR, lưu ảnh QR, copy số tài khoản/số tiền/nội dung, deep link ngân hàng khi có.
- Phản đối, xin bằng chứng đã che, nhắc có giới hạn, chuyển thiếu/sai số, hoàn tác xác nhận nhầm.
- Số dư tổng, số dư theo ngữ cảnh, lịch sử kiểm toán.
- Rời nhóm được **kể cả khi còn nghĩa vụ chưa tất toán**.
- Kiểm duyệt tối thiểu **có người trực thật**.

### 2.2 KHÔNG

| Bị cắt | Lý do |
|---|---|
| **Nhắn tin tự do giữa người với người** | Cho phép là biến thành app nhắn tin; mọi phản biện cũ quay lại |
| **Chế độ "một link ai có cũng xem được"** | Không thể vừa công khai, vừa không xác thực, vừa riêng tư. Cắt bỏ nghịch lý chấp thuận, và tránh phải đi xin phép công khai số tài khoản |
| **Chia sẻ hàng loạt / "Copy tất cả" / xuất gói link** | Chính là cửa sau xây lại chế độ link chung |
| Nhập bằng giọng nói | Quán ồn, thêm quyền, thêm lỗi; chưa có bằng chứng nhu cầu |
| Nhận diện khuôn mặt / sinh trắc học | Giá trị chỉ là đỡ vài lần chạm; đổi lại toàn bộ gánh nặng pháp lý và bảo mật |
| Quay video nhận món | Món Việt nhìn giống nhau; đồ uống không phân biệt được bằng mắt; phải suy luận món nào trước mặt ai |
| Gợi ý địa điểm, kế hoạch chuyến đi, kỉ niệm | Mỗi thứ cần dữ liệu, chuẩn chất lượng, mô hình quyền và bài toán chi phí riêng |
| Trí nhớ AI suy diễn sở thích | "Đã mua" ≠ "thích". Suy ra ăn chay/dị ứng là tạo hồ sơ sức khoẻ sau lưng người dùng |
| Bộ nhớ dùng chung giữa các kỹ năng | Kỹ năng sau không được đọc sổ chỉ vì cùng nằm trong một bot |
| Ma trận món × người trên UI | 10 món × 8 người = 80 ô bấm nhầm |
| Nhiều người ứng tiền trong một khoản chi | Biểu diễn được bằng nhiều khoản chi |
| **UI định kỳ** | Là schema ở phần mô hình tương lai, **không chạy migration ở v1**. "Thiết kế được đường mở rộng" ≠ "deploy một schema chết" |
| AI tự gây side effect vật chất | Ranh giới bất khả xâm phạm |
| Tự bù trừ xuyên đợt thu | Thay đổi thoả thuận xã hội mà không ai biết |
| Ảnh chuyển khoản làm bằng chứng mặc định | Dễ giả, lại thu thêm dữ liệu tài chính nhạy cảm |
| Ví, giữ tiền, tự xác nhận giao dịch ngân hàng | Vượt phạm vi, kéo theo giấy phép |
| Model gateway đa nhà cung cấp, plugin runtime tổng quát | Giải bài toán chưa tồn tại |
| Navigation cho kỹ năng chưa có | Hiện tab trống là cách nhanh nhất mất niềm tin |
| Quán trả tiền để được gợi ý | Chưa có gì để bán, và làm hỏng niềm tin |

---

## 3. Ranh giới AI ↔ tiền

- AI **chỉ tạo đề xuất có kiểu**. Một bộ thực thi tất định chỉ chạy sau khi **đúng chủ thể có thẩm quyền** xác nhận.
- Phát biểu chính xác: **AI không được gây side effect vật chất.** Truy vấn tất định (mở bảng thu, tính lại số dư) chạy ngay, không cần nút xác nhận vô nghĩa.
- Khoản chi do thành viên đã xác thực ghi và xác nhận thì **có hiệu lực ngay**, kể cả khi người ghi không phải người ứng tiền. **Không bao giờ có trạng thái chờ chặn ở tầng sổ.**
- Nhưng **không được phát thu tiền dưới danh nghĩa người ứng tiền** khi họ chưa xác nhận (mục 8).
- Ghi riêng `recorded_by`, `paid_by/advancer`, `payer_acknowledgement`.

### Ba mức xác minh của dữ liệu AI

| Loại | Nghĩa | Dùng vào việc gì |
|---|---|---|
| `draft_items` | Món do model suy ra | Gỡ lỗi, xây từ vựng món Việt, học chủ động. **Không phải chuẩn đúng** |
| `confirmed_allocations` | Số tiền theo người đã được nhìn và xác nhận | Sổ chính thức |
| `verified_items` | Món người dùng đã trực tiếp xem hoặc sửa | Tập đánh giá có nhãn |

Mỗi khoản chi mang cờ `verification_scope`: `totals_only` | `items_reviewed`.

**Lý do:** bấm "Đúng rồi" trên màn chỉ hiện *"Hà 82k"* **không** xác nhận *"trà sữa ô long 42k là của Hà"*. Dùng món do model sinh làm chuẩn chấm điểm chính model đó là tự chấm bài mình bằng đáp án của mình.

Nếu người dùng sửa trực tiếp tổng của một người khiến chi tiết món không còn khớp, drill-down phải được đánh dấu **"giải thích cũ"** hoặc tính lại — không được tiếp tục trình bày như bằng chứng đúng.

**Dữ liệu hoá đơn KHÔNG phải dữ liệu huấn luyện cho nhận diện món qua video** (thiếu nhãn thị giác). Nó chỉ cho từ vựng và tiên nghiệm.

---

## 4. Tính đúng của tiền

- Tiền lưu dạng **số nguyên đồng**. Không bao giờ dùng số thực.
- **Bất biến bắt buộc:** tổng các phần chia = đúng tổng khoản chi. Không ngoại lệ. Có test tự động. Bất biến số học phải đạt **100%**.
- Phần dư: **phương pháp phần dư lớn nhất**; người ứng tiền thắng tie-break **nếu họ thuộc tập tham gia**. Nếu người ứng tiền không tham gia khoản chi thì **không được tự tạo một phần cho họ**; đường lui là thứ tự ổn định theo ID người tham gia. Quy tắc phải **hiện ra cho người dùng thấy**.
- Phí/VAT/ship: mặc định phân bổ theo tỉ lệ tạm tính của từng người; có tuỳ chọn chia đều.
- Giảm giá chung: theo tỉ lệ. Giảm giá gắn với một món: trừ vào món đó.
- **V1 chỉ VND.**
- `WriteOff` là sự kiện riêng có kiểm toán. **Chỉ chủ nợ của đúng khoản phải thu đó** được miễn. Người tổ chức không được miễn thay Hà.
- Hoàn tiền: `CreditAdjustment` tham chiếu khoản chi gốc, từ đó sinh nghĩa vụ ngược. **Không** tạo nghĩa vụ ngược trôi nổi không giải thích được nguồn. Không sửa lịch sử.
- Sổ là nguồn sự thật; số dư là kết quả tính lại được (có thể cache để UI nhanh, nhưng luôn tái tạo được).
- Sửa khoản chi tạo **phiên bản mới**; khoản sai bị vô hiệu bằng sự kiện kiểm toán, không xoá âm thầm.

---

## 5. Luồng triệu hồi và hợp đồng kỹ năng

### 5.1 Ràng buộc cốt tử

- Mọi bài đăng là một `SkillInvocation` hoặc câu trả lời cho một invocation đang mở.
- **Không có primitive nhắn tin tự do.**
- Bot **không đọc thụ động cả luồng**. Mỗi lần gọi có một *context snapshot* tường minh.
- Không cần hiện diện realtime, trạng thái đang gõ, hay đã xem.
- **Vẫn cần kiểm duyệt** — đây là bề mặt nội dung do người dùng tạo, dùng chung.
- Trần token, số lần hỏi lại, thời gian, số tool call. **Không có bộ nhớ chung của nhóm theo mặc định.**

### 5.2 Bot là bộ định tuyến, không phải UI duy nhất

Kỹ năng tiền vẫn cần thẻ nháp riêng, bảng thu tiền riêng, trang khách riêng. **Ép mọi trạng thái vào bong bóng chat sẽ làm UX tệ hơn.**

Cấp app → hộp thư việc cần làm. Cấp nhóm → luồng invocation. Trong kỹ năng tiền → bảng thu tiền là mặt làm việc trung tâm.

### 5.3 Affordance thay vì ô nhập trống

Luồng mở ra hiện **các chip sinh từ capability registry** (không do model tự nghĩ), phụ thuộc vai trò và quyền. Gõ tiếng Việt tự do là đường cho người thạo.

Ba loại chip **khác nhau về bản chất**:
- Gọi kỹ năng AI — ví dụ `Chia tiền`
- **Truy vấn tất định, không gọi model** — ví dụ `Xem tiến độ đợt thu`
- Mở luồng có cấu trúc — chỉ gọi AI nếu người dùng gõ câu tự nhiên

Chip **mở màn review hoặc mặt làm việc, không gây side effect ngay**.

⚠️ Không được có chip *"Xem ai chưa gửi"* trả danh sách công khai trong luồng nhóm — đó chính là hành vi bêu tên đã bị cấm. Phải là `Xem tiến độ đợt thu`, mở riêng cho người có quyền.

### 5.4 Hợp đồng kỹ năng (bắt buộc, kể cả khi v1 chỉ có một kỹ năng)

`skill_id` · `version` · intent được hỗ trợ · input schema và loại attachment · `context_manifest` (dữ liệu được đọc, mục đích, snapshot, mức nhạy cảm) · `visibility_policy` · output schema + renderer · danh sách action được đề xuất kèm mức rủi ro · **ai có quyền xác nhận từng action** ("một người đã bấm" không tự động đủ quyền) · invariants và validator độc lập với model · chính sách side effect, idempotency, audit, rollback · trần chi phí, timeout, retry, fallback · quy tắc từ chối · **eval set và cổng phát hành riêng cho từng kỹ năng**.

### 5.5 Trung thực về năng lực

Bot chủ động hiện: việc hiện làm được · vài mẫu câu · việc chưa hỗ trợ · cách gửi yêu cầu tính năng.

Từ chối đúng cách:
> *"Hiện tôi chưa thể gợi ý quán đủ chính xác. Nếu bạn muốn, bạn có thể gửi một tín hiệu ẩn danh cho nhóm sản phẩm. Điều này không có nghĩa tính năng chắc chắn sẽ được xây."*

**Không có đường lui bí mật sang một LLM đa dụng để "cố trả lời".**

### 5.6 Vòng đời — ba thực thể tách biệt

```
Invocation:  queued → running ↔ waiting_for_user → succeeded | failed | cancelled | expired
Proposal:    draft → pending_confirmation → confirmed | rejected | superseded | expired | conflicted
ActionItem:  open → completed | cancelled | expired | declined     (do domain sinh ra tất định)
```

Invocation **không** chứa `draft_ready`/`confirmed` — đó là trạng thái của Proposal. Một invocation tiền có thể `succeeded` ngay sau khi tạo `ExpenseDraft`, trong khi proposal vẫn đang chờ xác nhận.

### 5.7 Đồng thời — điều kiện tiên quyết theo phiên bản

- Mọi `AnswerEvent` tham chiếu `proposal_version`.
- Answer đầu tiên tạo version mới. Answer đến từ version cũ bị đánh dấu `stale_conflict`.
- Hệ thống hiện cả hai và yêu cầu người có quyền chọn hoặc tạo bản kết hợp. **Không giới hạn số lần hỏi lại**; chưa giải quyết được thì chuyển `conflicted`, **không tự đoán**.
- ❌ Không dùng "cửa sổ xung đột ngắn". Tính đúng không được phụ thuộc hai người trả lời cách nhau mấy giây.
- Xác nhận cũ chỉ mất hiệu lực khi **thay đổi vật chất** (tổng, người ứng tiền, người tham gia, phân bổ, người nhận). Sửa chính tả không ép xác nhận lại.
- Người khác gửi `SuggestionEvent` về phần của **chính họ** — không tự đổi proposal.

**Người giải quyết xung đột theo từng loại field:**

| Loại xung đột | Ai quyết |
|---|---|
| Danh tính người ứng tiền / việc đã ứng tiền | Người ứng tiền |
| Nội dung hoá đơn | Người gọi (sửa nguồn) |
| Phân bổ bị phản đối | Người bị ảnh hưởng gửi SuggestionEvent → người gọi/người ứng tiền tạo proposal mới |
| Người gọi và người ứng tiền vẫn bất đồng | **Không publish.** Chuyển dispute hoặc huỷ |

Người giải quyết **chỉ thấy diff theo field** và phần nội dung họ được phép xem.

---

## 6. Mô hình dữ liệu — danh sách thực thể

Danh sách hợp nhất. Chi tiết ngữ nghĩa và máy trạng thái nằm ở các mục tương ứng.

### 6.1 Nhóm và danh tính *(mục 7)*

| Thực thể | Vai trò | Ghi chú then chốt |
|---|---|---|
| `Account` | Người đã đăng nhập | Cần account linking + recovery, nếu không một người thành hai sổ |
| `PersonStub` | "Hà" do người ghi tạo, chưa chắc có tài khoản | **Không bao giờ merge theo tên** |
| `PersonStubClaim` | Yêu cầu nhận `PersonStub` về một `Account` | Vòng đời riêng; chặn mọi quyền tài chính khi chưa `finalized` |
| `Membership` | Vai trò của Account/PersonStub trong một nhóm | `joined_at`, `left_at`, vai trò, biệt danh |
| `GuestCapability` | Quyền xem/báo trạng thái qua link | Phủ **một tập nghĩa vụ bất biến** của đúng một người gửi |
| `Group` | Nhóm người ổn định | |
| `EphemeralWorkspace` | Không gian riêng của lần dùng đầu | **ID ổn định**; lưu nhóm là *gắn*, không phải *chuyển* |
| `Context` | Chu kỳ sinh hoạt hoặc buổi/chuyến | **Tự sinh.** Người dùng chỉ thấy chữ "Chu kỳ / Buổi / Chuyến", không bao giờ thấy chữ `Context`. Một khoản chi thuộc đúng một context; một context có nhiều đợt thu |

### 6.2 Trợ lý *(mục 5)*

`SkillDefinition` (capability registry — sinh ra chip, không do model tự nghĩ) · `SkillInvocation` · `AnswerEvent` (tham chiếu `proposal_version`) · `SuggestionEvent` (góp ý về phần của chính mình, không tự đổi đề xuất) · `SharedInvocationSummary` (bản dẫn xuất đã che, audience snapshot **của chính nó**) · `UnsupportedIntentSignal` (chỉ lưu sau khi người dùng chủ động gửi).

### 6.3 Khoản chi *(mục 3, 4)*

| Thực thể | Ghi chú |
|---|---|
| `ExpenseDraft` + `DraftItem` | Model suy ra. **Bằng chứng chưa xác minh, không phải chuẩn đúng** |
| `ExpenseProposal` | Có `version`; vòng đời riêng, gồm `conflicted` |
| `ExpenseVersion` | Sửa tạo bản mới, **không ghi đè** |
| `ConfirmedAllocation` | Số tiền theo người đã được nhìn và xác nhận → **sổ chính thức** |
| `VerifiedItem` | Món người dùng trực tiếp xem/sửa → **tập đánh giá có nhãn** |
| `CreditAdjustment` | Hoàn tiền; tham chiếu khoản chi gốc |
| `WriteOff` | Miễn nợ; **chỉ chủ nợ của đúng khoản phải thu đó** |

Trường bắt buộc trên khoản chi: `recorded_by` · `paid_by/advancer` · `payer_acknowledgement` · `verification_scope` (`totals_only` \| `items_reviewed`) · phí/VAT/ship/giảm giá.

### 6.4 Thu tiền *(mục 8)*

`CollectionBatch` · `CollectionObligation` (một cạnh `sender → recipient`, có `due_at` **riêng**) · `CollectionEnvelope` (theo cặp `(batch, sender)`) · `GuestLink` (vòng đời riêng `active|revoked|expired|rotated`) · `PaymentReport` và `ReceiptConfirmation` (**event có số tiền**, tham chiếu từng nghĩa vụ — trạng thái nghĩa vụ **suy ra** từ tổng đã xác nhận) · `Dispute` (`open → accepted | rejected | withdrawn | resolved`) · `OffsetProposal` · `Settlement` · `PromisedFor`.

### 6.5 Tài khoản nhận tiền *(mục 7.4)*

`BankRecipient` · `BankRecipientAuthorization` (`account_id` + `claim_id/context` + `authorized_at` — provenance này là thứ giới hạn phạm vi đình chỉ khi có khiếu nại) · `BankRecipientSnapshot` (đóng băng trong phiên bản batch).

### 6.6 Điều phối, kiểm toán, an toàn

`ActionItem` (do domain sinh tất định; **LLM không bao giờ tự viết**) · `AuditEvent` · `IntegrityIncident` · `AccountCompromiseIncident` · `SettlementIntegrityIncident` · `ModerationReport` (`submitted → reviewing → removed | retained | escalated`) · `AttachmentAsset` + bảng **data-lineage** (blob, thumbnail, text OCR, input gửi model, log, cache, request ID và thời hạn lưu của nhà cung cấp) · `EvidenceHold` (`started_at`, lý do, reviewer, `expires_at`, **không tự gia hạn**).

### 6.7 Mô hình tương lai — KHÔNG chạy migration ở v1

`RecurringRule` (`active ↔ paused → archived`) và `RecurringOccurrence` (`scheduled → draft_generated → confirmed | skipped | expired`, giữ `rule_version`).

Tách hai thực thể này là bắt buộc về mặt thiết kế: nếu bản thân quy tắc đi từ `active` sang `confirmed` thì sau kỳ đầu tiên không còn gì để sinh kỳ tiếp theo. Nhưng **"thiết kế được đường mở rộng" khác "deploy một schema chết"** — chỉ triển khai sau cổng ở mục 18.

### 6.8 Bất biến xuyên suốt

1. Tổng các `ConfirmedAllocation` = đúng tổng khoản chi. Không ngoại lệ.
2. Tiền là **số nguyên đồng**. Không có số thực ở bất kỳ đâu.
3. Số dư luôn tính lại được từ sổ; bản cache không bao giờ là nguồn sự thật.
4. Mức hiển thị của output ≤ mức nhạy cảm nhất của input, trừ khi đã che **và** có chấp thuận.
5. Mọi thay đổi vật chất sau `published_at` cần chấp thuận của **tất cả** các bên bị ảnh hưởng.
6. Không có capability nào phủ nhiều hơn một tập nghĩa vụ bất biến của đúng một người gửi.
7. `completed` chỉ do domain transition tạo ra — không có nút "đánh dấu xong" tuỳ ý.

---

## 7. Danh tính

### 7.1 Bốn khái niệm tách biệt

| | Nghĩa |
|---|---|
| `Account` | Người đã đăng nhập |
| `PersonStub` | "Hà" do người ghi tạo ra, chưa chắc có tài khoản |
| `Membership` | Vai trò của một Account/PersonStub trong một nhóm |
| `GuestCapability` | Quyền xem/báo trạng thái của **đúng một tập nghĩa vụ**, qua link |

### 7.2 Đăng nhập tiến triển

- Tạo nháp được **trước** khi đăng nhập.
- Bắt buộc đăng nhập trước hành vi có **tác động ra ngoài**: ghi sổ trên server, tạo link, publish đợt thu, lưu nhóm.
- V1 dùng Google/Apple; email magic link là đường lui. **Không dùng SMS OTP mặc định** (tốn tiền, tạo ma sát).
- Số điện thoại chỉ là thuộc tính tuỳ chọn, có chấp thuận.
- **Cần account linking và recovery** — đăng nhập Apple hôm nay, Google ngày mai mà tạo hai tài khoản thì sổ sẽ tách đôi một người.
- **Không bao giờ merge theo tên hay biệt danh.**

### 7.3 Vòng đời claim PersonStub

```
requested → pending_verification → finalized | rejected
pending_verification | finalized → challenged → under_review
under_review → finalized | rejected | rolled_back
```

Trong `pending_verification` và `challenged/under_review`, claimant **KHÔNG** được: xem lịch sử nghĩa vụ cũ · đặt BankRecipient · acknowledge thay người ứng tiền · publish đợt thu · xem artifact lịch sử.

*(Rollback sau khi kẻ tấn công đã xem SettlementView hoặc đặt tài khoản nhận là quá muộn. Chặn trước, không sửa sau.)*

Yêu cầu claim: claimant có tài khoản đã xác thực · claim bind với Group + PersonStub + version · cần capability chỉ định đúng người **hoặc** bằng chứng liên tục từ guest capability cũ · nếu dùng phê duyệt thì phải là **người đã tạo/mời PersonStub đó** hoặc vai trò được uỷ quyền, **không phải thành viên bất kỳ** · thông báo cho các bên liên quan sau claim · có cửa sổ khiếu nại và rollback bằng sự kiện kiểm toán · chặn một tài khoản claim nhiều PersonStub mâu thuẫn · xử lý hai tài khoản cùng claim · **khôi phục tài khoản không được tạo đường chiếm lại PersonStub**.

**Người phán quyết khiếu nại: phía nền tảng (moderator), có SLA và kiểm toán.** Không được là thành viên nhóm — chính một thành viên có thể là kẻ tấn công. Không được là claimant hay challenger.

Moderator **không cần chứng minh ai là người thật**; họ đánh giá bằng chứng có đủ để duy trì binding hay không. **Không đủ bằng chứng thì fail closed** (reject hoặc rollback).

→ **Hệ quả kinh doanh:** bắt buộc có bộ phận hỗ trợ/kiểm duyệt **ngay từ ngày đầu**. Đây là chi phí thật.

### 7.4 Bốn mức bảo đảm — không bao giờ gom thành một cờ `valid=true`

1. `AccountAuthenticated` — chỉ chứng minh ai đó kiểm soát ô đăng nhập
2. `PersonStubClaimFinalized`
3. `BankRecipientConfirmedByRecipient`
4. `BankAccountOwnerVerified` — **chỉ được dùng tên này nếu thực sự có nguồn xác minh chủ tài khoản**

Không có nguồn xác minh → **cấm** dùng chữ "đã xác minh chủ sở hữu". Chỉ được nói "tài khoản do người nhận đã xác nhận", và **luôn nhắc người chuyển đối chiếu tên chủ tài khoản do chính app ngân hàng hiển thị** — đó là lớp kiểm tra cuối cùng ta không kiểm soát nhưng phải tận dụng.

Thêm/đổi BankRecipient: **xác thực lại tại chỗ**, ghi kiểm toán, thông báo các bên.

`BankRecipientAuthorization → account_id + claim_id/context + authorized_at`

### 7.5 Ba tầng kích hoạt (đo riêng, không gộp)

- `solo_value` — người tổ chức hoàn tất một invocation riêng tư
- `transactional_group` — khách thanh toán qua capability
- `collaborative_group` — từ hai tài khoản trở lên dùng invocation chung

⚠️ Link mở nhiều **không** chứng minh trợ lý dùng chung được chấp nhận. Người tổ chức quay lại **không** chứng minh thành viên khác muốn tham gia. Thành viên claim tài khoản nhưng không gọi bot **chưa** phải retention cộng tác.

---

## 8. Thu tiền

### 8.1 Đơn vị là đợt thu

Nếu mỗi lần mua bó rau 35k lại phát một link đòi tiền thì app thành máy spam. Một đợt thu gom được: một hoá đơn lẻ / một buổi đi chơi / một tuần tiền chợ / một chu kỳ sinh hoạt.

```
CollectionBatch: accruing → frozen → published → collecting → completed | closed_with_exceptions | cancelled
```

- Chỉ batch `accruing` nhận thêm khoản chi tự do.
- Sau `frozen`, phân bổ cố định.
- Sau `published`, khoản chi mới đi vào **batch bổ sung**; hoặc tạo bản sửa cần chấp thuận.
- UI *"Cộng vào đợt đang mở"* **chỉ liệt kê batch đang `accruing`**.
- `completed` chỉ khi mọi nghĩa vụ đang hiệu lực đã kết thúc. `closed_with_exceptions` cho batch có miễn nợ, tranh chấp, hoặc nghĩa vụ bị huỷ.

### 8.2 Nghĩa vụ và phong bì

- Một `CollectionObligation` là **một cạnh duy nhất** `sender → recipient`, kèm số tiền, nguồn phân bổ, snapshot tài khoản nhận, và **`due_at` riêng**.
- Các khoản cùng cặp `sender → recipient` trong một batch được cộng lại thành một nghĩa vụ. **Không tự bù trừ giữa các recipient khác nhau.**
- `CollectionEnvelope` theo cặp `(batch, sender)`. **Một capability phủ một tập nghĩa vụ bất biến của đúng một sender trong đúng một phiên bản batch.**
- Một khách mở **một link**, thấy nhiều khối thanh toán — nhưng mỗi khối là một nghĩa vụ độc lập.
- `PaymentReport` và `ReceiptConfirmation` là **event có số tiền**, tham chiếu **từng nghĩa vụ**. Trạng thái nghĩa vụ được **suy ra từ tổng số tiền đã xác nhận**, không phải một enum.
- Mỗi người nhận tự xác nhận phần mình. **Tranh chấp với Hà không chặn khoản gửi Nam.**
- `GuestLink` có vòng đời riêng: `active | revoked | expired | rotated` — link hết hạn **không** làm nghĩa vụ biến mất.

### 8.3 Ba cổng trước khi publish

| Cổng | Nội dung |
|---|---|
| 1 | Người gọi xác nhận `ExpenseProposal` → khoản chi vào sổ, kèm provenance |
| 2 | **Người ứng tiền acknowledge** — bắt buộc trước khi phát thu tiền dưới danh nghĩa họ |
| 3 | Publish đợt thu — cần đủ (a) đã ack, (b) `BankRecipientSnapshot` hợp lệ, (c) đã chọn cách giao |

**Cổng 1 không thay thế cổng 2.** Nếu không, một thành viên xấu có thể mượn danh người khác để đi thu tiền.

`AdvancerApprovalCapability`: link mục đích đơn nhất gửi đúng người ứng tiền — *"Hà ghi rằng bạn đã ứng 320k cho bữa lẩu. Đúng không?"* Có hạn dùng, thu hồi được, phạm vi chỉ đúng việc đó. **Không được dùng để đặt tài khoản nhận tiền** — muốn nhận tiền phải có tài khoản đã xác thực.

> Phát biểu đúng: **"Người chỉ cầm bearer link không thể một mình đổi nơi nhận tiền."**
> ❌ Không phải "không bao giờ chuyển tiền cho kẻ xấu".

### 8.4 Một người nhận chưa sẵn sàng

Trước khi freeze, người tạo đợt thu **phải chọn tường minh**: chờ tất cả người nhận sẵn sàng, **hoặc** tách các nghĩa vụ chưa sẵn sàng sang batch `blocked_recipient_setup`. Nghĩa vụ bị chặn **không bao giờ được âm thầm thêm vào phong bì đã publish**.

### 8.5 Giao link

- **Chỉ có link cá nhân hoá cho từng người.**
- **Không** có "Copy tất cả", **không** xuất gói, **không** chia sẻ hàng loạt.
- Mỗi lần chia sẻ một capability, kèm câu rõ: *"Link này dành cho Hà; bất kỳ ai có link đều xem được phần của Hà."*
- Không có trạng thái "đã giao". Chỉ đo `frozen_at` · `capability_exposed_at` (người dùng copy hoặc mở Share Sheet — từ đây coi như link **có thể** đã thoát khỏi app) · `first_opened_at`.
- **Rủi ro còn lại được ghi nhận thẳng:** người tổ chức vẫn có thể tự copy từng link rồi dán chung vào group chat, và khi đó thông tin lộ. App **không** cung cấp affordance giúp làm hàng loạt, và **không tuyên bố phát hiện được** hành vi ngoài app — hệ thống không thể biết.

### 8.6 Trang cho khách

Câu chữ **không được giả định** người mở link đúng là người được chỉ định:

> *"Nam đã ghi phần của Hà trong bữa lẩu là 82.000đ."*
> `[Đúng, xem cách chuyển]` · `[Số tiền không đúng]` · `[Tôi không phải Hà]`

- Token riêng từng phong bì, entropy cao, có hạn, thu hồi được, chỉ mở đúng nghĩa vụ của người đó.
- **Không lộ số dư hay lịch sử nhóm.** Khách **không bao giờ** thấy luồng invocation.
- Link preview dùng metadata trung tính, không chứa tên và số tiền.
- Giới hạn tần suất báo chuyển và phản đối.
- `Tôi đã chuyển` chỉ là tự khai, **không bao giờ tự đóng khoản**.
- **Không dùng OTP cho khách ở v1** — sẽ phá vòng lan truyền. Người nhận tiền vẫn là chốt chặn cuối.
- **Không** nhận ảnh chuyển khoản làm bằng chứng mặc định.
- ⚠️ **Người ta thường mở link trên chính chiếc điện thoại đang dùng** — lúc đó không có máy thứ hai để quét QR. Bắt buộc có: copy số tài khoản/số tiền/nội dung, deep link mở app ngân hàng, lưu ảnh QR.

### 8.7 Tiến độ

Đếm theo **lượt chuyển**: *"3/5 lượt chuyển hoàn tất"*. Phụ mới đếm theo người: *"2/4 người đã xong toàn bộ"*. Chỉ đếm người sẽ sai khi một người phải chuyển cho hai người nhận. Người ứng tiền không nằm trong mẫu số nếu họ không phải chuyển đi đâu.

### 8.8 Bù trừ

- Số dư toàn nhóm **luôn** hiển thị dạng đã bù trừ.
- Đợt thu **không bao giờ** tự bù trừ xuyên đợt.
- **Trước `published_at`:** sửa, gộp, bù trừ tự do — chưa có kỳ vọng xã hội nào bị thay đổi.
- **Sau `published_at`:** mọi thay đổi người trả/người nhận/số tiền tạo bản sửa và **cần chấp thuận của tất cả các bên bị ảnh hưởng**.
- Gợi ý "trả gọn nhất" (A nợ B, B nợ C → A trả thẳng C) **không phải chỉ là tối ưu thuật toán, mà là thay đổi thoả thuận xã hội**. Chỉ áp dụng khi mọi người bị đổi đối tác đều đồng ý. Có bản ghi bù trừ riêng để kiểm toán.

```
Offset: draft → proposed(published) → accepted_by_all → applied
                                   ↘ rejected | expired
```

### 8.9 Đợt thu bị bỏ dở

Ba khái niệm **khác nhau**: `stale` (nhãn UI suy ra từ thời gian, hoạt động lại được) · `archived` (ẩn khỏi hộp thư, **không** đổi sổ) · `abandoned`/`closed_with_exceptions` (kết quả nghiệp vụ có kiểm toán).

- `stale` khi quá `due_at` 14 ngày **và** không có hoạt động có ý nghĩa trong 7 ngày.
- Khi stale: dừng nhắc tự động, gom vào một thẻ "Đợt lâu chưa xử lý".
- Sau 30 ngày không hoạt động: thu gọn khỏi danh sách chính, **không tự lưu trữ tài chính, không tự miễn nợ**.
- Bất kỳ thao tác nào cũng làm hết stale.
- Màn xử lý: `Nhắc lại` · `Hẹn xem lại` · `Đóng đợt với khoản còn mở` · `Miễn phần này`.
- ⚠️ **Chống làm đẹp số:** đợt bị bỏ dở **sau khi publish vẫn nằm trong mẫu số** kết quả thu tiền. Chỉ đợt bị huỷ **trước** `capability_exposed_at` mới được loại. Mọi chuyển đổi sang miễn nợ/bỏ dở phải có actor, lý do, thời điểm, chủ nợ liên quan trong nhật ký kiểm toán.

---

## 9. Bảng phân quyền

**Spec triển khai phải có MỘT bảng duy nhất, mọi API và mọi ActionItem tham chiếu về đó.** Quyền rải rác chính là cách "confused deputy" quay lại. Bảng phủ 11 nhóm hành động: tạo invocation riêng/chung · xem input, clarification, proposal · xác nhận ExpenseProposal · acknowledge vai trò người ứng tiền · thêm/đổi BankRecipient · freeze/publish/revoke batch và envelope · giải quyết từng loại xung đột · yêu cầu và chia sẻ bằng chứng · mời, phê duyệt, khiếu nại claim PersonStub · gỡ nội dung hoặc thành viên · gắn workspace vào Group.

### 9.1 Freeze / Publish / Revoke

| Hành động | Ai |
|---|---|
| **Freeze** | Chỉ `batch_owner` |
| **Publish** | `batch_owner`, và chỉ khi **mọi** người nhận trong batch đủ điều kiện |
| **RevokeCapability** *(an toàn, đơn phương)* | `batch_owner` (cả batch) · **người nhận** (mọi phong bì chứa tài khoản của mình) · **người gửi** (capability của chính mình khi nghi lộ) |
| **CancelOrAmendObligation** *(nghiệp vụ)* | Sau publish vẫn theo đúng quy tắc chấp thuận và tạo version |

**Nguyên tắc:** ai có dữ liệu hoặc rủi ro trong một capability thì người đó được rút nó về.

`batch_owner` **không** được đơn phương: huỷ nghĩa vụ · xoá PaymentReport/ReceiptConfirmation · đóng tranh chấp · đổi số tiền sau publication.

Khi người nhận thu hồi một phong bì nhiều người nhận: **thu hồi toàn bộ capability đó** rồi tạo version mới cho các nghĩa vụ không bị ảnh hưởng. **Không âm thầm đổi nội dung phía sau cùng một URL.**

Nếu `batch_owner` mất khả năng hoạt động: trước publication cho chuyển `batch_owner` tường minh (người nhận quyền phải chấp thuận, có kiểm toán), hoặc huỷ rồi tạo batch mới. **Group admin không tự kế thừa quyền tài chính chỉ vì là admin.**

### 9.2 Group admin — hậu cần, không phải quyền lực tài chính

**Được:** quản lý thành viên và lời mời · gỡ nội dung do chính mình tải lên · loại thành viên khỏi nhóm · chuyển quyền admin. *(Quản lý quy tắc định kỳ thuộc giai đoạn tương lai.)*

**Không được:** sửa/vô hiệu bút toán của người khác · miễn nợ thay chủ nợ khác · xem invocation riêng tư của người khác · phán quyết danh tính · thêm/đổi BankRecipient của người khác · xoá lịch sử kiểm toán.

Loại một thành viên **không xoá** nghĩa vụ tài chính của họ hoặc với họ. Sau khi bị loại, người đó vẫn giữ `SettlementView` tối thiểu; admin không vì thế được xem thêm dữ liệu riêng của họ.

### 9.3 Khiếu nại danh tính — phạm vi đình chỉ

Khi claim bị `challenged`/`rolled_back`, **trong cùng một giao dịch cơ sở dữ liệu**: đình chỉ BankRecipient **được cấp quyền dựa trên đúng `claim_id` đó** · chặn batch/capability dùng binding đó · batch chưa publish quay về blocked · thu hồi capability chưa dùng · tạo `IntegrityIncident` · **ghi** thông báo vào transactional outbox.

*(Push/email chạy bất đồng bộ — không thể nằm trong transaction.)*

⚠️ **Không đóng băng toàn bộ tài khoản.** Một khiếu nại ác ý sẽ trở thành công cụ đánh sập tài khoản người khác. Chỉ `AccountCompromiseIncident` riêng mới được đình chỉ trên toàn tài khoản.

**Tiền đã chuyển trước khi có khiếu nại** — không được nói "dừng hướng dẫn thanh toán" như thể thu hồi được giao dịch ngân hàng:

| Tình huống | Xử lý |
|---|---|
| Mới có `PaymentReport`, chưa được xác nhận nhận | `payment_at_risk`: chặn tiến triển tự động, chuyển hỗ trợ thủ công, cảnh báo **riêng** cho người gửi và người nhận |
| Đã `receiver_confirmed`/`completed` | **Giữ nguyên toàn bộ sự kiện lịch sử**, gắn `SettlementIntegrityIncident`, **không tự mở lại nghĩa vụ**, và **tuyệt đối không yêu cầu người gửi trả lần nữa** |

**Đường vòng hợp lệ duy nhất khi danh tính bị tranh chấp:** tách nghĩa vụ **không liên quan** ra thu bình thường; nghĩa vụ liên quan chuyển `blocked_identity_dispute`; các bên tự xử lý ngoài app nhưng **app không chọn người nhận thay họ và không tự ghi `receiver_confirmed`**.

❌ **Người tạo đợt thu không được chuyển nghĩa vụ đang tranh chấp sang người nhận khác.** Đó là tự ý đổi chủ nợ — đúng thứ đã bị cấm ở phần rút gọn nợ. Áp lực vận hành không phải lý do chính đáng.

*(Thiết kế này cố tình khiến tốc độ phán quyết **không** là nút cổ chai của dòng tiền — vì áp lực vận hành sẽ đẩy tới phán quyết ẩu, mà phán quyết ẩu về danh tính thì tệ hơn chậm.)*

**Khi được minh oan:** không bật lại QR/link cũ một cách âm thầm. BankRecipient phải xác thực lại tại chỗ; batch tạo version mới và phát capability mới. **Chỉ nghĩa vụ chưa trả** mới nhận capability mới — khoản đã trả đang điều tra không được phát lại hướng dẫn thanh toán.

---

## 10. Hiển thị và quyền xem

### 10.1 Nguyên tắc chống rò rỉ ngữ cảnh

> **Output không bao giờ được có mức hiển thị rộng hơn input nhạy cảm nhất**, trừ khi đã che VÀ có chấp thuận.

Ba mức: `private_to_invoker` · `group_summary_private_details` (**mặc định**) · `group_visible`.

Hiển thị invocation **độc lập** với cách giao link. Đăng lệnh trong luồng nhóm **không** tự chuyển batch sang chế độ công khai.

### 10.2 Ma trận

| Thành phần | Mặc định |
|---|---|
| Sự kiện gọi bot (ai gọi, loại việc, thời điểm) | `group_summary` |
| Text người dùng gõ | Riêng tư với người gọi |
| Attachment (ảnh bill) | Riêng tư với người gọi. Mở rộng phải tường minh **và có cảnh báo** — bill hay chứa số tài khoản và số điện thoại |
| Câu hỏi lại của bot | Nội dung câu hỏi ở mức `group_summary`; câu trả lời riêng tư, trừ phần làm thay đổi phân bổ của người khác thì hiện cho đúng người bị ảnh hưởng |
| Output tóm tắt (tổng, số người, trạng thái) | `group_summary` |
| Output phân bổ từng người | Chỉ người có quyền |
| **Số tài khoản** | **Không bao giờ `group_visible`.** Chỉ trong `CollectionEnvelope` của đúng người phải chuyển |

Composer phải cảnh báo nếu nội dung đang gõ sẽ hiện cho cả nhóm. Không hiện thuật ngữ model hay điểm tin cậy dạng "73%" cho người dùng.

Chỗ AI không chắc phải thành **câu hỏi cụ thể**, không chỉ tô màu: *"Hà" là Hà Nguyễn hay Hà Trần?* · *82k của Nam đã gồm phí ship chưa?*

### 10.3 Declassification

- Invocation **riêng tư**: cả **sự kiện** cũng không hiện ra nhóm — nhóm không thấy dòng "X đã gọi bot".
- Là hành động tường minh của **chủ sở hữu field**, luôn tạo ra một **bản dẫn xuất đã che**. **Không bao giờ đổi ACL của bản gốc.**

### 10.4 Quyền xem lịch sử

Là **giao của ba điều kiện**: membership trong khoảng thời gian hợp lệ **và** object visibility cho phép **và** audience snapshot cho phép. *(Một invocation riêng tư không trở thành nhìn thấy được chỉ vì người xem là thành viên tại thời điểm đó.)*

- Thành viên mới: **không** xem lịch sử trước `joined_at`.
- Thành viên đã rời: không thấy invocation mới; chỉ giữ quyền đọc `SettlementView` của chính họ.
- Khách: chỉ thấy phong bì của mình. **Không bao giờ** thấy luồng nhóm.
- `SharedInvocationSummary` dùng audience snapshot **của chính summary**, không dùng timestamp của invocation nguồn.

**`SettlementView` tối thiểu** (cho nghĩa vụ ngoài khoảng membership): số tiền của họ · người nhận và hướng dẫn chuyển · nguồn tính ở mức đủ giải thích · các phiên bản đã làm đổi nghĩa vụ của họ · dispute và receipt events liên quan. **Không** lộ phân bổ người khác, bill gốc, hay clarification.

### 10.5 Xin bằng chứng khi tranh chấp

Người bị ghi phần phải có đường xin **bằng chứng đã che**: dòng món hoặc phép tính liên quan trực tiếp tới họ · trích đoạn bill đã che phần không liên quan · provenance và verification scope.

Nếu người tải lên không đồng ý chia sẻ thêm: dispute vẫn tồn tại, collection của nghĩa vụ đó **dừng**, và hệ thống **không được coi việc thiếu bằng chứng là người bị ghi phần đã sai**.

---

## 11. Vòng đời thành viên và promotion

### 11.1 Rời nhóm

**Không được bắt "tất toán xong mới được rời"** — một khoản tranh chấp là mắc kẹt vĩnh viễn.

1. Chốt ảnh chụp số dư tại `left_at`
2. Gỡ khỏi mọi quy tắc tương lai
3. Chuyển quyền quản trị / tài khoản nhận nếu cần
4. Tạo đợt thu cuối cho nghĩa vụ còn mở
5. **Chuyển trạng thái đã rời ngay**, không chờ thanh toán
6. Nghĩa vụ cũ vẫn tồn tại với thành viên đã lưu trữ
7. Dữ liệu hồ sơ không còn cần thiết phải xoá hoặc khử định danh

`Tất toán và rời` là nút tiện lợi, **không phải cổng chặn**.

**Chặn (block)** ngăn mời lại, ngăn nhắc tên, ngăn thông báo không cần thiết — nhưng **không xoá nghĩa vụ tài chính hợp lệ**. Hai người ghét nhau vẫn phải tất toán được.

### 11.2 Session-first → nhóm

- **Lần dùng đầu:** không gian riêng của người gọi (`EphemeralWorkspace` có **ID ổn định**). Vẫn là invocation, vẫn là bot, nhưng chỉ mình họ thấy. Không có luồng chung.
- Sau khi xác nhận khoản chi và chọn cách giao, app đề nghị lưu thành nhóm.
- **Hai lựa chọn độc lập:** `Đưa khoản chia vào sổ nhóm` · `Chia sẻ bản tóm tắt lần gọi bot`. Khoản chi có thể vào sổ nhóm trong khi prompt, ảnh bill và clarification vẫn riêng tư.
- **Không di chuyển dữ liệu.** Lưu nhóm chỉ là **gắn** context đó vào Group — không tạo lại Expense/Envelope/capability, nếu không link đã phát sẽ mất hiệu lực hoặc đẻ ra nghĩa vụ trùng.
- Invocation cũ **không** tự chuyển sang luồng chung; muốn chia sẻ thì tạo `SharedInvocationSummary` đã che.
- Người tạo thành `Membership` đã xác thực; các tên còn lại vẫn là `PersonStub`.
- ❌ Bỏ quy tắc "chỉ đề nghị lưu nhóm sau lần thứ hai" — không thực thi được khi chưa có mô hình danh tính và tên chỉ là chữ tự do.

**Ràng buộc giao dịch:** idempotency key do client tạo · ràng buộc duy nhất (một workspace không gắn được vào hai Group) · kiểm tra quyền lại **trong** transaction · danh sách Expense/Context attach phải **tường minh** · transactional outbox cho mời và thông báo · retry outbox không đẻ ra lời mời hay ActionItem trùng.

### 11.3 ActionItem

- Vòng đời nghiệp vụ: `open → completed | cancelled | expired | declined`. `completed` **chỉ do domain transition tạo** — không có nút "đánh dấu xong" tuỳ ý.
- Trạng thái trình bày tách riêng: `visible | snoozed_until | hidden`. **Không làm ActionItem tài chính biến mất khỏi tìm kiếm và kiểm toán.**
- Khoá dedupe: `(domain_object_type, domain_object_id, domain_version_or_occurrence, action_type, assigned_subject_id)`.
- Version mới sinh ActionItem mới → bản cũ phải `cancelled/superseded` **trong cùng transaction**.
- `assigned_subject_id` phải ổn định xuyên quá trình PersonStub được claim.
- **LLM không bao giờ tự viết ActionItem.**

Luồng nhóm và hộp thư là **hai projection trên cùng một ActionItem**, không phải hai hệ thống trạng thái. Hoàn tất ở đâu cũng cập nhật ngay ở chỗ kia.

---

## 12. Thông báo, an toàn, quyền của người gửi

### 12.1 Thông báo

Định tuyến theo `ActionItem.assigned_to`, **không** theo vai trò cố định. **Không có khái niệm "báo cả nhóm"** — nếu tất cả thật sự phải xác nhận thì tạo ActionItem riêng cho từng người.

Bốn mức ưu tiên (vì trần cứng có thể nuốt mất một xác nhận tiền quan trọng): bảo mật/toàn vẹn (**không** vào digest) · hành động tài chính (ưu tiên cao, tôn trọng giờ yên tĩnh trừ trường hợp bảo mật) · nhắc/tiến độ (dedupe + digest) · thông tin (bỏ được khi vượt trần).

Trần theo **người nhận** và **loại hành động**, không chỉ theo nhóm — một người ở nhiều nhóm vẫn có thể bị spam. Giờ yên tĩnh theo múi giờ người dùng. Nội dung trung tính trên màn hình khoá.

**Không có trạng thái "đã giao".** Chỉ đo `notification_requested → provider_accepted → opened`.

⚠️ **Khách không có kênh đẩy.** ActionItem giao cho khách vẫn tồn tại trong domain nhưng người tổ chức phải chia lại capability. **Đây là giới hạn đã thừa nhận, không được quảng cáo là đã giải quyết.**

→ Hệ quả: giả định *"nhắc tự động làm giảm sự ngại"* **chỉ kiểm chứng được với người đã cài app**. Với khách, giá trị của link là **thanh toán dễ và không phải cài app**, không phải được nhắc.

**Tuyệt đối cấm:** thông báo kiểu "X chưa chuyển tiền" gửi cho cả nhóm · bảng xếp hạng trả chậm · streak · màu đỏ bêu tên · thông báo công khai ai chưa gửi.

### 12.2 Quyền chủ động của người gửi

`Tôi sẽ gửi vào ngày…` (`promised_for` là **event riêng**, tạm ngừng nhắc đến ngày đã chọn nhưng **không** coi là đã thanh toán) · `Nhắc lại cho tôi sau` · `Tạm dừng nhắc` · `Số tiền không đúng`.

`promised_for`, dispute, stale tạm ngừng **đúng loại nhắc tương ứng** nhưng không tắt các xác nhận tiền quan trọng.

### 12.3 An toàn tệp và nội dung

**Kỹ thuật:** MIME sniffing · giải mã trong sandbox · giới hạn kích thước **sau** giải nén · quét mã độc · gỡ EXIF · bảng data-lineage (blob, thumbnail, text OCR, input gửi model, log, cache, request ID và thời hạn lưu của nhà cung cấp).

**Chống prompt injection:** tool allowlist · output của model **luôn** bị coi là không tin cậy · validator độc lập · eval riêng cho prompt injection. ⚠️ "Coi attachment là dữ liệu" là **nguyên tắc viết prompt, không phải biện pháp phòng thủ**. Đây là phòng thủ nhiều lớp — **không được mô tả là "đã chống được injection"**.

**Vận hành:** chính sách nội dung và tiêu chí gỡ/leo thang · workflow `submitted → reviewing → removed | retained | escalated` · **người trực thật, không chỉ SLA trên giấy** *(nút báo cáo không có người xử lý chỉ là nút trang trí)* · quyền kháng nghị · kiểm tra yêu cầu hiện hành của App Store/Google Play cho bề mặt nội dung do người dùng tạo · thu hồi bản dẫn xuất khi nguồn bị gỡ.

**Xoá attachment:** xoá blob và mọi bản dẫn xuất chứa PII; proposal chưa xác nhận bị vô hiệu; sổ đã xác nhận giữ record tối thiểu với tombstone *"nguồn đã bị xoá"*, **không giữ ảnh**.

**Ngoại lệ giữ bằng chứng — có kiểm soát chống lạm dụng** *(một người có thể mở dispute giả chỉ để giữ ảnh của người khác)*: dispute phải liên kết nghĩa vụ thật và người mở có standing · hold có `started_at`, lý do, reviewer, `expires_at` · **không tự gia hạn** chỉ vì tạo dispute mới · chỉ giữ phần tối thiểu, khoá chặt truy cập · người yêu cầu xoá được thông báo và có đường phản đối · hết hạn thì xoá tự động.

Ghi rõ SLA xoá cho object store, cache, backup, nhà cung cấp model. **Không hứa xoá ngay ở phía nhà cung cấp nếu hợp đồng của họ không cho.** Ảnh đã từng `group_visible` thì **không đảo ngược được** — chỉ thu hồi được quyền truy cập trong hệ thống.

### 12.4 Rủi ro quan hệ — guardrail có quyền phủ quyết

Sản phẩm có thể tăng tốc độ thu tiền bằng cách **tăng áp lực xã hội**. Đó không phải thành công.

Phỏng vấn **riêng từng người gửi**, trước và sau chu kỳ (không hỏi trong nhóm, không hỏi trước mặt người tổ chức): Tôi có thấy bị thúc ép hoặc bị theo dõi hơn không? · Con số có dễ hiểu và công bằng hơn không? · Tôi có muốn lần sau tiếp tục nhận yêu cầu theo cách này không? · Lời nhắc làm tôi dễ xử lý hơn hay làm quan hệ khó chịu hơn?

Đo hành vi: tắt nhắc · chặn · phản đối · không mở link · báo không phải mình · phàn nàn riêng · rút khỏi lần dùng tiếp theo.

> **Thanh toán nhanh hơn nhưng người bị đòi khó chịu hơn vẫn là THẤT BẠI.**
> Lợi ích của người tổ chức **không được bù trừ** cho tổn hại nghiêm trọng đối với người cần gửi.

---

## 13. Giai đoạn 0 — kiểm chứng bằng người, TRƯỚC khi viết code

> **Không xây máy trạng thái trước khi kiểm chứng bằng người thật.**
> "Khó sửa sau" không phải lý do xây nền móng cho một sản phẩm có thể không nên tồn tại. Giai đoạn 0 chỉ dùng công cụ nghiên cứu dùng một lần, cộng threat model và bản phác schema trên giấy.

### 13.1 Giao thức

- **Baseline trước:** quan sát trực tiếp một chu kỳ chi phí thật theo cách họ đang làm. **Không hỏi hồi tưởng** (recall bias). Baseline và concierge phải tương đương về số người, số tiền, độ phức tạp phân bổ, số người nhận.
- **Chu kỳ concierge:** người vận hành đứng **sau một giao diện giả lập**. Người tổ chức vẫn phải tự làm đúng những thao tác v1 đòi hỏi: nhập dữ liệu, chia sẻ, chủ động gửi lời nhắc. **Người vận hành không được tự nhắn và tự nhắc trực tiếp trong group chat** — app tương lai không có quyền đó với khách vô danh.
- Chuẩn hoá SLA, câu chữ, thời điểm và số lần nhắc. Mọi lần "linh hoạt giúp thêm" phải được ghi lại và **không được tính miễn phí vào hiệu quả sản phẩm**.
- **Gắn nhãn mọi thao tác của người vận hành:** `deterministic_automatable` · `model_plausible` · `human_judgment_required` · `out_of_contract_rescue`. Nếu phần lớn giá trị đến từ hai loại cuối → kết luận có thể là **dịch vụ vận hành, không phải phần mềm**.
- **Hai lane tách biệt:** lane kiểm chứng v1 (bot chỉ làm tiền, yêu cầu ngoài phạm vi bị từ chối và ghi `unsupported_intent`) và lane khám phá (có chấp thuận riêng; **dữ liệu lane này không được tính vào hiệu quả v1**).
- **Lấy mẫu tuần tự:** wave A 6 nhóm mỗi cohort để sửa giao thức → block 3 nhóm mỗi cohort → mở gate khi ≥10 nhóm trong một cohort **thực sự có cơ hội chi phí tiếp theo** → dừng tuyển khi hai block liên tiếp không sinh failure mode mới và hướng kết quả không còn đảo ngược.
- Gắn `protocol_version` cho từng nhóm. Dữ liệu trước và sau một thay đổi lớn không được gộp. *(Người vận hành sẽ giỏi dần — nếu không có SOP và version, cải thiện theo wave sẽ bị nhầm thành khác biệt cohort.)*

### 13.2 A/B cần chạy

- **Đường nhập:** text tiếng Việt · ảnh bill · form cấu trúc (**control bắt buộc**). Randomize thứ tự trên các bill tương đương hoặc dùng Latin square — **không** cho một người làm ba cách trên cùng một bill (lần đầu đã tiết lộ đáp án). Đo **thời gian tới phân bổ ĐÚNG**, không phải thời gian tới lúc có kết quả.
- **Chip so với gõ lệnh** — ý định của chủ sản phẩm không đòi người dùng phải gõ nếu một cái nút nhanh hơn.
- **Invocation riêng so với invocation chung.**
- **Thứ tự thông điệp:** `tầm nhìn rộng → năng lực tiền` so với `năng lực tiền → tầm nhìn rộng`. *(Không phải test xem có giữ RB-2 hay không; test cách diễn đạt ít gây hại nhất.)*

### 13.3 Cổng hành vi để được phép xây prototype

*(Chưa phải PMF)*

| Chỉ số | Ngưỡng |
|---|---|
| Nhóm có cơ hội hợp lệ tự khởi tạo lần dùng tiếp theo | `<4/10` → dừng hoặc đổi wedge · `4–5/10` → chưa được xây, chẩn đoán lại · `≥6/10` → được xây prototype tự phục vụ rẻ nhất · `≥7/10` kèm ≤20% phiên cần can thiệp "chỉ người mới làm được" → tín hiệu mạnh |
| Median thời gian chủ động của người tổ chức | Giảm ≥30% so với baseline |
| Lỗi sai người nhận hoặc sai số tiền nghiêm trọng | **0** |
| Trải nghiệm người cần gửi | Không xấu đi rõ rệt *(guardrail có quyền phủ quyết)* |
| Đường nhập | Ít nhất một đường nhanh hơn form cấu trúc về thời gian tới phân bổ đúng, không tăng lỗi vật chất |
| Hiểu đúng năng lực hiện tại sau onboarding | ≥80%. Không đạt → sửa lời hứa ra mắt |

⚠️ **Concierge là ước lượng thiên lệch theo từng chiều, không phải cận trên duy nhất.** Nó là cận **trên** cho khả năng hiểu câu mơ hồ, xử lý ngoại lệ, độ chính xác phân bổ. Nhưng là cận **dưới** cho niềm tin và quyền riêng tư (có người lạ đọc chi tiêu), tốc độ (phải chờ người), tính nhất quán và khả dụng 24/7, và mức sẵn lòng dùng (người dùng biết phía sau là con người).

⚠️ **Concierge có thể đang bán lao động miễn phí.** "Tự xin dùng lại" có thể nghĩa là họ thích có người làm hộ, không nghĩa là họ sẽ dùng app tự phục vụ. Một chu kỳ sau phải ép giao diện gần với sản phẩm thật và giới hạn người vận hành đúng các năng lực có thể tự động hoá.

⚠️ Tín hiệu "tự xin làm lần nữa" là **độ chính xác cao, độ bao phủ thấp** — chỉ có nghĩa khi: nhóm biết dịch vụ vẫn còn · thực sự phát sinh cơ hội chi phí hợp lệ · người tổ chức **chủ động** đưa khoản mới vào (không phải trả lời "có" khi được hỏi) · người vận hành không chăm sóc vượt mức sản phẩm tương lai.

### 13.4 Cổng OCR (nếu giữ đường ảnh bill)

**Gate A — 50 bill thật, đa dạng có chủ ý:** bill nhiệt rõ/mờ/lệch/nhàu · quán ăn, trà sữa, siêu thị nhỏ · ảnh camera và ảnh chụp màn hình/hoá đơn điện tử. **Không loại mẫu xấu sau khi đã đưa vào tập.**

**Cắt đường ảnh khỏi v1 nếu bất kỳ điều nào xảy ra:** độ chính xác tổng tiền <95% · ghép đúng dòng món–giá <85% · median từ chọn ảnh đến text đã làm sạch không nhanh hơn nhập tay ít nhất ~30% · có trường nhạy cảm đã đánh dấu mà bộ che bỏ sót · người dùng thường phải sửa hơn hai lỗi vật chất trên một bill.

**Gate B (nếu qua A):** chạy tập held-out lớn hơn trước phát hành; đo end-to-end **sau** thao tác sửa của người dùng; **không cho đường lui gửi ảnh gốc sang model để "cứu" độ chính xác**.

Fail → v1 chỉ còn text tiếng Việt và nhập tay. Đây là cắt đúng: ảnh bill là đường phụ, không phải wedge.

### 13.5 Đạo đức và rủi ro nghiên cứu

Mọi người bị quan sát phải biết và đồng ý — **kể cả việc có người thật đọc dữ liệu trong Wizard-of-Oz**. Ghi nhận thiên lệch chọn mẫu (chọn về các nhóm vốn dễ chịu với chia sẻ dữ liệu). VietQR do người vận hành tạo **vẫn có thể chuyển sai người** → quy trình hai bước đối chiếu người nhận, số tài khoản, số tiền, tên ngân hàng, kèm kế hoạch hoàn trả nếu nghiên cứu gây sai lệch.

**Chi phí người vận hành phải được đo như một biến kinh doanh:** phút xử lý mỗi đợt, số lần can thiệp, chi phí tương đương. Một concierge được yêu thích nhưng cần 15 phút lao động mỗi đợt **chứng minh pain nhưng đồng thời bác bỏ mô hình phần mềm biên lợi nhuận cao**.

**Giai đoạn 0 không rẻ chỉ vì không viết code** — vẫn cần tuyển nhóm, chi phí khuyến khích, người vận hành, quy trình chấp thuận, xử lý dữ liệu, kiểm soát tiền thật.

### 13.6 Thời gian

**Ngân sách 4 tháng, có thể kéo 5–6.** *(2 tháng chỉ khả thi khi dừng sớm hoặc với cohort có chi phí hàng tuần.)*

Với nhóm ở trọ: baseline tháng 0 → concierge tháng 1 → cơ hội quay lại tháng 2, cộng tuyển nhóm, thời gian thu tiền, phỏng vấn, các block bổ sung ≈ 12–16 tuần nếu tuyển đúng thời điểm.

**Rút ngắn hợp lệ:** tuyển ngay trước ngày tiền nhà hoặc sự kiện đã lên lịch · chạy nhiều nhóm song song, tuyển cuốn chiếu · chạy hai cohort đồng thời · A/B đường nhập song song với chu kỳ thu tiền · **cổng dừng sớm** nếu các nhóm đầu không có pain, xuất hiện tổn hại quan hệ, hoặc không ai muốn dùng lại · dùng chat cũ làm dữ liệu định tính bổ sung.

**Rút ngắn KHÔNG hợp lệ:** tạo khoản nợ giả · ép ba "chu kỳ" vào vài tuần · hỏi "bạn có dùng lại không?" thay cho quan sát lần dùng lại · dùng kết quả tiền chợ hàng tuần để suy ra retention tiền phòng · ưu tiên cohort đi chơi rồi lấy kết quả đó đại diện cho cohort ở trọ.

---

## 14. Kiến trúc và thứ tự xây

### 14.1 Stack

| Tầng | Chọn | Ghi chú |
|---|---|---|
| App | React Native + Expo, TypeScript | Một codebase iOS + Android. Cần Expo prebuild / dev client cho Share Extension — **không** phải managed thuần |
| Lõi dữ liệu | PostgreSQL | Tiền cần giao dịch toàn vẹn |
| API | FastAPI (Python 3.12+) | Cùng ngôn ngữ với tầng AI |
| Xử lý AI | Worker riêng + hàng đợi | Gọi model chậm và hay lỗi: chạy nền, thử lại, hạ cấp |
| Hiểu ngôn ngữ / ảnh | Interface nghiệp vụ mỏng + **một** adapter Gemini (paid tier) | **Không** model gateway đa nhà cung cấp ở v1. Prompt/schema/tên model tập trung một chỗ |
| Kiểm chứng | Validator số học **độc lập với nhà cung cấp** + eval tiếng Việt + canary khi đổi model | JSON schema chỉ đảm bảo **hình dạng** output, **không** đảm bảo tên người, số tiền, hay phép chia đúng |
| Ảnh | **Object storage riêng tư, KHÔNG CDN** | Bill là dữ liệu nhạy cảm. Cache CDN, log, và signed URL hết hạn sai làm việc xoá không thực hiện được thật. Dùng signed URL ngắn hạn |
| Thanh toán | Sinh VietQR | **Không giữ tiền, không làm ví** |
| Giám sát | Sentry + theo dõi riêng chất lượng AI | **Phải scrub PII khỏi Sentry và log AI** — che ảnh trước khi gửi model rồi rò số tài khoản qua error log thì vô nghĩa |

**Điều kiện nâng cấp lên gateway:** có nhà cung cấp thứ hai thật, hoặc sự cố ảnh hưởng cam kết dịch vụ, hoặc model trôi chất lượng lặp lại, hoặc yêu cầu pháp lý về nơi lưu dữ liệu.

**Job AI chạy nền** phải gắn `draft_version`, cancellation token, idempotency key. Kết quả chỉ được nhận nếu version hiện tại còn chờ — nếu không, một retry thành công muộn có thể ghi đè lên khoản chi người dùng đã nhập tay và xác nhận. Cần ngân sách độ trễ (mục tiêu 15 giây khó tương thích với retry không giới hạn).

**Đồng bộ ngoại tuyến:** `local_draft | pending_sync | synced | conflict`. **Không publish link trước khi server commit thành công.** Mọi sync và retry cần idempotency key.

### 14.2 Chi phí

Spec chỉ ghi **công thức** và **trần**:

```
Chi phí AI / nhóm hoạt động / tuần
= Σ( input_tokens × giá_input
   + output_tokens × giá_output
   + chi phí ảnh/OCR
   + chi phí retry và fallback )
```

Đơn vị là **mỗi lượt gọi**, bao gồm vòng hỏi lại và attachment (không phải mỗi khoản chi).

Trần phải là con số VND cụ thể hoặc tỉ lệ trên doanh thu mục tiêu, **quyết định trong bản kế hoạch triển khai**, kèm `verified_at`, mã model, hạng dịch vụ, đơn giá, tỉ giá, giả định token, hệ số thử lại — và **tính lại từ mẫu sử dụng thật trước khi phát hành**.

Kết luận định tính đã thống nhất: **AI dạng giao dịch thì chi phí kiểm soát được; AI dạng chat có thể đội lên hơn mười lần.** Trần theo lượt gọi và quota theo nhóm cũng là biện pháp chống **denial-of-wallet** khi có người gọi bot liên tục.

### 14.3 Thứ tự xây

1. Định nghĩa `SkillInvocation`, hợp đồng kỹ năng, **bảng phân quyền**, ma trận hiển thị, máy trạng thái thu tiền, ngữ nghĩa bù trừ, bảo mật link khách
2. Lõi tiền: sổ, bất biến, đường lui thủ công, danh tính và phân quyền tối thiểu
3. `money_skill` tạo đề xuất có kiểu, cùng luồng triệu hồi và thẻ tác vụ
4. `CollectionBatch`, `CollectionEnvelope`, trang khách, VietQR, xác nhận nhận tiền
5. Nhóm đã lưu, quyền xem lịch sử, vòng đời thành viên
6. Hộp thư hành động, lịch sử invocation, Home — **và chốt tên tab sau khi các trạng thái đã ổn định**

**Không thiết kế Home trước khi biết chính xác những hành động nào tồn tại.** Không xây một vỏ chat trống trước khi kỹ năng tiền và đề xuất có cấu trúc hoạt động.

---

## 15. Chỉ số và cổng quyết định

**Chỉ số chính:** tỉ lệ nhóm **hoàn tất đợt thu thứ hai do người dùng chủ động tạo**.
*(Không dùng "khoản chi thứ hai trong 30 ngày" — một người có thể nhập ba cuốc taxi trong cùng một buổi.)*
Cohort ở trọ: đo ở chu kỳ kế tiếp. Cohort đi chơi: đo ở cơ hội chi chung kế tiếp hoặc trong 60 ngày; mốc 30 ngày chỉ là chỉ báo sớm. **Chỉ tính repeat khi người dùng xác nhận VÀ publish một đợt thu có ít nhất một nghĩa vụ hợp lệ.** Nháp do quy tắc định kỳ tự sinh **không** tính.

**Vòng thu tiền:** tỉ lệ nghĩa vụ đạt `receiver_confirmed` trong 7 ngày kể từ `due_at` hoặc từ `capability_exposed_at`. Sàn thử nghiệm ≥50%. Nghĩa vụ đang tranh chấp **vẫn trong mẫu số**; nghĩa vụ bị huỷ hợp lệ thì loại. Báo **cả** tỉ lệ theo nghĩa vụ **và** theo nhóm — nếu không, ba nhóm đông người có thể chi phối toàn bộ kết quả.
⚠️ `receiver_confirmed` **không phải** bằng chứng ngân hàng. Người nhận quên bấm tạo thất bại giả; bấm nhầm tạo thành công giả.

**Tốc độ:** lần đầu, từ mở app đến có yêu cầu thu tiền sẵn sàng chia sẻ: median <60 giây. Nhóm đã lưu, từ mở app đến **đề xuất được xác nhận**: median <15 giây. Không tính thời gian thao tác bên trong Messenger/Zalo.

**Khách:** tỉ lệ mở link (mẫu số là link đã **thực sự** được chia sẻ) · tỉ lệ đạt `receiver_confirmed` mà khách không cài app · tỉ lệ "Tôi không phải…" · tỉ lệ phản đối · số link bị thu hồi.

**Chất lượng AI:** ≥80% đề xuất được xác nhận **không có sửa đổi vật chất** về tổng, người ứng tiền, người tham gia, phân bổ. *(Không dùng "≤1 lần sửa" — một lần sửa có thể là đổi toàn bộ tổng tiền.)* Bất biến số học 100%. Theo dõi riêng bốn loại lỗi: đọc hoá đơn, biệt danh, tổng tiền, phân bổ. Món chưa review **không** tính là đúng.
⚠️ "Không có sửa đổi vật chất" **đo hành vi sửa, không đo độ chính xác** — có thể chỉ nghĩa là người dùng bấm nhanh. Cần **mẫu kiểm toán có chuẩn đúng độc lập**, kiểm tra ngẫu nhiên sau xác nhận, tách `accepted_without_edit` khỏi `verified_correct`, và theo dõi lỗi phát hiện **sau** khi publish — đó mới là chấp nhận sai nguy hiểm.

**Gánh nặng người tổ chức** (chỉ số riêng): số phút mỗi đợt · số thao tác thủ công mỗi nghĩa vụ · số lần chia sẻ · số lời nhắc phải tự gửi · tỉ lệ tạo đợt thu thứ hai.
> Nếu thu tiền thành công nhưng người tổ chức vẫn phải chạm gần như từng người ở từng kỳ, **app chưa giải quyết pain đã tuyên bố**.

**Khoảng cách kỳ vọng:** người dùng hiểu đúng bot hiện chỉ làm tiền · tỉ lệ gọi ngoài phạm vi sau onboarding · tỉ lệ bỏ đi sau lời từ chối · mức tin tưởng trước và sau khi phát hiện giới hạn.

**Rào chắn:** tỉ lệ kích hoạt đến xác nhận · số lần nhắc mỗi nghĩa vụ · tỉ lệ tranh chấp · báo cáo nợ giả/lạm dụng · **sự cố sai lệch tiền phải = 0** *(đạt retention mà có một lần chuyển sai người vẫn là THẤT BẠI)* · thời gian thu đủ một đợt · gánh nặng hỗ trợ · mức sẵn lòng trả tiền thực tế.

**Baseline bắt buộc:** thu tiền đạt 50% là **vô nghĩa** nếu nhóm đó dùng Zalo đang đạt 70%. Phải quan sát một chu kỳ theo cách cũ rồi một chu kỳ với sản phẩm trong **cùng nhóm**, hoặc dùng thiết kế crossover. Comparator phải dùng **cùng mẫu số và cùng loại chi phí**.

**Ma trận chẩn đoán** (không kết luận vội):

| Thu tiền | Quay lại | Chẩn đoán |
|---|---|---|
| Cao | Thấp | Nhu cầu theo sự kiện, hoặc sai định vị — **không** phải wedge sai |
| Thấp | Cao | Sổ có giá trị nhưng **UX thanh toán hỏng** |
| Thấp | Thấp | Lúc này mới thực sự nghi ngờ wedge |

Cả hai thấp ở cả hai cohort → **dừng mở rộng phạm vi, chẩn đoán, chạy một vòng sửa có kiểm soát rồi đo lại.** Chỉ kết luận wedge sai nếu **sau vòng sửa**, sản phẩm vẫn không cải thiện thời gian hoặc tỉ lệ thu tiền so với cách làm hiện tại, ở những nhóm thực sự có cơ hội dùng lại.

**Cỡ mẫu:** ≥30 nhóm **đã kích hoạt mỗi cohort** (không phải 30 tổng). Gán cohort theo **ý định lúc thu nạp**, khoá lại, không gán lại theo hành vi; dùng chéo thì ghi riêng. Đăng ký trước mẫu số, ngưỡng, khung thời gian, cách gán cohort, cỡ mẫu. **30/cohort là sàn pilot, không đủ để tuyên bố cohort nào thắng** — với tỉ lệ 40%, khoảng bất định còn rất rộng.

**Đăng ký trước:** hoàn tất đợt thu thứ hai ≥40% · `receiver_confirmed` trong 7 ngày ≥50%. "Hoàn tất đợt thu thứ hai" cần định nghĩa cách xử lý tranh chấp, miễn nợ, nghĩa vụ bị huỷ **trước khi** pilot bắt đầu.

**Kích hoạt mạng lưới** (rủi ro chiến lược riêng): kỹ năng tiền tạo giá trị với một người tổ chức và nhiều khách; "nền tảng trợ lý nhóm" chỉ có giá trị đầy đủ khi nhiều người cài app. **Hai vòng tăng trưởng này khác nhau, không được gộp.**

---

## 16. Rủi ro và hạng mục cần rà soát

### 16.1 Pháp lý — cần luật sư, không được tự kết luận

- Lập bản đồ luồng dữ liệu cho mọi thứ gửi tới nhà cung cấp model.
- Rà theo **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15** (hiệu lực 01/01/2026) và **Nghị định 356/2025/NĐ-CP**. Đưa dữ liệu thu thập tại Việt Nam lên nền tảng ngoài Việt Nam để xử lý tiếp là **chuyển dữ liệu xuyên biên giới**, kéo theo hồ sơ đánh giá tác động. Consent phải có **trước khi thu thập**.
- Xác định: cơ sở đồng ý và thông báo xử lý · hợp đồng xử lý dữ liệu · thời hạn lưu và xoá · hồ sơ đánh giá tác động.
- **Hạng trả phí chỉ giải quyết chuyện dữ liệu có bị dùng để cải thiện model hay không — nó không tự tạo ra sự tuân thủ pháp luật.**
- Sổ bất biến phải tương thích quyền xoá dữ liệu: "bất biến" là tính chất **kiểm toán của hệ thống**, không có nghĩa là không bao giờ xoá hay khử định danh dữ liệu cá nhân.
- Nếu sau này tích hợp đối soát ngân hàng hoặc dịch vụ thanh toán → rà lại toàn bộ phạm vi. **V1 không giữ tiền.**

**Bài toán con gà quả trứng đã giải:** không thể che số tài khoản trên ảnh bill trước khi gửi model, vì muốn biết chỗ nào là số tài khoản thì phải đọc ảnh đã. Lời giải:

1. Ảnh gốc nằm trên thiết bị
2. OCR hệ thống chạy **trên máy**, trả text và toạ độ
3. Trên máy phát hiện QR/barcode, số điện thoại, email, chuỗi giống số tài khoản, tên đã biết → tạo bản che
4. Người dùng xem **màn che kiêm màn minh bạch** — thấy **chính xác đoạn text sắp rời khỏi máy**, sửa được, rồi mới bấm gửi
5. Model **chỉ nhận text đã làm sạch**, giữ ngắt dòng/toạ độ tương đối nếu cần hiểu bố cục. **Không nhận ảnh gốc.**
6. OCR không đủ tin cậy → chuyển sang nhập tay. Chỉ được gửi ảnh gốc khi luật sư duyệt riêng, có thông báo/consent rõ và thời hạn lưu cụ thể.

⚠️ Phải nói thật trong spec: đây là **giảm thiểu rủi ro**, không phải "khử định danh tuyệt đối". OCR trên máy vẫn là xử lý dữ liệu và vẫn cần thông báo phù hợp; nó chỉ tránh chuyển **ảnh gốc** xuyên biên giới.
→ Ảnh từ Share Sheet phải mở bộ che, **không được upload thẳng**.

### 16.2 VietQR — chặn phát hành

Sai payload thì **tiền chạy vào tài khoản người khác**. Đây là lỗi có hậu quả nặng nhất trong toàn bộ app.

- Không tự viết bộ mã hoá nếu đã có thư viện hoặc nhà cung cấp chính thức đủ tin cậy.
- Bộ test vector chuẩn cho payload và checksum (EMVCo/CRC).
- **Giải mã lại QR sau khi sinh**, đối chiếu mã ngân hàng, số tài khoản, số tiền, nội dung.
- Test Unicode, độ dài nội dung, số tiền ở biên, tình huống đổi tài khoản nhận.
- Test tương thích trên **ma trận ứng dụng ngân hàng thật** trước phát hành.
- Đổi tài khoản nhận → **vô hiệu hoá QR và link cũ**.
- Nhắc người chuyển kiểm tra tên chủ tài khoản do chính ngân hàng hiển thị.
- ⚠️ **Checksum đúng chỉ chứng minh payload không hỏng — nó không chứng minh số tài khoản là đúng người.** Phải xác minh cả dữ liệu đầu vào.

### 16.3 Bảo mật và lạm dụng

Chống tạo nợ giả và quấy rối · chống truy cập trực tiếp bằng cách đoán mã và dò token · thông báo tài chính ẩn nội dung nhạy cảm trên màn hình khoá · thao tác xác nhận nhanh phải gắn với thiết bị đã xác thực · **confused deputy**: bot chạy bằng service account mạnh nhưng quyền thực hiện phải tính theo `invoked_by` và chủ thể bị ảnh hưởng · **task interleaving**: câu "ừ, sửa Hà thành 92k" phải gắn với đúng `invocation_id`, không dùng bộ nhớ hội thoại chung để đoán · **shared-output authority**: mọi output ghi rõ `Đề xuất của bot` / `Ai đã xác nhận` / `Chưa có hiệu lực` — bot không được nói "nhóm đã chốt" khi mới có một người gọi.

### 16.4 Tính đúng và vận hành

Test tính chất cho tiền số nguyên, làm tròn, tổng phân bổ · bảo đảm thao tác lặp không nhân đôi hiệu lực · test sửa đồng thời, sinh khoản định kỳ, chấp thuận bù trừ · đường lui thủ công/ngoại tuyến khi AI quá hạn (**không được khoá luồng cốt lõi vì AI**) · tập đánh giá tiếng Việt cho biệt danh, đại từ ("nó", "thằng Nam"), tên trùng, hoá đơn lỗi — **AI không được tự đoán khi có nhiều ứng viên, phải hỏi** · thành viên rời nhóm không để nghĩa vụ mồ côi · thanh toán trên cùng một điện thoại phải có phương án ngoài quét QR.

### 16.5 Dữ liệu `unsupported_intent`

Sự kiện đã chuẩn hoá gắn pseudonymous group ID: **vẫn là dữ liệu cá nhân** trong tối đa 12 tháng — **không được gọi là vô danh**; sau đó chỉ còn tổng hợp không ID. Chỉ lưu **sau khi người dùng chủ động bấm gửi tín hiệu**.

Intent nhạy cảm gom lên taxonomy rộng hơn và **không bao giờ** hiện làm ví dụ *(nhãn như "tìm quán thân thiện … gần ký túc xá X" vẫn có thể tái nhận diện dù bỏ tên)*. Raw text có chấp thuận: tối đa 30 ngày, có nhật ký truy cập, xoá được, không dùng ngoài mục đích lộ trình. Ví dụ trên dashboard là **bản viết lại đã qua review**, không phải trích nguyên văn.

Thêm `taxonomy_version`, lịch sử phân loại lại, chống spam, xoá theo yêu cầu trước khi tổng hợp. Ngưỡng tối thiểu áp cho **từng lát cắt**, không chỉ cho tổng — không hiển thị "10 nhóm" nếu sau khi lọc theo cohort/onboarding chỉ còn một hai nhóm. Đếm theo **nhóm duy nhất** trên mẫu số nhóm hoạt động. **Luôn phân đoạn theo thông điệp onboarding người đó đã thấy** — nếu onboarding kể về quán và chuyến đi thì việc họ hỏi các thứ đó không còn là nhu cầu tự phát.

---

## 17. Giả định chưa được kiểm chứng

Nếu giả định số 1 sai thì cả sản phẩm sai.

1. **Việc thu tiền thực sự đau hơn phép tính** đối với sinh viên Việt Nam
2. Có người sẵn sàng làm người tổ chức và nhập khoản chi thay cả nhóm
3. Khách tin tưởng magic link và chịu thao tác mà không cần cài app
4. Nhắc tự động **giảm** sự ngại chứ không làm quan hệ căng thêm *(chỉ kiểm chứng được với người đã cài app)*
5. Cả nhóm ở trọ chung lẫn nhóm đi chơi đều có retention đủ cao
6. Cùng một mô hình nhóm phục vụ được hai dòng chi phí mà không gây nhầm lẫn số dư
7. Nhập bằng tiếng Việt tự nhiên rút ngắn quy trình **đủ nhiều** so với máy tính + Zalo — *"AI-first" có thể làm quy trình CHẬM hơn một form "tổng tiền + chia đều"; nếu vậy định vị phải chuyển thành collection-first, AI chỉ là một đường nhập phụ*
8. Deep link ngân hàng và VietQR trên cùng thiết bị hoạt động đủ rộng
9. Tỉ lệ tranh chấp và nợ giả nằm trong mức kiểm soát được
10. Người dùng chấp nhận việc app lưu lịch sử chi tiêu và hoá đơn
11. Chi phí model thực tế nằm dưới trần, sau khi tính cả thử lại và ảnh lớn
12. Luồng khách tạo ra **phân phối thật**, không chỉ tạo ra người xem rồi thôi — *guest không cài app là giảm ma sát, chưa phải phân phối hay lợi thế; chỉ được gọi là phân phối khi đo được khách trở thành người tổ chức của nhóm khác*
13. **Thành viên khác chịu cài app để tham gia luồng nhóm** — giả định mới do RB-1 và mô hình triệu hồi tạo ra
14. Organizer Pro có người chịu trả tiền — **chưa được coi là mô hình kinh doanh đã chứng minh**

---

## 18. Sau v1 — nơi tầm nhìn quay lại

Mỗi kỹ năng mới chỉ được mở khi có **nguồn dữ liệu, eval, renderer, mô hình quyền, cổng an toàn, và bài toán chi phí riêng**. "Tích hợp" **không phải** giấy phép dùng lại mọi dữ liệu — việc người dùng cho kỹ năng tiền đọc bill không cho kỹ năng gợi ý quán sau này đọc lịch sử chi tiêu.

| Giai đoạn | Điều kiện mở | Nội dung |
|---|---|---|
| **v1.5** | Vòng thu tiền đạt mốc | Bình luận gắn vào từng khoản chi. Tổng kết theo tháng |
| **v2** | Cohort được quảng cáo cho thấy chi phí lặp lại thật, **hoặc** một ràng buộc riêng của chủ sản phẩm | UI định kỳ, chia tỉ lệ theo ngày vào/ra. *(Nếu là ràng buộc thì phải ghi đúng là ràng buộc, không được gọi là kết luận nghiên cứu)* |
| **v2+** | Nhu cầu thật từ `unsupported_intent`, có nguồn dữ liệu | Kỹ năng thứ hai của bot — nhiều khả năng là chốt chỗ/gợi ý quán |
| **v3** | Có tập video/frame được chấp thuận và **gắn nhãn thị giác độc lập**, cùng bằng chứng video tạo giá trị hơn thao tác chọn người | Quay video nhận món. ⚠️ `verified_items` chỉ cung cấp từ vựng — **không** thay thế nhãn thị giác |
| **v3+** | Có bằng chứng dữ liệu chi tiêu dự báo được lựa chọn địa điểm | Gợi ý địa điểm, kế hoạch chuyến đi. Nếu có tài trợ thì phải gắn nhãn rõ và tách khỏi xếp hạng tự nhiên |
| **v4** | Người dùng chủ động muốn, và album/kỉ niệm tồn tại | Nhận diện khuôn mặt **do chính chủ tự đăng ký trên máy mình**, consent riêng **trước** khi thu thập, có nút xoá và rút lại. Dùng cho gắn tên ảnh — **không** dùng để gán món. ⚠️ Không mở face trước khi có album, nếu không tính năng đứng trước công việc của chính nó |

---

## 19. Phụ lục — 19 vòng tranh luận

| Vòng | Ai sai | Nội dung |
|---|---|---|
| 1 | Claude | Consent sinh trắc học sau khi crop mặt là thu thập trước khi có sự đồng ý — vi phạm khung pháp lý mới |
| 1 | Claude | Bắt tạo nhóm trước khi chia tiền là rào cản khởi đầu quá nặng → session-first |
| 1 | Claude | Ma trận món × người không dùng được trên điện thoại |
| 1 | Claude | "Mở QR" bị nhầm thành "đã thanh toán" |
| 1 | Claude | Chữ "Nợ nần" mang giọng đòi nợ, sai văn hoá bạn bè Việt |
| 2 | Codex | Quy tắc "chờ người trả xác nhận" tự mâu thuẫn với chính cảnh báo "sổ bị treo" của nó |
| 2 | Codex | Model gateway đa nhà cung cấp ở v1 là giải bài toán chưa tồn tại |
| 2 | Claude | Xác nhận tổng tiền ≠ xác nhận chi tiết món → sinh ra ba mức xác minh |
| 2 | Claude | Dữ liệu hoá đơn không phải dữ liệu huấn luyện cho nhận diện món qua video |
| **2** | **Cả hai** | **Phát hiện lớn nhất: việc thu tiền mới là phần đau nhất, không phải phép chia** |
| 3 | Codex | Chấp nhận "cùng một nhóm người, hai loại chi phí" — không phải chọn một trong hai |
| 3 | Claude | Bảng thu gắn với từng khoản chi biến app thành máy spam → chuyển sang đợt thu |
| 4 | Claude | "Tất toán rồi mới được rời nhóm" biến tư cách thành viên thành con tin của tranh chấp |
| 4 | Claude | Quy tắc dừng suy luận quá mạnh → thay bằng ma trận chẩn đoán 2×2 |
| 5 | — | Chốt ranh giới `published_at` cho bù trừ |
| **6** | **Claude** | **19 vấn đề, 4 lỗi chặn triển khai. "Che số tài khoản trước khi gửi model" là mâu thuẫn con gà quả trứng** |
| 6 | Claude | "Cộng vào đợt đang mở" đá thẳng vào quy tắc chấp thuận sau publish |
| 7 | Codex | Chấp nhận phân loại ba mức để chống scope phình lại |
| 7 | Codex | Chấp nhận cắt đường ảnh bill nếu OCR trên máy không đủ tốt |
| 7 | Claude | Link nhóm bị bác: không thể vừa công khai, vừa không xác thực, vừa riêng tư |
| 8 | Codex | Nhượng bộ chế độ giao theo từng đợt và batch nhiều người nhận |
| **8** | **Claude** | **"Concierge là cận trên" sai — độ lệch đi cả hai hướng** |
| **9** | **Claude** | **"Giai đoạn 0.5" bị bác: khó sửa sau không phải lý do xây nền móng cho sản phẩm có thể không nên tồn tại** |
| 10 | Codex | Chấp nhận cả hai chế độ thông điệp và pre-commit đầy đủ tập kết cục |
| **11** | **—** | **Chủ sản phẩm can thiệp: bot được triệu hồi vào luồng của nhóm. Mở lại quyết định "không có chat"** |
| 11 | Codex | Chấp nhận, kèm ràng buộc cốt tử: không có nhắn tin tự do thì mới không phải app nhắn tin |
| 12 | Claude | Bảy quyết định trước đó không còn đúng sau khi có mặt tiếp xúc triệu hồi |
| 13 | — | Chủ sản phẩm chốt app là ràng buộc cứng và định vị nền tảng |
| **14** | **Claude** | **Nguỵ biện vòng tròn: tuyển riêng nhóm ở trọ rồi lấy hành vi của mẫu tuyển riêng biện minh cho scope production** |
| 15 | Codex | Đề xuất hai nhát cắt: bỏ link chung, bắt người ứng tiền có tài khoản trước khi đặt số nhận |
| 16 | Claude | Nói quá về C2: tài khoản đã xác thực chỉ chứng minh ai đó kiểm soát ô đăng nhập |
| 16 | Claude | Cửa sau: nút "chia sẻ nhiều link cùng lúc" chính là xây lại chế độ link chung |
| 17 | Claude | `challenged` không có đường được minh oan; chưa có người phán quyết |
| **18** | **Claude** | **Lặp lại đúng lỗi đã nhận sai: cho người tạo đợt thu tự đổi người nhận tiền** |
| 18 | Claude | Đình chỉ toàn tài khoản khi có khiếu nại = công cụ đánh sập tài khoản; và có thể bắt người ta **trả tiền hai lần** |
| 19 | — | **ĐÃ HỘI TỤ.** Không còn bất đồng thực chất |
