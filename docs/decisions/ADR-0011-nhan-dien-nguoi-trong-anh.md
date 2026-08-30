# ADR-0011 — Nhận diện người trong ảnh (F21) và gắn người với món bằng hình (F22)

- **Trạng thái:** 🟡 **BẢN THẢO v4** 2026-08-30 — **đổi hướng thiết kế**: gom cụm rồi tự nhận, thay cho ghi danh
- **Ngày:** 2026-08-30
- **DRI:** Claude · **Reviewer:** Codex
- **Nguồn:** spec F21, F22 · ADR-0009 (ranh giới AI↔tiền) · AGENTS.md (luật dữ liệu riêng tư) · CLAUDE.md (ba luật về tiền)
- **Chặn:** F21, F22 — và chỉ hai cái đó

> **Không ai viết code nhận diện trước khi ADR này đóng băng.** Cùng lý do
> ADR-0004 và ADR-0009 tồn tại. Ở đây lý do nặng hơn: hợp đồng sai trong
> allocator làm sai tiền, hợp đồng sai ở đây làm rò khuôn mặt người không có
> mặt trong phòng lúc quyết định.

## Bối cảnh

Leader đã quyết làm đủ F21/F22. ADR này thực thi quyết định đó và không tranh
luận lại nó. Việc của nó là làm cho những lớp sai nguy hiểm nhất **không viết
ra được**, thay vì trông chờ mọi người nhớ.

Bài học đắt nhất của repo tính đến hôm nay là **"bảy cánh cửa"**: mọi chỗ nhận
một danh sách danh tính người từ thân request đều ghi tiền hoặc ghi quyền cho
những người chưa ai kiểm. F21 là phiên bản gắt nhất của đúng cánh cửa đó, vì ở
đây danh tính không do ai gõ vào mà do **máy suy ra**.

## v4 — vì sao đổi hướng, và nó bịt được cái gì

Ba vòng tấn công dừng ở một lỗ không vá được bằng câu chữ: **A ghi danh mặt B
dưới lần đồng ý của A.** Ràng buộc "tự mình cho mình" chứng minh được A đang ghi
danh *cho A*; không câu lệnh nào chứng minh **khuôn mặt trong ảnh** là mặt A.

Lỗ nằm ở **bước ghi danh**. Nên v4 bỏ hẳn bước đó.

**Gom cụm, đừng nhận dạng.** Máy nhóm các khuôn mặt trong ảnh **nhóm đã có** thành
những cụm **vô danh** — "khuôn mặt này xuất hiện ở bảy tấm" — chứ không hỏi họ là
ai. Rồi mỗi thành viên **nhận cụm của chính mình, một lần**, và từ đó mọi ảnh cũ
lẫn mới có họ đều tự gán.

Đổi lại được ba thứ cùng lúc:

- **Không còn đường tiêm mặt người ngoài.** Không có chỗ nào để tải một tấm ảnh
  lên rồi khai là mình. Chỉ nhận được cụm **đã tồn tại sẵn** trong ảnh nhóm đã
  chia sẻ. Lỗ của v3 biến mất vì cái cửa nó đi qua không còn tồn tại.
- **Tiện hơn hẳn.** Một cái bấm duy nhất, áp ngược lại toàn bộ ảnh cũ — thay vì
  mỗi tấm ảnh mỗi người bấm một lần.
- **Tự sửa được trong nhóm nhỏ.** Một cụm chỉ một người nhận. A nhận nhầm cụm của
  B thì B không nhận được nữa và **thấy ngay**.

**Phần dư, nói thẳng:** A vẫn có thể nhận cụm của B **trước** B. Cái đó không biến
mất. Nhưng nó khác hẳn về mức độ — nhìn thấy được, tranh chấp được, thu hồi được,
và chỉ mở cho người **đã ở sẵn trong nhóm**; khác với lỗ cũ vốn âm thầm và mở cho
cả người ngoài. Ghi nhận là rò rỉ dư được chấp nhận có ý thức.

### Thứ KHÔNG sửa được, và nó đúng với mọi hướng nhận diện

Codex chỉ ra một tính chất mà tôi phải ghi ở đầu ADR chứ không giấu ở cuối:

