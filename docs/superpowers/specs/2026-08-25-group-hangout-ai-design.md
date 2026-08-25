# Spec: App chi phí chung nhóm bạn, AI-first (Việt Nam)

Ngày: 2026-08-25
Trạng thái: ĐÃ HỘI TỤ sau 5 vòng tranh luận Claude ↔ Codex. Chờ chủ sản phẩm duyệt.

---

## 0. Tóm tắt điều hành

Sản phẩm dài hạn mà chủ sản phẩm hình dung là một "super app đi chơi nhóm": gợi ý địa điểm, chia sẻ kỉ niệm kiểu Locket, tường nhà kiểu Facebook, và một bot AI trong group chat tự đọc ảnh/tin nhắn để chia tiền — kèm nhận diện khuôn mặt và quay video để biết ai ăn món gì.

Sau tranh luận, **v1 thu hẹp về một thứ duy nhất**: đưa một nhóm bạn Việt Nam đi từ *"câu nói tiếng Việt lộn xộn hoặc tấm ảnh bill"* đến *"tiền đã được người nhận xác nhận là đã nhận"*.

Điểm thay đổi quan trọng nhất so với ý tưởng ban đầu:

> **Phép chia tiền không phải phần đau nhất. Việc đi thu tiền mới là.**
>
> Tính ra "Hà 82k, Nam 104k" chỉ là nửa đầu. Nửa sau — nhắn riêng từng đứa, gửi số tài khoản, nhớ ai đã chuyển ai chưa, nhắc mà không làm mất lòng — mới là phần mệt và ngại, và là phần chưa ai giải quyết cho thị trường Việt Nam. Nếu app tính nhanh hơn nhưng việc thu tiền vẫn diễn ra thủ công trong Zalo thì người dùng không có lý do ở lại.

Vì vậy màn hình trung tâm của v1 **không phải** màn chia tiền, mà là **bảng thu tiền**.

---

## 1. Định vị và phân khúc

- **V1 là:** công cụ ghi, thu và tất toán chi phí chung cho nhóm bạn trẻ Việt Nam.
- **Beachhead:** sinh viên Việt Nam 18–24, trong các nhóm người tương đối ổn định.
- **Hai cohort chạy song song, không chọn trước:**
  - **Sinh viên ở trọ chung** — chi phí định kỳ (phòng, điện, nước, mạng) và mua sắm chung. Tạo **tần suất**.
  - **Nhóm đi chơi thuần** — ăn uống, di chuyển, du lịch. Tạo **gắn kết cảm xúc**.
- **Nguyên tắc nền:** hai cohort này thường là *cùng một nhóm người*. Thực thể bền vững cần thiết kế quanh nó là **nhóm người ổn định có nhiều dòng chi phí**, không phải "chuyến đi" cũng không phải "hộ ở chung". Một sản phẩm, một mô hình dữ liệu.
- **Đối thủ thật không phải Splitwise**, mà là: máy tính bỏ túi + tin nhắn Zalo/Messenger + ảnh chụp màn hình chuyển khoản.
- **Moat giả thuyết** (chưa được chứng minh, phải đo):
  - Hiểu tiếng Việt đời thường, teencode, biệt danh, đơn vị "k".
  - Guest thao tác được mà không cần cài app.
  - Vòng thu tiền hoàn chỉnh, hợp tập quán Việt Nam.
  - VietQR và luồng thanh toán nội địa.
  - Phân phối qua chính các nhóm chat sẵn có.
- **Không phải moat:** cái nhãn "có AI". Splitwise Pro đã có quét hoá đơn và chia theo món.
- **Kiếm tiền:** v1 miễn phí hoàn toàn. Organizer Pro chỉ là *giả thuyết*, chỉ kiểm chứng sau khi retention được chứng minh. Không bán thứ hạng địa điểm cho quán.

---

## 2. Phạm vi v1

### 2.1 CÓ trong v1

- **Session-first:** chia tiền được ngay, không bắt tạo nhóm trước. Chỉ sau lần thứ hai với cùng nhóm người mới đề nghị lưu.
- **Ba đường vào ngang hàng:**
  - Gõ tiếng Việt tự nhiên.
  - Chụp / chọn / chia sẻ ảnh bill (kèm Share Sheet từ Messenger/Zalo).
  - Nhập tay — **phải chạy được khi AI lỗi hoặc mất mạng**.
