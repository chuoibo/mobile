# Product

<!-- impeccable:product-schema 1 -->

> **Nguồn của bản ghi này.** Phiên chạy không có công cụ hỏi người dùng
> (`AskUserQuestion` không tồn tại trong tool surface, đã kiểm bằng ToolSearch),
> nên không có vòng phỏng vấn nào diễn ra. Mọi mục dưới đây rút từ ba nguồn văn
> bản đã có, và mục nào là **suy luận** thì ghi rõ `[suy luận]`:
> `/home/lakiet/mobile/product/feature_list.md` (spec 47 feature),
> `/home/lakiet/mobile/product/mockup.png` + 5 tờ trong `features/`,
> và `CLAUDE.md` của repo. Người chốt lại bản ghi này là Lead.

## Platform

adaptive

Hai bề mặt cùng tồn tại và một người dùng thấy cả hai trong một buổi tối:
người tổ chức làm việc trong app Expo (`apps/mobile/`), người được rủ mở một
link web trên điện thoại của chính họ (`services/api/app/web/`). Điện thoại là
bề mặt chính. Đây không phải "web có bản mobile"; trang khách là một chặng thật
trong vòng lặp sản phẩm, nên nó phải dùng chung hệ thiết kế chứ không phải một
hệ thứ hai.

## Stack

Đã có sẵn, không phải quyết định mở: Expo / React Native + TypeScript cho app;
FastAPI + Jinja + CSS thuần cho trang khách; `packages/shared/` là tầng dùng
chung giữa hai bề mặt (hiện có `money.mjs`, `money-format.cases.json`,
`tokens.json`).

## Users

Hội bạn người Việt, phần lớn là sinh viên và người đi làm trẻ, đi chơi và ăn
uống theo nhóm 4 tới 10 người. Trong một buổi có hai vai rõ rệt:

- **Người tổ chức.** Rủ, chốt chỗ, ứng tiền trả bill, rồi phải đòi lại. Đây là
  người chịu toàn bộ công việc khó chịu hôm nay, và là người mở app.
- **Người được rủ.** Chỉ muốn biết đúng hai điều: mình nợ bao nhiêu, và chuyển
  cho ai. Người này thường **không cài app** — họ mở một link trong chat nhóm.

Việc thật đang diễn ra: chốt chỗ ăn giữa mười ý kiến, và chia một hoá đơn mà
mỗi người gọi món khác nhau.

## Product Purpose

Đưa cả vòng "tìm chỗ đi → rủ nhau → lên kế hoạch → đi chơi → ăn uống → chia
tiền → lưu kỷ niệm" vào một app, với một AI sống bên trong từng nhóm và có
context của nhóm đó (ai thích gì, ai đã trả, ai còn nợ, nhóm từng đi đâu).

Thành công của bản PoC này là **một đường đi chạy thật, đẹp thật**, không phải
47 feature nông:

```
mở app → đăng nhập → Khám phá (AI MATCH) → vào nhóm → chat, AI gợi ý chỗ ăn
→ chốt → chụp bill → AI đọc từng món → gán món cho người → AI chia
→ kết quả + VietQR → Cá nhân thấy tài chính cập nhật
```

## Positioning

Splitwise chia tiền nhưng không biết nhóm bạn là ai và không rủ được ai đi đâu.
Nhóm chat rủ được nhưng không chia được tiền. Rủ Đi giữ **context của nhóm
xuyên suốt cả vòng**: cùng một AI đã gợi ý quán là AI đọc hoá đơn của quán đó
và biết ai đã ngồi ở đó. Đó là câu một sản phẩm hàng xóm không sao chép thật
được nếu chỉ làm một chặng.

Chốt về tiền: sản phẩm **không giữ tiền và không chuyển tiền**. Nó dựng chuỗi
VietQR để người dùng tự chuyển bằng app ngân hàng của họ.

## Operating Context

- Điện thoại, mạng di động, buổi tối, trong hoặc ngay sau bữa ăn. Người ta đang
  đứng dậy ra về khi chuyện chia tiền xảy ra.
- Hoá đơn là **ảnh chụp giấy** dưới ánh đèn quán: cong, loá, nghiêng.
- Người trả tiền chuyển khoản bằng app ngân hàng riêng, quét QR. Rủ Đi chỉ sinh
  mã; không có xác nhận ngân hàng nào chảy ngược về sản phẩm.
- Người được rủ mở link trên trình duyệt mặc định, thường không đăng nhập.

## Capabilities and Constraints

Đã chạy được và **không được viết lại**:

- Allocator chia tiền, có 41 golden vector tính tay.
- Sổ cái, máy trạng thái đợt thu, sinh chuỗi VietQR, route tài khoản nhận tiền.
- Trang khách `GET /g/{token}` với view model ở `app/web/guest_view.py`.

Ba luật về tiền, hiệu lực cả trong PoC (`CLAUDE.md`):

1. Số nguyên đồng. Không `float`, không `Decimal`.
2. `Σ` phân bổ `=` đúng tổng khoản chi, 100%.
3. Số dư luôn tính lại được từ sổ; cache không bao giờ là nguồn sự thật.

