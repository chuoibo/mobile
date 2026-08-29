# rd-fe-11 · Đối chứng vỏ tab trên DOM đã render

Bộ đo này **không sửa gì cả**. Nó tồn tại để trả lời một câu: hai lỗi a11y từng
được báo trên thanh tab đã thật sự đóng chưa, đo trên trang trình duyệt nhận
được chứ không phải trên source.

Lý do có nó: báo lỗi `bug-120541` được gửi rồi **rút lại** — nó đo trên
`main @ aaefbfa` trong khi main đã chạy tiếp 4 commit, trong đó có #103 (tách
nút `[+]` ra khỏi `role="tablist"`) và #99 (điểm dừng bàn phím cho vùng cuộn).
Phiếu rút lại cũng là một khẳng định, và khẳng định thì phải đo lại chứ không
nhận lời.

## Chạy

Cần một bản export web và một máy chủ tĩnh. **Ghim cổng của riêng bạn**: cổng
mặc định 8651 trên máy này đang là container API của lane khác, và một cổng bị
chiếm trả về 200 cho trang của người khác trong khi server của bạn đã chết.
Đối chiếu hash bundle trước khi tin bất kỳ con số nào.

```bash
cd apps/mobile
EXPO_PUBLIC_API_URL=http://127.0.0.1:<cổng-api> \
  npx expo export --platform web --output-dir /tmp/fe11-web --clear
(cd /tmp/fe11-web && python3 -m http.server 8675 --bind 127.0.0.1 &)

# server này có đúng là build của mình không?
ls /tmp/fe11-web/_expo/static/js/web/
curl -s http://127.0.0.1:8675/index.html | grep -o 'index-[a-f0-9]*\.js'

cd tests/qa/rd-fe-11
WEB_URL=http://127.0.0.1:8675 node 01-tablist-axe.mjs
WEB_URL=http://127.0.0.1:8675 node 02-hinh-thanh-tab.mjs
WEB_URL=http://127.0.0.1:8675 node 03-vung-cuon.mjs
WEB_URL=http://127.0.0.1:8675 node 04-ca-nhan-that.mjs
WEB_URL=http://127.0.0.1:8675 node 05-bon-tab-co-du-lieu.mjs
```

`node_modules` ở đây là symlink sang `rd-fe-10` (playwright + `@axe-core/playwright`)
và bị `.gitignore` — repo guard fail closed với symlink.

## Năm script

| Script | Hỏi gì | Kết quả trên `9598ebb` + 2 commit rd-fe-07 |
|---|---|---|
| `01-tablist-axe.mjs` | axe WCAG 2.2 A/AA trên cả 4 tab, sau khi chứng minh axe còn sống | PASS · 0 vi phạm |
| `02-hinh-thanh-tab.mjs` | Tách `[+]` ra khỏi tablist có làm lệch bố cục hoặc chết vùng bấm không | PASS · 0 vấn đề |
| `03-vung-cuon.mjs` | Vùng cuộn có **thật sự tồn tại** để rule cuộn có việc không | công cụ chẩn đoán, không phải cổng |
| `04-ca-nhan-that.mjs` | Màn Cá nhân có dữ liệu, ở khung thường và khung ép ra vùng cuộn | PASS · 0 vi phạm |
| `05-bon-tab-co-du-lieu.mjs` | 4 tab ở trạng thái đã nạp dữ liệu | PASS · 0 vi phạm |

## Hai cái bẫy bộ này được viết ra để tránh

**1. Số 0 rỗng.** `01` trồng một `<img>` thiếu alt và một `<button>` không tên
vào chính trang đang đo và **đòi axe phải báo nhiều hơn** trước khi con số sạch
được tin. Đo được: `0 → 2`, đúng hai rule `image-alt` + `button-name`.

Cùng loại bẫy đã bắt được một lần nữa trong lượt này: `03` cho thấy ở bản build
không có API, **cả bốn tab đều có 0 vùng cuộn dọc**. Nghĩa là số 0 của rule
`scrollable-region-focusable` ở lượt đó là 0 rỗng, rule chưa từng có gì để nhìn.
Chỉ khi mở đúng `#tab=ca-nhan&nguoi=minh` trên bản build có API thì mới xuất
hiện 1 vùng cuộn thật, và `04` mới đo được nó (0 vi phạm, ở cả 390×844 lẫn
390×400 ép cuộn).

**2. Quét một màn bốn lần rồi gọi là bốn tab.** `01` và `05` đều đọc
`aria-selected` sau mỗi lần điều hướng và bắt buộc phải xác nhận màn đã đổi.
Điều đó đã bắt được một lỗi thật của chính bộ đo: `#tab=` chỉ được đọc lúc nạp
lần đầu, nên đổi hash trên một trang đang sống là điều hướng **cùng document**
mà app không bao giờ thấy — bốn lượt quét đầu ra đều là màn Khám phá. `05` giờ
mở một trang mới cho mỗi tab.

## Số đo

```
01 · đối chứng     : 0 → 2 vi phạm (image-alt, button-name). axe còn sống.
01 · bốn tab       : kham-pha 0 · len-plan 0 · tin-nhan 0 · ca-nhan 0
01 · cấu trúc      : {"soTablist":1,"conCuaTablist":[["tab","tab","tab","tab"]],
                      "soTab":4,"coNutTao":true,
                      "diemDung":[null,"tab","tab","tab","tab","button"]}
02 · [+]           : x=168 y=766 w=54 h=54, tâm x=195 (tâm màn 195), nhô 22pt
02 · tab           : 0/78 · 78/78 · 234/78 · 312/78  (tâm 39/117/273/351)
02 · chạm tâm      : ["Khám phá","Lên plan","Tin nhắn","Cá nhân"] + [+]
04 · ca-nhan       : 390×844 → 0 vi phạm, 1 vùng cuộn
                     390×400 → 0 vi phạm, 1 vùng cuộn
05 · bốn tab (data): cả 4 đều 0 vi phạm, con-cua-tablist = tab,tab,tab,tab
```

Hình học ở `02` trùng khít con số #103 tự khai trong commit message
(tâm 39/117/273/351, `[+]` tại 195, rộng 54), đo độc lập.

## Ô CHƯA quét

- **Trình đọc màn hình thật** (VoiceOver/TalkBack). axe đọc role, không đọc ra
  câu người dùng nghe. `tablist` hợp lệ không đảm bảo ai đó nghe được "tab 2/4".
- **iOS/Android.** Toàn bộ ở đây là Chromium 390×844 trên bản `expo export
  --platform web`. `accessibilityRole` đi qua cầu accessibility khác trên native.
- **WCAG 2.4.11** (focus bị che), **2.5.7** (kéo thả), **2.5.8** (kích thước
  vùng chạm): axe không có rule tự động hoặc chỉ phủ một phần.
- **Màn Cá nhân có giao dịch.** Stack đo được có `movements` rỗng và mọi số là
  `0đ`, nên phần danh sách giao dịch chưa được đo có dữ liệu.
- **Chế độ tối, 320px, cỡ chữ 200%.**
- API dùng để lấy dữ liệu là container của lane QA (`qa07-api-1`), chỉ đọc.