- Một người trả cho mỗi khoản chi. Nhiều người cùng trả thì tách thành nhiều khoản.
- AI sinh **bản nháp**; người dùng xác nhận thì mới vào sổ.
- UI mặc định hiện **số tiền theo từng người**. Có thể mở "Vì sao tôi trả 82k?" để xem chi tiết món, nhưng không ép.
- Nhóm đã lưu gồm: thành viên, khách, biệt danh, chi phí định kỳ, session sự kiện, vòng đời thành viên.
- Quy tắc định kỳ cho khoản cố định (tiền phòng) và khoản biến đổi (điện, nước).
- **Đợt thu tiền** gom được nhiều khoản chi.
- Bảng thu tiền + hộp thư việc cần xử lý.
- Link cá nhân hoá cho từng người.
- VietQR, lưu ảnh QR, copy số tài khoản / số tiền / nội dung, deep link ngân hàng khi có.
- Phản đối, nhắc có giới hạn, xử lý chuyển thiếu hoặc sai số, hoàn tác xác nhận nhầm.
- Số dư tổng, số dư theo ngữ cảnh, lịch sử kiểm toán.
- **Rời nhóm được kể cả khi còn nghĩa vụ chưa tất toán.**

### 2.2 KHÔNG có trong v1

| Bị cắt | Lý do |
|---|---|
| Chat trong app | Không ai lặp lại hội thoại đã có trên Messenger/Zalo. Timeline sẽ vừa trống vừa làm nhiễu sổ, lại đội chi phí AI lên nhiều lần |
| Nhập bằng giọng nói | Quán ồn, thêm quyền truy cập, thêm lỗi. Chưa có bằng chứng nhu cầu |
| Nhận diện khuôn mặt / dữ liệu sinh trắc học | Giá trị chỉ là đỡ vài lần chạm chọn người, đổi lại toàn bộ gánh nặng pháp lý và bảo mật. Tỉ lệ giá trị trên rủi ro tệ nhất toàn spec |
| Quay video nhận món ăn | Món Việt nhìn giống nhau; đồ uống không phân biệt được bằng mắt; phải suy luận món nào trước mặt ai. Tiền là lĩnh vực không dung thứ sai sót |
| Gợi ý địa điểm / Discovery | Chưa có traffic, chưa có dữ liệu chứng minh khả năng dự báo lựa chọn |
| Feed xã hội, tường nhà, kỉ niệm | Là vitamin, không phải painkiller. Dễ thành engagement giả |
| Trí nhớ AI suy diễn sở thích | "Đã mua" không đồng nghĩa "thích". Suy ra ăn chay / dị ứng từ lịch sử mua là tạo hồ sơ sức khoẻ nhạy cảm sau lưng người dùng |
| Ma trận món × người trên UI | 10 món × 8 người = 80 ô bấm nhầm trên điện thoại |
| Nhiều người trả trong một khoản chi | Biểu diễn được bằng nhiều khoản chi |
| AI tự ghi vào sổ | Ranh giới bất khả xâm phạm |
| Quy tắc định kỳ tự sinh nợ | Phải qua xác nhận |
| Tự bù trừ xuyên đợt thu | Thay đổi thoả thuận xã hội mà không ai biết |
| Ảnh chuyển khoản làm bằng chứng mặc định | Dễ giả, lại thu thêm dữ liệu tài chính nhạy cảm |
| Ví, giữ tiền, tự xác nhận giao dịch ngân hàng | Vượt xa phạm vi và kéo theo giấy phép |
| Model gateway đa nhà cung cấp | Giải bài toán chưa tồn tại |
| Quán trả tiền để được gợi ý | Chưa có gì để bán, và làm hỏng niềm tin |

---

## 3. Các quyết định đã chốt

### 3.1 Ranh giới AI ↔ tiền

- AI **chỉ** tạo bản nháp. Con người xác nhận thì mới thành khoản chi chính thức.
- Khoản chi do một thành viên đã xác thực ghi và xác nhận thì **có hiệu lực ngay**, kể cả khi người ghi không phải người trả. Không bao giờ có trạng thái chờ chặn — sổ không được treo vì một người không mở app.
- Ghi riêng `recorded_by`, `paid_by`, và `payer_acknowledgement`. Xác nhận của người trả là **tín hiệu tin cậy, không phải cổng chặn**.
- Ai cũng được phản đối phần của mình bất cứ lúc nào.

### 3.2 Tính đúng của tiền