> Phải tính vector và gom cụm **trước khi** biết cụm nào là của ai. Nên một người
> bật đồng ý sẽ khiến máy xử lý khuôn mặt của **mọi người trong ảnh** — kể cả
> người chưa đồng ý và người ngoài nhóm. Quyết định 1 *"chỉ chạy trên người đã tự
> bật"* **không thực thi được ở bước gom cụm**: đồng ý đến sau xử lý sinh trắc học.

Đúng, và tôi kiểm lại thì thấy nó **không riêng của v4**. Bất kỳ hình thức nhận
diện nào cũng phải tính đặc trưng cho *mọi* khuôn mặt trong ảnh rồi mới so được
với người đã đồng ý. Hướng "ghi danh" của v3 cũng thế; hướng "camera sống" cũng
thế. Khác biệt giữa các hướng chỉ nằm ở **cái gì được giữ lại**, không ở **cái gì
được xử lý**.

Đường duy nhất không có tính chất này là **không nhận diện** — chỉ khoanh ô vuông
vô danh, vì một cái ô không phải danh tính sinh trắc học. Đó là `#303`, đã làm xong.

Nên đây là thứ được **chấp nhận có ý thức** khi chọn làm F21, không phải thứ ADR
này sót. Giảm thiểu tối đa: xử lý trong bộ nhớ, không đếm, không ghi "có mặt lạ",
và mọi vector không thuộc cụm nào được nhận đều rơi vào hạn sống ở 2b-i.

**Bản v2 sửa năm chỗ Codex bắn thủng bản v1.** Bốn cái là lỗ thật trong hợp
đồng; cái thứ năm lôi ra một mâu thuẫn đã tồn tại sẵn trong repo, không do F21
sinh ra — ghi ở cuối, dành cho leader.

---

## Quyết định 1 — Đồng ý là opt-in, theo từng người, từng nhóm; mặc định TẮT

Nhận diện chỉ chạy trên những người **đã tự bật** trong **đúng nhóm đó**. Không
có đồng ý toàn cục, không kế thừa từ nhóm khác, không mặc định bật.

Đồng ý là **tự mình bật cho mình**: không ai bật hộ ai, kể cả chủ nhóm. Và nó
riêng cho F21/F22, không phải một ô "đồng ý dùng AI" chung — đồng ý cho bot đọc
chat không phải đồng ý cho máy đo khuôn mặt.

Lý do không phải lễ nghi. Đồng ý toàn cục nghĩa là một người bật một lần trong
nhóm bạn thân rồi bị nhận diện trong ảnh nhóm công ty.

## Quyết định 2 — Vector khuôn mặt thuộc về một *lần đồng ý*, không thuộc về một người

Khoá không phải `(context_id, person_id)` như bản v1 viết. Nó là
**`consent_grant_id`**: mỗi lần một người bật đồng ý là một grant mới, vector
sinh ra thuộc grant đó, và rút đồng ý là kết thúc grant đó cùng mọi vector treo
dưới nó.

Bản v1 sai ở đây và Codex chỉ đúng chỗ: `(context_id, person_id)` **không phân
biệt được kỳ đồng ý cũ với kỳ mới**. Rời nhóm rồi vào lại tạo membership row
mới, nhưng khoá cũ thì trùng — nên vector của kỳ trước có thể sống lại dưới một
lần đồng ý mà người ta chưa hề bật lại.

**Bản v1 còn nói dối một câu, xoá đi:** *"dò một khuôn mặt ngang qua các nhóm là
thứ không viết ra được"*. Sai. Khoá tổ hợp không ngăn được một câu query quên
`context_id`. Và trong cây hiện tại đã có sẵn **hai kho toàn cục thật**:

1. **Avatar.** `uploaded_images` có ràng buộc `num_nonnulls(context_id,
   owner_person_id) = 1` — tức một ảnh thuộc *hoặc* nhóm *hoặc* một người. Ảnh
   đại diện thuộc về **người**, không thuộc nhóm nào. ⇒ **Avatar không bao giờ
   được dùng làm nguồn ghi danh khuôn mặt.** Dùng nó là biến kho avatar thành
   kho sinh trắc học toàn cục, đúng cái Quyết định này tồn tại để chặn.
2. **`idempotency_keys`.** Middleware bọc mọi `POST` và giữ **nguyên văn thân
   phản hồi dạng bytes** để phát lại. Bảng không có `context_id`, không có TTL.
   ⇒ Một phản hồi chứa đề xuất nhận diện có thể sống sót qua lệnh rút đồng ý.
   **Các route của F21/F22 phải nằm ngoài cơ chế ghi lại đó**, hoặc bản ghi phải
   xoá được bằng chính đường rút đồng ý — chọn cái nào thì nói rõ trong PR và
   chứng minh bằng ca postgres.