Ràng buộc riêng của tầng hiển thị:

- Template **không bao giờ tự query**. Chỉ render đúng view model backend trả về.
- Khách chỉ thấy envelope của chính mình: không số dư nhóm, không lịch sử,
  không allocation của người khác.
- `receiver_confirmed` không phải bằng chứng ngân hàng, và câu chữ không được
  nói như thể nó là.
- Câu chữ tiếng Việt, không dùng em-dash (có test bắt), không để lộ mã lỗi
  tiếng Anh ra màn hình người dùng.
- Chưa có auth production. Header `X-Actor-*` là chỗ tạm; không xây gì dựa trên
  giả định nó an toàn.

Chưa quyết: Home và cấu trúc tab (spec mục 14.3 cấm thiết kế Home trước khi
biết hành động nào tồn tại).

## Brand Commitments

Ràng buộc, vì đã có trong mockup mà leader duyệt:

- Tên và wordmark **Rủ Đi**, chữ script nghiêng, dấu hỏi trên "u" là một phần
  của hình.
- Logo là squircle **gradient cam san hô**, cam ở trên trái chuyển sang hồng
  đỏ ở dưới phải. Đo được: `#fc7b37` → `#e75262`.
- Câu định vị đã có trên mockup: "AI đi chơi, chia bill thông minh".
- Câu hiệu triệu: "Rủ Đi thôi!".
- **Ba tông chức năng**, đọc được từ mockup và mang nghĩa, không phải trang trí:
  cam = thương hiệu và hành động chính · teal = chia bill và tiền ·
  tím = AI. Xem `DESIGN.md` để biết số đo và luật dùng.
- Giọng: xưng hô thân, ngắn, không hành chính. "Rủ Đi thôi!" chứ không phải
  "Khởi tạo chuyến đi".

## Evidence on Hand

Có thật, đường dẫn cụ thể:

- `/home/lakiet/mobile/product/mockup.png` (1448×1086) — 6 màn concept.
- `/home/lakiet/mobile/product/features/02..06-*.png` (1055×1491 mỗi tờ) —
  5 tờ feature, có màn chia bill 4 bước và màn AI chat.
- `/home/lakiet/mobile/product/feature_list.md` — spec 47 feature.
- `GEMINI_API_KEY` trong `.env` ở gốc repo. Đọc được; **không** commit, không
  in ra log, không đưa vào thông báo lỗi.
- 41 golden vector allocator trong `services/api/tests/domain/golden/`.

Chưa có và **không được bịa**:

- Chưa có người dùng thật, chưa có testimonial, chưa có số liệu tăng trưởng,
  chưa có tên đối tác, chưa có đánh giá trên store.
- Chưa có bằng chứng hành vi nào (ADR-0006 gác Giai đoạn 0).
- Số liệu trong mockup (4.7 sao, 326 đánh giá, "AI MATCH 95%", tên Minh Anh /
  Quang Huy...) là **dữ liệu trình diễn**, phải dán nhãn là dữ liệu mẫu ở bất
  kỳ màn nào dùng lại chúng.
- Ảnh bill thật, số tài khoản thật, tên người tham gia thật: không bao giờ vào
  Git.

## Product Principles

1. **Vòng lặp thắng feature.** Một đường đi chạy trọn từ rủ tới chia tiền đáng
   giá hơn 47 màn không nối được với nhau.
2. **Tiền không được sai, kể cả trong PoC.** Một phép chia duy nhất trong sản
   phẩm; hai phép chia song song là cách chắc chắn nhất để hai màn hình hiện
   hai con số khác nhau cho cùng một bữa ăn.
3. **Người không cài app vẫn là người dùng hạng nhất.** Trang khách phải đẹp và
   rõ ngang màn trong app, và dùng chung hệ thiết kế.
4. **Vỏ thì nói là vỏ.** Feature nằm ngoài đường đi chính được làm đúng vỏ và
   dán nhãn. Giấu chuyện nó là vỏ mới là lỗi.
5. **AI có mặt thì phải nói rõ là AI.** Kết quả AI luôn sửa được bằng tay trước
   khi chốt; không có bước nào AI tự quyết chuyện tiền thay người dùng.

## Accessibility & Inclusion

- Chữ Việt đủ dấu là yêu cầu chức năng, không phải chi tiết đẹp: "ế ự ỡ ạ" phải
  render đúng ở mọi cỡ chữ và mọi font được chọn.
- Đích ngắm tối thiểu 44×44pt. Chuyện chia tiền xảy ra khi người ta đang đứng
  dậy ra về, một tay cầm điện thoại.
- Tương phản chữ đạt **WCAG AA: 4.5:1** cho chữ thường, **3:1** cho chữ lớn và
  cho thành phần giao diện. Đây là ràng buộc có số đo, và nó **đã buộc phải
  sửa màu của mockup** — xem bảng trong `DESIGN.md`.
- Không truyền đạt trạng thái chỉ bằng màu. Trạng thái tiền luôn kèm chữ.
- Tôn trọng `prefers-reduced-motion` và `prefers-color-scheme`.