- Tiền lưu dạng **số nguyên đồng**. Không bao giờ dùng số thực.
- **Bất biến bắt buộc:** tổng các phần chia luôn bằng đúng tổng khoản chi. Không ngoại lệ. Phải có test tự động.
- Phần dư khi chia không hết được gán theo quy tắc cố định, và **quy tắc đó phải hiện ra cho người dùng thấy**, không giấu trong backend.
- Sổ là nguồn sự thật. Số dư là kết quả tính lại được, có thể cache để UI nhanh nhưng luôn tái tạo được từ sổ.
- Sửa khoản chi tạo **phiên bản mới**, không ghi đè lịch sử. Khoản sai bị vô hiệu bằng sự kiện kiểm toán, không xoá âm thầm.

### 3.3 Ba mức độ xác minh của dữ liệu AI

Đây là phân biệt quan trọng nhất về mặt dữ liệu:

| Loại | Nghĩa | Dùng được vào việc gì |
|---|---|---|
| `draft_items` | Món do model suy ra | Gỡ lỗi, xây từ vựng món Việt, học chủ động. **Không phải chuẩn đúng** |
| `confirmed_allocations` | Số tiền theo người mà người dùng đã thực sự nhìn và xác nhận | Sổ chính thức |
| `verified_items` | Món mà người dùng đã trực tiếp xem hoặc sửa | Tập đánh giá có nhãn |

Mỗi khoản chi mang cờ `verification_scope`: `totals_only` hoặc `items_reviewed`.

**Lý do:** bấm "Đúng rồi" trên màn hình chỉ hiện *"Hà 82k"* **không** xác nhận rằng *"trà sữa ô long 42k là của Hà"*. Dùng món do model sinh ra làm chuẩn để chấm điểm chính model đó là tự chấm bài mình bằng đáp án của mình.

Nếu người dùng sửa trực tiếp tổng của một người khiến phần chi tiết món không còn khớp, màn drill-down phải được đánh dấu là **giải thích cũ** hoặc tính lại — không được tiếp tục trình bày như bằng chứng đúng.

### 3.4 Thu tiền

- **Đơn vị thu tiền là đợt thu, không phải từng khoản chi.** Nếu mỗi lần mua bó rau 35k lại phát một link đòi tiền thì app thành máy spam.
- Một đợt thu có thể là: một hoá đơn lẻ / một buổi đi chơi / một tuần tiền chợ / một chu kỳ tiền nhà.
- Sau khi xác nhận khoản chi: chọn `Thu ngay` (tạo đợt mới) hoặc `Cộng vào đợt đang mở`. Nếu cộng vào đợt đang mở mà số tiền của người đã nhận link bị thay đổi thì **phải báo cho họ**.
- **Ba trạng thái hoàn toàn tách biệt:** mở QR ≠ người trả báo đã chuyển ≠ người nhận xác nhận đã nhận.
- Tiến độ đo bằng **"2/4 người đã hoàn tất"** (đã được xác nhận nhận tiền), không phải "đã gửi link". Người trả tiền không nằm trong mẫu số nếu họ không phải chuyển đi đâu cả.
- Không có nút "gửi tất cả" nếu app không thực sự có quyền nhắn tự động. Dùng Share Sheet và hiện rõ link nào đã được chia sẻ.

### 3.5 Bù trừ và rút gọn nợ

- Số dư toàn nhóm **luôn** hiển thị dạng đã bù trừ — đó là bản chất của sổ.
- Đợt thu **không bao giờ** tự bù trừ xuyên đợt.
- Ranh giới là `published_at`: thời điểm nghĩa vụ lần đầu được công bố qua hộp thư, thông báo đẩy, hoặc thao tác chia sẻ link.
  - **Trước `published_at`:** người tạo sửa, gộp, bù trừ thoải mái. Chưa có kỳ vọng xã hội nào bị thay đổi nên không cần đi xin chấp thuận — nếu không sẽ thành spam hỏi ý kiến ngay lúc đang gõ.
  - **Sau `published_at`:** mọi thay đổi người trả, người nhận, hoặc số tiền đều tạo bản sửa và **cần chấp thuận của tất cả các bên bị ảnh hưởng**.
- Gợi ý "trả gọn nhất" (A nợ B, B nợ C → A trả thẳng C) **không phải chỉ là tối ưu thuật toán, mà là thay đổi thoả thuận xã hội**. Chỉ áp dụng khi mọi người bị đổi đối tác đều đồng ý. Có bản ghi bù trừ riêng để kiểm toán. Ai không đồng ý thì các đợt thu gốc giữ nguyên.

