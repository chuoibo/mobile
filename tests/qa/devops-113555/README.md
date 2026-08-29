# devops-113555 · Nợ a11y trên vỏ tab và dải bản đồ — đo lại trên DOM đã render

Phiếu giao việc nói hai lỗi này **đang hỏng trên `main`**:

```
Khám phá   aria-prohibited-attr (serious) ×12   <- 12 chấm bản đồ
cả 4 tab   aria-required-children (critical)
```

**Cả hai đã đóng.** `#103` (`1bcd448`) sửa chúng và đã vào `main` trước khi phiếu
này tới tay. Bộ đo ở đây không sửa gì cả — nó tồn tại để trả lời câu hỏi mà một
commit message không trả lời được: *đóng thật, hay chỉ là chưa ai nhìn?*

## Câu bộ này hỏi mà bộ trước không hỏi

`rd-fe-11` đã quét bốn tab và ra 0 vi phạm. Nhưng nó không bao giờ khẳng định
**dải bản đồ đã render lúc axe chạy**.

Điều đó quan trọng vì `aria-prohibited-attr` là rule *của 12 chấm bản đồ*. Nó chỉ
có việc để làm khi 12 chấm thật sự nằm trên màn. Khám phá lấy dữ liệu từ
`GET /places`; route đó hỏng thì màn rơi vào trạng thái lỗi, dải bản đồ **không
tồn tại**, và số 0 của đúng rule đang được gác là một **số 0 rỗng** — không phân
biệt được với "đã sửa".

Đây không phải lo xa. API dùng chung ở cổng `8099` trên máy này **đang trả 404
cho `/places`** (bản build cũ hơn `rd-be-05`). Dựng bundle trỏ vào đó rồi quét
thì được đúng một bảng toàn số 0 không chứng minh gì hết.

Nên `01` **ĐỎ** nếu dải bản đồ vắng mặt hoặc không đếm đủ 12 chấm.

## Hai script

| Script | Hỏi gì | Kết quả trên `main @ 559a35d` |
|---|---|---|
| `01-bon-tab-axe.mjs` | 4 tab + 2 trạng thái tương tác, sau khi chứng minh axe còn sống **và** dải bản đồ có mặt | PASS · 0 vi phạm |
| `02-doi-chung-nham-rule.mjs` | Bộ đo có bắt được **đúng hai rule này** khi lỗi quay lại không | PASS · cả hai đỏ đúng lúc |

`02` là phần khiến `01` đáng tin. Trồng một `<img>` thiếu alt chỉ chứng minh axe
*có chạy*; nó không chứng minh bộ đo nhìn thấy được `aria-prohibited-attr`. Nên
`02` dựng lại đúng cái DOM trước `#103` ngay trên trang đang sống — gỡ `role` khỏi
dải bản đồ và trả `aria-label` về cho 12 chấm; đưa `[+]` trở vào `role="tablist"`
— rồi **đòi axe phải đỏ**. Đột biến chỉ sống trong DOM, không file nào bị sửa.

## Chạy

Cần một API có `/places` (route `rd-be-05`). **Ghim cổng của riêng bạn** — cổng
trên máy này hay bị container của lane khác chiếm, và một cổng bị chiếm trả 200
cho trang của người khác trong khi server của bạn đã chết.

```bash
# 1. API nào có /places? (8099 dùng chung KHÔNG có)
curl -s -o /dev/null -w '%{http_code}\n' \
  "http://127.0.0.1:8607/places?context_id=1aa00000-aaaa-4aaa-8aaa-0000a0000001"

# 2. Dựng bundle trỏ vào API đó
cd apps/mobile
EXPO_PUBLIC_API_URL=http://127.0.0.1:8607 \
  npx expo export --platform web --output-dir /tmp/do113-web --clear

# 3. Phục vụ trên cổng của riêng mình, rồi ĐỐI CHIẾU HASH
(cd /tmp/do113-web && python3 -m http.server 8712 --bind 127.0.0.1 &)
curl -s http://127.0.0.1:8712/index.html | grep -o 'index-[a-f0-9]*\.js' | sort -u

# 4. Đo
cd tests/qa/devops-113555
WEB_URL=http://127.0.0.1:8712 EXPECT_BUNDLE=index-<hash>.js node 01-bon-tab-axe.mjs
WEB_URL=http://127.0.0.1:8712 node 02-doi-chung-nham-rule.mjs
```

Phụ thuộc: `playwright` + `@axe-core/playwright`. Cài vào một thư mục ngoài repo
rồi chạy `node` từ đó, hoặc dùng lại `node_modules` của `rd-fe-10`. **Không commit
symlink** — repo guard fail closed với symlink.

## Số đo (`main @ 559a35d`, Chromium 390×844, vi-VN, axe-core 4.13.0, wcag2a+2aa+22aa)

### `01-bon-tab-axe.mjs` — PASS