`audit_events.event_data`, cache của model, và index ANN toàn bảng là ba đường
tiếp theo cùng loại. PR phải nói rõ nó xử lý chúng thế nào.

**Rời nhóm đóng grant, kể cả khi không ai bấm rút.** Grant treo dưới đúng *đời*
membership sinh ra nó. Vòng `bật → rời (không rút) → vào lại` phải sinh grant
mới; vector của đời trước chết theo đời trước. Không có cái này thì `consent_grant_id`
chỉ đổi tên cho lỗ cũ chứ không bịt nó — vì "chưa ai bấm rút" không có nghĩa là
"vẫn còn đồng ý".

Hệ quả phải ghi vì sẽ bị coi là bug: cùng một người, cùng một ảnh, hai nhóm khác
nhau có thể ra hai kết quả khác nhau. Đó là hành vi đúng.

## Quyết định 2b (v4) — **Không có bước ghi danh nào cả.** Cụm sinh ra từ ảnh nhóm đã có

Thay cho toàn bộ Quyết định 2b của v3, đã bỏ.

- Vector chỉ tính từ **ảnh nhóm đã chia sẻ trong đúng nhóm đó**. Không có đường
  nào để tải một tấm ảnh lên riêng cho việc ghi danh.
- Vector của một khuôn mặt **chưa ai nhận** là dữ liệu tạm: nó sống đủ lâu để
  gom cụm rồi bị xoá, **trừ khi** có người nhận cụm đó. Người không bao giờ nhận
  thì hệ thống không giữ gì lâu dài về họ.
- Một người, một nhóm, **một cụm**. Nhận cụm là một hành động của actor cho chính
  actor; không ai nhận hộ ai.
- **Nhận cụm phải thấy được với cả nhóm**, và **thu hồi được**. Đây là thứ thay
  cho mọi phép kiểm mật mã mà ta không có: trong một nhóm bạn bè, một lời khai
  sai về mặt ai là chuyện nhìn thấy và cãi được.
- Bỏ nhận cụm thì mọi phần gán suy ra từ nó **mất hiệu lực về sau**, và vector
  của cụm bị xoá.

Đây cũng là chỗ v3 sai mà không tự thấy: nó cố kiểm *ảnh ghi danh có đúng mặt
người bấm không* — một câu hỏi không trả lời được — thay vì bỏ đi cái bước đẻ ra
câu hỏi đó.

### 2b-i — "tạm" phải là một con số, không phải một ý định

v4 bản đầu viết vector chưa ai nhận là "dữ liệu tạm". Codex chỉ đúng: không TTL,
không dọn khi job lỗi, và **muốn ghép ảnh mới vào cụm cũ thì vẫn phải giữ
centroid** — mà centroid cũng là dữ liệu sinh trắc học. "Tạm" như thế là một
cache không ai xoá.

Chốt bằng số:

- Cụm chưa ai nhận có **hạn sống cứng 7 ngày** kể từ lần chạm cuối. Hết hạn thì
  xoá vector **và** centroid, không đánh dấu.
- Có **một reaper chạy định kỳ**, và nó phải có ca chứng minh nó thật sự xoá —
  không phải một `DELETE` chưa ai gọi. Xem lại bài học "cổng mặc định là đồ
  trang trí".
- Job chết giữa chừng thì vector mồ côi vẫn nằm trong tầm reaper, vì hạn sống
  tính theo *thời điểm ghi*, không theo *trạng thái job*.
- Điều này **thu hẹp Quyết định 7**: câu "mặt không khớp thì không lưu gì, kể cả
  tạm" giữ nguyên cho **kết quả trả về**, nhưng bước gom cụm buộc phải giữ vector
  trong hạn trên. Nói ra chỗ mâu thuẫn thay vì để hai câu đá nhau.

### 2b-ii — Cụm sống ở vùng nháp **của riêng một nhóm**

Không bảng cụm dùng chung, **không ANN index toàn bảng**. `context_id` là điều
kiện query, không phải ranh giới — chính v2 đã ghi điều đó khi nói về hai kho
toàn cục có sẵn (`uploaded_images`, `idempotency_keys`). Một bảng cụm phẳng cho
mọi nhóm sẽ là **kho thứ ba**, và lần này là kho sinh trắc học.