### 3.6 Ngôn ngữ giao diện

- Dùng **"cần gửi" / "sẽ nhận"**. Tuyệt đối tránh giọng đòi nợ kiểu "Bạn nợ...".
- Cho phép bỏ qua khoản quá nhỏ, và cho người ứng tiền chủ động miễn phần còn lại.
- Không hiện thuật ngữ model hay điểm tin cậy dạng "73%" cho người dùng.
- Chỗ AI không chắc phải thành **câu hỏi cụ thể**, không chỉ tô màu:
  - *"Hà" là Hà Nguyễn hay Hà Trần?*
  - *82k của Nam đã gồm phí ship chưa?*

### 3.7 Bảo mật link khách

- Câu chữ **không được giả định** người mở link đúng là người được chỉ định — link bị chuyển tiếp là chuyện thường.
  - Viết: *"Nam đã ghi phần của Hà trong bữa lẩu là 82.000đ."*
  - Ba lựa chọn: `Đúng, xem cách chuyển` · `Số tiền không đúng` · `Tôi không phải Hà`
- Mỗi nghĩa vụ một token riêng, entropy cao, có hạn dùng, thu hồi được.
- Token chỉ mở đúng nghĩa vụ của người đó. **Không lộ số dư hay lịch sử cả nhóm.**
- Link preview trong Zalo/Messenger dùng metadata trung tính, không chứa tên và số tiền.
- Giới hạn tần suất thao tác báo chuyển và phản đối.
- Người nhận tiền tự chọn tài khoản được chia sẻ; không mặc định phát tán thông tin ngân hàng cũ.
- `Tôi đã chuyển` chỉ là tự khai, không bao giờ tự đóng khoản.
- **Không dùng OTP cho khách ở v1** — sẽ phá vòng lan truyền. Sở hữu magic link là đủ để báo trạng thái, vì người nhận tiền vẫn là chốt chặn cuối. Chỉ thêm OTP nếu có lạm dụng thật.
- Sau này cài app thì nhận lại nghĩa vụ hiện có; không bắt cài trước khi thanh toán.

### 3.8 Vòng đời thành viên

**Không được bắt "tất toán xong mới được rời nhóm"** — chỉ cần một khoản tranh chấp là người dùng mắc kẹt vĩnh viễn.

1. Chốt ảnh chụp số dư tại `left_at`.
2. Gỡ khỏi mọi quy tắc định kỳ trong tương lai.
3. Chuyển quyền quản trị / tài khoản nhận tiền nếu cần.
4. Tạo đợt thu cuối cho các nghĩa vụ còn mở.
5. **Chuyển sang trạng thái đã rời ngay**, không chờ thanh toán.
6. Nghĩa vụ cũ vẫn tồn tại với thành viên đã lưu trữ, tất toán sau được.
7. Dữ liệu hồ sơ không còn cần thiết phải được xoá hoặc khử định danh; chỉ giữ phần tối thiểu cần cho kế toán.

`Tất toán và rời` là nút tiện lợi, không phải cổng chặn.

---

## 4. Mô hình dữ liệu và máy trạng thái

### 4.1 Thực thể

`Group` · `Membership` (vai trò, biệt danh, `joined_at`, `left_at`) · `Context` (chu kỳ sinh hoạt hoặc session sự kiện) · `RecurringRule` · `ExpenseDraft` · `DraftItem` · `ExpenseVersion` · `ConfirmedAllocation` · `VerifiedItem` · `CollectionBatch` · `CollectionObligation` · `GuestLink` · `PaymentReport` · `ReceiptConfirmation` · `Dispute` · `OffsetProposal` · `Settlement` · `BankRecipient` · `AuditEvent`

### 4.2 Máy trạng thái

**Khoản chi**
```
draft → confirmed → disputed → adjusted (bằng phiên bản mới)
```
`payer_acknowledgement` là trạng thái độc lập, không nằm trong chuỗi này.

**Nghĩa vụ thu tiền**
```
draft → published → reported_transferred → partially_received → received
```
Nhánh phụ:
```
published / reported → disputed
published → expired | revoked
received → undone (khi xác nhận nhầm)
```

**Đợt thu**
```
draft → open → partially_received → completed | closed
```

