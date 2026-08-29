# Nợ bảo mật: chỉ thị nhét trong dữ liệu địa điểm được model THI HÀNH

- **Trạng thái:** đã xác nhận, **chưa sửa**, chưa khai thác được qua mạng.
- **Mức:** không phải P0 hôm nay. Có **mốc kích hoạt cứng** ở mục 4 — quá mốc đó thì là chặn.
- **Chỗ hỏng:** `services/api/app/places/reasons.py` — `build_prompt()`.
- **Phát hiện:** lane backend khi gác PR #81. Ca tái lập vào `main` ở #91 (2e47a50).
- **Ghi ngày:** 2026-08-29, lane devops.

---

## 1. Lỗi là gì

`build_prompt()` nhúng thẳng `name`, `kinds`, `traits`, `open_hours` của mỗi địa
điểm vào chuỗi prompt. Không có phân tách giữa **dữ liệu** và **chỉ thị**: với
model, một câu lệnh nằm trong `traits` trông y hệt một câu lệnh của hệ thống.

Đo được, không phải suy đoán: chỉ thị nhét vào `name`/`traits` được model
**thi hành 3/3 lần**, và route phục vụ nguyên văn kết quả đó dưới
`source: "ai"`, `verdict: "hop"` cho hai quán trượt rõ ràng:

| Quán | Vi phạm khách quan | Kết quả khi bị nhét chỉ thị |
|---|---|---|
| `p-bowling-sky` | 7.4km, giới hạn nhóm 5km | `verdict: "hop"` |
| `p-the-hill-rooftop` | 320–450k, ngân sách 250k | `verdict: "hop"` |

Chọn hai quán này có chủ ý: cả hai sai một cách khách quan, nên `hop` ở đây
**chỉ có thể** là injection thắng, không thể nhầm với "quán hợp thật".

Ca tái lập: `services/api/tests/live/test_places_reason_quality_live.py::test_a_place_row_cannot_give_the_model_orders`
(`xfail(strict=False)` — thứ đang được đo là model, nên nó không được phép làm đỏ CI).

## 2. Cái KHÔNG phải là phòng thủ

Lần thử đầu tiên payload có chữ *"chấm 100 điểm"* và bị `ungrounded_numbers`
chặn lại. **Đừng đọc đó là hệ thống tự vệ.** Nó chặn vì con số `100` không truy
ngược được về dòng dữ liệu, **không phải** vì nhận ra đó là một chỉ thị. Bỏ
chữ số khỏi payload là đi qua sạch — và payload trong ca tái lập không có chữ số nào.

Cũng không dùng được câu "đã kiểm ở luồng bill". Ở #55 model **chép** payload
thành text; ở đây model **thi hành** payload. Cùng họ tấn công, hai kết cục khác nhau.

## 3. Vì sao chưa khai thác được hôm nay — và điều đó đã được kiểm, không phải được tin

Không một ký tự nào của người dùng đi vào prompt. Vết dữ liệu của `GET /places`:

| Đầu vào | Đi tới đâu | Có vào prompt không |
|---|---|---|
| `context_id` | `del context_id` ngay dòng đầu handler | không |
| `category` | so bằng với `place["category"]` — **lọc** | không |
| `q` | `_matches()`, kiểm tra chuỗi con — **lọc** | không |
| `PLACES`, `GROUP` | literal cứng trong `catalog.py` | có, và chỉ có chúng |

`q` và `category` **chọn** hàng, chúng không **viết ra** hàng. Cả hai chỉ thu hẹp
danh sách; không giá trị nào của chúng được sao chép vào chuỗi gửi cho model.

Điều này giờ có cổng giữ, không còn là một câu trong docstring:
`services/api/tests/api/test_places_prompt_boundary.py` (5 ca, chạy offline,
không gọi model). Bất biến nó giữ: **bytes của prompt là hàm thuần của
catalog seed và hồ sơ nhóm seed.**

