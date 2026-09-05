# ADR-0017 — Danh mục địa điểm là dữ liệu thật nhập từ OpenStreetMap, không phải mười hai dòng bịa trong code; ảnh phải có giấy phép

- **Trạng thái:** 🟡 **ĐỀ XUẤT** 2026-09-05 — chờ Lead đánh ĐÃ CHẤP NHẬN. Mã M9 của lộ trình vòng 2 không merge trước khi dòng này đổi.
- **Quyết định bởi:** Lead (phiên 2026-09-05: «địa điểm nhập từ OpenStreetMap», «ảnh Wikimedia CC + ảnh người dùng»).
- **Thay đổi dữ liệu sản phẩm VÀ một luật thiết kế đang có hiệu lực** (`DESIGN.md` dòng 376). Đọc trước khi thêm bất kỳ ảnh nào vào một màn địa điểm.

## 1. Bối cảnh

`services/api/app/places/catalog.py` giữ **12 địa điểm bịa** trong code và tự khai lý do ở ngay đầu file: *«Synthetic but plausible. Names, addresses, ratings and coordinates are invented for a demo: no real business is being described, rated or geolocated here»* — vì charter cấm dữ liệu thật của người tham gia vào Git, và bịa thì tránh được câu hỏi đó. Cùng file cũng tự khai hạn dùng: *«When places become user-editable this file is the thing that gets replaced»*.

Hạn ấy tới rồi. Lead yêu cầu app gợi ý được chỗ đi chơi **khắp Việt Nam**, đổi được điểm đến, và gợi ý phải **có hình ảnh**. Mười hai dòng quanh Đà Lạt và TP.HCM không làm được điều đó, và không có cách nào «thêm cho đủ» mà vẫn giữ chúng trong Git: một danh mục toàn quốc là dữ liệu thật của hàng nghìn cơ sở kinh doanh thật.

Đo được từ máy này ngày 2026-09-05: Overpass API trả **643 điểm có tên** chỉ trong bbox Đà Lạt (quán ăn, cafe, bar, điểm tham quan, công viên). Dữ liệu có tên, toạ độ, loại hình, một phần địa chỉ; **hầu như không có** giờ mở cửa, giá, đánh giá.

## 2. Quyết định

### 2.1 Danh mục chuyển từ code sang bảng

Ba bảng mới: `destinations` (điểm đến cấp thành phố/khu), `places` (địa điểm, khoá chính giữ nguyên dạng `id` văn bản đang dùng), `place_photos`. `find_place()` giữ nguyên chữ ký và trở thành một lần đọc bảng; hình dạng wire của `GET /places` **không đổi** ngoài phần nói ở 2.3.

Mười hai địa điểm bịa hiện tại được **nhập lại vào bảng** với `source = 'seed'` và **giữ nguyên id** (`p-tiem-nuong-xom-lao`, …). Đó là điều kiện để mọi test, mọi flow Maestro, `seed-rudi-world.mjs`, `saved_places` và `outing_stops.place_id` đang trỏ vào chúng tiếp tục đúng. Một DB production chỉ chạy trình nhập OSM; một DB demo chạy cả hai.

### 2.2 Nguồn dữ liệu là OpenStreetMap, nhập bằng script, không đi vào Git

`scripts/import_osm_places.py` truy vấn Overpass theo bbox của từng điểm đến, ánh xạ tag sang bốn category đang có, chặn trần số dòng mỗi điểm đến, và upsert theo `source_ref` (`node/123456`) nên chạy lại là no-op.

Mỗi dòng mang `source = 'osm'`, `source_ref`, `license = 'ODbL-1.0'`. **Giấy phép ODbL buộc phải ghi nguồn**: app hiện dòng «Dữ liệu địa điểm: OpenStreetMap (ODbL)» ở chi tiết địa điểm và ở màn Khám phá.

**Dữ liệu nhập không bao giờ vào Git.** Script ở trong Git; dữ liệu ở trong database. Test dùng một mẫu Overpass **tổng hợp** do ta viết, không phải bản tải về. Đây chính là cách charter quy định cho dữ liệu thật, và nó đồng thời trả lời câu mà `catalog.py` né bằng cách bịa.

Chiều đi ra: script gửi tới Overpass **một bbox và một danh sách tag**. Không dữ liệu người dùng, không toạ độ của ai, không id của ai. Repo guard quét thứ *vào* Git; câu này là cam kết về thứ *đi ra*, và nó được gác bằng chỗ gọi: chỉ script nhập gọi Overpass, tiến trình phục vụ request không bao giờ gọi.

### 2.3 Cái gì không biết thì để trống, không bịa và không nhờ AI điền

OSM cho tên, toạ độ, loại hình, một phần địa chỉ và một phần tag tiện ích. OSM **không** cho giá, giờ mở cửa, đánh giá.

Vậy `rating`, `rating_count`, `price_min_vnd`, `price_max_vnd`, `open_hours`, `open_now`, `travel_minutes`, `distance_km`, `group_fit` **được phép null** trên wire, và màn nói «chưa có giờ mở cửa» thay vì vẽ một con số. `scoring.py` chấm bằng những gì biết và `match.factors[]` nói rõ đã dùng gì; một địa điểm thiếu giá không bị loại, nó chỉ không được cộng điểm ngân sách.