**Quy tắc định kỳ**
```
active → sinh draft → confirmed | skipped
active ↔ paused
active | paused → archived
```
- Khoản cố định: xác nhận bằng **một chạm ngay từ thông báo**, gắn với thiết bị đã xác thực. Không bắt mở app đi qua cả luồng.
- Khoản biến đổi: bắt buộc nhập số thực tế.
- Hỗ trợ: sửa kỳ này / sửa từ kỳ sau / bỏ qua một kỳ / tạm dừng quy tắc.

**Bù trừ**
```
draft → proposed (published) → accepted_by_all → applied
                            ↘ rejected | expired
```

**Thành viên**
```
active → (chốt snapshot tại left_at) → left
```

---

## 5. Giao diện

**Thứ tự ưu tiên thiết kế** (không thiết kế Home trước — phải biết có những trạng thái nào rồi mới tổng hợp được):

1. Máy trạng thái thu tiền, phạm vi đợt thu, hợp đồng của link khách.
2. Tạo khoản chi + thẻ nháp.
3. **Bảng thu tiền và trang web cho khách — thiết kế như một cặp.**
4. Quy tắc định kỳ.
5. Nhóm đã lưu.
6. Hộp thư việc cần xử lý / Home.

**Thẻ nháp phải có:** ai đã trả · tổng hoá đơn, phí, giảm giá · phần của người trả so với số người khác cần gửi · câu nói hoặc ảnh nguồn để đối chiếu · kiểm tra tổng phân bổ bằng tổng khoản chi · các điểm không chắc dưới dạng câu hỏi cụ thể. Nút: `Sửa` và `Xác nhận khoản chia`. Xác nhận **không** tự gửi yêu cầu thu tiền — bước sau mới chọn `Thu ngay` hay `Để cộng dồn`.

**Bảng thu tiền còn cần:** ghi nhận chuyển thiếu hoặc sai số · hoàn tác xác nhận nhầm · hết hạn và thu hồi từng link · ngừng nhắc người đang phản đối · chọn tài khoản nhận · bảng giải thích con số đến từ đâu.

**Lưu ý dễ bỏ sót:** người ta thường mở link **trên chính chiếc điện thoại đang dùng** — lúc đó không có máy thứ hai để quét QR. Bắt buộc phải có: copy số tài khoản / số tiền / nội dung, deep link mở thẳng app ngân hàng, và lưu ảnh QR.

**Tên tab** để mở, chốt sau khi máy trạng thái xong. Nguyên tắc đã thống nhất: app cần một **hộp thư hành động** trả lời "việc gì đang cần tôi làm", không phải một trang chủ tổng hợp mờ nhạt.

---

## 6. Kiến trúc kỹ thuật

| Tầng | Chọn | Ghi chú |
|---|---|---|
| App | React Native + Expo, TypeScript | Một codebase iOS + Android. Cần Expo prebuild / dev client cho Share Extension, không phải managed thuần |
| Lõi dữ liệu | PostgreSQL | Tiền cần giao dịch toàn vẹn |
| API | FastAPI (Python 3.12+) | Cùng ngôn ngữ với tầng AI |
| Xử lý AI | Worker riêng + hàng đợi | Gọi model là thao tác chậm và hay lỗi: cần chạy nền, thử lại, hạ cấp khi hỏng |
| Hiểu ngôn ngữ / ảnh | Interface nghiệp vụ mỏng + **một** adapter Gemini (paid tier) | Không dựng model gateway đa nhà cung cấp ở v1. Prompt, schema, tên model tập trung một chỗ |
| Kiểm chứng | Validator số học **độc lập với nhà cung cấp** + tập đánh giá tiếng Việt + canary khi đổi model | JSON schema chỉ đảm bảo hình dạng output, **không** đảm bảo tên người, số tiền hay phép chia đúng |
| Ảnh | Lưu trữ đối tượng có CDN | |
| Thanh toán | Sinh VietQR | Không giữ tiền, không làm ví |
| Giám sát | Sentry + theo dõi riêng chất lượng lời gọi AI | Phải đo được AI đang giỏi lên hay dốt đi |

**Điều kiện nâng cấp lên gateway đa nhà cung cấp:** khi có nhà cung cấp thứ hai thật, hoặc sự cố ảnh hưởng cam kết dịch vụ, hoặc model trôi chất lượng lặp lại, hoặc yêu cầu pháp lý về nơi lưu dữ liệu buộc phải đổi.