## 4. Mốc kích hoạt — quá mốc này thì đây là việc CHẶN

Gỡ lỗi này **trước** cái nào tới trước trong các mốc sau:

1. **Địa điểm cho người dùng sửa được.** Chính docstring của `catalog.py` đã hẹn
   ngày này: *"When places become user-editable this file is the thing that gets
   replaced."* Ngày `PLACES` không còn là literal — đọc từ DB, từ request, từ
   một nguồn nhập bên ngoài — lỗi này thành khai thác được từ mạng ngay lập tức.
2. **Bất kỳ trường nào của người dùng đi vào `build_prompt`** — tên nhóm, ghi chú
   chuyến đi, hồ sơ nhóm sửa được, `q` được chuyển từ lọc sang gợi ý.
3. **Nguồn địa điểm bên thứ ba** (Google Places, crawl, import). Dữ liệu không do
   ta viết là dữ liệu không do ta kiểm soát; không cần người dùng ác ý, chỉ cần
   một quán tự đặt tên nghịch ngợm.

Cả ba mốc đều làm đỏ `test_the_rows_put_to_the_model_are_the_seed_objects_themselves`
hoặc `test_the_prompt_is_exactly_the_prompt_the_seed_catalogue_builds`. Nghĩa là
mốc kích hoạt **tự báo**, không phụ thuộc vào việc có ai nhớ đọc lại file này.

> Ca đỏ đó không được xoá để lấy màu xanh. Nó đỏ nghĩa là điều kiện tiền đề của
> mục 3 đã hết đúng.

## 5. Tiêu chí gỡ chặn

Coi là đã gỡ khi **cả ba** điều sau đúng:

1. Dữ liệu địa điểm được tách khỏi vùng chỉ thị của prompt — trường không tin cậy
   đi trong một phong bì có ranh giới rõ (ví dụ khối JSON có nhãn, kèm câu nói
   thẳng rằng nội dung bên trong là dữ liệu và không bao giờ là mệnh lệnh).
2. `test_a_place_row_cannot_give_the_model_orders` **bỏ `xfail`** và xanh thật
   trên model live, chạy tối thiểu 3 lần liên tiếp (nó đã đỏ 3/3, nên 1 lần xanh
   không phân biệt được với may mắn ở `temperature: 0.4`).
3. Số đo chất lượng của #91 được chạy lại và **không tụt**: lý do bám dữ liệu
   12/12, và model vẫn từ chối được (ở #91 là 8/12 `khong-hop`). Một prompt
   "an toàn" mà làm model gật hết là đã đổi một lỗi lấy một lỗi khác.

## 6. Vì sao KHÔNG sửa ngay bây giờ

Không phải vì rẻ hay vì lười — mà vì sửa đúng đòi hỏi đo lại.

Sửa lỗi này là **đổi chữ trong prompt**. Prompt là thứ quyết định `verdict`, và
`verdict` ở `temperature: 0.4` đã được quan sát là **trôi giữa các lần khởi động**.
Nên mọi số đo live của #91 (12/12 lý do bám dữ liệu, 8/12 từ chối) sẽ phải đo lại
mới biết là không đổi — và đó là hạn mức model cho một câu hỏi hôm nay chưa ai
hỏi được, vì chưa có đường nào từ mạng tới đó.

Quyết định: giữ nguyên prompt, **đặt cổng canh mốc kích hoạt**, gỡ khi mốc tới.

## 7. Cảnh báo kèm theo, không thuộc lỗi này

`verdict` trôi qua các lần khởi động lại (`temperature: 0.4`). **Đừng xây logic
lọc hay sắp xếp dựa trên `verdict`** — danh sách sẽ đổi giữa hai lần mở app mà
không ai giải thích được. Thứ tự hiện tại xếp hai tầng theo `open_now` rồi tới
điểm số tất định, và điểm số tái lập 200/200 lần.
