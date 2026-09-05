# ADR-0019 — Sở thích cá nhân được lưu và dùng thật; tin nhắn thoại chỉ ghi và nghe lại

- **Trạng thái:** 🟡 **ĐỀ XUẤT** 2026-09-05 — chờ Lead đánh ĐÃ CHẤP NHẬN. Mã M11 và M14 không merge trước khi dòng này đổi.
- **Quyết định bởi:** Lead (phiên 2026-09-05: cá nhân hoá để AI gợi ý hợp gu; «tin nhắn thoại: ghi + nghe lại», không phụ đề AI).
- **Mở một quyền hệ điều hành đang bị chặn** (`RECORD_AUDIO`). Đọc trước khi sửa `app.json`.

## 1. Bối cảnh

Màn cá nhân hoá (`/personalization`) thu sáu sở thích và sáu «vibe», rồi **nói thẳng trên màn**: *«Rủ Đi chỉ dùng lựa chọn này để cá nhân hóa gợi ý trên máy. Chưa gửi lên máy chủ.»* Đúng như vậy: giá trị nằm trong AsyncStorage và không màn nào đọc. Máy chủ không có bảng sở thích nào; `app/domain/preferences.py` từ chối có một bảng như thế và suy «gu nhóm» từ check-in và sổ chi mỗi lần đọc. Trong khi đó `GET /places?context_id=` **nhận rồi bỏ qua** tham số nhóm và chấm điểm theo một hồ sơ nhóm **viết cứng** (6 người, 250.000đ, thích «Chill, View đẹp, Đồ nướng»).

Về media: chat có `kind` là `text | image | ai_card`. Không có audio ở bất kỳ tầng nào, và `app.json` đang **chặn** `RECORD_AUDIO`.

## 2. Quyết định

### 2.1 Sở thích được lưu, từ vựng đóng

Bảng `person_interests(person_id, tag)` với **từ vựng đóng do máy chủ giữ** (`GET /interests` trả danh sách). Từ vựng đóng vì hai lý do: nó là chỗ bám cho AI (thẻ gợi ý chỉ được nói tới tag có thật), và nó giữ cho phép chấm điểm so sánh được giữa người với người.

`PUT /people/me/interests` ghi; `GET /people/me` trả về. Sửa được bất cứ lúc nào từ màn Cá nhân — mockup 01.03 nói rõ *«Preferences là editable sau onboarding»*.

Sở thích của một người **không hiện cho người khác**. `GET /people/{id}` không mang chúng. Trong nhóm chỉ hiện dạng **tổng hợp** («nhóm này nghiêng về đồ nướng và cafe»), tính từ nhiều người, không quy được về một ai.

### 2.2 Hồ sơ nhóm viết cứng bị thay

`GET /places?context_id=` bắt đầu **dùng** tham số ấy: hồ sơ nhóm = tổng hợp sở thích thành viên + `build_preference_profile()` đang có (check-in và sổ chi). Hằng `GROUP` trong `catalog.py` bị xoá. Đây là cái seam mà chính route đã để sẵn từ đầu (`routes/places.py:475`).

Người chưa chọn sở thích nào thì hồ sơ trống, và `match.factors[]` nói ra điều đó — không đoán thay họ. Mockup 01.03: *«Nếu user bỏ qua budget, recommendation engine dùng default/unknown thay vì đoán cứng.»*

### 2.3 Tin nhắn thoại: ghi và nghe lại, không phụ đề

`kind = "audio"` với `audio_url` và `duration_ms`. Giới hạn: **m4a/aac**, tối đa **60 giây**, tối đa **5 MiB**; một limiter riêng cho route tải lên.

**Không phiên âm, không phụ đề, không đưa tiếng nói cho mô hình.** Lead chọn như vậy, và nó cũng tránh việc gửi giọng của người dùng ra một dịch vụ ngoài — một biên mà repo guard không nhìn thấy. Hệ quả phải nói trước: nội dung thoại **không tìm kiếm được** và người không tiện nghe sẽ không đọc được. Khi nào muốn có phụ đề thì mở ADR riêng, vì nó là một cửa AI mới và một luồng dữ liệu mới.

### 2.4 Mở `RECORD_AUDIO` kèm cổng canh quyền

`android.permission.RECORD_AUDIO` rời khỏi `blockedPermissions`. Vì hiện **không cổng nào canh `app.json`**, cùng PR thêm `tests/quyen-app-json.test.mjs` ghim danh sách quyền xin và quyền chặn: thêm hay bỏ một quyền từ nay phải sửa test, tức là phải có người đọc.

Micro chỉ được xin khi người dùng bấm nút ghi âm lần đầu, không xin lúc mở app.

## 3. Hệ quả

- Một bản dev client mới nữa (`expo-audio`).
- Máy này **không có micro thật**, nên bằng chứng trên máy ảo dừng ở: file thật đi qua máy chủ, bong bóng có nút phát và độ dài. «Nghe rõ hay không» phải do Lead thử trên máy thật một lần.
- Chấm điểm địa điểm đổi kết quả khi nhóm có sở thích — các ca test đang ghim thứ tự theo hồ sơ viết cứng phải viết lại theo hồ sơ thật.

## 4. Phương án đã bác

| Phương án | Vì sao bác |
|---|---|
| Sở thích dạng văn bản tự do | Không bám được cho AI, không so sánh được, và mời gọi người ta gõ dữ liệu cá nhân vào một trường không ai kiểm. |
| Suy sở thích hoàn toàn từ hành vi (giữ nguyên hiện trạng) | Người mới chưa có hành vi nào, và đó đúng là lúc cần gợi ý nhất. |
| Hiện sở thích của người khác trên hồ sơ | Không ai xin điều đó, và nó biến một tiện ích gợi ý thành hồ sơ công khai. |
| Phiên âm giọng nói bằng Gemini | Lead không chọn; và nó gửi giọng người dùng ra ngoài. |

## 5. Cách kiểm chứng

- Ca API: sở thích ghi rồi đọc lại; `GET /people/{id}` **không** mang sở thích; hai nhóm khác sở thích cho ra thứ tự địa điểm khác nhau.
- Đột biến: bỏ `context_id` khỏi phép chấm phải làm đỏ (nếu không thì tham số vẫn là trang trí).
- Ca API cho audio: quá 60 giây, quá 5 MiB, sai định dạng đều bị từ chối; `kind=audio` không kèm `audio_url` bị CHECK chặn.
- `tests/quyen-app-json.test.mjs` đỏ khi danh sách quyền đổi mà không ai sửa test.