**Ngôi sao giả bị bỏ hẳn.** Thay cho «4.7★ (128 đánh giá)» — con số mà ta không có và không được bịa — thẻ hiện bằng chứng ta thật sự có: **«3 người trong nhóm bạn đã tới»**, đếm từ check-in và kỷ niệm của chính các nhóm người đọc đang ở. Không nhóm nào của người khác lộ qua con số này.

### 2.4 Ảnh: chỉ hai nguồn, cả hai đều nói được xuất xứ

1. **Ảnh có giấy phép**, nhập từ Wikimedia Commons bằng `scripts/import_place_photos.py`. Mỗi ảnh lưu `author`, `license`, `source_url`; màn **hiện tác giả và giấy phép** ngay dưới ảnh. Ảnh không đọc được giấy phép thì không nhập.
2. **Ảnh của người dùng**: ảnh kỷ niệm đã gắn `place_id`. Chỉ hiện cho người **cùng nhóm** với người đăng — máy chủ lọc theo nhóm của người đọc, không phải màn hình lọc. Ảnh nhóm không bao giờ thành ảnh minh hoạ công khai của một quán.

Ảnh nằm trong `PhotoStorage` như mọi ảnh khác (EXIF bị lột bằng re-encode). **Không byte ảnh nào vào Git.**

### 2.5 Luật ảnh trong `DESIGN.md` đổi theo, không lặng lẽ

`DESIGN.md` dòng 376 đang nói: *«Danh mục thật không có ảnh; một ảnh stock ở đó là bịa»*. Câu đó đúng khi danh mục là dữ liệu bịa và ảnh là ảnh stock. Nó **không còn đúng** khi địa điểm là chỗ có thật và ảnh là ảnh của chính chỗ đó kèm giấy phép. Luật mới:

> Ảnh địa điểm được phép, **và chỉ được phép**, khi nó nói được nguồn: ảnh có giấy phép thì hiện tác giả + giấy phép; ảnh của nhóm thì chỉ người trong nhóm thấy. Không có xuất xứ thì quay về dải typographic.

Luật avatar (`DESIGN.md` dòng 101, «không bao giờ là ảnh người thật») **giữ nguyên trong đợt này**: ảnh đại diện là việc riêng, đụng tới ảnh chân dung, và sẽ có quyết định riêng khi làm.

## 3. Hệ quả

- Một migration lớn, và tất cả những chỗ đang giả định danh mục là hằng số phải đọc lại: `scoring.py`, `reasons.py`, `search.py`, `areas.py`, `details.py`, và bốn màn client (`ExploreLive`, `PlaceDetailLive`, `PickOutingLive`, `OutingLive`).
- Wire có thêm null ⇒ `src/screens/kham-pha/places.ts` (parser nghiêm) và các màn phải có trạng thái «chưa biết». Đây là phần dễ vỡ nhất của mốc.
- App có nhiều ô trống hơn trước. Đó là cái giá của việc nói thật về dữ liệu thưa, và nó đổi lại tên với toạ độ đúng.
- Người dùng sẽ muốn bổ sung giờ/giá. Việc đó (đóng góp dữ liệu) **không** thuộc ADR này.

## 4. Phương án đã bác

| Phương án | Vì sao bác |
|---|---|
| Google Places / Goong | Chất lượng tốt nhất, nhưng cần billing của Lead, và điều khoản Google cấm lưu dữ liệu địa điểm lâu dài (chỉ được cache `place_id`) ⇒ mỗi lượt xem là một lời gọi trả tiền, và app phải online. Lead chọn OSM. |
| Gemini sinh danh mục | Địa chỉ, giá, giờ do mô hình sinh ra là bịa có vẻ thật — đúng thứ mà `ungrounded_numbers` đang chặn ở chỗ khác. Không kiểm chứng được thì không đưa vào một sản phẩm nói «quán này có thật». |
| Giữ 12 dòng bịa, thêm tay | Không mở rộng ra toàn quốc được, và mỗi dòng thêm vào Git là một cơ sở kinh doanh thật bị mô tả trong repo. |
| Ảnh stock / ảnh do AI vẽ | Một tấm ảnh trông như quán mà không phải quán đó là lời nói dối bằng hình. |

## 5. Cách kiểm chứng ADR này được tuân thủ

- `tests/postgres` cho ba bảng mới (di trú thật, rồi đọc lại).
- Một test khẳng định **không** route phục vụ request nào gọi ra Overpass/Wikimedia (chỉ script nhập được phép).
- Một test khẳng định mọi dòng `source='osm'` có `license` và `source_ref`; mọi `place_photos` có `author` + `license` + `source_url`.
- Một test khẳng định wire cho phép null ở tám trường ở 2.3, và một ca đột biến: đặt lại `rating` thành số bịa phải làm đỏ.
- Ảnh nhóm: ca live chứng minh người ngoài nhóm **không** nhận được ảnh ấy trong gallery của địa điểm.
- Trên máy: flow Maestro mở chi tiết một địa điểm OSM và đọc được dòng nguồn dữ liệu.