### 2b-iii — Bỏ nhận cụm **không** sửa sổ

v4 bản đầu viết "mọi phần gán suy ra từ cụm mất hiệu lực về sau". Sai, và sai
đúng kiểu Codex đã bắt ở Quyết định 5 vòng một: làm thế là **đổi số dư mà sổ
không có phiên bản mới**. Tệ hơn, Quyết định 5 đã xoá sạch dấu vết nguồn máy, nên
sau đó **không tìm lại được** phần gán nào đến từ cụm.

Chốt: bỏ nhận cụm chỉ xoá **cụm** và **đề xuất chưa xác nhận**. Phần gán **đã
xác nhận** là quyết định của một con người và chỉ đổi được bằng **một phiên bản
khoản chi mới**, như mọi sửa đổi khác.

## ~~Quyết định 2b (v3) — Ghi danh là tự mình, từ ảnh chụp tại chỗ~~ *(đã thay bằng v4 ở trên)*

Cấm avatar rồi thì phải nói nguồn ghi danh là gì, nếu không mỗi người tự chế một
nguồn.

- Ghi danh **self-only**: `actor.id == person_id`, không ai ghi danh hộ ai.
- Nguồn là **một ảnh chụp trong luồng ghi danh**, gắn với đúng grant đang mở.
- Tính xong vector thì **xoá ảnh ghi danh**. Nó không phải kỷ niệm, không phải
  avatar, không có lý do gì để sống tiếp.
- Một người, một nhóm, **một grant mở tại một thời điểm**.

**Phần này có một lỗ không bịt được, ghi thẳng ra:** không có cách nào chứng minh
khuôn mặt trong ảnh ghi danh đúng là mặt người đang bấm. Ai đó có thể ghi danh
mặt bạn mình vào grant của chính mình. Cái chặn thiệt hại là Quyết định 6b —
đề xuất chỉ hiện cho người *bị nhận diện*, mà ở đây người đó chính là kẻ ghi
danh, nên thứ họ thu được đúng bằng thứ họ đã tự mang vào. Vẫn là rò rỉ dư, vẫn
được ghi nhận là đã biết, không giả vờ là đã kín.

## Quyết định 3 — AI đề xuất, người xác nhận. Nhận diện KHÔNG BAO GIỜ tự ghi

Nhận diện sinh ra **đề xuất** kèm độ tin cậy. Nó không ghi vào
`PUT /bills/{bill_id}/assignments`, không sinh allocation, không chạm sổ.

Không có "tự động gán khi độ tin cậy trên 95%". Không ngưỡng nào mở được đường
đó. Đây là ADR-0009 áp cho hình ảnh: đầu ra của model **không phải một quyết
định**. Và nó là phòng tuyến cuối cho luật tiền — một nhận diện sai mà tự ghi
được là tiền ghi cho người không ăn món đó.

## Quyết định 4 — Route không có trường danh tính nào trong body, và cả hai selector trên đường dẫn đều bị khoá

`POST /contexts/{context_id}/bills/{bill_id}/face-suggestions` **không có thân
request nào cả** — không ảnh, không `person_ids`, không `candidates`, không
`hints`.

Bản v2 nói route "nhận ảnh" ở đây rồi lại nói ở Quyết định 7 rằng nó chỉ xử lý
ảnh bất biến đã gắn phía server. Đó là hai hợp đồng khác nhau và Codex chỉ đúng.
Chốt bản sau: route **đặt tên** cái bill, và server tự lấy tấm ảnh đã gắn sẵn với
bill đó. Người gọi không đưa vào pixel nào.

Điều này làm cả một lớp tấn công không viết ra được: không có chỗ để bắn một
khuôn mặt tuỳ ý vào mà dò, nên route không thể bị dùng làm máy tra "người này có
trong nhóm không". Cùng lý do `POST reactions` không có body.

Tập ứng viên do server dựng lại, và bản v1 mô tả nó quá lỏng. Đúng phải là:

- **`bill.context_id == context_id` trên đường dẫn.** Hai selector đều do người
  gọi điều khiển; không khoá lại thì người gọi ghép một bill của nhóm này với
  danh sách ứng viên của nhóm kia.
