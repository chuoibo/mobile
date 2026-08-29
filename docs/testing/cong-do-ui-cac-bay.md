# Bẫy của công cụ đo UI

Mọi lane đều chạy công cụ đo giao diện, và cả ba bẫy dưới đây đều cho ra kết quả
**trông y hệt "sạch"**. Ghi ở đây vì hai lane đã độc lập vấp cùng một cái, nghĩa là
nó là bẫy của công cụ chứ không phải sai sót của một người.

Luật chung: **trước khi tin một con số 0, hãy chứng minh công cụ còn sống.** Cho nó
quét một mẫu CỐ TÌNH XẤU. Nếu mẫu xấu cũng ra 0 thì con số 0 kia không có nghĩa gì.

## 1. react-native-web bơm style qua insertRule, nên thẻ `<style>` serialize ra RỖNG

Chụp `outerHTML` rồi đọc CSS trong đó sẽ thấy `<style>` không có nội dung. Mọi rule
tương phản/typography đọc từ đó đều báo sai. Lần đầu nó ăn 28 finding giả.

Cách gỡ: đọc CSS từ CSSOM thật (`document.styleSheets` → `cssRules`) rồi
materialize lại thành text, hoặc đo bằng `getComputedStyle` trên phần tử thật thay
vì parse chuỗi HTML.

## 2. `imp detect` trên file `.tsx` là chế độ regex, và nó gần như mù

`imp detect --help` nói rõ: file không phải HTML thì chỉ "regex pattern matching".

Đo thật ngày 2026-08-29: một file `.tsx` cố tình nhồi gradient tím, glow neon,
chữ `#bbb` trên nền `#ccc`, cỡ chữ 11px và câu quảng cáo sáo rỗng cho ra **0
finding**. Cùng nội dung đó viết bằng HTML + CSS cho ra **10 finding**.

Nghĩa là `[]` khi quét `.tsx` KHÔNG phải bằng chứng màn hình đạt. Muốn có bằng
chứng thật thì phải quét **URL đã render**, vì đường URL dùng Puppeteer dựng DOM
thật.

## 3. Quét URL trả `[]` kèm exit 0 khi thiếu Chrome, và preflight vẫn báo "available"

Đây là cái nguy hiểm nhất vì có hai lớp che nhau:

- `imp preflight` in `url scanning : available`. **Dòng này không đáng tin.** Nó
  không thực sự mở trình duyệt.
- Khi Chrome thiếu, `imp detect --json <url>` in `[]` và **thoát mã 0**. Lỗi
  `Could not find Chrome` chỉ nằm ở stderr, còn stdout sạch bong.

Chạy `imp detect --json <url> > out.json` rồi chỉ nhìn `out.json` là thấy một trang
hoàn hảo, trong khi không có trang nào được mở.

Cách gỡ: trỏ sang chromium của Playwright đã cài sẵn.

```bash
export PUPPETEER_EXECUTABLE_PATH=$(ls -d ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome | tail -1)
```

Và luôn **đọc cả stderr, không chỉ stdout**, khi quét URL.

## Nếp làm đúng, gói gọn

```bash
# 1. chứng minh công cụ còn sống trên một mẫu cố tình xấu
imp detect --json /tmp/probe.html          # phải ra > 0 finding

# 2. dựng bản web rồi phục vụ nó ở cổng LẠ (cổng quen hay bị lane khác chiếm)
python3 -m http.server 8231 --directory .expo-build-check --bind 127.0.0.1 &

# 3. đối chiếu hash để chắc mình đang quét bundle CỦA MÌNH
curl -s http://127.0.0.1:8231/index.html | sha256sum
sha256sum .expo-build-check/index.html

# 4. quét cả hai khổ màn; điện thoại là mặt chính của sản phẩm
imp detect --json http://127.0.0.1:8231/index.html
imp detect --json --viewport 390x844 http://127.0.0.1:8231/index.html
```

Bước 3 không thừa: đã có lần server của lane mình thoát mã 1 mà `curl` vẫn trả 200,
vì cổng đang bị tiến trình của lane khác giữ, và findings khi đó là của trang người
khác.
