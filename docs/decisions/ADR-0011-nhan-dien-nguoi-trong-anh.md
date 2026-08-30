# ADR-0011 — Nhận diện người trong ảnh (F21) và gắn người với món bằng hình (F22)

- **Trạng thái:** 🟡 **BẢN THẢO** 2026-08-30 — chờ Codex tấn công
- **Ngày:** 2026-08-30
- **DRI:** Claude · **Reviewer:** Codex
- **Nguồn:** spec F21, F22 · ADR-0009 (ranh giới AI↔tiền) · CLAUDE.md (ba luật về tiền, luật dữ liệu riêng tư)
- **Chặn:** F21, F22 — và chỉ hai cái đó

> **Không ai viết code nhận diện trước khi ADR này đóng băng.** Cùng lý do
> ADR-0004 và ADR-0009 tồn tại. Ở đây lý do còn nặng hơn: hợp đồng sai trong
> allocator làm sai tiền, hợp đồng sai ở đây làm rò khuôn mặt người không có
> mặt trong phòng lúc quyết định.

## Bối cảnh

Leader đã quyết làm đủ F21/F22, sau khi tôi nêu rằng hai tính năng này khác mọi
thứ còn lại trong backlog: chúng xử lý **dữ liệu sinh trắc học của người thứ
ba**. Người bị nhận diện thường không phải người bấm nút — họ là bạn của người
bấm nút, đang ăn tối, không biết có một vector đặc trưng khuôn mặt vừa được
tính từ mặt mình.

Quyết định đó là của leader và ADR này thực thi nó, không tranh luận lại. Việc
của ADR là làm cho *cách* làm đủ trở nên an toàn được, và quan trọng hơn: làm
cho những lớp sai nguy hiểm nhất **không viết ra được**, thay vì trông chờ mọi
người nhớ.

Bài học đắt nhất của repo này tính đến hôm nay là **"bảy cánh cửa"**: mọi chỗ
nhận một danh sách danh tính người từ thân request đều ghi tiền hoặc ghi quyền
cho những người chưa ai kiểm. Chứng minh *người gọi* có quyền không nói gì về
những người *bị gọi tên*. F21 là phiên bản gắt nhất của đúng cánh cửa đó, vì ở
đây danh tính không do ai gõ vào mà do **máy suy ra**.

---

## Quyết định 1 — Đồng ý là opt-in, theo từng người, từng nhóm; mặc định TẮT

Nhận diện chỉ chạy trên những người **đã tự bật** trong **đúng nhóm đó**. Không
có đồng ý toàn cục, không có đồng ý kế thừa từ nhóm khác, không có mặc định bật.

Người vào nhóm sau không tự động được nhận diện. Người rời nhóm mất đồng ý ngay.

Lý do không phải là lễ nghi. Đồng ý toàn cục nghĩa là một người bật một lần
trong nhóm bạn thân rồi bị nhận diện trong ảnh của nhóm công ty. Đó là chính
xác cái hại mà tính năng này có khả năng gây ra, nên nó phải bị chặn ở tầng
kiểu dữ liệu chứ không ở tầng nhắc nhở.

## Quyết định 2 — Vector khuôn mặt sống trong phạm vi một nhóm, không dùng chung

Một người tham gia ba nhóm thì có **ba** bản ghi đặc trưng độc lập, khoá theo
`(context_id, person_id)`. Không có bảng khuôn mặt toàn cục.

Điều này cố ý **đắt hơn** cách làm thông thường. Đổi lại, nó khiến việc dò một
khuôn mặt ngang qua các nhóm trở thành thứ không có đường nào để viết — không
phải thứ bị cấm bằng lời.

Hệ quả kèm theo, phải ghi rõ vì nó sẽ bị coi là bug: cùng một người, cùng một
ảnh, hai nhóm khác nhau có thể ra hai kết quả khác nhau. Đó là hành vi đúng.

## Quyết định 3 — AI đề xuất, người xác nhận. Nhận diện KHÔNG BAO GIỜ tự ghi

Nhận diện sinh ra **đề xuất** kèm độ tin cậy. Nó không ghi vào
`PUT /bills/{bill_id}/assignments`, không sinh allocation, không chạm sổ.

Đường ghi duy nhất vẫn là đường đang có, vẫn do người bấm. Không có "tự động
gán khi độ tin cậy trên 95%". Không có ngưỡng nào mở được đường đó.

Đây là ADR-0009 áp cho hình ảnh: đầu ra của model **không phải một quyết định**.
Và nó là phòng tuyến cuối cùng cho luật tiền — một nhận diện sai mà tự ghi được
là tiền ghi cho người không ăn món đó.

## Quyết định 4 — Route nhận diện không có trường danh tính nào trong body

`POST /contexts/{context_id}/bills/{bill_id}/face-suggestions` nhận **ảnh**, và
không nhận gì khác. Không `person_ids`, không `candidates`, không `hints`.

Tập ứng viên được **server dựng lại** từ: thành viên của nhóm ∩ những người đã
bật đồng ý. Người gọi không có cách nào mở rộng tập đó, kể cả bằng cách nói dối.

Đây là "làm cho không viết ra được, đừng làm cho nhớ được" — cùng hình dạng với
`POST reactions` không có body và F45 nhận vùng thay vì toạ độ.

