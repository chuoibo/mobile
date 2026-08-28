# Kế hoạch tới Demo B — cái gì còn chặn, và ai gỡ

> Viết ngày 2026-08-28 sau khi merge 14 PR. Đối chiếu spec mục 14.3 với
> `main` thật, không với trí nhớ.

## Đã có trên `main`

| Mục 14.3 | Trạng thái |
|---|---|
| 1. Hợp đồng kỹ năng, phân quyền, ma trận hiển thị, máy trạng thái thu tiền | ✅ |
| 2. Lõi tiền: sổ, bất biến, allocator, 41 golden vector | ✅ |
| 2. **Danh tính và phân quyền tối thiểu** | 🟡 schema xong, **routes chưa** |
| 3. `money_skill` đề xuất có kiểu | 🟡 validator + corpus 6/12, **chưa có extractor thật** |
| 4. `CollectionBatch`, trang khách, VietQR, xác nhận nhận tiền | ✅ |
| 5. Nhóm đã lưu, quyền xem lịch sử, vòng đời thành viên | ❌ |
| 6. Hộp thư hành động, lịch sử invocation, Home | ❌ (spec cấm làm trước) |

## Bốn thứ còn chặn một buổi demo cho khách

### 1. App chưa nối API — `OFFLINE = true`

`apps/mobile/src/api.ts` vẫn phát lại fixture. Người xem demo gõ một số
tiền bất kỳ thì app **từ chối** vì không có fixture — đúng thiết kế, và
vô dụng trước mặt khách.

Chặn bởi: routes danh tính. Không có nhóm thì không tạo được khoản chi
thật.

**Ai:** Codex làm routes, tôi nối app.

### 2. Chưa có URL nào mở được bằng điện thoại

Có `Dockerfile` và `docker-compose.yml`, không có nơi chạy. Trang khách
là bề mặt chính của sản phẩm và nó **chỉ có nghĩa khi mở được từ máy
người khác** — link gửi qua Zalo mà chỉ chạy trên `localhost` thì không
phải link.

**Ai:** leader quyết chỗ chạy. Đây là quyết định có tiền và có rủi ro
lộ dữ liệu, không phải việc kỹ thuật thuần.

⚠️ **Trước khi mở ra internet, ba thứ phải xử lý:**
- Header `X-Actor-*` hiện là **chỗ tạm do gateway tin cậy ghi đè**. Trên
  internet công cộng, bất kỳ ai đặt header cũng thành bất kỳ ai.
- Token trang khách nằm trong URL. Link rò là dữ liệu rò.
- Chưa có rate limit ở tầng HTTP.

### 3. Chưa có extractor thật cho `money_skill`

Đây là chỗ làm sản phẩm "AI-first" thay vì một cái form. Hiện có:
validator tất định, corpus 12 ca, interface `MoneyExtractor`, và một bản
giả tất định.

Thiếu: một hiện thực gọi model thật để đọc tiếng Việt đời thường.

**Chưa quyết:** model nào. Tôi đề nghị Claude API và đã dựng interface
để câu hỏi này **không chặn** việc khác. Nhưng tới lúc demo thì nó chặn:
không có extractor thì bot không đọc được luồng chat, và đó là toàn bộ
lời hứa của sản phẩm.

### 4. Corpus 12 ca là quá ít để tin

Codex nói thẳng, và tôi đồng ý: qua 12/12 ngay lần đầu thường nghĩa là
corpus quá dễ chứ không phải code quá tốt. Năm quyết định ADR-0009 vừa
thêm đều sinh từ đúng năm ca trượt — thiếu một tình huống nghĩa là hợp
đồng hở đúng chỗ đó mà **không ai biết**.

## Thứ tự tôi đề nghị

1. **Codex:** routes + repository danh tính *(đang chạy)*
2. **Tôi:** nối app vào API, tắt `OFFLINE`, ngay khi routes có
3. **Tôi:** extractor thật sau interface, chạy lại corpus, báo cả ca trượt
4. **Tôi + agy:** thêm ca corpus cho tới khi nó bắt được lỗi mới
5. **Leader:** quyết nơi chạy, và ba việc bảo mật ở mục 2

## Thứ cố ý KHÔNG làm

- **Không dựng vỏ chat.** Mục 14.3 cấm làm trước khi kỹ năng tiền và đề
  xuất có cấu trúc chạy được. Thẻ đề xuất đã có; màn chat thì chưa.
- **Không thiết kế Home.** Mục 14.3 cấm trước khi biết hành động nào tồn tại.
- **Không tự deploy ra internet.** Đó là hành động một chiều và có rủi ro
  lộ dữ liệu; leader quyết.
- **Không mở FIELD-GATE.** Không participant thật, không tiền thật.

## Ghi lại một điều về hôm nay

agy tìm ra **tám lỗi**, trong đó một lỗ hổng CRITICAL và hai lần nó bác
bỏ một luật do tôi tự đặt. Cả tám đều nằm trong code viết trong ngày, và
**không test nào tôi viết bắt được** — vì tôi viết test cho những thứ tôi
đã nghĩ tới.

Con số đáng nhớ hơn: lỗi nặng nhất là một tham số `actor` được nhận rồi
không bao giờ đọc. Test hộp đen tìm ra nó vì agy gọi API như người lạ.
Một lần đọc code cũng tìm ra, và nhanh hơn. Từ nay agy làm cả hai.