**Chi phí:** spec chỉ ghi *công thức* và *trần chi phí*, không ghi tên model và đơn giá như chân lý. Bản kế hoạch triển khai phải ghi kèm `verified_at`, mã model, hạng dịch vụ, đơn giá, tỉ giá, giả định token, hệ số thử lại — và **tính lại từ mẫu sử dụng thật trước khi phát hành**. Kết luận định tính đã thống nhất: AI dạng giao dịch thì chi phí kiểm soát được; AI dạng chat có thể đội lên hơn mười lần.

---

## 7. Chỉ số và cổng quyết định

**Chỉ số chính**
Tỉ lệ nhóm **hoàn tất đợt thu thứ hai do người dùng chủ động tạo**.
(Không dùng "khoản chi thứ hai trong 30 ngày" — một người có thể nhập ba cuốc taxi trong cùng một buổi.)
- Cohort ở trọ chung: đo ở chu kỳ chi phí kế tiếp.
- Cohort đi chơi: đo ở cơ hội chi chung kế tiếp, hoặc trong 60 ngày. Mốc 30 ngày chỉ là chỉ báo sớm.

**Chứng minh vòng lặp thu tiền**
Tỉ lệ nghĩa vụ đạt trạng thái `received` trong vòng 7 ngày kể từ hạn hoặc từ lúc link được giao. Mục tiêu thử nghiệm ban đầu: ≥ 50%. Nghĩa vụ đang tranh chấp **vẫn nằm trong mẫu số**; nghĩa vụ bị huỷ hợp lệ thì loại ra.

**Tốc độ**
- Lần đầu, từ mở app đến có yêu cầu thu tiền sẵn sàng chia sẻ: median < 60 giây.
- Nhóm đã lưu, từ mở app đến **bản nháp được xác nhận**: median < 15 giây. Không tính thời gian thao tác bên trong Messenger/Zalo.

**Khách**
Tỉ lệ mở link (mẫu số là link đã thực sự được chia sẻ) · tỉ lệ hoàn tất mà không cài app · tỉ lệ bấm "Tôi không phải…" · tỉ lệ phản đối · số link bị thu hồi.

**Chất lượng AI**
- ≥ 80% bản nháp được xác nhận **không có sửa đổi vật chất** về tổng tiền, người trả, người tham gia, hoặc phân bổ. (Không dùng "≤ 1 lần sửa" — một lần sửa có thể là đổi toàn bộ tổng tiền.)
- Bất biến số học đạt 100%.
- Theo dõi riêng bốn loại lỗi: đọc hoá đơn, biệt danh, tổng tiền, phân bổ.
- Món chưa được review **không** được tính là đúng.

**Rào chắn**
Tỉ lệ kích hoạt đến xác nhận · số lần nhắc trên mỗi nghĩa vụ · tỉ lệ tranh chấp · báo cáo nợ giả / lạm dụng · sự cố sai lệch tiền · thời gian thu đủ một đợt · gánh nặng hỗ trợ.

**Ma trận chẩn đoán** (không được kết luận vội)

| Thu tiền | Quay lại | Chẩn đoán |
|---|---|---|
| Cao | Thấp | Nhu cầu theo sự kiện, hoặc sai định vị — **không** phải wedge sai |
| Thấp | Cao | Sổ có giá trị nhưng **UX thanh toán hỏng** |
| Thấp | Thấp | Lúc này mới thực sự nghi ngờ wedge |

Cả hai chỉ số thấp ở cả hai cohort → **dừng mở rộng phạm vi, chẩn đoán, chạy một vòng sửa có kiểm soát rồi đo lại.** Chỉ kết luận wedge sai nếu sau vòng sửa, sản phẩm vẫn không cải thiện được thời gian hoặc tỉ lệ thu tiền so với cách làm hiện tại, ở những nhóm thực sự có cơ hội dùng lại.

Chỉ đánh giá sau khi mỗi cohort có đủ số nhóm đã kích hoạt và ít nhất **hai cơ hội chi phí hợp lệ**.

---

## 8. Rủi ro và hạng mục cần rà soát đặc biệt

### 8.1 Pháp lý — cần luật sư, không được tự kết luận