- **Membership `ACTIVE`, không phải "chưa rời"**. `list_members()` hiện chỉ lọc
  `left_at IS NULL`, nên nó **trả về cả người mới được mời chưa nhận**. Người
  được mời chưa vào nhóm mà đã nằm trong tập ứng viên nhận diện là sai.
- **Giao với grant đồng ý còn hiệu lực**, join **cùng một câu**, không phải hai
  lượt đọc rồi lọc trong Python.
- **Kiểm lại grant ngay trước khi lưu và trước khi trả kết quả.** Một job đang
  chạy dở không được phép làm vector sống lại sau khi người ta đã rút.

Người gọi không có cách nào mở rộng tập đó, kể cả bằng cách nói dối. Đây là "làm
cho không viết ra được, đừng làm cho nhớ được" — cùng hình dạng với
`POST reactions` không body và F45 nhận vùng thay vì toạ độ.

## Quyết định 5 — Rút đồng ý xoá được MỌI đầu ra sinh trắc học, kể cả cái đã dùng

Bản v1 giữ lại đề xuất **đã** xác nhận, vì nó có thể đang gánh tiền trong sổ.
**Sai, và Codex chỉ đúng chỗ sai:** tôi giữ nhầm đối tượng. Nó còn mâu thuẫn
thẳng với Quyết định 6.

Cái sổ cần không phải kết quả nhận diện. Cái sổ cần là **một con người đã khẳng
định ai ăn món gì**. Hai thứ đó tách được, nên tách:

- Lúc xác nhận, hệ thống ghi một bản ghi **quyết định của con người** (ai bấm,
  lúc nào, gán ai vào món nào) và sinh **phiên bản khoản chi mới**.
- Rồi **xoá** đề xuất: vector, độ tin cậy, khung cắt mặt, và mọi dấu vết cho
  biết cái gán này từng đến từ máy.
- Rút đồng ý xoá mọi đề xuất **chưa** xác nhận ngay lập tức.
- Người bị gắn "gỡ" mình ra sau khi đã vào sổ thì sinh **phiên bản/điều chỉnh
  mới**, không xoá lịch sử cũ.

Sổ vẫn tính lại được từ chính nó, và không dòng nào trong sổ là đầu ra sinh trắc
học. Bất biến 3 giữ nguyên; quyền riêng tư không phải trả giá.

## Quyết định 6 — Người bị nhận diện phải thấy được điều đó

Ai bị một đề xuất trỏ vào phải nhìn thấy nó, và gỡ được, kể cả khi người khác đã
xác nhận.

Một hệ thống nhận diện mà đối tượng của nó không nhìn thấy đầu ra là hệ thống
giám sát. Khác biệt giữa hai thứ nằm ở đúng câu này.

## Quyết định 6b — Đề xuất **chưa** xác nhận chỉ người bị nhận diện thấy. Chốt, không để ngỏ

v2 để quyền của người tổ chức ở dạng "nếu", và để ngỏ thì mỗi người triển khai
một kiểu. Chốt:

- Đề xuất chưa xác nhận **chỉ hiện cho đúng người bị nhận diện**. Người tải ảnh
  lên, chủ nhóm, và mọi thành viên khác thấy đúng một trạng thái: *"tự gán tay"*
  — giống hệt lúc máy không nhận ra ai.
- Người đó xác nhận thì phần gán trở thành **một phần gán bình thường**, cả nhóm
  thấy, và **không phân biệt được với một phần gán do người ta tự bấm**.
- Không ai xác nhận hộ ai.

Cái này trả giá bằng sản phẩm và tôi ghi rõ để không ai tưởng là miễn phí: luồng
"chủ nhóm ngồi gán cả bàn trong ba mươi giây" **không tồn tại**. Đổi lại, không
ai nhận được một phỏng đoán của máy về khuôn mặt người khác, và **quyền thấy/gỡ
ở Quyết định 6 áp cho mọi bản ghi gán người, bất kể nguồn** — nên nó không cần
biết cái gán đó từng đến từ máy hay không, và mâu thuẫn Codex chỉ ra giữa QĐ5
với QĐ6 biến mất.

## Quyết định 7 — Không khớp thì im lặng; và phần rò rỉ còn lại được ghi nhận, không giả vờ là không có

Khuôn mặt không khớp ai đã bật đồng ý thì kết quả là **không biết**. Không dò
sang nhóm khác, không trả "giống người X 40%", không đếm số mặt lạ.