```
✓ bundle khớp: index-7cc2337caeb7b5f493dafe25e13b8338.js

ĐỐI CHỨNG
  trước khi trồng lỗi                  0 vi phạm · 25 rule pass · 1 incomplete
  sau khi trồng img+button             2 vi phạm · 25 rule pass
      ✗ [critical] button-name ×1
      ✗ [critical] image-alt ×1
      ✓ axe còn sống: 0 -> 2

  [kham-pha] đang chọn="Khám phá — gợi ý chỗ đi cho nhóm" · con-tablist=["tab","tab","tab","tab"]
      dải bản đồ: có=true · số chấm=12
      nhãn="Sơ đồ vị trí tương đối của 12 chỗ: Tiệm Nướng Xóm Lào, Lưng Chừng Cafe, …"
      aria-label trên phần tử KHÔNG role: 0

  trạng thái                        vi phạm  rule-pass
  axe · kham-pha                         0         25
  axe · len-plan                         0         20
  axe · tin-nhan                         0         20
  axe · ca-nhan                          0         21
  axe · menu [+] đang mở                 0         18
  axe · chi tiết địa điểm                0         22
```

Cả bốn tab đều xác nhận `aria-selected` khớp tab được yêu cầu, nên đây là bốn màn
khác nhau chứ không phải một màn quét bốn lần. `con-tablist` là `tab,tab,tab,tab`
ở cả bốn — `[+]` nằm ngoài, đúng như `#103` để lại.

### `02-doi-chung-nham-rule.mjs` — PASS

```
  0 · nguyên trạng (đã sửa)                        0 vi phạm · 25 rule pass
  1 · DOM dải bản đồ như TRƯỚC #103                1 vi phạm · 24 rule pass
      ✗ [serious]  aria-prohibited-attr ×12
  2 · [+] nằm TRONG tablist, như TRƯỚC #103        1 vi phạm · 24 rule pass
      ✗ [critical] aria-required-children ×1
```

Hai con số đột biến dựng lại **khớp từng chữ số** với phiếu gốc: `×12` serious và
`×1` critical. Nghĩa là bộ đo nhìn thấy đúng loại lỗi nó đang gác, và bảng 0 ở
`01` là im lặng có nghĩa chứ không phải im lặng vì mù.

### Cổng "số 0 rỗng" tự nó có đỏ được không — ĐÃ THỬ, CÓ

Một cổng chưa từng đỏ là một cổng chưa từng được kiểm. Nên tôi dựng thêm một
bundle trỏ vào một cổng chết (`EXPO_PUBLIC_API_URL=http://127.0.0.1:9`) và chạy
lại `01` trên đúng bundle đó:

```
  trạng thái                        vi phạm  rule-pass
  trước khi trồng lỗi                    0         22
  sau khi trồng img+button               2         22   <- axe vẫn sống
  axe · kham-pha                         0         22   <- SẠCH, và vô nghĩa
  axe · len-plan                         0         20
  axe · tin-nhan                         0         20
  axe · ca-nhan                          0         20

01-bon-tab-axe: FAIL — 2 vấn đề:
  ✗ kham-pha: DẢI BẢN ĐỒ KHÔNG RENDER — số 0 của aria-prohibited-attr là số 0
    rỗng, không phải bằng chứng. Kiểm tra GET /places của API mà bundle đang trỏ tới.
  ✗ không tìm thấy thẻ địa điểm để mở màn chi tiết
```

Đây là toàn bộ lý do bộ này tồn tại. Bảng vi phạm **giống hệt** bảng xanh ở trên
— `axe · kham-pha  0 vi phạm` — nhưng lượt này không chứng minh gì cả, vì rule
chưa từng có gì để nhìn. Không có cổng đó thì hai lượt chạy không phân biệt được,
và lượt rỗng là lượt dễ chạy hơn.

Số rule pass cũng lệch (22 so với 25): màn ít nội dung hơn thì ít rule có việc
hơn. Đó là lý do con số này được in cạnh danh sách vi phạm rỗng thay vì chỉ in
`violations: []`.

## Cái bộ này KHÔNG chứng minh

- **Không phải WCAG 2.2 AA đầy đủ.** axe không có rule tự động cho 2.4.11
  (focus bị che), 2.5.7 (thao tác kéo), và chỉ phủ một phần 2.5.8 (kích thước
  đích). Xanh ở đây không phải chứng chỉ tuân thủ.
- **Không phải trình đọc màn hình thật.** Cây accessibility đúng không đảm bảo
  VoiceOver/TalkBack đọc ra câu người ta hiểu được. Nhãn dải bản đồ đọc liền 12
  tên là *đúng chuẩn*; nó dễ nghe hay không thì phải có người khiếm thị nghe thử,
  và việc đó chưa ai làm.
- **Không phải bàn phím.** `01` đọc vai trò và tên, không đi Tab qua từng chỗ.
- **Chỉ những trạng thái đã quét.** Bốn tab, menu `[+]`, màn chi tiết địa điểm.
  Các màn khác của app không nằm trong lượt này.
- **Chưa gác trong CI.** Nó cần một bản export web, một Chromium và một API có
  `/places` — ba thứ CI hiện không dựng. Chạy tay, và nói rõ là chạy tay.