- Lập bản đồ luồng dữ liệu cho mọi thứ gửi tới Gemini.
- Rà theo **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15** (hiệu lực 01/01/2026) và **Nghị định 356/2025/NĐ-CP**. Đưa dữ liệu thu thập tại Việt Nam lên nền tảng ngoài Việt Nam để xử lý tiếp là **chuyển dữ liệu xuyên biên giới**, kéo theo hồ sơ đánh giá tác động.
- Xác định: cơ sở đồng ý và thông báo xử lý · hợp đồng xử lý dữ liệu với nhà cung cấp · thời hạn lưu và xoá · hồ sơ đánh giá tác động.
- Khử định danh tên người trước khi gửi model. Che số tài khoản, số điện thoại, dữ liệu tài chính không cần thiết khỏi ảnh hoá đơn.
- **Hạng trả phí chỉ giải quyết chuyện dữ liệu có bị dùng để cải thiện model hay không — nó không tự tạo ra sự tuân thủ pháp luật.**
- Sổ bất biến phải tương thích với quyền xoá dữ liệu: "bất biến" là tính chất kiểm toán của hệ thống, **không** có nghĩa là không bao giờ xoá hay khử định danh dữ liệu cá nhân.
- Nếu sau này tích hợp đối soát ngân hàng hoặc dịch vụ thanh toán thì phải rà lại toàn bộ phạm vi pháp lý. V1 **không giữ tiền**.

### 8.2 VietQR — chặn phát hành

Sai payload thì **tiền chạy vào tài khoản người khác**. Đây là lỗi có hậu quả nặng nhất trong toàn bộ app.

- Không tự viết bộ mã hoá nếu đã có thư viện hoặc nhà cung cấp chính thức đủ tin cậy.
- Bộ test vector chuẩn cho payload và checksum.
- Giải mã lại QR sau khi sinh, đối chiếu mã ngân hàng, số tài khoản, số tiền, nội dung.
- Test Unicode, độ dài nội dung, số tiền ở biên, và tình huống đổi tài khoản nhận.
- Test tương thích trên một ma trận **ứng dụng ngân hàng thật** trước khi phát hành.
- Đổi tài khoản nhận thì vô hiệu hoá QR và link cũ.
- Nhắc người chuyển kiểm tra tên chủ tài khoản do chính ngân hàng hiển thị.
- **Checksum đúng chỉ chứng minh payload không hỏng — nó không chứng minh số tài khoản là đúng người.** Phải xác minh cả dữ liệu đầu vào.

### 8.3 Bảo mật và lạm dụng

- Chống tạo nợ giả và quấy rối: xác nhận danh tính, giới hạn tần suất, chặn và báo cáo, giới hạn số lần nhắc.
- Chống truy cập trực tiếp bằng cách đoán mã và dò token.
- Thông báo tài chính phải ẩn nội dung nhạy cảm trên màn hình khoá.
- Thao tác xác nhận nhanh phải gắn với thiết bị đã xác thực.

### 8.4 Tính đúng và vận hành

- Test tính chất cho: tiền số nguyên, làm tròn, tổng phân bổ.
- Bảo đảm thao tác lặp không nhân đôi hiệu lực: báo chuyển, xác nhận, hoàn tác.
- Test sửa đồng thời, sinh khoản định kỳ, chấp thuận bù trừ.
- Đường lui thủ công / ngoại tuyến khi AI quá hạn — **không được khoá luồng cốt lõi vì AI**.
- Tập đánh giá tiếng Việt cho: biệt danh, đại từ ("nó", "thằng Nam"), tên trùng, hoá đơn lỗi. **AI không được tự đoán khi có nhiều ứng viên** — phải hỏi.
- Thành viên rời nhóm không được để nghĩa vụ mồ côi.
- Thanh toán trên cùng một điện thoại phải có phương án ngoài việc quét QR.

---

## 9. Giả định chưa được kiểm chứng

Toàn bộ kế hoạch này đứng trên các giả định sau. Nếu cái đầu tiên sai thì cả sản phẩm sai.

1. **Việc thu tiền thực sự đau hơn phép tính** đối với sinh viên Việt Nam.
2. Có một người trong nhóm sẵn sàng làm người tổ chức và nhập khoản chi thay cả nhóm.
3. Khách tin tưởng magic link và chịu thao tác mà không cần cài app.
4. Nhắc tự động **giảm** sự ngại chứ không làm quan hệ căng thêm.
5. Cả nhóm ở trọ chung lẫn nhóm đi chơi đều có retention đủ cao.
6. Cùng một mô hình nhóm phục vụ được hai dòng chi phí mà không gây nhầm lẫn số dư.
7. Nhập bằng tiếng Việt tự nhiên rút ngắn quy trình **đủ nhiều** so với máy tính + Zalo.
8. Deep link ngân hàng và VietQR trên cùng thiết bị hoạt động đủ rộng trên các ngân hàng mục tiêu.
9. Tỉ lệ tranh chấp và nợ giả nằm trong mức kiểm soát được.
10. Người dùng chấp nhận việc app lưu lịch sử chi tiêu và hoá đơn.
11. Chi phí model thực tế nằm dưới trần, sau khi tính cả thử lại và ảnh lớn.
12. Luồng khách tạo ra phân phối thật, không chỉ tạo ra người xem rồi thôi.
13. Organizer Pro có người chịu trả tiền — **chưa được coi là mô hình kinh doanh đã chứng minh**.