Nhưng bản v1 dừng ở đó là tự lừa mình. **Chính việc có hay không có đề xuất đã
là một bit.** Người gọi bắn cùng một ảnh nhiều lần, hoặc bắn từng khung cắt, thì
route trở thành một cỗ máy trả lời hai câu: *"người này có trong nhóm không"* và
*"người này đã bật đồng ý chưa"*. Đồng nhất status/thân/thời gian chỉ giấu được
người nghe lén, không giấu được chính người gọi hợp lệ.

Bịt được đến đâu thì bịt, và Quyết định 4 với 6b đã bịt phần lớn:

- Route **không có thân request**, nên không có chỗ bắn một khuôn mặt tuỳ ý vào.
- Mỗi ảnh chạy **một lần**, quota theo `(actor, context, bill)`.
- Đề xuất chưa xác nhận **chỉ người bị nhận diện thấy**, nên người tải ảnh lên
  không đọc được bit nào — với họ, "khớp" và "không khớp" trông hệt nhau.

**Khuôn mặt không khớp thì không được lưu lại gì.** Không vector, không khung
cắt, không đếm, không cờ "có mặt lạ" — kể cả tạm, kể cả trong thân phản hồi.
Người trong ảnh mà không có grant thì **không có đường nào để rút**, nên thứ duy
nhất an toàn là chưa từng ghi. Đây là chỗ Codex chỉ ra và v2 bỏ sót.

**Phần còn lại không bịt được:** chính người bị nhận diện vẫn học được rằng mình
xuất hiện trong một tấm ảnh của nhóm. Đó là thông tin về **chính họ**, nên nó
chấp nhận được — nhưng ghi ra đây để không ai đọc dòng xanh thành "đã kín".

## Quyết định 8 — Vector đặc trưng và kết quả nhận diện là dữ liệu riêng tư hạng nặng

- không bao giờ vào Git, kể cả fixture, kể cả dạng đã băm
- không bao giờ vào log, không bao giờ vào thông báo lỗi
- không bao giờ ra trang khách `/g/{token}` — khách không được biết nhóm này có
  bật nhận diện hay không
- ảnh đầu vào vẫn bị **tước sạch EXIF** như mọi ảnh khác trước khi lưu

## Quyết định 9 — F22 không đổi số học của tiền

F22 đổi **ai gánh phần nào**, không đổi tổng. `Σ` phân bổ vẫn đúng bằng tổng
khoản chi, 100%. Không có đường nào để nhận diện sinh ra một allocation.

Đề xuất được xác nhận làm đổi `shared_by` của một món thì đó là **sửa khoản
chi** ⇒ tạo phiên bản mới, không ghi đè.

## Quyết định 10 — Model chạy **cục bộ**. Không có lời gọi ra dịch vụ ngoài

Bản v1 mặc nhiên coi đây là "quyết định kỹ thuật, không phải quyết định về
quyền" và đẩy nó ra khỏi phạm vi. Sai. AGENTS.md viết thẳng:

> **Never put in Git, and never send to an external service**: bill photos, bank
> account numbers, participant names, raw transcripts, exports, a real `.env`.

Ảnh bàn ăn có mặt người là dữ liệu người tham gia. Nên: **suy luận chạy trong
tiến trình của service, không gọi ra ngoài.** Bộ sinh vector đặt sau một seam để
test thay được bằng bản giả tất định — seam đó **không phải** chỗ để lén cắm một
client mạng vào.

**File model nằm trong ảnh Docker, không nằm trong Git.** Đo được: `cv2.FaceRecognizerSF`
và `cv2.FaceDetectorYN` có sẵn trong OpenCV đang dùng, cộng `onnxruntime`. Trọng số
SFace là một file `.onnx` **38,7 MB** — tải lúc `docker build` (Dockerfile đã có
mạng ở bước `pip install`), **ghim bằng `sha256`**, và không bao giờ commit. Repo
guard fail-closed với nhị phân là đúng và không được nới ra vì việc này.

Vì không còn hạn mức của nhà cung cấp, trần nhịp ở đây không phải để giữ tiền mà
để giữ CPU: vẫn phải có, vẫn phải chứng minh **không dùng chung cửa sổ** với các
cửa gọi model khác, và vẫn phải xử lý đúng bài học #297 — thả khoá trước phần
tính nặng thì phải đánh dấu đang-chạy, nếu không trần thật là *số request đồng
thời/phút*.

---

## Bằng chứng bắt buộc trước khi merge

