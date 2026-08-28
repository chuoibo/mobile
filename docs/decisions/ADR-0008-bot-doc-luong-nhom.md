# ADR-0008 — Bot đọc luồng nhóm, lật ràng buộc §5.1

- **Trạng thái:** 🟡 **ĐÃ QUYẾT** 2026-08-27, chờ Codex review
- **Ngày:** 2026-08-27
- **DRI:** Chủ sản phẩm · **Ghi chép:** Claude · **Reviewer:** Codex
- **Lật:** spec mục 5.1, gạch đầu dòng 3
- **Chặn:** `money_skill` (bước 3 của mục 14.3), toàn bộ demo

## Quyết định

Chủ sản phẩm mô tả sản phẩm là **người đi thông báo**: được tag hỏi "chuyến đi
chơi này tốn bao nhiêu tiền", nó chia rõ ràng ra.

Khi được hỏi các khoản chi từ đâu ra, chủ sản phẩm chọn: **bot đọc lại cả luồng
chat**. Mặt tiếp xúc là luồng nhóm trong app của mình.

Điều này trái với spec mục 5.1:

> Bot **không đọc thụ động cả luồng**. Mỗi lần gọi có một *context snapshot*
> tường minh.

Ràng buộc đó đã được nêu ra trước khi chọn, và chủ sản phẩm vẫn chọn. Đây là
quyết định của chủ sản phẩm, không phải sơ suất. Spec mục 5.1 nay **hết hiệu
lực** ở phần cấm đọc thụ động.

Tiền lệ: dòng 946 của spec ghi lần can thiệp trước, khi chủ sản phẩm mở lại
quyết định "không có chat" và tạo ra chính mô hình triệu hồi này.

## Vì sao ràng buộc cũ tồn tại, và cái gì thay chỗ nó

Bỏ một rào chắn mà không thay gì vào chỗ nó là cách người ta mất tiền của người
khác. Bốn thứ mục 5.1 đang giữ, và cách xử lý từng thứ:

### 1. Riêng tư

Đọc cả luồng nghĩa là đọc cả những gì không liên quan tới tiền. Mục 9 và mục 10
dựng trên nguyên tắc hiển thị **fail-closed**; đọc thụ động là chiều ngược lại.

**Thay bằng:** bot chỉ đọc **khi được gọi**, trên một khoảng tường minh, và
`context_manifest` của mục 5.4 phải khai đúng nó đã đọc từ đâu tới đâu. Không
có bộ nhớ chung của nhóm theo mặc định — ràng buộc đó của mục 5.1 vẫn còn.

### 2. Trần chi phí

Đọc cả một chuyến đi tốn nhiều token hơn đọc một câu. Trần token, timeout, số
tool call của mục 5.1 **vẫn nguyên hiệu lực** và giờ quan trọng hơn trước.

### 3. Độ chính xác — đây là rủi ro nặng nhất

Suy ra "ai trả bao nhiêu" từ tiếng Việt nói chuyện phiếm khó hơn nhiều so với
đọc một câu người ta cố ý viết cho bot. Model sẽ sai thường xuyên hơn.

**Ranh giới mục 3 chính là thứ giữ cho việc này không thành thảm hoạ.** Model
chỉ **trích xuất** ra cấu trúc; allocator **tính**. Nên một lần đọc sai hiện ra
thành một đề xuất sai mà người phải duyệt, chứ không thành số học sai. Bất biến
`Σ allocated_vnd == total_vnd` vẫn đúng 100% dù model đọc nhầm gì đi nữa.

### 4. Không kiểm chứng được

Một bot nói "chuyến này hết 3 triệu 2" mà không nói vì sao thì không ai kiểm
được. Đây là chỗ mục 5.1 im lặng vì nó chưa bao giờ dự tính tình huống này.

**Ràng buộc mới, bắt buộc:** mỗi khoản chi bot trích ra **phải trỏ về đúng tin
nhắn nó đọc được khoản đó**. Không có trích dẫn thì người duyệt không duyệt
được gì cả, họ chỉ có thể bấm đồng ý. Mục 15 cảnh báo đúng điều này: *"không có
sửa đổi vật chất" đo hành vi sửa, không đo độ chính xác* — có thể chỉ nghĩa là
người dùng bấm nhanh.

## Hệ quả

- Cổng xác nhận ở mục 8.3 chuyển từ *nên có* sang **thứ duy nhất đứng giữa một
  lần đọc sai và một lời buộc nợ sai**. Không được nới.
- `context_manifest` phải khai khoảng tin nhắn đã đọc, không được để trống.
- Renderer của đề xuất phải hiện trích dẫn nguồn cho từng khoản.
- Chỉ số mục 15 cần tách `accepted_without_edit` khỏi `verified_correct` — với
  đầu vào là chat tự do, khoảng cách giữa hai con số này sẽ rộng hơn nhiều.

## Cái không đổi

- Mục 3: AI không bao giờ tự tính tiền.
- ADR-0004: hợp đồng allocator vẫn đóng băng, 41 golden vector vẫn là chuẩn.
- Mục 5.1 phần còn lại: không có primitive nhắn tin tự do, không có bộ nhớ
  chung theo mặc định, trần token và số lần hỏi lại.
- Mục 5.3: chip sinh từ capability registry, gõ tự do là đường cho người thạo.

## Ngoài phạm vi lần này

Thu tiền. Chủ sản phẩm đã chốt: bot chỉ chia rõ ràng, chưa thu. `CollectionBatch`,
trang khách, VietQR, luồng phản đối — **đem cất, không xoá**. Chúng đã xong và
đã kiểm chứng trên Postgres thật; chúng chỉ không nằm trên đường tới demo.