**Kiểm chứng tối thiểu trước khi mở rộng:** chạy ít nhất 30 nhóm qua 2–3 lần chia tiền thật, đạt các mốc ở mục 7.

---

## 10. Sau v1 — nơi tầm nhìn ban đầu quay lại

Những phần bị cắt khỏi v1 **không bị xoá khỏi tầm nhìn**, chúng chỉ bị đặt sau cánh cổng dữ liệu.

| Giai đoạn | Điều kiện mở | Nội dung |
|---|---|---|
| **v1.5** | Vòng thu tiền đạt mốc | Bình luận gắn vào từng khoản chi (không phải chat). Tổng kết theo tháng. Chia tỉ lệ theo ngày vào/ra |
| **v2** | Retention được chứng minh ở ít nhất một cohort | Nhận diện khuôn mặt **do chính chủ tự đăng ký trên máy mình**, có consent riêng trước khi thu thập, có nút xoá và rút lại. Dùng cho điểm danh và gắn tên ảnh — **không** dùng để gán món |
| **v3** | Có đủ `verified_items` làm tập đánh giá thật | Quay video nhận món. Cần thu thập nhãn thị giác riêng — dữ liệu hoá đơn **không** thay thế được, nó chỉ cho từ vựng và tiên nghiệm |
| **v3+** | Có bằng chứng dữ liệu chi tiêu dự báo được lựa chọn địa điểm | Gợi ý địa điểm. Nếu có tài trợ thì phải gắn nhãn rõ và tách khỏi xếp hạng tự nhiên |
| **v4** | Người dùng chủ động muốn | Kỉ niệm, album chuyến đi, mạng xã hội bạn bè |

---

## 11. Phụ lục — nhật ký tranh luận

Spec này là kết quả 5 vòng tranh luận đối kháng giữa Claude và Codex. Các điểm đổi hướng lớn:

| Vòng | Ai sai | Nội dung |
|---|---|---|
| 1 | Claude | Consent sinh trắc học sau khi đã crop mặt là thu thập trước khi có sự đồng ý — vi phạm khung pháp lý mới. Ý tưởng "consent flow làm kênh tăng trưởng" bị bỏ |
| 1 | Claude | Bắt tạo nhóm trước khi chia tiền là rào cản khởi đầu quá nặng → chuyển sang session-first |
| 1 | Claude | Ma trận món × người không dùng được trên điện thoại |
| 1 | Claude | "Mở QR" bị nhầm thành "đã thanh toán" |
| 2 | Codex | Quy tắc "chờ người trả xác nhận" tự mâu thuẫn với chính cảnh báo "sổ bị treo" của nó |
| 2 | Codex | Đề xuất model gateway đa nhà cung cấp ở v1 là giải bài toán chưa tồn tại |
| 2 | Claude | Xác nhận tổng tiền không đồng nghĩa xác nhận chi tiết món → sinh ra phân biệt ba mức xác minh |
| 2 | Claude | Dữ liệu hoá đơn không phải dữ liệu huấn luyện cho nhận diện món qua video |
| 2 | Cả hai | **Phát hiện lớn nhất: việc thu tiền mới là phần đau nhất, không phải phép chia** |
| 3 | Codex | Chấp nhận lập luận "cùng một nhóm người, hai loại chi phí" — không phải chọn một trong hai |
| 3 | Claude | Bảng thu gắn với từng khoản chi sẽ biến app thành máy spam → chuyển sang đợt thu |
| 4 | Claude | "Tất toán rồi mới được rời nhóm" biến tư cách thành viên thành con tin của tranh chấp |
| 4 | Claude | Quy tắc dừng suy luận quá mạnh → thay bằng ma trận chẩn đoán 2×2 |
| 5 | — | Chốt ranh giới `published_at` cho việc bù trừ: trước khi công bố thì sửa tự do, sau khi công bố thì cần chấp thuận |