Không cái nào tuỳ chọn, không cái nào thay được bằng lời khai:

1. **Probe rò rỉ theo từng vai**: người ngoài nhóm · thành viên chưa bật đồng ý
   · **người mới được mời chưa nhận** · khách trên `/g/{token}`. Khẳng định **cả
   số bản ghi**, không chỉ status — `404` thân rỗng và `404` thân đầy dữ liệu
   đọc giống hệt nhau ở `assert status == 404`.
2. **Đột biến chứng minh probe có răng**: đổi một phép kiểm đồng ý thành `True`,
   probe phải ĐỎ. Dán cả lần đỏ lẫn lần xanh vào PR.
3. **Hàng đối chứng giữ tính chất phải XANH**: đổi một hằng số phụ mà không đụng
   tính chất. Bảng đột biến toàn đỏ thì bảng đó không phân biệt được gì.
4. **Ca rút đồng ý**, ở **tầng postgres thật**: bật → sinh đề xuất → xác nhận một
   cái → rút. Khẳng định vector và đề xuất chưa xác nhận đã biến mất, bản ghi
   quyết định của con người còn nguyên, và **số dư tính lại vẫn đúng**.
5. **Ca vào lại nhóm**, tầng postgres, **hai biến thể**: `bật → rút → vào lại`
   **và** `bật → rời mà KHÔNG rút → vào lại`. Vector của kỳ trước không được
   sống lại ở cả hai. Biến thể thứ hai mới là ca thật — biến thể thứ nhất đi
   vòng qua đúng chỗ khó.
5b. **Ca mặt không khớp**: chạy trên ảnh có một khuôn mặt không thuộc ai có grant.
   Khẳng định **không hàng nào** được ghi ở bảng vector, bảng đề xuất, hay
   `audit_events` — đếm hàng trước và sau, không chỉ đọc phản hồi.
5c. **Ca người khác không thấy**: đề xuất chưa xác nhận, đọc bằng chủ nhóm và
   bằng người tải ảnh lên. Cả hai phải thấy đúng trạng thái "tự gán tay", không
   phân biệt được với ca máy không nhận ra ai.
6. **Ca hai nhóm**: cùng người, cùng ảnh, nhóm chưa bật đồng ý phải ra "không
   biết".
7. **Ca `idempotency_keys`**: gửi kèm khoá idempotency, rút đồng ý, rồi phát lại
   đúng request đó. Không được trả lại đề xuất đã xoá.

Mở rộng fake repo rồi coi đó là bằng chứng về database là nói dối — bảng ở
CLAUDE.md đã nói thẳng.

## Câu hỏi treo cho leader — không do F21 sinh ra

Trong lúc kiểm điểm số 5 của Codex, lộ ra một mâu thuẫn **đã có sẵn**:

AGENTS.md cấm gửi **ảnh bill** ra dịch vụ ngoài. Nhưng đường hero đang chạy hôm
nay — `POST /receipts/scan` và `POST /screenshots/scan` — gửi thẳng bytes ảnh ra
Gemini (`screenshot_gemini.py`, `types.Part.from_bytes(...)`). CLAUDE.md bản
tiếng Việt chỉ cấm *đưa vào Git*, không có vế "dịch vụ ngoài"; hai file lệch
nhau.

Nên một trong hai điều sau đang đúng, và chỉ leader chốt được:

- **(a)** Luật đúng như viết ⇒ đường quét bill hiện tại đang vi phạm và cần một
  quyết định riêng.
- **(b)** Luật ý nói hẹp hơn (ví dụ chỉ cấm trong lúc FIELD-GATE còn đóng, hoặc
  chỉ cấm dữ liệu thật) ⇒ **AGENTS.md phải sửa cho khớp cái mình thật sự làm**.

ADR này **không chờ** câu trả lời đó: nó khoá F21/F22 chạy cục bộ, nên nó không
mở rộng vi phạm dù câu trả lời là gì.

## Cái ADR này cố ý KHÔNG quyết

- Chọn kiến trúc/thư viện model cục bộ nào.
- Ngưỡng độ tin cậy hiển thị — thuộc về câu chữ giao diện.
- Có cho nhận diện trong ảnh **kỷ niệm** (F35) không. ADR này chỉ mở cho ảnh
  **hoá đơn/món ăn**. Mở rộng phạm vi là quyết định riêng, không phải hệ quả.