## Quyết định 5 — Rút đồng ý là xoá thật, và kéo theo mọi đề xuất chưa xác nhận

`DELETE .../face-consent` phải xoá vector đặc trưng **và** mọi đề xuất chưa được
người xác nhận có trỏ tới người đó. Không đánh dấu `revoked`, không giữ lại
"cho mục đích thống kê".

Đề xuất **đã** được người xác nhận thì giữ, vì lúc đó nó không còn là kết quả
nhận diện nữa — nó là việc một con người đã khẳng định ai ăn món gì, và nó có
thể đang gánh tiền trong sổ. Xoá nó là sửa sổ.

## Quyết định 6 — Người bị nhận diện phải thấy được điều đó

Ai bị một đề xuất nhận diện trỏ vào phải nhìn thấy đề xuất đó, và gỡ được, kể
cả khi người khác đã xác nhận nó.

Một hệ thống nhận diện mà đối tượng của nó không nhìn thấy đầu ra là hệ thống
giám sát. Khác biệt giữa hai thứ nằm ở đúng câu này.

## Quyết định 7 — Không khớp thì im lặng, không đoán ra ngoài nhóm

Khuôn mặt không khớp ai đã bật đồng ý thì kết quả là **không biết**. Không dò
sang nhóm khác, không trả về "giống người X 40%", không đếm số mặt lạ.

"Có 3 khuôn mặt không nhận ra trong ảnh của nhóm này" tự nó đã là dữ liệu về
những người chưa từng đồng ý gì.

## Quyết định 8 — Vector đặc trưng và kết quả nhận diện là dữ liệu riêng tư hạng nặng

Áp dụng đủ luật đang có, không có ngoại lệ nào:

- không bao giờ vào Git, kể cả fixture, kể cả dạng đã băm
- không bao giờ vào log, không bao giờ vào thông báo lỗi
- không bao giờ ra trang khách `/g/{token}` — trang khách không được biết nhóm
  này có bật nhận diện hay không
- ảnh đầu vào vẫn bị **tước sạch EXIF** như mọi ảnh khác trước khi lưu

## Quyết định 9 — F22 không đổi số học của tiền

F22 đổi **ai gánh phần nào**, không đổi tổng. `Σ` phân bổ vẫn đúng bằng tổng
khoản chi, 100%. Không có đường nào để nhận diện sinh ra một allocation.

Nếu một đề xuất được xác nhận làm đổi `shared_by` của một món, đó là sửa khoản
chi — nên nó tạo **phiên bản mới**, không ghi đè, đúng luật đang có.

## Quyết định 10 — Đây là cửa gọi model thứ chín, và nó có trần ngay từ PR đầu

Không để lần sau. Trần phải:

- có test chứng minh nó **không dùng chung cửa sổ** với tám cửa kia
- xử lý đúng bài học #297: nếu thả khoá trước lời gọi mạng thì phải đánh dấu
  đang-hỏi, nếu không trần thật là *số request đồng thời/phút* chứ không phải
  `n/phút`

---

## Bằng chứng bắt buộc trước khi merge

Không cái nào trong đây là tuỳ chọn, và không cái nào được thay bằng lời khai:

1. **Probe rò rỉ theo từng vai**: người ngoài nhóm · thành viên chưa bật đồng ý
   · khách trên `/g/{token}`. Khẳng định **cả số bản ghi**, không chỉ status —
   `404` với thân rỗng và `404` với thân đầy dữ liệu đọc giống hệt nhau ở
   `assert status == 404`.
2. **Đột biến chứng minh probe có răng**: đổi một phép kiểm đồng ý thành `True`,
   probe phải ĐỎ. Dán cả lần đỏ lẫn lần xanh vào PR.
3. **Hàng đối chứng giữ tính chất phải XANH**: đổi một hằng số phụ mà không đụng
   tính chất, bảng đột biến toàn đỏ thì bảng đó không phân biệt được gì.
4. **Ca rút đồng ý**: bật → sinh đề xuất → rút → khẳng định vector **và** đề xuất
   chưa xác nhận đã biến mất khỏi database thật, không phải khỏi fake repo.
5. **Ca hai nhóm**: cùng một người, cùng một ảnh, hai nhóm — nhóm chưa bật đồng ý
   phải ra "không biết". Đây là ca chứng minh Quyết định 2 có thật.

Tầng `tests/postgres` bắt buộc cho ca 4 và 5. Mở rộng fake repo rồi coi đó là
bằng chứng về database là nói dối — bảng ở CLAUDE.md đã nói thẳng.

## Cái ADR này cố ý KHÔNG quyết

- Chọn model/thư viện nhận diện nào — quyết định kỹ thuật, không phải quyết định
  về quyền.
- Ngưỡng độ tin cậy hiển thị — thuộc về câu chữ giao diện.
- Có cho nhận diện trong ảnh **kỷ niệm** (F35) không. ADR này chỉ mở cho ảnh
  **hoá đơn/món ăn** trong phạm vi F21/F22. Muốn mở rộng sang tường kỷ niệm thì
  mở ADR mới — phạm vi rộng ra là quyết định riêng, không phải hệ quả.
