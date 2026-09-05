# ADR-0018 — Vị trí thiết bị dùng tức thời rồi bỏ; điểm đến là thứ người ta chọn, không phải thứ app đoán

- **Trạng thái:** 🟡 **ĐỀ XUẤT** 2026-09-05 — chờ Lead đánh ĐÃ CHẤP NHẬN. Mã M10 không merge trước khi dòng này đổi.
- **Quyết định bởi:** Lead (phiên 2026-09-05: «thay đổi địa chỉ giống Grab hay Shopee, suggest real time follow location»).
- **Thêm một quyền hệ điều hành mới.** Đọc trước khi thêm bất kỳ lời gọi vị trí nào.

## 1. Bối cảnh

Hôm nay app không biết người dùng đang ở đâu và cũng không cho họ nói ra. `expo-location` không có trong `package.json`, `app.json` không xin quyền vị trí nào, và toàn bộ `lat`/`lng` trong client chỉ để dựng một link `geo:` cho ứng dụng bản đồ. Màn Khám phá viết cứng «Đà Lạt · danh mục Rủ Đi»; bản fixture có chữ «Khu vực chưa chọn» với một mũi tên **không bấm được**.

Máy chủ cũng chưa có khái niệm điểm đến: không cột `city`/`region` trên `places`, `contexts` hay `outings`; `people.city` là văn bản tự do không ai đọc. Không truy vấn nào theo bán kính, không PostGIS. Có sẵn `haversine_km` và tám «khu vực» viết cứng ở `app/places/areas.py`, cùng `nearest_area()` với bán kính tối đa 25 km.

Đồng thời có một luật đã đứng vững của repo: **không cột, không cache, không file cho số điện thoại** (ADR-0016). Toạ độ của một người là dữ liệu cùng hạng, nếu không muốn nói là hơn.

## 2. Quyết định

### 2.1 Điểm đến là một bảng, và là thứ người dùng chọn

`destinations`: slug, tên, tỉnh/thành, tâm (lat/lng), bbox, mô tả ngắn, thứ tự. Người dùng chọn điểm đến ở thanh đầu màn Khám phá; lựa chọn ấy sống **trên máy** (AsyncStorage), không phải trên máy chủ — nó là trạng thái duyệt, không phải hồ sơ.

Kèo (`outings`) có `destination_id`: một chuyến đi thì có nơi đến, và đó là thứ cả nhóm cùng thấy.

### 2.2 GPS: dùng trong một request rồi quên

`expo-location` chỉ xin **quyền foreground**, chỉ đọc **một lần** khi người dùng bấm «Gần tôi», và trước khi hỏi hệ điều hành thì app phải nói trước nó dùng vị trí để làm gì (mockup 01.03 yêu cầu đúng nếp này cho danh bạ; áp cùng nếp cho vị trí).

Toạ độ đi vào **một** lời gọi `GET /destinations/near?lat=&lng=` hoặc `GET /places?near=lat,lng`, và:

- **không cột nào lưu chúng**;
- **không log nào in chúng** (kể cả access log: tham số `near` bị che như token);
- **không cache nào giữ chúng**;
- máy chủ trả về **điểm đến gần nhất** và khoảng cách đã làm tròn, không trả lại toạ độ vừa nhận.

Từ chối quyền là một đường đi bình thường: app vẫn dùng được, thanh điểm đến nói «Chưa bật vị trí», người dùng chọn tay. Không màn nào chặn ở đó.

### 2.3 Vẫn chưa có bản đồ

Không SDK bản đồ trong đợt này (ADR-0016 §2.4 để «map SDK» ra ngoài). «Chỉ đường» vẫn là `geo:` bàn giao cho ứng dụng bản đồ của máy. Điều này giữ app khỏi một phụ thuộc trả tiền và giữ đợt này ở kích thước đo được.

### 2.4 Đo được trên máy ảo, nếu không thì không phải bằng chứng

Emulator nhận `adb emu geo fix <lng> <lat>`, nên đường GPS **lái được và tái lập được**: flow đặt toạ độ Đà Lạt rồi khẳng định thanh điểm đến nói «Gần bạn: Đà Lạt». Đối chứng âm: từ chối quyền thì app phải nói «Chưa bật vị trí» chứ không được im lặng dùng một điểm đến đoán bừa.

Phép «tìm điểm đến gần nhất» chạy **ở máy chủ** (haversine trên bảng `destinations`), không dùng `reverseGeocodeAsync` của thiết bị: geocoder của Android phụ thuộc Google Play services, máy ảo AOSP không có, và một phép đo chỉ chạy trên máy có Play services thì không phải phép đo.

## 3. Hệ quả

- Một bản dev client mới (native module) — Lead phải cài lại APK nếu test trên máy thật.
- `app.json` có thêm quyền vị trí. Vì **không cổng nào đang canh danh sách quyền**, đợt này thêm một test ghim danh sách ấy (xem ADR-0019 §2.4, cùng một test).
- `GET /places` có thêm tham số; hợp đồng client-server phải cập nhật hai đầu trong cùng chuỗi PR.

## 4. Phương án đã bác

| Phương án | Vì sao bác |
|---|---|
| Lưu vị trí gần nhất của mỗi người | Một cột toạ độ là một cột theo dõi. Không có tính năng nào trong v1 cần lịch sử vị trí. |
| Theo dõi nền (background location) | Play Store xét duyệt riêng, và sản phẩm không cần biết bạn ở đâu khi không mở app. |
| `reverseGeocodeAsync` trên máy | Phụ thuộc Play services; không đo được trên máy ảo đang dùng làm thước đo. |
| Bản đồ nhúng | Trả tiền hoặc thêm SDK nặng; `geo:` đã đủ cho «chỉ đường». |

## 5. Cách kiểm chứng

- Một test quét mã: không nơi nào ghi `lat`/`lng` của người gọi vào DB hoặc log.
- Ca API: `near=` trả điểm đến gần nhất; toạ độ không xuất hiện trong response.
- Trên máy: `adb emu geo fix` → flow khẳng định tên điểm đến; ca từ chối quyền → câu «Chưa bật vị trí».
